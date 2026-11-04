#!/usr/bin/env python3
"""Create deterministic v2 fixture outputs for pipeline tests only.

Every row is labelled ``run_type=fixture``.  The structured block exists to
freeze the *coding interface* for later mechanism coding; every measurement slot
is ``null`` with ``coding_status=unobserved``.  Nothing here is a model result,
a human code, or an effect estimate.

The runner reads only ``generation_input`` from the manifest.  It never opens
``materials_v2.jsonl``, ``annotation_only_v2.jsonl`` or any gold artefact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTERFACE_VERSION = "huitong-mechanism-interface-v1"


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def output_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fixture_text(row: dict) -> str:
    gen = row["generation_input"]
    arg = gen["intermediate_argument"]
    claims = "；".join(f"{c['claim_id']}：{c['text']}（{c['strength']}/{c['status']}）" for c in arg["claims"])
    evidence = "；".join(f"{e['evidence_id']}：{e['text']}〔{e['locator']}〕" for e in arg["evidence"])
    votes = "；".join(f"{v['evidence_id']}={v['status']}" for v in arg["verification"])
    dissent = "；".join(f"{d['dissent_id']}：{d['text']}（{d['status']}）" for d in arg["dissent"]) or "无登记异议"
    return (
        f"【fixture 占位文本｜非模型输出】\n"
        f"【案例】{gen['case_id']}（{gen['case_type']}）{gen['topic']}\n"
        f"【问题】{gen['question']}\n"
        f"【主张】{claims}\n"
        f"【证据】{evidence}\n"
        f"【核验】{votes}\n"
        f"【反例与分歧】{dissent}\n"
        f"【编辑条件】{gen['condition_label']}（preserve={gen['preserve']}, audit={gen['audit']}）\n"
        f"【条件指令】{gen['instruction']}"
    )


def structured_block(gen: dict) -> dict:
    """Freeze the mechanism coding interface with unobserved slots."""
    arg = gen["intermediate_argument"]
    claims = [
        {"claim_id": c["claim_id"], "strength_in": c["strength"], "status_in": c["status"],
         "retained": None, "strength_out": None, "revision_reason": None,
         "coding_status": "unobserved"}
        for c in arg["claims"]
    ]
    links = [
        {"claim_id": link["claim_id"], "evidence_id": link["evidence_id"],
         "relation_in": link["relation"],
         "source_ids": next((e["source_ids"] for e in arg["evidence"] if e["evidence_id"] == link["evidence_id"]), []),
         "link_completeness": None, "link_alignment": None, "coding_status": "unobserved"}
        for link in arg["links"]
    ]
    verification = [
        {"evidence_id": v["evidence_id"], "verification_status_in": v["status"],
         "action_observed": None, "coding_status": "unobserved"}
        for v in arg["verification"]
    ]
    dissent = [
        {"dissent_id": d["dissent_id"], "target_claim_id": d["target_claim_id"],
         "status_in": d["status"], "handling": None, "carried_in_article": None,
         "coding_status": "unobserved"}
        for d in arg["dissent"]
    ]
    return {
        "interface_version": INTERFACE_VERSION,
        "values_are_fixture_placeholders": True,
        "not_a_model_result": True,
        "claims": claims,
        "claim_evidence_source_links": links,
        "verification_actions": verification,
        "challenge_handling": dissent,
        "certainty_downgrades": [],
        "revision_reasons": [],
        "edit_audit": [],
        "constraint_compliance": "not_observed",
        "turns": 1,
        "manual_intervention_count": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=HERE / "runs_v2" / "manifest.jsonl")
    parser.add_argument("--output", type=Path, default=HERE / "runs_v2" / "outputs.jsonl")
    parser.add_argument("--records", type=Path, default=HERE / "runs_v2" / "run_records.jsonl")
    args = parser.parse_args()

    rows = read_jsonl(args.manifest)
    outputs, records = [], []
    for row in rows:
        gen = row.get("generation_input")
        if not isinstance(gen, dict):
            raise ValueError(f"manifest_generation_input_missing:{row.get('run_id')}")
        for key in ("case_id", "case_type", "intermediate_argument", "instruction", "condition_id"):
            if key not in gen:
                raise ValueError(f"manifest_generation_input_incomplete:{row.get('run_id')}:{key}")
        text = fixture_text(row)
        digest = output_hash(text)
        structured = structured_block(gen)
        outputs.append({
            "run_id": row["run_id"],
            "case_id": row["case_id"],
            "case_type": row["case_type"],
            "condition_id": row["condition_id"],
            "preserve": row["preserve"],
            "audit": row["audit"],
            "replicate": row["replicate"],
            "run_type": "fixture",
            "status": "completed",
            "attempt": 1,
            "seed": row["seed"],
            "input_hash": row["input_hash"],
            "material_hash": row["material_hash"],
            "object_hash": row["object_hash"],
            "material_payload_hash": row["material_payload_hash"],
            "config_hash": row["config_hash"],
            "protocol_hash": row["protocol_hash"],
            "prompt_hash": row["prompt_hash"],
            "material_version": row["material_version"],
            "prompt_version": row["prompt_version"],
            "protocol_version": row["protocol_version"],
            "gateway_version": row["gateway_version"],
            "provider": row["provider"],
            "region": row["region"],
            "model": row["model"],
            "reasoning_effort": row["reasoning_effort"],
            "generation_input": gen,
            "text": text,
            "structured": structured,
            "output_hash": digest,
            "latency_ms": 0,
            "input_tokens": 0,
            "output_tokens": len(text),
            "turns": 1,
            "retry_count": 0,
            "manual_intervention_count": 0,
            "error_category": None,
            "error_summary": None,
            "error": None,
        })
        records.append({
            **row,
            "run_type": "fixture",
            "status": "completed",
            "attempt": 1,
            "started_at": None,
            "finished_at": None,
            "latency_ms": 0,
            "input_tokens": 0,
            "output_tokens": len(text),
            "turns": 1,
            "retry_count": 0,
            "manual_intervention_count": 0,
            "error_category": None,
            "error_summary": None,
            "error": None,
            "output_hash": digest,
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in outputs) + "\n", encoding="utf-8")
    args.records.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")
    print(f"generated {len(outputs)} fixture outputs -> {args.output}; records -> {args.records}")


if __name__ == "__main__":
    main()
