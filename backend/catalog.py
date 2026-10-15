import re
import json
from typing import List, Dict, Any, Optional, Tuple

def extract_weight_or_pack(text: str) -> Optional[str]:
    """Extracts weights like 1kg, 500g, 1.5kg, or pack counts like 6 pack, box of 10."""
    t = text.lower()
    # kg matches
    kg_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg|kilo|kilos)", t)
    if kg_match:
        val = kg_match.group(1)
        return f"{val}kg"

    # g matches
    g_match = re.search(r"(\d+)\s*(?:g|grams?|gm)", t)
    if g_match:
        val = g_match.group(1)
        return f"{val}g"

    # half kg
    if "half kg" in t or "500g" in t or "half kilo" in t or "1/2 kg" in t:
        return "500g"

    # box / pack matches
    box_match = re.search(r"(?:box of|pack of|box|pack)\s*(\d+)", t)
    if box_match:
        return f"Box of {box_match.group(1)}"

    num_box = re.search(r"(\d+)\s*(?:box|pack|pieces|pcs)", t)
    if num_box:
        return f"Box of {num_box.group(1)}"

    return None

def match_catalog_item(
    product_query: str,
    variant_query: str,
    catalog_items: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Deterministically matches extracted product intent to the seller's catalog.
    Computes exact prices and flags confidence.
    """
    clean_p = product_query.strip().lower()
    clean_v = variant_query.strip().lower()

    # If variant is empty, check if it's embedded in the product name
    if not clean_v:
        extracted_v = extract_weight_or_pack(clean_p)
        if extracted_v:
            clean_v = extracted_v.lower()

    best_match = None
    best_score = 0.0

    for item in catalog_items:
        item_name = item["name"].lower()
        item_variant = item["variant"].lower()
        aliases = [a.lower() for a in item.get("aliases", [])]

        score = 0.0

        # Exact alias match with variant
        for alias in aliases:
            if clean_p == alias:
                score = 0.95
                break
            elif alias in clean_p or clean_p in alias:
                score = max(score, 0.75)

        # Name match
        if clean_p == item_name:
            score = max(score, 0.9)
        elif item_name in clean_p or clean_p in item_name:
            score = max(score, 0.7)

        # Token overlap
        p_tokens = set(clean_p.split())
        item_tokens = set(item_name.split())
        overlap = len(p_tokens.intersection(item_tokens))
        if overlap > 0:
            token_score = (overlap / max(len(p_tokens), 1)) * 0.65
            score = max(score, token_score)

        # Variant match bonus/penalty
        if clean_v and item_variant:
            if clean_v == item_variant:
                score += 0.3
            elif clean_v in item_variant or item_variant in clean_v:
                score += 0.2
            else:
                # Mismatched variant penalty if score was high
                if score > 0.5:
                    score -= 0.25

        if score > best_score:
            best_score = score
            best_match = item

    if best_match and best_score >= 0.5:
        unit_price = float(best_match["price"])
        matched_variant = best_match["variant"]
        catalog_id = best_match["id"]
        canonical_name = best_match["name"]
        confidence = min(best_score, 1.0)
    else:
        unit_price = 0.0
        matched_variant = variant_query or "1kg"
        catalog_id = None
        canonical_name = product_query
        confidence = 0.4

    return {
        "catalog_id": catalog_id,
        "product_name": canonical_name,
        "variant": matched_variant,
        "unit_price": unit_price,
        "confidence": round(confidence, 2),
        "is_matched": catalog_id is not None
    }

def price_order_items(
    items: List[Dict[str, Any]],
    catalog_items: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], float]:
    """
    Computes prices and totals for all items in an order deterministically.
    """
    priced_items = []
    total_amount = 0.0

    for it in items:
        prod_name = it.get("product_name", "")
        variant = it.get("variant", "")
        qty = float(it.get("quantity", 1.0) or 1.0)

        match_info = match_catalog_item(prod_name, variant, catalog_items)
        unit_price = match_info["unit_price"]
        item_total = unit_price * qty
        total_amount += item_total

        priced_item = {
            "catalog_id": match_info["catalog_id"],
            "product_name": match_info["product_name"],
            "quantity": qty,
            "variant": match_info["variant"],
            "unit_price": unit_price,
            "total_price": item_total,
            "notes": it.get("notes", ""),
            "source_message_ids": it.get("source_message_ids", []),
            "confidence": match_info["confidence"],
            "is_matched": match_info["is_matched"]
        }
        priced_items.append(priced_item)

    return priced_items, round(total_amount, 2)
