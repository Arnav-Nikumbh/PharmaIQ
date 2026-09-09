"""Text tidying applied to anything a person will read.

Models ignore a "do not use em dashes" instruction often enough that the rule
has to be enforced in code rather than hoped for in a prompt.
"""

import re

# Em dash, en dash, and the non-breaking hyphen models sometimes emit.
_SPACED_DASH = re.compile(r"\s*[—–]\s*")
_BARE_DASH = re.compile(r"[—–]")


def plain_dashes(text: str) -> str:
    """Replace em and en dashes with plain punctuation.

    A dash with space around it becomes a spaced hyphen; one joining two words
    becomes a plain hyphen. Non-breaking hyphens become ordinary ones.
    """
    if not text:
        return text
    text = text.replace("‑", "-")
    text = _SPACED_DASH.sub(
        lambda m: "-" if m.group(0) == m.group(0).strip() else " - ", text
    )
    return _BARE_DASH.sub("-", text)
