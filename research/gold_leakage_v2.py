#!/usr/bin/env python3
"""Automated gold-leakage scan for the v2 generation side.

Three independent levels are checked on the manifest (including every
``generation_input``), the outputs (whole row, including ``text`` and
``structured``) and the run records:

1. **field names** — gold-only keys at any nesting depth, plus serialized key
   occurrences inside free text;
2. **exact values** — a gold list item or reference string appearing verbatim
   as a value in a generation-side record;
3. **distinctive content** — long gold strings (reference conclusions, manual
   anchors, allowed/must-not-claim statements) appearing as substrings.

Level 3 only covers strings long enough to be distinctive, so ordinary Chinese
overlap between material text and gold phrasing cannot produce false positives.
"""

from __future__ import annotations

import json
import re


GOLD_ONLY_FIELDS = {
    "required_elements", "required_qualifiers", "supported_alternatives", "incorrect_views",
    "reference_conclusion", "claim_level_gold", "expected_action", "case_hash",
    "scoring_side", "allowed_conclusion_scope", "must_not_claim", "manual_anchor_metric",
    "manual_anchors", "annotation_version", "gold", "gold_annotations",
}

# Gold strings shorter than this are checked only for exact value equality.
DISTINCTIVE_MIN_LENGTH = 12


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", value)


def gold_strings(gold_rows: list[dict], material_rows: list[dict]) -> list[tuple[str, str, str]]:
    """Return ``(source, field, value)`` for every scoring-side string."""
    items = []
    for row in gold_rows:
        case_id = row.get("case_id", "?")
        for field in ("required_elements", "required_qualifiers", "supported_alternatives", "incorrect_views"):
            for value in row.get(field, []) or []:
                items.append((case_id, field, str(value)))
        if row.get("reference_conclusion"):
            items.append((case_id, "reference_conclusion", str(row["reference_conclusion"])))
        for entry in row.get("claim_level_gold", []) or []:
            items.append((case_id, "expected_action", str(entry.get("expected_action", ""))))
    for row in material_rows:
        case_id = row.get("case_id", "?")
        side = row.get("scoring_side") or {}
        for field in ("allowed_conclusion_scope", "must_not_claim"):
            for value in side.get(field, []) or []:
                items.append((case_id, f"scoring_side.{field}", str(value)))
        for key, value in (side.get("manual_anchors") or {}).items():
            items.append((case_id, f"scoring_side.manual_anchors.{key}", str(value)))
        if side.get("manual_anchor_metric"):
            items.append((case_id, "scoring_side.manual_anchor_metric", str(side["manual_anchor_metric"])))
    return [item for item in items if item[2].strip()]


def walk_keys(value, path=""):
    """Yield ``path.key`` for every dict key at any depth."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield f"{path}.{key}" if path else key
            yield from walk_keys(item, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_keys(item, f"{path}[{index}]")


def walk_values(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from walk_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_values(item)
    else:
        yield value


def scan_row(row: dict, gold_values: list[tuple[str, str, str]], label: str) -> list[dict]:
    findings = []
    run_id = row.get("run_id", "?")

    for key_path in walk_keys(row):
        leaf = key_path.split(".")[-1].split("[")[0]
        if leaf in GOLD_ONLY_FIELDS:
            findings.append({"level": "field_name", "label": label, "run_id": run_id,
                             "path": key_path, "detail": leaf, "total": 1})

    serialized = json.dumps(row, ensure_ascii=False)
    for field in GOLD_ONLY_FIELDS:
        if f'"{field}"' in serialized:
            key_path = _first_key_path(row, field)
            if key_path:
                findings.append({"level": "field_name_in_text", "label": label, "run_id": run_id,
                                 "path": key_path, "detail": field, "total": 1})

    exact_values = {normalize(value) for _, _, value in gold_values}
    for path, value in _walk_scalar_paths(row):
        if isinstance(value, str) and normalize(value) in exact_values and normalize(value):
            findings.append({"level": "exact_value", "label": label, "run_id": run_id,
                             "path": path, "detail": value[:80], "total": 1})

    normalized_serialized = normalize(serialized)
    for case_id, field, value in gold_values:
        normalized_value = normalize(value)
        if len(normalized_value) < DISTINCTIVE_MIN_LENGTH:
            continue
        if field in {"required_elements", "required_qualifiers", "expected_action"}:
            continue
        if normalized_value in normalized_serialized:
            findings.append({"level": "distinctive_content", "label": label, "run_id": run_id,
                             "path": "*", "detail": f"{case_id}:{field}:{value[:80]}", "total": 1})
    return findings


def _first_key_path(row, field) -> str:
    for key_path in walk_keys(row):
        if key_path.split(".")[-1].split("[")[0] == field:
            return key_path
    return ""


def _walk_scalar_paths(value, path=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk_scalar_paths(item, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_scalar_paths(item, f"{path}[{index}]")
    else:
        yield path, value


def scan(manifest: list[dict], outputs: list[dict], records: list[dict],
         gold_rows: list[dict], material_rows: list[dict]) -> dict:
    gold_values = gold_strings(gold_rows, material_rows)
    findings = []
    for row in manifest:
        findings.extend(scan_row(row, gold_values, "manifest"))
    for row in outputs:
        findings.extend(scan_row(row, gold_values, "outputs"))
    for row in records:
        findings.extend(scan_row(row, gold_values, "run_records"))

    by_level: dict[str, int] = {}
    for item in findings:
        by_level[item["level"]] = by_level.get(item["level"], 0) + 1

    return {
        "count": len(findings),
        "total": len(findings),
        "by_level": by_level,
        "by_label": {
            label: sum(1 for item in findings if item["label"] == label)
            for label in ("manifest", "outputs", "run_records")
        },
        "gold_string_count": len(gold_values),
        "scanned_rows": {"manifest": len(manifest), "outputs": len(outputs), "run_records": len(records)},
        "findings": findings,
        "checked_levels": ["field_name", "field_name_in_text", "exact_value", "distinctive_content"],
    }
