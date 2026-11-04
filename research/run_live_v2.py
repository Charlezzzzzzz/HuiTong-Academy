#!/usr/bin/env python3
"""Run one live final-edit call per selected v2 manifest row.

Safety rules enforced here:

* reads the API key only from the local ``data/model_config.json`` (0600) or
  ``HUITONG_MODEL_CONFIG_PATH``; the key is never printed, logged, hashed into a
  report or written into any run artefact;
* refuses to run unless the runtime model config matches the frozen manifest;
* reads only ``generation_input`` from the manifest and rebuilds the prompt from
  ``prompt_templates_v2.json``;
* validates the JSON contract of each response before storing it;
* writes to a separate live directory so fixture and live rows are never mixed.

Usage (pilot: one case x four conditions x one replicate):

    python3 research/run_live_v2.py --case-id error_01 --conditions all \
        --replicate 1 --max-attempts 1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Settings  # noqa: E402
from app.model_gateway import GatewayError, ModelGateway  # noqa: E402

HERE = Path(__file__).resolve().parent
CONDITION_ORDER = ("ordinary", "audit_only", "preserve_only", "preserve_audit")
HIDDEN_KEYS = {"analysis", "reasoning", "thought", "thoughts", "chain_of_thought", "hidden_reasoning"}
ALLOWED_COMPLIANCE = {"complied", "partially_complied", "bypassed"}
ALLOWED_STRENGTH = {"strong", "qualified", "weak", "open"}
ALLOWED_HANDLING = {"retained", "answered", "archived_open"}
ALLOWED_ACTION = {"checked", "not_checked", "marked_insufficient"}
ALLOWED_RELATION = {"supports", "refutes", "qualifies", "insufficient"}
REQUIRED_OUTPUT_FIELDS = {
    "article": str,
    "claims": list,
    "links": list,
    "verification_actions": list,
    "dissent_handling": list,
    "certainty_downgrades": list,
    "constraint_compliance": str,
    "edit_audit": list,
}


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def canonical_hash(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def strip_hidden(value):
    if isinstance(value, dict):
        return {key: strip_hidden(item) for key, item in value.items() if key not in HIDDEN_KEYS}
    if isinstance(value, list):
        return [strip_hidden(item) for item in value]
    return value


def block_claims(arg: dict) -> str:
    return "\n".join(
        f"{c['claim_id']}｜强度={c['strength']}｜状态={c['status']}｜来源={'/'.join(c['source_ids'])}｜{c['text']}"
        for c in arg["claims"])


def block_evidence(arg: dict) -> str:
    return "\n".join(
        f"{e['evidence_id']}｜方向={e['direction']}｜出处={e['locator']}｜来源={'/'.join(e['source_ids'])}｜{e['text']}"
        for e in arg["evidence"])


def block_links(arg: dict) -> str:
    return "\n".join(f"{link['claim_id']} —{link['relation']}→ {link['evidence_id']}" for link in arg["links"])


def block_verification(arg: dict) -> str:
    return "\n".join(f"{v['evidence_id']}｜核验={v['status']}｜{v['note']}" for v in arg["verification"])


def block_dissent(arg: dict) -> str:
    if not arg["dissent"]:
        return "（本案例没有登记异议）"
    return "\n".join(
        f"{d['dissent_id']}｜针对={d['target_claim_id']}｜状态={d['status']}｜{d['text']}"
        for d in arg["dissent"])


def build_messages(generation_input: dict, prompts: dict) -> list[dict]:
    """Fill the frozen template by literal token replacement.

    ``str.format`` cannot be used because the template embeds a JSON example
    whose braces would be read as format fields.
    """
    arg = generation_input["intermediate_argument"]
    replacements = {
        "{case_id}": generation_input["case_id"],
        "{case_type}": generation_input["case_type"],
        "{question}": generation_input["question"],
        "{task}": generation_input["task"],
        "{claims_block}": block_claims(arg),
        "{evidence_block}": block_evidence(arg),
        "{links_block}": block_links(arg),
        "{verification_block}": block_verification(arg),
        "{dissent_block}": block_dissent(arg),
        "{condition_instruction}": generation_input["instruction"],
    }
    user = prompts["user_template"]
    for token, value in replacements.items():
        user = user.replace(token, value)
    return [{"role": "system", "content": prompts["system"]}, {"role": "user", "content": user}]


def validate_response(result) -> list[str]:
    problems = []
    if not isinstance(result, dict):
        return ["response_not_object"]
    for field, expected in REQUIRED_OUTPUT_FIELDS.items():
        if field not in result:
            problems.append(f"missing_field:{field}")
        elif not isinstance(result[field], expected):
            problems.append(f"wrong_type:{field}")
    article = result.get("article")
    if isinstance(article, str) and not article.strip():
        problems.append("empty_article")
    if isinstance(result.get("constraint_compliance"), str) and \
            result["constraint_compliance"] not in ALLOWED_COMPLIANCE:
        problems.append("compliance_value_invalid")
    return problems


def schema_warnings(result: dict) -> list[str]:
    """Record enum drift without discarding an otherwise usable output."""
    warnings = []
    for entry in result.get("claims", []):
        if not isinstance(entry, dict):
            continue
        strength = entry.get("strength_out")
        if strength is not None and strength not in ALLOWED_STRENGTH:
            warnings.append(f"strength_out_not_in_enum:{entry.get('claim_id')}:{strength}")
        if "retained" in entry and not isinstance(entry.get("retained"), bool):
            warnings.append(f"retained_not_bool:{entry.get('claim_id')}")
    for entry in result.get("dissent_handling", []):
        if isinstance(entry, dict) and entry.get("handling") not in ALLOWED_HANDLING:
            warnings.append(f"handling_not_in_enum:{entry.get('dissent_id')}:{entry.get('handling')}")
    for entry in result.get("verification_actions", []):
        if isinstance(entry, dict) and entry.get("action") not in ALLOWED_ACTION:
            warnings.append(f"verification_action_not_in_enum:{entry.get('evidence_id')}:{entry.get('action')}")
    for entry in result.get("links", []):
        if isinstance(entry, dict) and entry.get("relation") not in ALLOWED_RELATION:
            warnings.append(f"link_relation_not_in_enum:{entry.get('claim_id')}:{entry.get('relation')}")
    return warnings


def structured_from_response(result: dict, generation_input: dict) -> dict:
    """Map model output onto the frozen coding interface; human-only slots stay null."""
    arg = generation_input["intermediate_argument"]
    material_claim_ids = [c["claim_id"] for c in arg["claims"]]
    evidence_ids = {e["evidence_id"]: e["source_ids"] for e in arg["evidence"]}
    claims = []
    by_id = {entry.get("claim_id"): entry for entry in result.get("claims", []) if isinstance(entry, dict)}
    for claim_id in material_claim_ids:
        entry = by_id.get(claim_id, {})
        claims.append({
            "claim_id": claim_id,
            "retained": entry.get("retained") if isinstance(entry.get("retained"), bool) else None,
            "strength_out": entry.get("strength_out") if isinstance(entry.get("strength_out"), str) else None,
            "revision_reason": entry.get("revision_reason"),
            "coding_status": "observed" if entry else "unobserved",
        })
    links = []
    for link in result.get("links", []):
        if not isinstance(link, dict):
            continue
        links.append({
            "claim_id": link.get("claim_id"),
            "evidence_id": link.get("evidence_id"),
            "relation_out": link.get("relation"),
            "source_ids": evidence_ids.get(link.get("evidence_id"), []),
            "link_completeness": None,
            "link_alignment": None,
            "coding_status": "observed_pending_annotation",
        })
    verification = [
        {"evidence_id": entry.get("evidence_id"), "action_observed": entry.get("action"),
         "coding_status": "observed"} if isinstance(entry, dict) else entry
        for entry in result.get("verification_actions", [])
    ]
    dissent = [
        {"dissent_id": entry.get("dissent_id"), "handling": entry.get("handling"),
         "note": entry.get("note"), "carried_in_article": None,
         "coding_status": "observed_pending_annotation"} if isinstance(entry, dict) else entry
        for entry in result.get("dissent_handling", [])
    ]
    return {
        "interface_version": "huitong-mechanism-interface-v1",
        "values_are_fixture_placeholders": False,
        "not_a_model_result": False,
        "claims": claims,
        "claim_evidence_source_links": links,
        "verification_actions": verification,
        "challenge_handling": dissent,
        "certainty_downgrades": result.get("certainty_downgrades", []),
        "revision_reasons": [c["revision_reason"] for c in claims if c["revision_reason"]],
        "edit_audit": result.get("edit_audit", []),
        "constraint_compliance": result.get("constraint_compliance"),
        "turns": 1,
        "manual_intervention_count": 0,
    }


def runtime_settings(settings_file: Path | None) -> Settings:
    base = Settings.from_env()
    candidates = [settings_file] if settings_file else []
    env_path = os.getenv("HUITONG_MODEL_CONFIG_PATH")
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(ROOT / "data" / "model_config.json")
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if isinstance(payload, dict) and payload.get("api_key"):
            return Settings.from_payload(payload, current=base)
    return base


def usage_counts(meta: dict) -> tuple[int | None, int | None]:
    usage = meta.get("usage") if isinstance(meta, dict) else None
    if not isinstance(usage, dict):
        return None, None
    prompt_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
    completion_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
    return prompt_tokens, completion_tokens


def select_rows(manifest: list[dict], case_ids: set[str], conditions: list[str], replicate: int) -> list[dict]:
    rows = [row for row in manifest
            if (not case_ids or row["case_id"] in case_ids)
            and (not conditions or row["condition_id"] in conditions)
            and (replicate == 0 or row["replicate"] == replicate)]
    order = {case: index for index, case in enumerate(sorted({row["case_id"] for row in rows}))}
    return sorted(rows, key=lambda row: (order[row["case_id"]], CONDITION_ORDER.index(row["condition_id"]),
                                         row["replicate"]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=HERE / "runs_v2" / "manifest.jsonl")
    parser.add_argument("--prompts", type=Path, default=HERE / "prompt_templates_v2.json")
    parser.add_argument("--live-dir", type=Path, default=HERE / "runs_v2" / "live")
    parser.add_argument("--case-id", action="append", default=[], help="Repeatable; default = all cases.")
    parser.add_argument("--conditions", default="all", help="'all' or comma list of canonical condition ids.")
    parser.add_argument("--replicate", type=int, default=0, help="0 = all replicates.")
    parser.add_argument("--limit", type=int, default=0, help="Optional hard cap on rows (0 = no cap).")
    parser.add_argument("--max-attempts", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true", help="Print prompt for the first row and exit.")
    parser.add_argument("--settings-file", type=Path, default=None)
    parser.add_argument("--rebase-config", action="store_true",
                        help="Allow a runtime model config different from the frozen manifest; "
                             "writes a separate live manifest instead of touching the fixture one.")
    args = parser.parse_args()

    manifest = read_jsonl(args.manifest)
    prompts = json.loads(args.prompts.read_text(encoding="utf-8"))
    if args.conditions == "all":
        conditions = list(CONDITION_ORDER)
    else:
        conditions = [item.strip() for item in args.conditions.split(",") if item.strip()]
        unknown = [item for item in conditions if item not in CONDITION_ORDER]
        if unknown:
            raise SystemExit(f"unknown_conditions:{unknown}")

    rows = select_rows(manifest, set(args.case_id), conditions, args.replicate)
    if args.limit:
        rows = rows[:args.limit]
    if not rows:
        raise SystemExit("no_rows_selected")

    if args.dry_run:
        generation_input = rows[0]["generation_input"]
        messages = build_messages(generation_input, prompts)
        print(json.dumps({"run_id": rows[0]["run_id"], "messages": messages}, ensure_ascii=False, indent=2))
        return

    settings = runtime_settings(args.settings_file)
    if settings.mode != "live":
        raise SystemExit("live_runner_requires_live_mode")
    if not settings.api_key:
        raise SystemExit("missing_api_key")

    frozen = {key: rows[0].get(key) for key in ("model", "provider", "region", "reasoning_effort")}
    current = {"model": settings.model, "provider": settings.provider,
               "region": settings.region, "reasoning_effort": settings.reasoning_effort}
    mismatch = {key: {"manifest": frozen[key], "runtime": current[key]}
                for key in frozen if frozen[key] is not None and frozen[key] != current[key]}
    if mismatch and not args.rebase_config:
        raise SystemExit(f"frozen_config_mismatch:{json.dumps(mismatch, ensure_ascii=False)}")

    args.live_dir.mkdir(parents=True, exist_ok=True)
    if mismatch:
        # The frozen v2 manifest was authored for the Aliyun model. Rebasing writes
        # a separate live manifest so the fixture batch keeps its original hashes.
        config_hash = canonical_hash({
            "provider": settings.provider, "region": settings.region, "model": settings.model,
            "reasoning_effort": settings.reasoning_effort, "gateway_version": rows[0]["gateway_version"],
            "replicates": len({row["replicate"] for row in manifest})})
        rebased = []
        for row in rows:
            row = dict(row)
            row["provider"] = settings.provider
            row["model"] = settings.model
            row["reasoning_effort"] = settings.reasoning_effort
            row["config_hash"] = config_hash
            rebased.append(row)
        rows = rebased
        with (args.live_dir / "manifest_live.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        (args.live_dir / "config_rebase.json").write_text(json.dumps({
            "reason": "runtime model config differs from the frozen fixture manifest",
            "manifest_values": frozen, "runtime_values": current, "config_hash": config_hash,
            "scope": "live batch only; fixture batch unchanged",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"config_rebased provider={settings.provider} model={settings.model}")

    args.live_dir.mkdir(parents=True, exist_ok=True)
    outputs_path = args.live_dir / "outputs.jsonl"
    records_path = args.live_dir / "run_records.jsonl"
    gateway = ModelGateway(settings)
    written = {"planned": len(rows), "completed": 0, "failed": 0}

    with outputs_path.open("w", encoding="utf-8") as out_handle, \
            records_path.open("w", encoding="utf-8") as rec_handle:
        for row in rows:
            run_id = row["run_id"]
            generation_input = row["generation_input"]
            if canonical_hash(generation_input) != row["input_hash"]:
                raise SystemExit(f"manifest_input_hash_mismatch:{run_id}")
            messages = build_messages(generation_input, prompts)
            started_at = now_iso()
            started = time.perf_counter()
            result, error_category, error_summary, attempts = None, None, None, 0
            for attempt in range(1, args.max_attempts + 1):
                attempts = attempt
                try:
                    raw = gateway.complete(messages, response_format={"type": "json_object"})
                    raw = strip_hidden(raw)
                    problems = validate_response(raw)
                    if problems:
                        raise GatewayError("response_schema_invalid:" + ",".join(problems))
                    result = raw
                    error_category, error_summary = None, None
                    break
                except Exception as exc:  # keep the final failure verbatim
                    message = str(exc) or exc.__class__.__name__
                    lower = message.lower()
                    if "http_401" in lower or "invalid_api_key" in lower:
                        error_category = "configuration"
                    elif "http_4" in lower:
                        error_category = "request_invalid"
                    elif "rate" in lower or "429" in message:
                        error_category = "rate_limit"
                    elif "timeout" in lower or "timed out" in lower:
                        error_category = "timeout"
                    elif "response_" in lower or "not_json" in lower:
                        error_category = "format"
                    elif "gateway_request_failed" in lower or isinstance(exc, OSError):
                        error_category = "network"
                    else:
                        error_category = "unknown"
                    error_summary = message
                    if attempt >= args.max_attempts:
                        break
                    time.sleep(min(0.5 * attempt, 2.0))
            finished_at = now_iso()
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            meta = result.pop("_meta", {}) if isinstance(result, dict) else {}
            input_tokens, output_tokens = usage_counts(meta)

            if result is not None:
                text = str(result["article"])
                structured = structured_from_response(result, generation_input)
                status, output_hash, error = "completed", text_hash(text), None
                warnings = schema_warnings(result)
            else:
                text, structured, status, output_hash = "", {}, "failed", None
                error = error_summary
                warnings = []
            base = {
                "run_id": run_id, "case_id": row["case_id"], "case_type": row["case_type"],
                "condition_id": row["condition_id"], "preserve": row["preserve"], "audit": row["audit"],
                "replicate": row["replicate"], "seed": row["seed"],
                "material_hash": row["material_hash"], "object_hash": row["object_hash"],
                "material_payload_hash": row["material_payload_hash"],
                "config_hash": row["config_hash"], "protocol_hash": row["protocol_hash"],
                "prompt_hash": row["prompt_hash"], "input_hash": row["input_hash"],
                "material_version": row["material_version"], "prompt_version": row["prompt_version"],
                "protocol_version": row["protocol_version"], "gateway_version": row["gateway_version"],
                "provider": row["provider"], "region": row["region"], "model": row["model"],
                "reasoning_effort": row["reasoning_effort"], "generation_input": generation_input,
            }
            out_handle.write(json.dumps({
                **base, "run_type": "live", "status": status, "attempt": attempts,
                "text": text, "structured": structured, "output_hash": output_hash,
                "latency_ms": latency_ms, "input_tokens": input_tokens, "output_tokens": output_tokens,
                "turns": 1, "retry_count": max(0, attempts - 1), "manual_intervention_count": 0,
                "request_id": meta.get("request_id") if isinstance(meta, dict) else None,
                "schema_warnings": warnings,
                "error_category": error_category, "error_summary": error_summary, "error": error,
            }, ensure_ascii=False) + "\n")
            rec_handle.write(json.dumps({
                **row, "run_type": "live", "status": status, "attempt": attempts,
                "started_at": started_at, "finished_at": finished_at, "latency_ms": latency_ms,
                "input_tokens": input_tokens, "output_tokens": output_tokens, "turns": 1,
                "retry_count": max(0, attempts - 1), "manual_intervention_count": 0,
                "output_hash": output_hash, "error_category": error_category,
                "error_summary": error_summary, "error": error,
            }, ensure_ascii=False) + "\n")
            written["completed" if status == "completed" else "failed"] += 1
            print(f"{run_id} {row['case_id']} {row['condition_id']} r{row['replicate']} "
                  f"{status} {latency_ms}ms {output_tokens or 0}tok")

    summary = {
        "run_type": "live", "model": settings.model, "provider": settings.provider,
        "region": settings.region, "conditions": conditions,
        "case_ids": sorted({row["case_id"] for row in rows}),
        "replicate": args.replicate, "max_attempts": args.max_attempts,
        "counts": written, "outputs": str(outputs_path), "records": str(records_path),
        "api_key_printed": False,
    }
    (args.live_dir / "pilot_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("counts", "model", "provider")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
