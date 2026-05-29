import re
from typing import Any

COLOR_ALIASES: dict[str, str] = {
    "white": "White", "black": "Black", "navy": "Navy", "navy blue": "Navy",
    "beige": "Beige", "olive": "Olive", "grey": "Grey", "gray": "Grey",
    "blue": "Blue", "sky blue": "Sky Blue", "charcoal": "Charcoal",
    "purple": "Purple", "red": "Red", "green": "Green", "khaki": "Khaki",
    "burgundy": "Burgundy", "mint": "Mint", "coral": "Coral", "teal": "Teal",
    "cream": "Cream", "pink": "Pink", "brown": "Brown", "tan": "Tan",
    "gold": "Gold", "silver": "Silver", "terracotta": "Terracotta",
    "lavender": "Lavender", "mustard": "Mustard", "clear": "Clear",
    "rose": "Rose", "orange": "Orange", "nude": "Nude", "amber": "Amber",
    "multicolor": "Multicolor", "peach": "Peach", "blush": "Blush",
    "floral": "Floral",
}

CATEGORY_HINTS: dict[str, str] = {
    "sneaker": "Footwear", "sneakers": "Footwear", "shoe": "Footwear",
    "shoes": "Footwear", "boot": "Footwear", "boots": "Footwear",
    "sandals": "Footwear", "sandal": "Footwear", "loafer": "Footwear",
    "loafers": "Footwear", "heel": "Footwear", "heels": "Footwear",
    "shirt": "Apparel", "t-shirt": "Apparel", "top": "Apparel",
    "pant": "Apparel", "pants": "Apparel", "jean": "Apparel",
    "jeans": "Apparel", "short": "Apparel", "shorts": "Apparel",
    "dress": "Apparel", "jacket": "Apparel", "hoodie": "Apparel",
    "sweater": "Apparel", "blazer": "Apparel", "skirt": "Apparel",
    "legging": "Apparel", "leggings": "Apparel", "trouser": "Apparel",
    "trousers": "Apparel", "coat": "Apparel",
    "tv": "Electronics", "speaker": "Electronics", "headphone": "Electronics",
    "headphones": "Electronics", "camera": "Electronics", "laptop": "Electronics",
    "phone": "Electronics", "watch": "Electronics",
    "cushion": "Home", "pillow": "Home", "lamp": "Home", "vase": "Home",
    "plant": "Home", "mug": "Home", "towel": "Home", "rug": "Home",
    "candle": "Home", "shelf": "Home",
    "lipstick": "Beauty", "perfume": "Beauty", "lotion": "Beauty",
    "soap": "Beauty", "shampoo": "Beauty",
}

SUBCATEGORY_HINTS: dict[str, str] = {
    "sneaker": "Sports", "sneakers": "Sports", "running": "Sports",
    "boots": "Boots", "hiking": "Boots", "loafer": "Formal",
    "loafers": "Formal", "oxford": "Formal", "formal": "Formal",
    "sandals": "Casual", "heel": "Heels", "heels": "Heels",
    "t-shirt": "Tops", "shirt": "Tops", "hoodie": "Tops",
    "sweater": "Tops", "skirt": "Bottoms", "short": "Bottoms",
    "shorts": "Bottoms", "pant": "Bottoms", "pants": "Bottoms",
    "trouser": "Bottoms", "trousers": "Bottoms", "jean": "Bottoms",
    "dress": "Dresses", "jacket": "Outerwear", "blazer": "Outerwear",
    "coat": "Outerwear",
}


def parse_attributes(text: str | None) -> dict[str, Any]:
    result: dict[str, Any] = {
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

    for alias, canonical in sorted(COLOR_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in lower:
            result["color"] = canonical
            break

    size_patterns = [
        r"(?:size|sz|sizes?)\s*(\d+(?:\.\d+)?)\s*(?:-|to|–)\s*(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)\s*(?:-|to|–)\s*(\d+(?:\.\d+)?)(?:\s*(?:size|sz))?",
    ]
    for pat in size_patterns:
        m = re.search(pat, lower)
        if m:
            result["size_min"] = float(m.group(1))
            result["size_max"] = float(m.group(2))
            if result["size_min"] > result["size_max"]:
                result["size_min"], result["size_max"] = result["size_max"], result["size_min"]
            break

    if result["size_min"] is None:
        m = re.search(r"(?:size|sz|sizes?)\s*(\d+(?:\.\d+)?)", lower)
        if m:
            v = float(m.group(1))
            result["size_min"] = v - 0.5
            result["size_max"] = v + 0.5

    price_patterns = [
        r"(?:under|below|less than|max|budget|at most)\s*(?:rs\.?\s*|inr\s*|₹\s*|£\s*|\$\s*|€\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)",
        r"(?:rs\.?\s*|inr\s*|₹\s*|£\s*|\$\s*|€\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:or\s*)?(?:under|below|less)",
    ]
    for pat in price_patterns:
        m = re.search(pat, lower)
        if m:
            price_str = m.group(1).replace(",", "")
            result["max_price"] = float(price_str)
            break

    for keyword, cat in CATEGORY_HINTS.items():
        if keyword in lower:
            result["category"] = cat
            break

    if result["size_min"] is not None and result["category"] is None:
        result["category"] = "Footwear"

    for keyword, sub in SUBCATEGORY_HINTS.items():
        if keyword in lower:
            result["subcategory"] = sub
            break

    return result
