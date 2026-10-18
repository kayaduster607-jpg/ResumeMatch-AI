"""Prompt rendering helpers.

Do not use str.format() on prompt files that contain JSON examples: literal
braces in the examples will be treated as Python format placeholders and raise
KeyError.  This helper only replaces explicit placeholders like {raw_text}.
"""

from typing import Any


def render_prompt(template: str, **values: Any) -> str:
    text = template or ""
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value if value is not None else ""))
    return text
