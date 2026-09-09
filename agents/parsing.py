"""Tolerant JSON parsing for model replies.

Models often wrap JSON in prose or a code fence. Rather than fight that with
prompting alone, read whatever object is in there and let callers decide what
to do when there is none.
"""

import json
import re

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def parse_json_object(text: str) -> dict | None:
    """Return the first JSON object in `text`, or None if there is not one."""
    if not text:
        return None
    match = _FENCE.search(text)
    candidate = match.group(1).strip() if match else text.strip()

    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(candidate[start:end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None
