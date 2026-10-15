import re
from datetime import datetime
from typing import List, Dict, Any, Optional

# Match WhatsApp header patterns across Android and iOS
# Pattern 1 (Android): "15/10/2026, 14:30 - Sender: Message" or "10/15/26, 2:30 pm - Sender: Message"
# Pattern 2 (iOS): "[15/10/2026, 14:30:15] Sender: Message" or "[10/15/26, 2:30:15 PM] Sender: Message"
REGEX_ANDROID = re.compile(
    r"^(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[apAP][mM])?)\s*[-–]\s*(.*?):\s*(.*)$"
)
REGEX_IOS = re.compile(
    r"^\[(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[apAP][mM])?)\]\s*(.*?):\s*(.*)$"
)
# System notification patterns to ignore
SYSTEM_MESSAGE_PATTERNS = [
    re.compile(r"messages and calls are end-to-end encrypted", re.IGNORECASE),
    re.compile(r"<media omitted>", re.IGNORECASE),
    re.compile(r"image omitted", re.IGNORECASE),
    re.compile(r"audio omitted", re.IGNORECASE),
    re.compile(r"video omitted", re.IGNORECASE),
    re.compile(r"sticker omitted", re.IGNORECASE),
    re.compile(r"this message was deleted", re.IGNORECASE),
    re.compile(r"you deleted this message", re.IGNORECASE),
    re.compile(r"missed voice call", re.IGNORECASE),
    re.compile(r"missed video call", re.IGNORECASE)
]

# Sri Lankan phone number detection pattern
PHONE_REGEX = re.compile(r"(?:\+94|0094|0)?(?:7[01245678]\d{7}|11\d{7}|81\d{7}|31\d{7})")

def clean_whatsapp_text(text: str) -> str:
    """Removes invisible WhatsApp unicode markers and normalizes spaces."""
    return (
        text.replace("\u200e", "")
            .replace("\u202f", " ")
            .replace("\xa0", " ")
            .replace("\u200b", "")
            .replace("\ufeff", "")
    )

def normalize_phone(phone_str: str) -> Optional[str]:
    """Normalizes Sri Lankan phone numbers to standard +94 7X XXX XXXX format."""
    digits = re.sub(r"[^\d+]", "", phone_str)
    if digits.startswith("+94"):
        raw = digits[3:]
    elif digits.startswith("0094"):
        raw = digits[4:]
    elif digits.startswith("0"):
        raw = digits[1:]
    else:
        raw = digits

    if len(raw) == 9 and raw.startswith("7"):
        return f"+94 {raw[:2]} {raw[2:5]} {raw[5:]}"
    elif len(raw) == 9:
        return f"+94 {raw[:2]} {raw[2:5]} {raw[5:]}"
    elif len(digits) >= 9:
        return digits
    return None

def extract_phone_from_text(text: str) -> Optional[str]:
    """Finds any phone number mentioned within a text string."""
    clean = text.replace(" ", "").replace("-", "")
    match = PHONE_REGEX.search(clean)
    if match:
        return normalize_phone(match.group(0))
    return None

def parse_whatsapp_raw(raw_content: str, seller_name_hint: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Deterministically parses a WhatsApp chat export .txt file.
    Returns a list of structured message objects with normalized timestamps,
    sender identifiers, and multiline body preservation.
    """
    cleaned_content = clean_whatsapp_text(raw_content)
    lines = cleaned_content.splitlines()

    parsed_messages: List[Dict[str, Any]] = []
    current_msg: Optional[Dict[str, Any]] = None
    msg_counter = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        match = REGEX_ANDROID.match(stripped) or REGEX_IOS.match(stripped)

        if match:
            date_str, time_str, sender, content = match.groups()
            sender = sender.strip()
            content = content.strip()

            # Check if this is a system message
            is_system = any(p.search(content) for p in SYSTEM_MESSAGE_PATTERNS) or any(p.search(sender) for p in SYSTEM_MESSAGE_PATTERNS)
            if is_system:
                continue

            # Save previous message
            if current_msg:
                parsed_messages.append(current_msg)

            msg_counter += 1
            timestamp_str = f"{date_str} {time_str}"
            extracted_phone = normalize_phone(sender) or extract_phone_from_text(content)

            current_msg = {
                "message_index": msg_counter,
                "timestamp_str": timestamp_str,
                "sender": sender,
                "phone": extracted_phone,
                "message_text": content,
                "is_seller": False
            }
        else:
            # Continuation line of the previous message
            if current_msg:
                current_msg["message_text"] += "\n" + stripped

    if current_msg:
        parsed_messages.append(current_msg)

    # Determine seller vs customer
    # If seller_name_hint is given, mark matches. Otherwise, determine by frequency or presence.
    senders = {}
    for m in parsed_messages:
        s = m["sender"]
        senders[s] = senders.get(s, 0) + 1

    for m in parsed_messages:
        if seller_name_hint and (seller_name_hint.lower() in m["sender"].lower()):
            m["is_seller"] = True
            m["is_customer"] = False
        else:
            m["is_customer"] = True

    return parsed_messages
