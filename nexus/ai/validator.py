from __future__ import annotations

_TYPE_MAP: dict[str, type] = {
    "string":  str,
    "integer": int,
    "boolean": bool,
    "array":   list,
    "object":  dict,
}


class ValidationError(Exception):
    def __init__(self, tool_name: str, errors: list[str]) -> None:
        self.tool_name = tool_name
        self.errors    = errors
        super().__init__(f"{tool_name}: {'; '.join(errors)}")


def validate_args(name: str, args: dict, schema: dict) -> None:
    """Raise ValidationError if args do not satisfy the JSON schema (required + types)."""
    errors: list[str] = []
    props = schema.get("properties", {})

    for field in schema.get("required", []):
        if field not in args:
            errors.append(f"missing required field '{field}'")

    for field, value in args.items():
        if field not in props:
            continue
        expected = props[field].get("type")
        py_type  = _TYPE_MAP.get(expected)
        if not py_type:
            continue
        # bool is a subclass of int in Python — explicitly reject it for integer fields
        if expected == "integer" and isinstance(value, bool):
            errors.append(f"'{field}' must be integer, got bool")
        elif not isinstance(value, py_type):
            errors.append(f"'{field}' must be {expected}, got {type(value).__name__}")

    if errors:
        raise ValidationError(name, errors)
