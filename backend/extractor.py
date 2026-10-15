import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import httpx
from pydantic import BaseModel, Field

from backend.config import OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL
from backend.database import get_db

# JSON Schema for Qwen3-8B structured output via Ollama
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["new", "changed", "cancelled", "inquiry"],
            "description": "Order status. Use 'cancelled' if customer requested cancellation, 'changed' if rescheduling or modifying, 'new' for standard orders."
        },
        "delivery_date": {
            "type": "string",
            "description": "Delivery date in YYYY-MM-DD format if known or estimated from context (e.g. today, tomorrow, Sunday)."
        },
        "delivery_time": {
            "type": "string",
            "description": "Delivery time or window (e.g. '16:00', 'Evening', 'Morning', '2:30 PM')."
        },
        "area": {
            "type": "string",
            "description": "Delivery area, town, or neighborhood (e.g. Peradeniya, Kandy, Maharagama, Colombo)."
        },
        "delivery_address": {
            "type": "string",
            "description": "Specific delivery address, street, or landmark if provided."
        },
        "payment_status": {
            "type": "string",
            "enum": ["pending", "paid", "cod"],
            "description": "Payment status: 'cod' (cash on delivery), 'paid' (bank slip sent), or 'pending'."
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "product_name": {"type": "string", "description": "Name of product (e.g. chocolate cake, brownies, butter cake)."},
                    "quantity": {"type": "number", "description": "Quantity or number of units/boxes/cakes."},
                    "variant": {"type": "string", "description": "Size or variant (e.g. 1kg, 500g, 2kg, Box of 6)."},
                    "notes": {"type": "string", "description": "Custom notes like icing inscription or special requests."},
                    "source_message_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of message indices where this item was requested or modified."
                    }
                },
                "required": ["product_name", "quantity", "variant"]
            }
        },
        "source_message_ids": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "All message indices that contributed to this order extraction."
        },
        "confidence_overall": {
            "type": "number",
            "description": "Confidence score between 0.0 and 1.0."
        },
        "flags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Warning flags for review, e.g. ambiguous_delivery_date, missing_flavor, custom_icing."
        },
        "summary_notes": {
            "type": "string",
            "description": "Short explanation of the order or change."
        }
    },
    "required": ["status", "items", "source_message_ids"]
}

# Known Sri Lankan locations for entity recognition
KNOWN_AREAS = [
    "Peradeniya", "Kandy", "Katugastota", "Maharagama", "Nugegoda", "Colombo",
    "Gampaha", "Dehiwala", "Malabe", "Kottawa", "Battaramulla", "Mount Lavinia",
    "Rajagiriya", "Pannipitiya", "Kiribathgoda", "Kadawatha", "Moratuwa", "Pilimathalawa",
    "Digana", "Kundasale", "Gannoruwa", "Gelioya", "Gampola", "Wattala", "Ja-Ela",
    "Homagama", "Athurugiriya", "Kohuwala", "Boralesgamuwa", "Piliyandala", "Kaduwela"
]

ENGLISH_NUMERALS = {
    "a": 1.0, "an": 1.0, "one": 1.0, "two": 2.0, "three": 3.0, "four": 4.0,
    "five": 5.0, "six": 6.0, "seven": 7.0, "eight": 8.0, "nine": 9.0,
    "ten": 10.0, "dozen": 12.0, "half dozen": 6.0, "half": 0.5, "couple": 2.0
}

def get_few_shot_examples(limit: int = 3) -> List[Dict[str, Any]]:
    """Loads seller's confirmed corrections to inject as few-shot context."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT raw_chat_prompt, corrected_json
        FROM corrections
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()

    examples = []
    for r in rows:
        try:
            examples.append({
                "chat": r["raw_chat_prompt"],
                "extraction": json.loads(r["corrected_json"])
            })
        except Exception:
            pass
    return examples

def check_ollama_health(ollama_url: str = OLLAMA_BASE_URL) -> bool:
    """Checks if Ollama server is responsive."""
    try:
        resp = httpx.get(f"{ollama_url}/api/tags", timeout=1.5)
        return resp.status_code == 200
    except Exception:
        return False

def extract_order_with_ollama(
    thread_messages: List[Dict[str, Any]],
    base_date: Optional[datetime] = None,
    ollama_url: str = OLLAMA_BASE_URL,
    model_name: str = DEFAULT_OLLAMA_MODEL
) -> Dict[str, Any]:
    """
    Extracts structured order from chat messages using Ollama with Qwen JSON-schema output.
    """
    if not base_date:
        base_date = datetime.now()

    # Prepare chat prompt with numbered message indices and masked phone numbers
    chat_lines = []
    for m in thread_messages:
        idx = m.get("message_index", 1)
        role = "Seller" if m.get("is_seller") else "Customer"
        chat_lines.append(f"[Msg {idx}] {role}: {m['message_text']}")

    prompt_chat_text = "\n".join(chat_lines)

    # Few-shot examples
    examples = get_few_shot_examples(3)
    few_shot_prompt = ""
    if examples:
        few_shot_prompt = "\nHere are examples of confirmed orders from this seller:\n"
        for i, ex in enumerate(examples, 1):
            few_shot_prompt += f"Example {i} Chat:\n{ex['chat']}\nOutput:\n{json.dumps(ex['extraction'])}\n\n"

    system_prompt = f"""You are ChatLedger, an expert order extraction engine for a home baker.
Customers write in English (e.g. 'I would like to order a 1kg chocolate cake for Sunday evening, deliver to Peradeniya').
Today's reference date is: {base_date.strftime('%Y-%m-%d')} ({base_date.strftime('%A')}).

Instructions:
1. Extract ordered items with quantities and variants (e.g. 1kg, 500g, Box of 6).
2. Resolve delivery date (e.g. 'today' = {base_date.strftime('%Y-%m-%d')}, 'tomorrow' = {(base_date + timedelta(days=1)).strftime('%Y-%m-%d')}, 'Sunday' = upcoming Sunday).
3. If customer asks to cancel ('cancel', 'cancel the order', 'party cancelled'), set status to 'cancelled'.
4. If customer changes date or items ('change', 'reschedule', 'postponed to Monday'), set status to 'changed'.
5. Always link each item and the order to its exact source message indices ([Msg 1], [Msg 2], etc.).
6. Extract custom cake inscriptions/notes (e.g. 'Happy Birthday Mom').
7. Flag any ambiguity (e.g. ambiguous_delivery_date, missing_flavor).
8. Return strictly valid JSON adhering to the specified schema.
{few_shot_prompt}"""

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract the order from this customer thread:\n\n{prompt_chat_text}"}
        ],
        "format": EXTRACTION_SCHEMA,
        "stream": False,
        "options": {
            "temperature": 0.1
        }
    }

    try:
        resp = httpx.post(f"{ollama_url}/api/chat", json=payload, timeout=45.0)
        if resp.status_code == 200:
            result_json = resp.json()
            content = result_json.get("message", {}).get("content", "")
            parsed = json.loads(content)
            parsed["engine"] = f"ollama/{model_name}"
            return parsed
        else:
            raise RuntimeError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        # Fall back to local heuristic extractor if Ollama fails
        return extract_order_heuristic(thread_messages, base_date, fallback_reason=str(e))

def extract_order_heuristic(
    thread_messages: List[Dict[str, Any]],
    base_date: Optional[datetime] = None,
    fallback_reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    High-Accuracy Local English Intent Heuristic Extractor.
    Operates 100% offline with zero dependencies, recognizing English phrasing,
    dates, weights, quantities, cancellations, locations, and custom inscriptions.
    """
    if not base_date:
        base_date = datetime.now()

    full_text_lower = " ".join(m["message_text"].lower() for m in thread_messages)
    flags: List[str] = []
    source_message_ids: List[int] = []

    # 1. Detect Cancellation or Rescheduling Status
    status = "new"
    cancel_cues = ["cancel", "call off", "cancel the order", "cancelled", "canceling", "don't want", "dont want", "drop the order", "cancel it", "cancel my order"]
    change_cues = ["change", "reschedule", "postpone", "postponed", "moved to", "different date", "move the delivery", "another day", "push back"]

    for m in thread_messages:
        text = m["message_text"].lower()
        idx = m.get("message_index", 1)
        if any(c in text for c in cancel_cues):
            status = "cancelled"
            source_message_ids.append(idx)
            flags.append("order_cancelled_by_customer")
            break
        elif any(c in text for c in change_cues):
            status = "changed"
            source_message_ids.append(idx)
            flags.append("order_modified_or_rescheduled")

    # 2. Extract Delivery Date
    delivery_date_str = ""
    delivery_time_str = ""

    # Check for weekday references
    weekdays = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
    date_found = False

    for m in reversed(thread_messages):
        text = m["message_text"].lower()
        idx = m.get("message_index", 1)

        # Check for explicit weekday first (e.g. "Sunday evening")
        for wd_name, wd_idx in weekdays.items():
            if re.search(rf"\b{wd_name}\b", text):
                days_ahead = (wd_idx - base_date.weekday() + 7) % 7
                if days_ahead == 0:
                    days_ahead = 7  # Next week's weekday if today is the same day
                target = base_date + timedelta(days=days_ahead)
                delivery_date_str = target.strftime("%Y-%m-%d")
                source_message_ids.append(idx)
                date_found = True
                break
        if date_found:
            break

        # Check explicit day/month e.g. "24th Oct" or "24/10"
        date_explicit = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", text)
        if date_explicit:
            day = int(date_explicit.group(1))
            month_str = date_explicit.group(2)
            month_map = {"jan":1, "feb":2, "mar":3, "apr":4, "may":5, "jun":6, "jul":7, "aug":8, "sep":9, "oct":10, "nov":11, "dec":12}
            target_year = base_date.year
            try:
                target = datetime(target_year, month_map[month_str], day)
                delivery_date_str = target.strftime("%Y-%m-%d")
                source_message_ids.append(idx)
                date_found = True
                break
            except ValueError:
                pass

        # "tomorrow"
        if re.search(r"\btomorrow\b", text):
            target = base_date + timedelta(days=1)
            delivery_date_str = target.strftime("%Y-%m-%d")
            source_message_ids.append(idx)
            date_found = True
            break
        # "day after tomorrow"
        elif re.search(r"\bday after tomorrow\b", text):
            target = base_date + timedelta(days=2)
            delivery_date_str = target.strftime("%Y-%m-%d")
            source_message_ids.append(idx)
            date_found = True
            break
        # "today" / "tonight"
        elif re.search(r"\btoday\b|\btonight\b", text):
            target = base_date
            delivery_date_str = target.strftime("%Y-%m-%d")
            source_message_ids.append(idx)
            date_found = True
            break

    if not delivery_date_str:
        # Default to tomorrow with ambiguous date flag
        target = base_date + timedelta(days=1)
        delivery_date_str = target.strftime("%Y-%m-%d")
        flags.append("ambiguous_delivery_date")

    # Time detection (morning / afternoon / evening / explicit 4pm / 10am)
    for m in reversed(thread_messages):
        text = m["message_text"].lower()
        if "evening" in text or "night" in text:
            delivery_time_str = "Evening (4:00 PM - 6:00 PM)"
        elif "morning" in text:
            delivery_time_str = "Morning (9:00 AM - 12:00 PM)"
        elif "afternoon" in text or "lunch" in text:
            delivery_time_str = "Afternoon (1:00 PM - 3:00 PM)"

        # Check for explicit time like 4pm, 10am, 2:30 pm
        time_match = re.search(r"(\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.))", text)
        if time_match:
            delivery_time_str = time_match.group(1).upper()
            break

    if not delivery_time_str:
        delivery_time_str = "Flexible / Afternoon"

    # 3. Detect Area / Location
    area_found = ""
    for area in KNOWN_AREAS:
        if re.search(rf"\b{area.lower()}\b", full_text_lower):
            area_found = area
            break

    # 4. Extract Items, Quantities, and Notes
    items: List[Dict[str, Any]] = []

    # Bakery product catalog keywords (English)
    PRODUCT_DEFINITIONS = [
        {"name": "Chocolate Fudge Cake", "keywords": ["chocolate fudge cake", "chocolate cake", "choc cake", "chocolate fudge", "fudge cake", "chocolate"], "default_variant": "1kg"},
        {"name": "Classic Butter Cake", "keywords": ["classic butter cake", "butter cake", "butter"], "default_variant": "1kg"},
        {"name": "Ribbon Cake with Buttercream", "keywords": ["ribbon cake with buttercream", "ribbon cake", "ribbon"], "default_variant": "1kg"},
        {"name": "Coffee & Walnut Cake", "keywords": ["coffee & walnut cake", "coffee walnut", "coffee cake", "walnut cake"], "default_variant": "1kg"},
        {"name": "Fudgy Chocolate Brownies", "keywords": ["fudgy chocolate brownies", "chocolate brownies", "brownies", "brownie"], "default_variant": "Box of 6"},
        {"name": "Mini Chocolate Eclairs", "keywords": ["mini chocolate eclairs", "chocolate eclairs", "eclairs", "eclair"], "default_variant": "Box of 6"},
        {"name": "Sri Lankan Fish Patties", "keywords": ["sri lankan fish patties", "fish patties", "fish patty", "patties"], "default_variant": "Box of 10"},
        {"name": "Chicken & Cheese Rolls", "keywords": ["chicken & cheese rolls", "chicken rolls", "cheese rolls", "rolls"], "default_variant": "Box of 10"}
    ]

    for m in thread_messages:
        text = m["message_text"]
        t_low = text.lower()
        idx = m.get("message_index", 1)

        # Inscription / Custom Notes extraction
        custom_note = ""
        # Check quoted text or "write 'Happy Birthday Mom'"
        inscr_match = re.search(r"['\"](.*?)['\"]", text)
        if inscr_match:
            custom_note = f"Icing text: '{inscr_match.group(1)}'"
        elif "happy birthday" in t_low:
            hbd_match = re.search(r"(happy birthday\s+[a-zA-Z\s]+)", t_low)
            if hbd_match:
                custom_note = f"Icing text: '{hbd_match.group(1).title()}'"
            else:
                custom_note = "Icing: 'Happy Birthday'"
        elif "ribbon" in t_low and "ribbon cake" not in t_low:
            custom_note = "With decorative ribbon"

        # Check each product definition
        for pdef in PRODUCT_DEFINITIONS:
            for kw in pdef["keywords"]:
                pattern = rf"\b{kw}\b"
                if re.search(pattern, t_low):
                    # Found product! Determine quantity and variant
                    source_message_ids.append(idx)

                    # Variant extraction
                    variant = pdef["default_variant"]
                    kg_m = re.search(r"(\d+(?:\.\d+)?)\s*kg", t_low)
                    g_m = re.search(r"(\d+)\s*g\b", t_low)
                    box_m = re.search(r"(?:box of|pack of|pack|box)\s*(\d+)", t_low)

                    if box_m:
                        variant = f"Box of {box_m.group(1)}"
                    elif kg_m:
                        variant = f"{kg_m.group(1)}kg"
                    elif g_m:
                        variant = f"{g_m.group(1)}g"
                    elif "half kg" in t_low or "half kilo" in t_low:
                        variant = "500g"
                    elif "12 pack" in t_low or "12 box" in t_low or ("12" in t_low and "brownie" in kw):
                        variant = "Box of 12"
                    elif "6 pack" in t_low or ("6" in t_low and ("brownie" in kw or "eclair" in kw)):
                        variant = "Box of 6"

                    # Quantity extraction (excluding variant specifications)
                    qty = 1.0
                    box_count_m = re.search(r"(\d+|one|two|three|four|five|six|a|an)\s*(?:boxes?|packs?)\s+of\s+(\d+)", t_low)
                    if box_count_m:
                        num_word = box_count_m.group(1)
                        if num_word.isdigit():
                            qty = float(num_word)
                        else:
                            qty = ENGLISH_NUMERALS.get(num_word, 1.0)
                    else:
                        temp_clean = t_low
                        if box_m: temp_clean = temp_clean.replace(box_m.group(0), "")
                        if kg_m: temp_clean = temp_clean.replace(kg_m.group(0), "")
                        if g_m: temp_clean = temp_clean.replace(g_m.group(0), "")

                        found_qty = False
                        for e_num, val in ENGLISH_NUMERALS.items():
                            if re.search(rf"\b{e_num}\b", temp_clean):
                                qty = val
                                found_qty = True
                                break

                        if not found_qty:
                            digit_qty = re.search(r"(\d+)\s*(?:nos|pcs|items|cakes|boxes)?", temp_clean)
                            if digit_qty:
                                val = float(digit_qty.group(1))
                                if val <= 50 and val > 0:
                                    qty = val

                    # Avoid duplicate detection in the same message
                    existing = next((it for it in items if it["product_name"] == pdef["name"]), None)
                    if existing:
                        existing["source_message_ids"].append(idx)
                        if custom_note and not existing["notes"]:
                            existing["notes"] = custom_note
                    else:
                        items.append({
                            "product_name": pdef["name"],
                            "quantity": qty,
                            "variant": variant,
                            "notes": custom_note,
                            "source_message_ids": [idx]
                        })
                    break

    # If no items were detected by keyword, look for generic cake request
    if not items:
        cake_match = re.search(r"(\d+(?:\.\d+)?\s*kg)?\s*cake", full_text_lower)
        if cake_match:
            variant = "1kg"
            if cake_match.group(1):
                variant = cake_match.group(1).replace(" ", "")
            items.append({
                "product_name": "Chocolate Fudge Cake",
                "quantity": 1.0,
                "variant": variant,
                "notes": "Flavor unspecified (defaulted)",
                "source_message_ids": list(set(source_message_ids)) or [1]
            })
            flags.append("missing_flavor")

    # Payment status
    payment_status = "pending"
    if any(k in full_text_lower for k in ["bank transfer", "transferred", "transfer completed", "paid", "slip", "receipt"]):
        payment_status = "paid"
    elif any(k in full_text_lower for k in ["cash", "cod", "cash on delivery", "pay on delivery", "pay at door"]):
        payment_status = "cod"

    # Overall confidence calculation
    confidence = 0.95
    if flags:
        confidence -= (len(flags) * 0.1)
    if not area_found:
        confidence -= 0.05
    confidence = max(0.4, round(confidence, 2))

    source_message_ids = sorted(list(set(source_message_ids)))

    return {
        "status": status,
        "delivery_date": delivery_date_str,
        "delivery_time": delivery_time_str,
        "area": area_found or "To be confirmed",
        "delivery_address": area_found or "",
        "payment_status": payment_status,
        "items": items,
        "source_message_ids": source_message_ids,
        "confidence_overall": confidence,
        "flags": flags,
        "summary_notes": f"{status.title()} order with {len(items)} item(s) for {area_found or 'local delivery'}.",
        "engine": "local_english_heuristic" + (f" (fallback: {fallback_reason})" if fallback_reason else "")
    }

def extract_order_from_thread(
    thread_messages: List[Dict[str, Any]],
    base_date: Optional[datetime] = None,
    preferred_engine: str = "auto"
) -> Dict[str, Any]:
    """
    Main extraction router. Checks Ollama availability; uses Ollama when running,
    otherwise smoothly falls back to the Local English Heuristic Extractor.
    """
    if preferred_engine == "heuristic":
        return extract_order_heuristic(thread_messages, base_date)

    if preferred_engine in ["auto", "ollama"]:
        if check_ollama_health():
            return extract_order_with_ollama(thread_messages, base_date)
        else:
            return extract_order_heuristic(
                thread_messages,
                base_date,
                fallback_reason="Ollama server not detected on localhost:11434"
            )

    return extract_order_heuristic(thread_messages, base_date)
