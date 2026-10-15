import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from backend.config import DB_PATH, CURRENCY, SELLER_DEFAULT_NAME, SELLER_DEFAULT_PHONE

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Catalogs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS catalogs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        variant TEXT NOT NULL,
        price REAL NOT NULL,
        unit TEXT DEFAULT 'unit',
        aliases TEXT DEFAULT '[]',
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # WhatsApp Chat exports tracking
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
        total_messages INTEGER DEFAULT 0,
        total_threads INTEGER DEFAULT 0
    )
    """)

    # Grouped Threads (one thread per customer per ~48h conversation)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS threads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        upload_id INTEGER,
        customer_name TEXT,
        customer_phone TEXT,
        start_time TEXT,
        end_time TEXT,
        message_count INTEGER DEFAULT 0,
        raw_text TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (upload_id) REFERENCES chat_uploads(id) ON DELETE CASCADE
    )
    """)

    # Parsed Messages
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id INTEGER NOT NULL,
        sender TEXT NOT NULL,
        is_customer INTEGER DEFAULT 1,
        timestamp TEXT,
        message_text TEXT NOT NULL,
        message_index INTEGER NOT NULL,
        FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
    )
    """)

    # Extracted Orders
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id INTEGER NOT NULL,
        customer_name TEXT,
        customer_phone TEXT,
        delivery_date TEXT,
        delivery_time TEXT,
        area TEXT,
        delivery_address TEXT,
        status TEXT DEFAULT 'new', -- 'new', 'changed', 'cancelled', 'confirmed', 'completed'
        payment_status TEXT DEFAULT 'pending', -- 'pending', 'paid', 'cod'
        total_amount REAL DEFAULT 0.0,
        confidence_score REAL DEFAULT 1.0,
        flags TEXT DEFAULT '[]', -- JSON array of warning flags
        source_message_ids TEXT DEFAULT '[]', -- JSON array of message IDs
        extracted_json TEXT, -- Raw LLM JSON
        is_user_corrected INTEGER DEFAULT 0,
        user_notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
    )
    """)

    # Order Line Items
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        catalog_id INTEGER,
        product_name TEXT NOT NULL,
        quantity REAL DEFAULT 1.0,
        variant TEXT DEFAULT '',
        unit_price REAL DEFAULT 0.0,
        total_price REAL DEFAULT 0.0,
        notes TEXT DEFAULT '',
        source_message_ids TEXT DEFAULT '[]',
        confidence REAL DEFAULT 1.0,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY (catalog_id) REFERENCES catalogs(id) ON DELETE SET NULL
    )
    """)

    # User Corrections (Gold Dataset for LoRA & Few-Shot Dynamic Prompting)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS corrections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        thread_id INTEGER NOT NULL,
        raw_chat_prompt TEXT NOT NULL,
        original_extracted_json TEXT NOT NULL,
        corrected_json TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
    )
    """)

    # Settings Key-Value Store
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    conn.commit()
    seed_default_catalog(conn)
    seed_default_settings(conn)
    conn.close()

def seed_default_settings(conn: sqlite3.Connection):
    cursor = conn.cursor()
    defaults = {
        "seller_name": SELLER_DEFAULT_NAME,
        "seller_phone": SELLER_DEFAULT_PHONE,
        "currency": CURRENCY,
        "ollama_url": "http://127.0.0.1:11434",
        "ollama_model": "qwen3:8b",
        "use_local_fallback": "true"
    }
    for k, v in defaults.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
    conn.commit()

def seed_default_catalog(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM catalogs")
    count = cursor.fetchone()[0]
    if count > 0:
        return

    default_catalog = [
        # Cakes
        ("Chocolate Fudge Cake", "Cakes", "1kg", 3800.0, "kg", ["chocolate cake", "choc cake", "chocolate fudge", "choc fudge", "choc", "chocolate"]),
        ("Chocolate Fudge Cake", "Cakes", "500g", 2200.0, "kg", ["500g chocolate cake", "half kg chocolate", "half kg choc", "small chocolate cake"]),
        ("Chocolate Fudge Cake", "Cakes", "1.5kg", 5500.0, "kg", ["1.5kg chocolate cake", "1.5 kg chocolate", "1.5kg choc cake"]),
        ("Chocolate Fudge Cake", "Cakes", "2kg", 7200.0, "kg", ["2kg chocolate cake", "2 kg chocolate", "large chocolate cake"]),
        ("Classic Butter Cake", "Cakes", "1kg", 2800.0, "kg", ["butter cake", "classic butter", "butter"]),
        ("Classic Butter Cake", "Cakes", "500g", 1600.0, "kg", ["500g butter cake", "half kg butter"]),
        ("Classic Butter Cake", "Cakes", "1.5kg", 4000.0, "kg", ["1.5kg butter cake"]),
        ("Ribbon Cake with Buttercream", "Cakes", "1kg", 3200.0, "kg", ["ribbon cake", "birthday ribbon", "ribbon"]),
        ("Ribbon Cake with Buttercream", "Cakes", "1.5kg", 4600.0, "kg", ["1.5kg ribbon cake"]),
        ("Coffee & Walnut Cake", "Cakes", "1kg", 4200.0, "kg", ["coffee cake", "coffee walnut", "walnut cake"]),
        # Brownies & Desserts
        ("Fudgy Chocolate Brownies", "Desserts", "Box of 6", 2400.0, "box", ["brownies 6", "brownie 6", "6 brownies", "box of 6 brownies", "fudge brownies"]),
        ("Fudgy Chocolate Brownies", "Desserts", "Box of 12", 4500.0, "box", ["brownies 12", "brownie 12", "12 brownies", "box of 12 brownies"]),
        ("Mini Chocolate Eclairs", "Desserts", "Box of 6", 1800.0, "box", ["eclairs 6", "6 eclairs", "eclair 6", "box of 6 eclairs"]),
        ("Mini Chocolate Eclairs", "Desserts", "Box of 12", 3400.0, "box", ["eclairs 12", "12 eclairs", "box of 12 eclairs"]),
        # Short-eats & Savories
        ("Sri Lankan Fish Patties", "Savories", "Box of 10", 1500.0, "box", ["fish patties", "patties 10", "10 patties", "fish patty", "box of 10 patties"]),
        ("Sri Lankan Fish Patties", "Savories", "Box of 20", 2900.0, "box", ["patties 20", "20 patties", "box of 20 patties", "20 fish patties"]),
        ("Chicken & Cheese Rolls", "Savories", "Box of 10", 1800.0, "box", ["chicken rolls", "rolls 10", "10 rolls", "cheese rolls", "box of 10 rolls"]),
        ("Chicken & Cheese Rolls", "Savories", "Box of 20", 3500.0, "box", ["rolls 20", "20 rolls", "box of 20 rolls", "20 chicken rolls"])
    ]

    for name, cat, variant, price, unit, aliases in default_catalog:
        cursor.execute(
            "INSERT INTO catalogs (name, category, variant, price, unit, aliases) VALUES (?, ?, ?, ?, ?, ?)",
            (name, cat, variant, price, unit, json.dumps(aliases, ensure_ascii=False))
        )
    conn.commit()

def get_all_catalog_items() -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM catalogs WHERE is_active = 1 ORDER BY category, name, price")
    rows = cursor.fetchall()
    result = []
    for r in rows:
        item = dict(r)
        item["aliases"] = json.loads(item["aliases"]) if item["aliases"] else []
        result.append(item)
    conn.close()
    return result

def get_setting(key: str, default: str = "") -> str:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key: str, value: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()
