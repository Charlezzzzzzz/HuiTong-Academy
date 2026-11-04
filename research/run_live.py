#!/usr/bin/env python3
"""Run one auditable final-edit call per manifest row.

The runner reads only ``generation_input`` from the frozen manifest.  It never
loads cases.jsonl or annotation_only.jsonl, and it never stores hidden model
reasoning.  It is intentionally separate from run_fixture.py.
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
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Settings  # noqa: E402
from app.model_gateway import GatewayError, ModelGateway  # noqa: E402


HERE = Path(__file__).resolve().parent
GOLD_FIELDS = {"required_elements", "required_qualifiers", "supported_alternatives", "incorrect_views"}
HIDDEN_KEYS = {"analysis", "reasoning", "thought", "thoughts", "chain_of_thought", "hidden_reasoning"}
RETRYABLE = {"network", "timeout", "rate_limit", "format"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def contains_gold_fields(value: Any) -> bool:
    if isinstance(value, dict):
        return any(key in GOLD_FIELDS or contains_gold_fields(item) for key, item in value.items())
    if isinstance(value, list):
        return any(contains_gold_fields(item) for item in value)
    return False


def strip_hidden_fields(value: Any) -> Any:
    """Drop common hidden-reasoning keys before anything is persisted."""
    if isinstance(value, dict):
        return {key: strip_hidden_fields(item) for key, item in value.items() if key not in HIDDEN_KEYS}
    if isinstance(value, list):
        return [strip_hidden_fields(item) for item in value]
    return value


def classify_error(exc: BaseException) -> tuple[str, str]:
    message = str(exc) or exc.__class__.__name__
    lower = message.lower()
    if "missing_api_key" in lower:
        return "configuration", message
    if "rate" in lower or "429" in lower or "限流" in message:
        return "rate_limit", message
    if "timeout" in lower or "timed out" in lower or "超时" in message:
        return "timeout", message
    if any(token in lower for token in ("response_", "response_not_json", "response_not_object", "response_invalid", "not_json")):
        return "format", message
    if "gateway_request_failed" in lower or isinstance(exc, (OSError, ConnectionError)):
        return "network", message
    return "unknown", message


def validate_result(result: Any, condition_id: str) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise GatewayError("response_not_object")
    text = result.get("text")
    if not isinstance(text, str) or not text.strip():
        raise GatewayError("response_text_missing")
    edit_audit = result.get("edit_audit")
    if edit_audit is not None and not isinstance(edit_audit, list):
        raise GatewayError("response_edit_audit_invalid")
    stage = result.get("stage")
    if stage is not None and stage != condition_id:
        raise GatewayError("response_stage_mismatch")
    dissent_status = result.get("dissent_status")
    if dissent_status is not None and not isinstance(dissent_status, str):
        raise GatewayError("response_dissent_status_invalid")
    return result


def usage_counts(meta: dict[str, Any]) -> tuple[int | None, int | None]:
    usage = meta.get("usage") if isinstance(meta, dict) else None
    if not isinstance(usage, dict):
        return None, None
    input_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
    output_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
    if output_tokens is None and usage.get("total_tokens") is not None and input_tokens is not None:
        output_tokens = max(0, int(usage["total_tokens"]) - int(input_tokens))
    return input_tokens, output_tokens


def build_messages(generation_input: dict[str, Any]) -> list[dict[str, str]]:
    if contains_gold_fields(generation_input):
        raise ValueError("gold_fields_in_generation_input")
    system = (
        "你是会通的最终编辑器。只依据用户提供的冻结材料进行一次最终编辑。"
        "保持原有论证强度，区分确定、限定和未决内容；不要补充外部事实。"
        "只返回 JSON object，字段至少包含 text、stage、edit_audit、dissent_status。"
    )
    user = json.dumps(generation_input, ensure_ascii=False, sort_keys=True)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def runtime_settings(settings_file: Path | None) -> Settings:
    """Load the local protected model config without printing its secret."""
    base = Settings.from_env()
    candidates = []
    if settings_file is not None:
        candidates.append(settings_file)
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=HERE / "runs" / "manifest.jsonl")
    parser.add_argument("--outputs", type=Path, default=HERE / "live" / "outputs.jsonl")
    parser.add_argument("--records", type=Path, default=HERE / "live" / "run_records.jsonl")
    parser.add_argument("--settings-file", type=Path, default=None, help="Optional local 0600 model_config.json path.")
    parser.add_argument("--max-attempts", type=int, default=2, help="Total calls per row; only retryable failures may use the extra call.")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.max_attempts < 1:
        raise SystemExit("--max-attempts must be >= 1")

    settings = runtime_settings(args.settings_file)
    if settings.mode != "live":
        raise SystemExit("live_runner_requires_HUITONG_GATEWAY_MODE=live")
    manifest = read_jsonl(args.manifest)
    if not manifest:
        raise SystemExit("manifest_empty")
    first = manifest[0]
    frozen = {
        "model": first.get("model"),
        "provider": first.get("provider"),
        "region": first.get("region"),
        "reasoning_effort": first.get("reasoning_effort"),
    }
    current = {
        "model": settings.model,
        "provider": settings.provider,
        "region": settings.region,
        "reasoning_effort": settings.reasoning_effort,
    }
    if any(frozen[key] is not None and frozen[key] != current[key] for key in frozen):
        raise SystemExit(f"frozen_config_mismatch:{json.dumps({'manifest': frozen, 'runtime': current}, ensure_ascii=False)}")
    for row in manifest[1:]:
        if any(row.get(key) != first.get(key) for key in frozen):
            raise SystemExit(f"manifest_config_not_uniform:{row.get('run_id')}")
    if args.outputs.exists() or args.records.exists():
        if not args.overwrite:
            raise SystemExit("output_exists_use_--overwrite")
    args.outputs.parent.mkdir(parents=True, exist_ok=True)
    args.records.parent.mkdir(parents=True, exist_ok=True)
    gateway = ModelGateway(settings)
    output_handle = args.outputs.open("w", encoding="utf-8")
    record_handle = args.records.open("w", encoding="utf-8")
    try:
        for run in manifest:
            run_id = run.get("run_id")
            generation_input = run.get("generation_input")
            if not isinstance(generation_input, dict):
                raise SystemExit(f"manifest_generation_input_missing:{run_id}")
            if canonical_hash(generation_input) != run.get("input_hash"):
                raise SystemExit(f"manifest_input_hash_mismatch:{run_id}")
            messages = build_messages(generation_input)
            started_at = now_iso()
            started = time.perf_counter()
            final_result = None
            error_category = None
            error_summary = None
            attempts = 0
            for attempt in range(1, args.max_attempts + 1):
                attempts = attempt
                try:
                    final_result = validate_result(
                        strip_hidden_fields(gateway.complete(messages, response_format={"type": "json_object"})),
                        str(run.get("condition_id")),
                    )
                    error_category = None
                    error_summary = None
                    break
                except Exception as exc:  # preserve the final failure in the audit record
                    error_category, error_summary = classify_error(exc)
                    if error_category not in RETRYABLE or attempt >= args.max_attempts:
                        break
                    time.sleep(min(0.25 * attempt, 1.0))
            finished_at = now_iso()
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            meta = final_result.pop("_meta", {}) if isinstance(final_result, dict) else {}
            input_tokens, output_tokens = usage_counts(meta)
            if final_result is not None:
                text = str(final_result["text"])
                status = "completed"
                output_hash = text_hash(text)
                error = None
            else:
                text = ""
                status = "failed"
                output_hash = None
                error = error_summary
            common = {
                "run_id": run_id,
                "case_id": run.get("case_id"),
                "case_type": run.get("case_type"),
                "condition_id": run.get("condition_id"),
                "replicate": run.get("replicate"),
                "run_type": "live",
                "status": status,
                "attempt": attempts,
                "input_hash": run.get("input_hash"),
                "config_hash": run.get("config_hash"),
                "provider": run.get("provider"),
                "region": run.get("region"),
                "model": run.get("model"),
                "reasoning_effort": run.get("reasoning_effort"),
                "gateway_version": run.get("gateway_version"),
                "material_version": run.get("material_version"),
                "prompt_version": run.get("prompt_version"),
                "protocol_version": run.get("protocol_version"),
                "output_hash": output_hash,
                "latency_ms": latency_ms,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "retry_count": max(0, attempts - 1),
                "error_category": error_category,
                "error_summary": error_summary,
                "error": error,
                "started_at": started_at,
                "finished_at": finished_at,
            }
            output_row = {**common, "text": text, "structured": final_result, "call_meta": meta}
            record_row = {**run, **common}
            output_handle.write(json.dumps(output_row, ensure_ascii=False) + "\n")
            record_handle.write(json.dumps(record_row, ensure_ascii=False) + "\n")
            output_handle.flush()
            record_handle.flush()
    finally:
        output_handle.close()
        record_handle.close()
    print(f"completed live runner rows={len(manifest)} outputs={args.outputs} records={args.records}")


if __name__ == "__main__":
    main()
