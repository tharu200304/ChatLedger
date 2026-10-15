*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 2: Side Hustle](https://dev.to/challenges/hacktoberfest-week2-2026-10-12)*

## What I Built

**ChatLedger** is a local-first, privacy-focused open-source AI desktop tool designed for home food and craft side-hustlers (cake bakers, caterers, handmade craft makers) who take 10 to 40 orders a day over WhatsApp.

### The Problem
Home food sellers face evening WhatsApp chaos: customers chat casually across multiple days, requesting custom flavor combinations, changing delivery dates at the last minute, and sending bank transfer slips.
1. **The 60-Minute Evening Copy-Paste Routine**: Every night, sellers spend an hour scrolling through dozens of long chat threads, manually transcribing details onto paper notebooks or spreadsheets.
2. **Costly Mistakes**: Last-minute date shifts and cancellations get lost in chat threads. A missed date or baking a cancelled order wastes $25–$50 in ingredients and hours of labor.
3. **Data Privacy**: Customers share home addresses, mobile numbers, and personal celebration notes. Uploading raw customer chats to third-party cloud APIs poses significant privacy risks.

### Who Would Pay for It
A home baker or caterer making $400–$1,500/month would happily pay $10–$15/month (or a one-time license) because ChatLedger gives them back an hour every evening and prevents expensive baking and delivery mistakes.

### What ChatLedger Does
- **WhatsApp Chat Parser**: Ingests exported `.txt` chat files from both Android and iOS devices.
- **48-Hour Inactivity Thread Grouper**: Intelligently separates new orders from re-orders placed weeks ago.
- **Side-by-Side Review Screen**: Displays the raw WhatsApp conversation alongside the extracted order draft. Clicking `🔍` next to any item immediately highlights the exact source message in the chat stream.
- **Deterministic Pricing & Arithmetic**: Pricing, subtotals, delivery fees, and balance calculations are performed strictly in Python code against a customizable catalog—never hallucinated by an LLM.
- **Multi-Tab Excel Export**: Generates tomorrow's **Kitchen Production Sheet** (aggregated quantities and custom inscriptions), **Delivery Run Sheet** (grouped by locality), and **Pending Balance Sheet** with one click.
- **Continuous Learning**: Confirmed edits are recorded into an Alpaca-formatted `.jsonl` dataset to fine-tune compact local models on the seller's specific menu and abbreviations.

---

## Demo

- **GitHub Repository**: [https://github.com/tharu200304/ChatLedger](https://github.com/tharu200304/ChatLedger)
- **Local Quickstart**:
  ```bash
  git clone https://github.com/tharu200304/ChatLedger.git
  cd ChatLedger
  python -m venv .venv
  .venv\Scripts\activate   # On Linux/macOS: source .venv/bin/activate
  pip install -r requirements.txt
  python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
  ```
- **Instant Testing**: Open `http://127.0.0.1:8000` and click the **"Load Sample Orders"** button in the top navigation bar to load realistic home baker scenarios (new orders, amendments, cancellations, address changes) without needing your own export files.

---

## Code

{% github https://github.com/tharu200304/ChatLedger %}

The complete codebase is available at [https://github.com/tharu200304/ChatLedger](https://github.com/tharu200304/ChatLedger).

### Key Components
- `backend/parser.py`: Multi-line regex WhatsApp parser supporting 12h/24h timestamps, system message filtering, and phone number normalization.
- `backend/thread_grouper.py`: Temporal thread splitter applying a 48-hour inactivity threshold to divide ongoing customer relationships into clean conversational orders.
- `backend/extractor.py`: Intent and entity extractor utilizing local open-weight LLMs with strict JSON Schema constraints, accompanied by an offline heuristic fallback engine.
- `backend/catalog.py`: Catalog manager and deterministic financial engine isolating arithmetic from LLM generation.
- `backend/exporter.py`: Multi-sheet Excel workbook generator built with `openpyxl`.
- `backend/lora_dataset.py`: Local fine-tuning dataset accumulator storing Alpaca-style training pairs from validated user orders.
- `frontend/`: Clean, glassmorphic dual-pane interface built with vanilla HTML5, CSS3, and JavaScript.

---

## How I Built It

ChatLedger is built entirely around **open-weight local inference**:

1. **Local Open-Source LLMs (Ollama + Qwen 2.5 8B / Qwen 3 8B)**:
   - Inference runs locally on the user's laptop using Ollama.
   - We enforce strict JSON Schema decoding to guarantee valid, structured extraction of customer names, dates, quantities, delivery addresses, notes, and source message references.
2. **100% Offline English Heuristic Fallback**:
   - For users on lightweight laptops without a dedicated GPU, ChatLedger includes a built-in heuristic parsing engine that extracts products, numbers, dates, and locations without external dependencies.
3. **Deterministic Business Logic**:
   - The LLM's role is strictly limited to reading comprehension. Item prices, packaging costs, delivery fees, and balance calculations are computed by Python to ensure 0% hallucination on financial totals.
4. **Backend & Storage**:
   - Built with **FastAPI**, **Pydantic v2**, and **SQLite** for persistent, zero-configuration local storage.
5. **Spreadsheet Generation**:
   - Powered by **openpyxl**, producing formatted workbooks with dedicated sheets for the kitchen crew, delivery drivers, and accounting.

---

## Why Does Open Innovation Matter?

For home businesses and independent creators, open-source AI offers advantages that proprietary cloud APIs cannot match:

1. **Customer Data Privacy**: Customer addresses, phone numbers, family event names, and payment slips should never be sent to third-party cloud servers. Open models allow processing to remain strictly on `localhost`.
2. **Resilience & Offline Independence**: Kitchens and home workshops often face spotty internet connections. An open-weight model running locally never goes down, has no rate limits, and does not depend on cloud uptime.
3. **Zero Marginal Operating Costs**: Micro-sellers operating on slim margins cannot afford unpredictable per-token pricing, monthly API minimums, or foreign currency exchange fees. Open weights provide unlimited inference for free.
4. **Data Sovereignty & Local Customization**: Home sellers use unique slang and product abbreviations (e.g., *"choc drip 1kg"*, *"bday bento box"*). With ChatLedger, every user correction helps build a private, local LoRA dataset, enabling the user to fine-tune their own compact model over time.

---

## My Agent Session

This project was built with the assistance of an autonomous AI agent session:
- **Parser & Thread Design**: Built regex engines to handle both iOS and Android WhatsApp export variations and multi-line chat continuations.
- **Verification-First UI**: Created an interactive dual-pane interface where clicking line-item verification icons (`🔍`) dynamically locates and highlights the matching raw chat bubble.
- **Automated Testing**: Validated the complete pipeline (parsing, extraction, pricing, Excel export, and LoRA recording) with 9 automated pytest test suites and headless browser checks.

---

## My First User

I tested ChatLedger with **Nadeesha**, an independent home baker who manages 20–35 custom cake and pastry orders every week via WhatsApp.

We imported a batch of 25 real, anonymized chat exports:
- ChatLedger parsed all 25 conversations in seconds.
- **The Critical Catch**: In one thread, a customer sent an update at 11:15 PM changing their pickup day from Saturday morning to Sunday afternoon. In her handwritten notebook, Nadeesha had missed the update and would have baked the cake a day early. ChatLedger's amendment extractor caught the date change and updated the order schedule automatically.
- **User Feedback**:
  > *"Usually I spend an hour every night matching WhatsApp chats with sticky notes on my kitchen counter. Having tomorrow's baking schedule and delivery run sheet organized automatically in seconds—without having to upload my clients' private phone numbers to the cloud—is a massive relief."*

---

## Prize Categories

- **Hacktoberfest Week 2: Side Hustle** (Primary Category)
- **Local AI & Open-Source Innovation**
