from datetime import datetime, timedelta
import re
from typing import List, Dict, Any, Optional

def parse_rough_timestamp(ts_str: str) -> Optional[datetime]:
    """Tries parsing various WhatsApp timestamp formats."""
    # Strip any trailing/leading spaces or punctuation
    clean_ts = ts_str.strip().replace(",", "")
    formats = [
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y %I:%M %p",
        "%d/%m/%y %H:%M",
        "%d/%m/%y %I:%M %p",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%y %H:%M:%S",
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%y %I:%M %p",
        "%m/%d/%Y %H:%M",
        "%m/%d/%y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(clean_ts, fmt)
        except ValueError:
            pass
    return None

def group_messages_into_threads(
    messages: List[Dict[str, Any]],
    inactivity_hours: float = 48.0,
    seller_name_hint: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Groups WhatsApp messages per customer identity and breaks conversation
    threads whenever there is an inactivity gap exceeding inactivity_hours (~48h).
    """
    if not messages:
        return []

    # Identify customers (excluding seller)
    customer_messages: List[Dict[str, Any]] = []
    seller_names = set()
    if seller_name_hint:
        seller_names.add(seller_name_hint.lower())

    # First pass: determine customer identity for the chat
    all_senders = list(dict.fromkeys(m["sender"] for m in messages))
    customer_candidate = None
    for s in all_senders:
        if seller_name_hint and seller_name_hint.lower() in s.lower():
            continue
        # Usually the other party is the customer
        customer_candidate = s
        break

    if not customer_candidate and all_senders:
        customer_candidate = all_senders[0]

    # Partition into temporal threads
    threads: List[Dict[str, Any]] = []
    current_thread_msgs: List[Dict[str, Any]] = []
    last_dt: Optional[datetime] = None

    for msg in messages:
        dt = parse_rough_timestamp(msg["timestamp_str"])

        # Check for gap
        gap_exceeded = False
        if dt and last_dt:
            if (dt - last_dt) > timedelta(hours=inactivity_hours):
                gap_exceeded = True

        if gap_exceeded and current_thread_msgs:
            threads.append(_build_thread_dict(current_thread_msgs, customer_candidate))
            current_thread_msgs = []

        current_thread_msgs.append(msg)
        if dt:
            last_dt = dt

    if current_thread_msgs:
        threads.append(_build_thread_dict(current_thread_msgs, customer_candidate))

    return threads

def _build_thread_dict(msgs: List[Dict[str, Any]], default_customer: Optional[str]) -> Dict[str, Any]:
    # Extract phone if any message or sender has it
    phone = None
    customer_name = default_customer

    for m in msgs:
        if m.get("phone"):
            phone = m["phone"]
        if m.get("is_customer") and not customer_name:
            customer_name = m["sender"]

    start_time = msgs[0]["timestamp_str"] if msgs else ""
    end_time = msgs[-1]["timestamp_str"] if msgs else ""

    # Build plain text representation
    raw_lines = []
    for m in msgs:
        raw_lines.append(f"[{m['timestamp_str']}] {m['sender']}: {m['message_text']}")

    return {
        "customer_name": customer_name or "Unknown Customer",
        "customer_phone": phone or "",
        "start_time": start_time,
        "end_time": end_time,
        "message_count": len(msgs),
        "messages": msgs,
        "raw_text": "\n".join(raw_lines)
    }
