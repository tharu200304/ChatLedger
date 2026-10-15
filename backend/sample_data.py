import os
from pathlib import Path
from typing import List, Dict

SAMPLE_CHATS_DIR = Path(__file__).resolve().parent.parent / "sample_chats"
SAMPLE_CHATS_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_CHATS = [
    {
        "filename": "01_english_peradeniya_cake.txt",
        "description": "Standard English order with custom icing inscription and Peradeniya delivery",
        "content": """15/10/2026, 14:15 - Kasun Perera (+94 77 234 5678): Hi, I would like to order a 1kg chocolate cake for Sunday evening, delivered to Peradeniya please.
15/10/2026, 14:18 - The Cake Studio: Hello Kasun! Yes, Sunday evening at 5:00 PM is available. Would you like any custom message piped on the cake?
15/10/2026, 14:22 - Kasun Perera (+94 77 234 5678): Yes please, could you write 'Happy Birthday Mom' in chocolate icing? The address is No 45, Station Road, Peradeniya.
15/10/2026, 14:25 - The Cake Studio: Noted! The total is 3,800 LKR. Would you prefer bank transfer or cash on delivery?
15/10/2026, 14:28 - Kasun Perera (+94 77 234 5678): I will pay cash on delivery when you deliver. Thank you so much!"""
    },
    {
        "filename": "02_rescheduled_butter_cake_kandy.txt",
        "description": "Customer changes the delivery date from Saturday to Monday",
        "content": """15/10/2026, 09:30 - Dilani Jayawardena (+94 71 890 1234): Good morning! I need a 1kg butter cake for Saturday afternoon delivered to Kandy.
15/10/2026, 09:35 - The Cake Studio: Good morning Dilani! Your Saturday afternoon slot has been confirmed.
15/10/2026, 16:45 - Dilani Jayawardena (+94 71 890 1234): Hi, there is a slight change of plans, our Saturday event was postponed. Could we please reschedule the cake delivery to Monday morning?
15/10/2026, 16:50 - The Cake Studio: Absolutely Dilani, no problem at all. We will deliver Monday morning at 10:00 AM to Kandy town."""
    },
    {
        "filename": "03_cancelled_brownies_order.txt",
        "description": "Customer cancels their order due to event cancellation",
        "content": """14/10/2026, 11:00 - Nuwan Senanayake (+94 76 543 2109): Hi! Could you deliver a box of 6 brownies to Maharagama tomorrow evening around 4pm?
14/10/2026, 11:15 - The Cake Studio: Hello Nuwan! Yes, we can deliver tomorrow at 4:00 PM to Maharagama junction.
15/10/2026, 08:20 - Nuwan Senanayake (+94 76 543 2109): Hi, I am very sorry, but our family gathering was cancelled today. Could we please cancel the brownie order? Really sorry for the inconvenience.
15/10/2026, 08:25 - The Cake Studio: No problem at all Nuwan, completely understandable. Your order has been cancelled."""
    },
    {
        "filename": "04_catering_savories_katugastota.txt",
        "description": "Large multi-item catering order with fish patties, rolls, and brownies",
        "content": """15/10/2026, 10:05 - Shalini Wickramasinghe (+94 72 345 6789): Good morning! I would like to place a catering order for our office party this Friday morning.
15/10/2026, 10:08 - The Cake Studio: Hello Shalini! Which items would you like to order?
15/10/2026, 10:14 - Shalini Wickramasinghe (+94 72 345 6789): A box of 20 fish patties, a box of 20 chicken rolls, and a box of 12 brownies. Please deliver this Friday at 10:00 AM to our Katugastota branch.
15/10/2026, 10:20 - The Cake Studio: Confirmed! Total amount is: Patties 2,900 + Rolls 3,500 + Brownies 4,500 = 10,900 LKR.
15/10/2026, 10:28 - Shalini Wickramasinghe (+94 72 345 6789): I have completed the online bank transfer and sent the payment receipt slip. Thanks!"""
    },
    {
        "filename": "05_birthday_ribbon_cake_maharagama.txt",
        "description": "Pure English ribbon cake order with custom birthday inscription and Maharagama delivery",
        "content": """15/10/2026, 12:40 - Hiruni Fernando (+94 78 901 2345): Hello! I would like to order a 1.5kg ribbon cake for tomorrow morning, delivery to Maharagama.
15/10/2026, 12:42 - The Cake Studio: Hello Hiruni! Tomorrow morning at 10:30 AM is available. Would you like a custom inscription on the cake?
15/10/2026, 12:45 - Hiruni Fernando (+94 78 901 2345): Could you please pipe 'Happy 5th Birthday Liam' with blue and white ribbon icing?
15/10/2026, 12:48 - The Cake Studio: Sure thing! The total is 4,600 LKR.
15/10/2026, 12:50 - Hiruni Fernando (+94 78 901 2345): Perfect, I will pay cash on delivery. Thank you!"""
    }
]

def create_sample_chat_files():
    """Writes the sample chats to the sample_chats folder."""
    # Clean out any old sample files first
    for old_f in SAMPLE_CHATS_DIR.glob("*.txt"):
        try:
            old_f.unlink()
        except Exception:
            pass

    for item in SAMPLE_CHATS:
        fpath = SAMPLE_CHATS_DIR / item["filename"]
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(item["content"])

create_sample_chat_files()
