#!/usr/bin/env python3
"""A deliberately small JSON-Schema subset checker.

The environment does not ship ``jsonschema``; installing packages is out of
scope for this task.  This module implements exactly the keywords used by
``materials_v2.schema.json`` and fails loudly on an unsupported keyword, so the
subset cannot silently weaken validation.
"""

from __future__ import annotations

import re


SUPPORTED = {
    "$schema", "$id", "title", "description", "type", "required", "properties",
    "additionalProperties", "items", "enum", "const", "minItems", "maxItems",
    "uniqueItems", "minLength", "pattern",
}

TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}


def _type_ok(value, expected) -> bool:
    expected = [expected] if isinstance(expected, str) else list(expected)
    for name in expected:
        if name == "boolean":
            if isinstance(value, bool):
                return True
            continue
        if name in {"number", "integer"}:
            if isinstance(value, bool):
                continue
            if isinstance(value, TYPE_MAP[name]):
                return True
            continue
        if isinstance(value, TYPE_MAP[name]):
            return True
    return False


def _check_unsupported(schema, path):
    for key in schema:
        if key not in SUPPORTED:
            raise ValueError(f"unsupported_schema_keyword:{path}:{key}")


def validate(instance, schema, path="$"):
    """Return a list of ``path: message`` strings; empty means valid."""
    _check_unsupported(schema, path)
    errors = []

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: const mismatch")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value {instance!r} not in enum")

    if "type" in schema and not _type_ok(instance, schema["type"]):
        errors.append(f"{path}: expected type {schema['type']}, got {type(instance).__name__}")
        return errors

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: does not match pattern {schema['pattern']}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: fewer than minItems {schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: more than maxItems {schema['maxItems']}")
        if schema.get("uniqueItems"):
            seen = []
            for item in instance:
                if item in seen:
                    errors.append(f"{path}: duplicate item")
                seen.append(item)
        if "items" in schema:
            for index, item in enumerate(instance):
                errors.extend(validate(item, schema["items"], f"{path}[{index}]"))

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required field {key}")
        properties = schema.get("properties", {})
        for key, value in instance.items():
            if key in properties:
                errors.extend(validate(value, properties[key], f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected field {key}")
            elif isinstance(schema.get("additionalProperties"), dict):
                errors.extend(validate(value, schema["additionalProperties"], f"{path}.{key}"))
    return errors
