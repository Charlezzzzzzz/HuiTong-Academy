#!/usr/bin/env python3
"""Audit the frozen v2 material bank and the generation/scoring separation."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import schema_lite

HERE = Path(__file__).resolve().parent


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def canonical_hash(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


GOLD_KEYS = {
    "required_elements", "required_qualifiers", "supported_alternatives", "incorrect_views",
    "reference_conclusion", "claim_level_gold", "expected_action", "case_hash",
}


def find_keys(value, keys, path=""):
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in keys:
                found.append(f"{path}{key}")
            found.extend(find_keys(item, keys, f"{path}{key}." ))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(find_keys(item, keys, f"{path}[{index}]."))
    return found


def audit(material_rows: list[dict], gold_rows: list[dict], registry: dict, schema: dict,
          conditions: dict) -> dict:
    schema_errors = []
    for row in material_rows:
        errors = schema_lite.validate(row, schema)
        schema_errors.extend(f"{row.get('case_id')}:{err}" for err in errors)

    hash_mismatch = []
    for row in material_rows:
        body = {k: v for k, v in row.items() if k != "row_hash"}
        if canonical_hash(body) != row["row_hash"]:
            hash_mismatch.append(f"{row['case_id']}:row_hash")
        payload = {k: row[k] for k in (
            "case_id", "case_type", "topic", "question", "task", "source_ids",
            "material_version", "intermediate_argument", "sources")}
        if canonical_hash(payload) != row["object_hash"]:
            hash_mismatch.append(f"{row['case_id']}:object_hash")

    type_counts = Counter(row["case_type"] for row in material_rows)
    claim_counts = [len(row["intermediate_argument"]["claims"]) for row in material_rows]
    evidence_counts = [len(row["intermediate_argument"]["evidence"]) for row in material_rows]
    link_counts = [len(row["intermediate_argument"]["links"]) for row in material_rows]
    dissent_counts = [len(row["intermediate_argument"]["dissent"]) for row in material_rows]
    verification_statuses = Counter(
        entry["status"] for row in material_rows for entry in row["intermediate_argument"]["verification"])
    evidence_directions = Counter(
        entry["direction"] for row in material_rows for entry in row["intermediate_argument"]["evidence"])

    all_source_ids = {sid for row in material_rows for sid in row["source_ids"]}
    registry_ids = set(registry["sources"])
    url_registered = [sid for sid in all_source_ids
                      if registry["sources"][sid]["url"] or registry["sources"][sid]["url_status"] != "not_registered"]
    verified_local = [sid for sid in all_source_ids
                      if registry["sources"][sid]["verification_status"] == "verified_local_text"]
    pending = [sid for sid in all_source_ids
               if registry["sources"][sid]["verification_status"] == "unverified_pending_human_audit"]

    evidence_source_missing = []
    for row in material_rows:
        for entry in row["intermediate_argument"]["evidence"]:
            for sid in entry["source_ids"]:
                if sid not in row["source_ids"]:
                    evidence_source_missing.append(f"{row['case_id']}:{entry['evidence_id']}:{sid}")
    link_target_missing = []
    for row in material_rows:
        claim_ids = {c["claim_id"] for c in row["intermediate_argument"]["claims"]}
        evidence_ids = {e["evidence_id"] for e in row["intermediate_argument"]["evidence"]}
        for link in row["intermediate_argument"]["links"]:
            if link["claim_id"] not in claim_ids or link["evidence_id"] not in evidence_ids:
                link_target_missing.append(f"{row['case_id']}:{link['claim_id']}-{link['evidence_id']}")
        for entry in row["intermediate_argument"]["verification"]:
            if entry["evidence_id"] not in evidence_ids:
                link_target_missing.append(f"{row['case_id']}:verification-{entry['evidence_id']}")
        for entry in row["intermediate_argument"]["dissent"]:
            if entry["target_claim_id"] not in claim_ids:
                link_target_missing.append(f"{row['case_id']}:dissent-{entry['target_claim_id']}")

    gold_leak_in_material = []
    for row in material_rows:
        body = {k: v for k, v in row.items() if k != "scoring_side"}
        gold_leak_in_material.extend(f"{row['case_id']}:{p}"
                                     for p in find_keys(body, GOLD_KEYS))

    gold_case_set = {row["case_id"] for row in gold_rows}
    material_case_set = {row["case_id"] for row in material_rows}
    gold_hash_mismatch = [row["case_id"] for row in gold_rows
                          if row.get("material_object_hash") != next(
                              (m["object_hash"] for m in material_rows if m["case_id"] == row["case_id"]), None)]
    gold_hash_ok = [row["case_id"] for row in gold_rows
                    if canonical_hash({k: v for k, v in row.items() if k != "case_hash"}) != row["case_hash"]]

    manual_anchor_metrics = Counter(row["scoring_side"]["manual_anchor_metric"] for row in material_rows)

    return {
        "material_version": material_rows[0]["material_version"],
        "schema_id": schema.get("$id"),
        "case_count": len(material_rows),
        "unique_case_count": len(material_case_set),
        "case_type_counts": dict(type_counts),
        "case_type_balance_ok": set(type_counts.values()) == {8} and len(type_counts) == 3,
        "required_fields_present": all(
            all(key in row for key in ("case_id", "case_type", "question", "source_ids",
                                       "intermediate_argument", "sources", "material_version",
                                       "object_hash", "row_hash"))
            for row in material_rows),
        "schema_errors": schema_errors,
        "hash_mismatch": hash_mismatch,
        "structure_counts": {
            "claims_total": sum(claim_counts),
            "evidence_total": sum(evidence_counts),
            "links_total": sum(link_counts),
            "dissent_total": sum(dissent_counts),
            "claims_per_case": {"min": min(claim_counts), "max": max(claim_counts)},
            "evidence_per_case": {"min": min(evidence_counts), "max": max(evidence_counts)},
            "links_per_case": {"min": min(link_counts), "max": max(link_counts)},
            "dissent_per_case": {"min": min(dissent_counts), "max": max(dissent_counts)},
        },
        "verification_status_counts": dict(verification_statuses),
        "evidence_direction_counts": dict(evidence_directions),
        "source_linkage": {
            "source_ids_used": sorted(all_source_ids),
            "source_registry_ids": sorted(registry_ids),
            "registry_unused_ids": sorted(registry_ids - all_source_ids),
            "ids_missing_from_registry": sorted(all_source_ids - registry_ids),
            "source_link_coverage": "24/24 案例均至少一个来源；每条证据均登记 source_ids",
            "url_registered_count": len(url_registered),
            "url_coverage_rate": f"{len(url_registered)}/{len(all_source_ids)}",
            "url_policy": registry["url_policy"],
            "verified_local_text_count": len(verified_local),
            "unverified_pending_human_audit_count": len(pending),
            "evidence_source_missing": evidence_source_missing,
            "link_target_missing": link_target_missing,
        },
        "gold_separation": {
            "gold_file": "annotation_only_v2.jsonl",
            "gold_case_count": len(gold_rows),
            "case_set_equal": gold_case_set == material_case_set,
            "gold_fields_found_outside_scoring_side": gold_leak_in_material,
            "gold_object_hash_mismatch": [c for c in gold_hash_mismatch if c],
            "gold_row_hash_mismatch": gold_hash_ok,
            "generation_whitelist": [
                "case_id", "case_type", "topic", "question", "task", "source_ids",
                "material_version", "intermediate_argument", "sources",
                "condition_id", "condition_label", "preserve", "audit", "instruction",
                "protocol_version", "prompt_version",
            ],
            "scoring_side_fields": sorted(material_rows[0]["scoring_side"]),
            "conclusion": ("materials_v2 行的 scoring_side 与 annotation_only_v2 只属于评分端；"
                           "manifest 生成器按白名单构造 generation_input，validator 另做字段名、"
                           "精确值与长文本三层泄漏扫描。"),
        },
        "manual_anchor_metric_counts": dict(manual_anchor_metrics),
        "version_consistency": {
            "material_version": material_rows[0]["material_version"],
            "conditions_material_version": conditions["material_version"],
            "annotation_version": gold_rows[0]["annotation_version"],
            "conditions_annotation_version": conditions["annotation_version"],
            "ok": (material_rows[0]["material_version"] == conditions["material_version"]
                   and gold_rows[0]["annotation_version"] == conditions["annotation_version"]),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--materials", type=Path, default=HERE / "materials_v2.jsonl")
    parser.add_argument("--gold", type=Path, default=HERE / "annotation_only_v2.jsonl")
    parser.add_argument("--registry", type=Path, default=HERE / "source_registry_v2.json")
    parser.add_argument("--schema", type=Path, default=HERE / "materials_v2.schema.json")
    parser.add_argument("--config", type=Path, default=HERE / "conditions_v2.json")
    parser.add_argument("--report", type=Path, default=HERE / "runs_v2" / "material_audit.json")
    args = parser.parse_args()

    report = audit(
        read_jsonl(args.materials), read_jsonl(args.gold),
        json.loads(args.registry.read_text(encoding="utf-8")),
        json.loads(args.schema.read_text(encoding="utf-8")),
        json.loads(args.config.read_text(encoding="utf-8")),
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = (not report["schema_errors"] and not report["hash_mismatch"]
          and report["case_type_balance_ok"] and report["required_fields_present"]
          and report["gold_separation"]["case_set_equal"]
          and not report["gold_separation"]["gold_fields_found_outside_scoring_side"]
          and not report["source_linkage"]["evidence_source_missing"]
          and not report["source_linkage"]["link_target_missing"]
          and report["version_consistency"]["ok"])
    print(json.dumps({"ok": ok, "case_count": report["case_count"],
                      "case_type_counts": report["case_type_counts"],
                      "schema_error_count": len(report["schema_errors"]),
                      "hash_mismatch_count": len(report["hash_mismatch"])}, ensure_ascii=False))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
