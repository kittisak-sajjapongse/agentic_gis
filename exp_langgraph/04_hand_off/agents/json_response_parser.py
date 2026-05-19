from __future__ import annotations

import json


def parse_llm_json_object(raw_content: str) -> dict:
    """Parse a JSON object from LLM text, tolerating markdown code fences.

    This handles common model formatting drift such as:
    - ```json ... ```
    - leading/trailing prose around a JSON object
    """
    text = (raw_content or "").strip()
    if not text:
        raise ValueError("LLM returned empty content")

    # Fast path: already valid raw JSON object text.
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Remove fenced wrapper when present.
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        while lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # Last resort: parse first balanced JSON object slice.
    start = text.find("{")
    if start >= 0:
        depth = 0
        in_string = False
        escape = False
        for idx in range(start, len(text)):
            ch = text[idx]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : idx + 1]
                    parsed = json.loads(candidate)
                    if isinstance(parsed, dict):
                        return parsed
                    break

    raise ValueError("LLM response is not a parseable JSON object")

