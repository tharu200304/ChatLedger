import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from backend.config import BASE_DIR, EXPORTS_DIR, CURRENCY, SELLER_DEFAULT_NAME
from backend.database import (
    init_db, get_db, get_all_catalog_items, get_setting, set_setting
)
from backend.parser import parse_whatsapp_raw
from backend.thread_grouper import group_messages_into_threads
from backend.extractor import (
    extract_order_from_thread, check_ollama_health
)
from backend.catalog import price_order_items
from backend.exporter import (
    export_production_sheet, export_delivery_sheet, export_payment_pending_sheet
)
from backend.lora_dataset import export_lora_dataset
from backend.sample_data import SAMPLE_CHATS

# Initialize database
init_db()

app = FastAPI(title="ChatLedger", description="Turning WhatsApp chaos into tomorrow's order sheet, entirely on her laptop")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Models for request validation
class ItemPayload(BaseModel):
    catalog_id: Optional[int] = None
    product_name: str
    quantity: float
    variant: str = ""
    unit_price: float = 0.0
    total_price: float = 0.0
    notes: str = ""
    source_message_ids: List[int] = []

class OrderUpdatePayload(BaseModel):
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    delivery_date: Optional[str] = None
    delivery_time: Optional[str] = None
    area: Optional[str] = None
    delivery_address: Optional[str] = None
    status: Optional[str] = None
    payment_status: Optional[str] = None
    user_notes: Optional[str] = None
    items: Optional[List[ItemPayload]] = None

class CatalogItemPayload(BaseModel):
    name: str
    category: str
    variant: str
    price: float
    unit: str = "unit"
    aliases: List[str] = []

class SettingsPayload(BaseModel):
    seller_name: Optional[str] = None
    seller_phone: Optional[str] = None
    ollama_url: Optional[str] = None
    ollama_model: Optional[str] = None
    currency: Optional[str] = None

# Helper to fetch hydrated order
def get_hydrated_order(order_id: int, conn=None) -> Optional[Dict[str, Any]]:
    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True

    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.*, t.raw_text as thread_raw_text, t.start_time as thread_start_time,
               t.end_time as thread_end_time, t.message_count as thread_message_count
        FROM orders o
        JOIN threads t ON o.thread_id = t.id
        WHERE o.id = ?
    """, (order_id,))
    row = cursor.fetchone()
    if not row:
        if should_close: conn.close()
        return None

    order = dict(row)
    order["flags"] = json.loads(order["flags"]) if order["flags"] else []
    order["source_message_ids"] = json.loads(order["source_message_ids"]) if order["source_message_ids"] else []

    # Get items
    cursor.execute("""
        SELECT * FROM order_items WHERE order_id = ?
    """, (order_id,))
    items_rows = cursor.fetchall()
    items = []
    for ir in items_rows:
        it = dict(ir)
        it["source_message_ids"] = json.loads(it["source_message_ids"]) if it["source_message_ids"] else []
        items.append(it)
    order["items"] = items

    # Get thread messages
    cursor.execute("""
        SELECT * FROM messages WHERE thread_id = ? ORDER BY message_index ASC
    """, (order["thread_id"],))
    msgs_rows = cursor.fetchall()
    order["thread_messages"] = [dict(mr) for mr in msgs_rows]

    if should_close: conn.close()
    return order

# 1. System Health & Connection Status
@app.get("/api/status")
def get_system_status():
    ollama_url = get_setting("ollama_url", "http://127.0.0.1:11434")
    ollama_online = check_ollama_health(ollama_url)
    model = get_setting("ollama_model", "qwen3:8b")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'confirmed'")
    confirmed_orders = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM corrections")
    total_corrections = cursor.fetchone()[0]

    conn.close()

    return {
        "status": "online",
        "app_name": "ChatLedger",
        "version": "1.0.0",
        "ollama_online": ollama_online,
        "ollama_url": ollama_url,
        "active_model": model,
        "local_fallback_ready": True,
        "total_orders": total_orders,
        "confirmed_orders": confirmed_orders,
        "total_corrections": total_corrections,
        "currency": get_setting("currency", CURRENCY),
        "seller_name": get_setting("seller_name", SELLER_DEFAULT_NAME)
    }

# 2. Process WhatsApp Chat Export
def process_chat_content(filename: str, content: str, engine_preference: str = "auto") -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()

    seller_name = get_setting("seller_name", SELLER_DEFAULT_NAME)
    messages = parse_whatsapp_raw(content, seller_name_hint=seller_name)
    threads = group_messages_into_threads(messages, inactivity_hours=48.0, seller_name_hint=seller_name)

    cursor.execute(
        "INSERT INTO chat_uploads (filename, total_messages, total_threads) VALUES (?, ?, ?)",
        (filename, len(messages), len(threads))
    )
    upload_id = cursor.lastrowid
    catalog_items = get_all_catalog_items()

    created_orders = []

    for thread in threads:
        # Insert thread
        cursor.execute("""
            INSERT INTO threads (upload_id, customer_name, customer_phone, start_time, end_time, message_count, raw_text)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            upload_id, thread["customer_name"], thread["customer_phone"],
            thread["start_time"], thread["end_time"], thread["message_count"], thread["raw_text"]
        ))
        thread_id = cursor.lastrowid

        # Insert messages
        for msg in thread["messages"]:
            cursor.execute("""
                INSERT INTO messages (thread_id, sender, is_customer, timestamp, message_text, message_index)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                thread_id, msg["sender"], 1 if msg["is_customer"] else 0,
                msg["timestamp_str"], msg["message_text"], msg["message_index"]
            ))

        # Extract order intent
        extracted = extract_order_from_thread(thread["messages"], preferred_engine=engine_preference)

        # Price items against catalog deterministically
        raw_items = extracted.get("items", [])
        priced_items, total_amount = price_order_items(raw_items, catalog_items)

        # Insert order
        cursor.execute("""
            INSERT INTO orders (
                thread_id, customer_name, customer_phone, delivery_date, delivery_time,
                area, delivery_address, status, payment_status, total_amount,
                confidence_score, flags, source_message_ids, extracted_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            thread_id,
            thread["customer_name"],
            thread["customer_phone"],
            extracted.get("delivery_date", ""),
            extracted.get("delivery_time", "Anytime"),
            extracted.get("area", "Local"),
            extracted.get("delivery_address", ""),
            extracted.get("status", "new"),
            extracted.get("payment_status", "pending"),
            total_amount,
            extracted.get("confidence_overall", 0.9),
            json.dumps(extracted.get("flags", [])),
            json.dumps(extracted.get("source_message_ids", [])),
            json.dumps(extracted, ensure_ascii=False)
        ))
        order_id = cursor.lastrowid

        # Insert order items
        for it in priced_items:
            cursor.execute("""
                INSERT INTO order_items (
                    order_id, catalog_id, product_name, quantity, variant,
                    unit_price, total_price, notes, source_message_ids, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_id, it["catalog_id"], it["product_name"], it["quantity"],
                it["variant"], it["unit_price"], it["total_price"], it["notes"],
                json.dumps(it["source_message_ids"]), it["confidence"]
            ))

        created_orders.append(order_id)

    conn.commit()
    conn.close()

    return {
        "upload_id": upload_id,
        "filename": filename,
        "total_messages": len(messages),
        "total_threads": len(threads),
        "orders_created": len(created_orders),
        "order_ids": created_orders
    }

@app.post("/api/upload-chat")
async def upload_chat_file(file: UploadFile = File(...), engine: str = Form("auto")):
    content_bytes = await file.read()
    content_text = content_bytes.decode("utf-8", errors="replace")
    result = process_chat_content(file.filename, content_text, engine_preference=engine)
    return result

@app.post("/api/load-sample-chats")
def load_sample_chats(engine: str = Query("auto")):
    """Loads all bundled English baking test chats into the database."""
    results = []
    for sc in SAMPLE_CHATS:
        r = process_chat_content(sc["filename"], sc["content"], engine_preference=engine)
        results.append(r)
    return {"message": "Sample chats processed successfully", "results": results}

# 3. Orders API
@app.get("/api/orders")
def list_orders(
    date: Optional[str] = None,
    status: Optional[str] = None,
    area: Optional[str] = None,
    search: Optional[str] = None
):
    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT id FROM orders WHERE 1=1"
    params = []

    if date:
        query += " AND delivery_date = ?"
        params.append(date)
    if status and status != "all":
        query += " AND status = ?"
        params.append(status)
    if area and area != "all":
        query += " AND area LIKE ?"
        params.append(f"%{area}%")
    if search:
        query += " AND (customer_name LIKE ? OR customer_phone LIKE ? OR area LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s])

    query += " ORDER BY delivery_date ASC, id DESC"
    cursor.execute(query, params)
    order_ids = [r["id"] for r in cursor.fetchall()]

    orders = [get_hydrated_order(oid, conn) for oid in order_ids]
    conn.close()
    return orders

@app.get("/api/orders/{order_id}")
def get_order_detail(order_id: int):
    order = get_hydrated_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.put("/api/orders/{order_id}")
def update_order(order_id: int, payload: OrderUpdatePayload):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Order not found")

    updates = []
    params = []

    if payload.customer_name is not None:
        updates.append("customer_name = ?")
        params.append(payload.customer_name)
    if payload.customer_phone is not None:
        updates.append("customer_phone = ?")
        params.append(payload.customer_phone)
    if payload.delivery_date is not None:
        updates.append("delivery_date = ?")
        params.append(payload.delivery_date)
    if payload.delivery_time is not None:
        updates.append("delivery_time = ?")
        params.append(payload.delivery_time)
    if payload.area is not None:
        updates.append("area = ?")
        params.append(payload.area)
    if payload.delivery_address is not None:
        updates.append("delivery_address = ?")
        params.append(payload.delivery_address)
    if payload.status is not None:
        updates.append("status = ?")
        params.append(payload.status)
    if payload.payment_status is not None:
        updates.append("payment_status = ?")
        params.append(payload.payment_status)
    if payload.user_notes is not None:
        updates.append("user_notes = ?")
        params.append(payload.user_notes)

    # If items are updated
    if payload.items is not None:
        cursor.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
        total_amount = 0.0
        catalog_items = get_all_catalog_items()

        for it in payload.items:
            unit_p = it.unit_price
            if unit_p == 0.0 and it.catalog_id:
                cat_match = next((c for c in catalog_items if c["id"] == it.catalog_id), None)
                if cat_match:
                    unit_p = cat_match["price"]

            item_total = unit_p * it.quantity
            total_amount += item_total

            cursor.execute("""
                INSERT INTO order_items (
                    order_id, catalog_id, product_name, quantity, variant,
                    unit_price, total_price, notes, source_message_ids, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_id, it.catalog_id, it.product_name, it.quantity,
                it.variant, unit_p, item_total, it.notes,
                json.dumps(it.source_message_ids), 1.0
            ))

        updates.append("total_amount = ?")
        params.append(total_amount)

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(order_id)

    cursor.execute(f"UPDATE orders SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()

    return get_hydrated_order(order_id)

@app.post("/api/orders/{order_id}/confirm")
def confirm_order_and_save_correction(order_id: int):
    """
    Confirms an order, marking it confirmed. If the user edited any fields,
    saves the correction as a few-shot example and LoRA fine-tuning training row!
    """
    conn = get_db()
    cursor = conn.cursor()

    order = get_hydrated_order(order_id, conn)
    if not order:
        conn.close()
        raise HTTPException(status_code=404, detail="Order not found")

    # Mark as confirmed
    cursor.execute("UPDATE orders SET status = 'confirmed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (order_id,))

    # Save to corrections table for few-shot dynamic context & future LoRA training
    cleaned_items = []
    for it in order["items"]:
        cleaned_items.append({
            "product_name": it["product_name"],
            "quantity": it["quantity"],
            "variant": it["variant"],
            "notes": it["notes"],
            "source_message_ids": it["source_message_ids"]
        })

    corrected_record = {
        "status": "confirmed",
        "delivery_date": order["delivery_date"],
        "delivery_time": order["delivery_time"],
        "area": order["area"],
        "delivery_address": order["delivery_address"],
        "payment_status": order["payment_status"],
        "items": cleaned_items,
        "source_message_ids": order["source_message_ids"]
    }

    cursor.execute("""
        INSERT INTO corrections (order_id, thread_id, raw_chat_prompt, original_extracted_json, corrected_json)
        VALUES (?, ?, ?, ?, ?)
    """, (
        order_id,
        order["thread_id"],
        order.get("thread_raw_text", ""),
        order.get("extracted_json") or "{}",
        json.dumps(corrected_record, ensure_ascii=False)
    ))

    conn.commit()
    conn.close()

    return {"status": "success", "message": "Order confirmed and saved to continuous learning dataset."}

@app.delete("/api/orders/{order_id}")
def delete_order(order_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Order deleted"}

# 4. Catalog API
@app.get("/api/catalog")
def get_catalog():
    return get_all_catalog_items()

@app.post("/api/catalog")
def add_catalog_item(payload: CatalogItemPayload):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO catalogs (name, category, variant, price, unit, aliases)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        payload.name, payload.category, payload.variant, payload.price,
        payload.unit, json.dumps(payload.aliases, ensure_ascii=False)
    ))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return {"id": new_id, **payload.dict()}

@app.put("/api/catalog/{item_id}")
def update_catalog_item(item_id: int, payload: CatalogItemPayload):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE catalogs
        SET name = ?, category = ?, variant = ?, price = ?, unit = ?, aliases = ?
        WHERE id = ?
    """, (
        payload.name, payload.category, payload.variant, payload.price,
        payload.unit, json.dumps(payload.aliases, ensure_ascii=False), item_id
    ))
    conn.commit()
    conn.close()
    return {"id": item_id, **payload.dict()}

@app.delete("/api/catalog/{item_id}")
def delete_catalog_item(item_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE catalogs SET is_active = 0 WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

# 5. Excel Exports API (openpyxl)
@app.get("/api/export/production")
def download_production_sheet(date: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()
    if date:
        cursor.execute("SELECT id FROM orders WHERE delivery_date = ?", (date,))
    else:
        cursor.execute("SELECT id FROM orders")
    order_ids = [r["id"] for r in cursor.fetchall()]
    orders = [get_hydrated_order(oid, conn) for oid in order_ids]
    conn.close()

    seller_name = get_setting("seller_name", SELLER_DEFAULT_NAME)
    filepath = export_production_sheet(orders, target_date=date, seller_name=seller_name)
    return FileResponse(
        filepath,
        filename=os.path.basename(filepath),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.get("/api/export/delivery")
def download_delivery_sheet(date: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()
    if date:
        cursor.execute("SELECT id FROM orders WHERE delivery_date = ?", (date,))
    else:
        cursor.execute("SELECT id FROM orders")
    order_ids = [r["id"] for r in cursor.fetchall()]
    orders = [get_hydrated_order(oid, conn) for oid in order_ids]
    conn.close()

    seller_name = get_setting("seller_name", SELLER_DEFAULT_NAME)
    filepath = export_delivery_sheet(orders, target_date=date, seller_name=seller_name)
    return FileResponse(
        filepath,
        filename=os.path.basename(filepath),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.get("/api/export/payment-pending")
def download_payment_pending_sheet():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM orders WHERE payment_status != 'paid'")
    order_ids = [r["id"] for r in cursor.fetchall()]
    orders = [get_hydrated_order(oid, conn) for oid in order_ids]
    conn.close()

    seller_name = get_setting("seller_name", SELLER_DEFAULT_NAME)
    filepath = export_payment_pending_sheet(orders, seller_name=seller_name)
    return FileResponse(
        filepath,
        filename=os.path.basename(filepath),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# 6. LoRA Fine-tuning Dataset Export
@app.get("/api/export/lora")
def download_lora_dataset(format: str = Query("alpaca")):
    result = export_lora_dataset(format_type=format)
    return FileResponse(
        result["filepath"],
        filename=result["filename"],
        media_type="application/x-jsonlines"
    )

# 7. Settings API
@app.get("/api/settings")
def get_all_settings():
    return {
        "seller_name": get_setting("seller_name", SELLER_DEFAULT_NAME),
        "seller_phone": get_setting("seller_phone", "+94 77 123 4567"),
        "currency": get_setting("currency", CURRENCY),
        "ollama_url": get_setting("ollama_url", "http://127.0.0.1:11434"),
        "ollama_model": get_setting("ollama_model", "qwen3:8b")
    }

@app.post("/api/settings")
def save_settings(payload: SettingsPayload):
    if payload.seller_name is not None: set_setting("seller_name", payload.seller_name)
    if payload.seller_phone is not None: set_setting("seller_phone", payload.seller_phone)
    if payload.currency is not None: set_setting("currency", payload.currency)
    if payload.ollama_url is not None: set_setting("ollama_url", payload.ollama_url)
    if payload.ollama_model is not None: set_setting("ollama_model", payload.ollama_model)
    return get_all_settings()

# Mount frontend static files
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
(FRONTEND_DIR / "css").mkdir(parents=True, exist_ok=True)
(FRONTEND_DIR / "js").mkdir(parents=True, exist_ok=True)

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
