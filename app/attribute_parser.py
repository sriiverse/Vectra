"""
Vectra: Query Attribute Parser.

Extracts structured attributes from natural language text modifiers.
Translates fuzzy text like "white, size 8-9, under 5000" into precise
SQL-level filters: color="White", size range intersects [8,9], price <= 5000.

Why this matters:
  CLIP doesn't understand "size 8-9" — it treats it as arbitrary tokens.
  The cross-encoder can't match "size 8-9" to product descriptions either.
  By parsing attributes explicitly and applying them as SQL filters,
  we guarantee non-footwear products are excluded when the user asks for shoes.
"""

import re

# Known color names mapped to canonical form (matching our DB color values)
COLOR_ALIASES: dict[str, str] = {
    "white": "White",
    "black": "Black",
    "navy": "Navy",
    "navy blue": "Navy",
    "beige": "Beige",
    "olive": "Olive",
    "grey": "Grey",
    "gray": "Grey",
    "blue": "Blue",
    "sky blue": "Sky Blue",
    "charcoal": "Charcoal",
    "purple": "Purple",
    "red": "Red",
    "green": "Green",
    "khaki": "Khaki",
    "burgundy": "Burgundy",
    "mint": "Mint",
    "coral": "Coral",
    "teal": "Teal",
    "cream": "Cream",
    "pink": "Pink",
    "brown": "Brown",
    "tan": "Tan",
    "gold": "Gold",
    "silver": "Silver",
    "terracotta": "Terracotta",
    "lavender": "Lavender",
    "mustard": "Mustard",
    "clear": "Clear",
    "rose": "Rose",
    "orange": "Orange",
    "nude": "Nude",
    "amber": "Amber",
    "multicolor": "Multicolor",
    "peach": "Peach",
    "blush": "Blush",
    "floral": "Floral",
}

# Category hints — if the text names a product type, infer the category
CATEGORY_HINTS: dict[str, str] = {
    # Footwear
    "sneaker": "Footwear",
    "sneakers": "Footwear",
    "shoe": "Footwear",
    "shoes": "Footwear",
    "boot": "Footwear",
    "boots": "Footwear",
    "sandals": "Footwear",
    "sandal": "Footwear",
    "loafer": "Footwear",
    "loafers": "Footwear",
    "heel": "Footwear",
    "heels": "Footwear",
    "flip flop": "Footwear",
    "flip flops": "Footwear",
    "espadrilles": "Footwear",
    # Apparel
    "shirt": "Apparel",
    "t-shirt": "Apparel",
    "tshirt": "Apparel",
    "top": "Apparel",
    "pant": "Apparel",
    "pants": "Apparel",
    "jean": "Apparel",
    "jeans": "Apparel",
    "short": "Apparel",
    "shorts": "Apparel",
    "dress": "Apparel",
    "jacket": "Apparel",
    "hoodie": "Apparel",
    "sweater": "Apparel",
    "blazer": "Apparel",
    "skirt": "Apparel",
    "legging": "Apparel",
    "leggings": "Apparel",
    "trouser": "Apparel",
    "trousers": "Apparel",
    "chino": "Apparel",
    "chinos": "Apparel",
    "sweatpant": "Apparel",
    "sweatpants": "Apparel",
    "jogger": "Apparel",
    "joggers": "Apparel",
    "coat": "Apparel",
    "tank top": "Apparel",
    "cardigan": "Apparel",
    # Electronics
    "tv": "Electronics",
    "television": "Electronics",
    "speaker": "Electronics",
    "headphone": "Electronics",
    "headphones": "Electronics",
    "earbud": "Electronics",
    "earbuds": "Electronics",
    "camera": "Electronics",
    "laptop": "Electronics",
    "tablet": "Electronics",
    "phone": "Electronics",
    "smartwatch": "Electronics",
    "watch": "Electronics",
    "charger": "Electronics",
    "monitor": "Electronics",
    "keyboard": "Electronics",
    "mouse": "Electronics",
    "bulb": "Electronics",
    # Home
    "cushion": "Home",
    "pillow": "Home",
    "lamp": "Home",
    "vase": "Home",
    "pot": "Home",
    "plant": "Home",
    "jar": "Home",
    "mug": "Home",
    "cup": "Home",
    "towel": "Home",
    "mat": "Home",
    "rug": "Home",
    "candle": "Home",
    "frame": "Home",
    "organiser": "Home",
    "organizer": "Home",
    "shelf": "Home",
    "basket": "Home",
    # Beauty
    "lipstick": "Beauty",
    "lip": "Beauty",
    "foundation": "Beauty",
    "cream": "Beauty",
    "lotion": "Beauty",
    "serum": "Beauty",
    "perfume": "Beauty",
    "cologne": "Beauty",
    "sunscreen": "Beauty",
    "shampoo": "Beauty",
    "soap": "Beauty",
    "moisturiser": "Beauty",
    "moisturizer": "Beauty",
    "mascara": "Beauty",
    "blush": "Beauty",
    "eyeliner": "Beauty",
    "nail": "Beauty",
    "polish": "Beauty",
}

# Subcategory hints — map specific product types to subcategories
SUBCATEGORY_HINTS: dict[str, str] = {
    "sneaker": "Sports",
    "sneakers": "Sports",
    "running": "Sports",
    "basketball": "Sports",
    "hiking": "Boots",
    "combat": "Boots",
    "boots": "Boots",
    "loafer": "Formal",
    "loafers": "Formal",
    "oxford": "Formal",
    "formal": "Formal",
    "sandals": "Casual",
    "heel": "Heels",
    "heels": "Heels",
    "platform": "Heels",
    "wedge": "Heels",
    "t-shirt": "Tops",
    "tshirt": "Tops",
    "shirt": "Tops",
    "polo": "Tops",
    "hoodie": "Tops",
    "sweater": "Tops",
    "skirt": "Bottoms",
    "short": "Bottoms",
    "shorts": "Bottoms",
    "pant": "Bottoms",
    "pants": "Bottoms",
    "trouser": "Bottoms",
    "trousers": "Bottoms",
    "jean": "Bottoms",
    "legging": "Bottoms",
    "leggings": "Bottoms",
    "dress": "Dresses",
    "jacket": "Outerwear",
    "blazer": "Outerwear",
    "coat": "Outerwear",
}


def parse_attributes(text: str | None) -> dict:
    """
    Parse a text string into structured attribute filters.

    Args:
        text: User's text modifier (e.g. "white colour, size 8-9, under 5000")

    Returns:
        Dict with keys:
          - color: canonical color name or None
          - size_min: float or None
          - size_max: float or None
          - category: inferred category or None
          - subcategory: inferred subcategory or None
          - max_price: float or None
          - raw_text: original text (for downstream reranking)
    """
    result: dict = {
        "color": None,
        "size_min": None,
        "size_max": None,
        "category": None,
        "subcategory": None,
        "max_price": None,
        "raw_text": text or "",
    }

    if not text or not text.strip():
        return result

    lower = text.lower().strip()

    # --- Extract color ---
    for alias, canonical in COLOR_ALIASES.items():
        if alias in lower:
            result["color"] = canonical
            break

    # --- Extract size range ---
    # Patterns: "size 8-9", "size 8 to 9", "size 8", "sz 8-9", "8-9"
    size_patterns = [
        r"(?:size|sz|sizes?)\s*(\d+(?:\.\d+)?)\s*(?:-|to|–)\s*(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)\s*(?:-|to|–)\s*(\d+(?:\.\d+)?)(?:\s*(?:size|sz))?",
    ]
    for pat in size_patterns:
        m = re.search(pat, lower)
        if m:
            result["size_min"] = float(m.group(1))
            result["size_max"] = float(m.group(2))
            # Clamp to reasonable range
            if result["size_min"] > result["size_max"]:
                result["size_min"], result["size_max"] = result["size_max"], result["size_min"]
            break

    if result["size_min"] is None:
        m = re.search(r"(?:size|sz|sizes?)\s*(\d+(?:\.\d+)?)", lower)
        if m:
            v = float(m.group(1))
            result["size_min"] = v - 0.5
            result["size_max"] = v + 0.5

    # --- Extract max price ---
    price_patterns = [
        r"(?:under|below|less than|max|budget|at most)\s*(?:rs\.?\s*|inr\s*|₹\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)",
        r"(?:rs\.?\s*|inr\s*|₹\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:or\s*)?(?:under|below|less)",
    ]
    for pat in price_patterns:
        m = re.search(pat, lower)
        if m:
            price_str = m.group(1).replace(",", "")
            result["max_price"] = float(price_str)
            break

    # --- Infer category from product type keywords ---
    # Also use "size" mention as a hint for Footwear/Apparel
    for keyword, cat in CATEGORY_HINTS.items():
        if keyword in lower:
            result["category"] = cat
            break

    # If "size" was mentioned but no specific category, infer Apparel+Footwear intent
    if result["size_min"] is not None and result["category"] is None:
        result["category"] = "Footwear"  # default to footwear for size queries

    # --- Infer subcategory ---
    for keyword, sub in SUBCATEGORY_HINTS.items():
        if keyword in lower:
            result["subcategory"] = sub
            break

    return result


def build_sql_filters(attrs: dict) -> tuple[list[str], list]:
    """
    Convert parsed attributes into SQL WHERE conditions and parameter list.

    Returns:
        (conditions list, params list) suitable for appending to a query.
    """
    conditions = []
    params: list = []

    if attrs.get("color"):
        conditions.append("color = %s")
        params.append(attrs["color"])

    if attrs.get("size_min") is not None and attrs.get("size_max") is not None:
        # Range overlap: product range intersects query range
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
