import os
import json
import unittest
from datetime import datetime
from pathlib import Path

from backend.parser import parse_whatsapp_raw, normalize_phone, extract_phone_from_text
from backend.thread_grouper import group_messages_into_threads
from backend.extractor import extract_order_heuristic
from backend.catalog import match_catalog_item, price_order_items
from backend.exporter import export_production_sheet, export_delivery_sheet, export_payment_pending_sheet
from backend.lora_dataset import export_lora_dataset
from backend.database import init_db, get_all_catalog_items

class TestChatLedger(unittest.TestCase):

    def setUp(self):
        init_db()
        self.catalog = get_all_catalog_items()

    def test_phone_normalization(self):
        self.assertEqual(normalize_phone("0772345678"), "+94 77 234 5678")
        self.assertEqual(normalize_phone("+94718901234"), "+94 71 890 1234")
        self.assertEqual(normalize_phone("0094765432109"), "+94 76 543 2109")

    def test_whatsapp_parser_android(self):
        sample = """15/10/2026, 14:15 - Kasun Perera (+94 77 234 5678): Hi, I would like to order a 1kg chocolate cake for Sunday evening, delivered to Peradeniya please.
15/10/2026, 14:18 - The Cake Studio: Hello Kasun! Yes, Sunday evening at 5:00 PM is available.
15/10/2026, 14:22 - Kasun Perera (+94 77 234 5678): Please write 'Happy Birthday Mom' in chocolate icing.
Address is No 45, Station Road, Peradeniya."""
        
        parsed = parse_whatsapp_raw(sample, seller_name_hint="The Cake Studio")
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0]["sender"], "Kasun Perera (+94 77 234 5678)")
        self.assertTrue(parsed[1]["is_seller"])
        self.assertFalse(parsed[0]["is_seller"])
        # Multiline preservation
        self.assertIn("No 45, Station Road", parsed[2]["message_text"])

    def test_whatsapp_parser_ios(self):
        sample = """[15/10/2026, 14:15:10] Dilani Jayawardena: Good morning! I need a 1kg butter cake for Saturday afternoon delivered to Kandy.
[15/10/2026, 14:18:22] The Cake Studio: Good morning Dilani! Confirmed."""
        
        parsed = parse_whatsapp_raw(sample, seller_name_hint="The Cake Studio")
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["sender"], "Dilani Jayawardena")

    def test_thread_grouper_48h(self):
        msgs = [
            {"message_index": 1, "timestamp_str": "10/10/2026 10:00", "sender": "Kasun", "is_customer": True, "message_text": "Order 1"},
            {"message_index": 2, "timestamp_str": "10/10/2026 10:05", "sender": "Kasun", "is_customer": True, "message_text": "Thanks"},
            {"message_index": 3, "timestamp_str": "15/10/2026 14:00", "sender": "Kasun", "is_customer": True, "message_text": "Order 2 (after 5 days)"}
        ]
        threads = group_messages_into_threads(msgs, inactivity_hours=48.0)
        self.assertEqual(len(threads), 2)
        self.assertEqual(len(threads[0]["messages"]), 2)
        self.assertEqual(len(threads[1]["messages"]), 1)

    def test_english_extraction_cake_order(self):
        msgs = [
            {"message_index": 1, "message_text": "Hi, I would like to order a 1kg chocolate cake for Sunday evening, delivered to Peradeniya."},
            {"message_index": 2, "message_text": "Please write 'Happy Birthday Mom' in chocolate icing."}
        ]
        base_dt = datetime(2026, 10, 15) # Thursday
        extracted = extract_order_heuristic(msgs, base_date=base_dt)

        self.assertEqual(extracted["status"], "new")
        self.assertEqual(extracted["area"], "Peradeniya")
        self.assertEqual(len(extracted["items"]), 1)
        self.assertEqual(extracted["items"][0]["product_name"], "Chocolate Fudge Cake")
        self.assertEqual(extracted["items"][0]["variant"], "1kg")
        self.assertIn("Happy Birthday Mom", extracted["items"][0]["notes"])
        # Upcoming Sunday from Thursday 15th is Sunday 18th
        self.assertEqual(extracted["delivery_date"], "2026-10-18")

    def test_cancellation_detection(self):
        msgs = [
            {"message_index": 1, "message_text": "Could you deliver a box of 6 brownies to Maharagama tomorrow evening?"},
            {"message_index": 2, "message_text": "I am so sorry, but our family party was cancelled today. Could we please cancel the brownie order?"}
        ]
        extracted = extract_order_heuristic(msgs)
        self.assertEqual(extracted["status"], "cancelled")
        self.assertIn("order_cancelled_by_customer", extracted["flags"])

    def test_rescheduled_date_detection(self):
        msgs = [
            {"message_index": 1, "message_text": "Saturday afternoon I need a 1kg butter cake delivered to Kandy."},
            {"message_index": 2, "message_text": "There is a slight change of plans, the event was postponed. Could we please reschedule the cake delivery to Monday morning?"}
        ]
        extracted = extract_order_heuristic(msgs)
        self.assertEqual(extracted["status"], "changed")
        self.assertIn("order_modified_or_rescheduled", extracted["flags"])

    def test_catalog_matching_and_pricing(self):
        raw_items = [
            {"product_name": "chocolate cake", "variant": "1kg", "quantity": 1, "notes": "", "source_message_ids": [1]},
            {"product_name": "brownies", "variant": "Box of 6", "quantity": 2, "notes": "", "source_message_ids": [2]}
        ]
        priced_items, total = price_order_items(raw_items, self.catalog)
        self.assertEqual(len(priced_items), 2)
        # Choc 1kg: 3800 + Brownies Box of 6 (2400 x 2 = 4800) = 8600
        self.assertEqual(total, 8600.0)

    def test_excel_exports_generation(self):
        sample_order = {
            "id": 101,
            "customer_name": "Kasun Perera",
            "customer_phone": "+94 77 234 5678",
            "delivery_date": "2026-10-18",
            "delivery_time": "Evening 5pm",
            "area": "Peradeniya",
            "delivery_address": "No 45, Station Road, Peradeniya",
            "status": "new",
            "payment_status": "cod",
            "total_amount": 3800.0,
            "user_notes": "Icing: Happy Birthday Mom",
            "items": [
                {
                    "product_name": "Chocolate Fudge Cake",
                    "variant": "1kg",
                    "quantity": 1,
                    "unit_price": 3800.0,
                    "total_price": 3800.0,
                    "notes": "Happy Birthday Mom"
                }
            ]
        }

        p_sheet = export_production_sheet([sample_order], target_date="2026-10-18")
        d_sheet = export_delivery_sheet([sample_order], target_date="2026-10-18")
        pay_sheet = export_payment_pending_sheet([sample_order])

        self.assertTrue(Path(p_sheet).exists())
        self.assertTrue(Path(d_sheet).exists())
        self.assertTrue(Path(pay_sheet).exists())

if __name__ == "__main__":
    unittest.main()
