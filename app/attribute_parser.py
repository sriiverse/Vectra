import json
from typing import Any

import anthropic

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a product search attribute extractor.
Extract structured attributes from a user's search modifier text.
Return ONLY valid JSON with these optional keys:
- color (string, e.g. "Black", "Navy")
- size_min (float)
- size_max (float)
- max_price (float, strip currency symbols)
- category (string)
- subcategory (string)
If an attribute is not mentioned, omit the key entirely.
Return only the JSON object, no explanation."""


def parse_attributes(text: str | None) -> dict[str, Any]:
    if not text or not text.strip():
        return {}

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=256,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
    )

    raw = response.content[0].text.strip()
    return json.loads(raw)


def build_sql_filters(attrs: dict) -> tuple[list[str], list]:
    conditions = []
    params: list[Any] = []

    if attrs.get("color"):
        conditions.append("color = %s")
        params.append(attrs["color"])

    if attrs.get("size_min") is not None and attrs.get("size_max") is not None:
        conditions.append("size_min IS NOT NULL AND size_max IS NOT NULL")
        conditions.append("size_min <= %s AND size_max >= %s")
        params.append(attrs["size_max"])
        params.append(attrs["size_min"])

    if attrs.get("category"):
        conditions.append("category = %s")
        params.append(attrs["category"])

    if attrs.get("subcategory"):
        conditions.append("subcategory = %s")
        params.append(attrs["subcategory"])

    if attrs.get("max_price") is not None:
        conditions.append("price <= %s")
        params.append(attrs["max_price"])

    return conditions, params
