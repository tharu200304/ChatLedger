# 🧁 ChatLedger

> **Turning a home seller’s WhatsApp chaos into tomorrow’s order sheet, entirely on her own laptop.**

ChatLedger is an open-source, local-first application designed for home-based bakers, caterers, and craft sellers who receive 10–40 orders a day over WhatsApp in English (*“I would like to order a 1kg chocolate cake for Sunday evening, deliver to Peradeniya”*).

---

## 🎯 The Core Philosophy & Privacy Guarantee

1. **Your customers' data never leaves your laptop**: Addresses, phone numbers, and chat histories stay on the machine. Zero cloud APIs, zero third-party data leaks.
2. **Deterministic where it matters**:
   - The LLM **never does arithmetic or sees phone numbers**.
   - Phone numbers, message IDs, timestamps, catalog IDs, and prices are computed deterministically in code.
   - The LLM interprets **intent only**.
3. **Every extracted field links back to its source message**:
   - Clicking any item or field highlights the exact message bubbles in the WhatsApp thread so the seller can verify in 2 seconds.
4. **Continuous Learning & LoRA Dataset**:
   - Every confirmation and user correction is saved as ground truth.
   - Used immediately for dynamic few-shot prompt injection.
   - Exportable as an Alpaca or ShareGPT JSONL training set for fine-tuning **Qwen3-8B** on the seller's specific order vocabulary.
5. **100% Offline Resilience**:
   - Automatically detects **Ollama (Qwen3-8B / Qwen2.5)** when available.
   - If Ollama is offline or uninstalled, seamlessly falls back to the built-in **Local English Intent Heuristic Engine** with zero dependencies.

---

## 🏗️ Architecture & Tech Stack

```
WhatsApp "Export chat" (.txt)
        │
        ▼
 Deterministic parser (parser.py) ── splits messages, reads phone numbers/timestamps, strips system notices
        │
        ▼
 Thread grouping (thread_grouper.py) ── per customer, per ~48h window
        │
        ▼
 Extraction Engine (extractor.py) ── Ollama Qwen3-8B (JSON schema) / Local English Heuristic
   items[{product, qty, variant, notes, source_message_ids}], delivery_date,
   area, status (new/changed/cancelled)
        │
        ▼
 Catalog matcher (catalog.py) ── maps product & aliases to catalog items, computes price
        │
        ▼
 Review Screen (FastAPI + Vanilla CSS) ── side-by-side WhatsApp chat with highlighted source snippets,
                                         confidence badges, one-click confirm/edit
        │
        ▼
 openpyxl Exporters (exporter.py) ── 1. Daily Kitchen Production Sheet (.xlsx)
                                     2. Dispatch & Delivery Sheet by Area (.xlsx)
                                     3. Outstanding Payments & COD Tracker (.xlsx)
```

| Component | Role | Why it's load-bearing |
| :--- | :--- | :--- |
| **Qwen3-8B / Qwen2.5** | Reads thread and extracts order | High-precision English intent extraction and structured schema output. |
| **Ollama / llama.cpp** | Local inference runtime | 100% offline, privacy guarantee, JSON schema constrained output. |
| **SQLite + FastAPI** | Local ledger and review UI | Orders, catalog, and corrections never leave the laptop. |
| **openpyxl** | Exports production and delivery sheets | Generates professional Excel sheets formatted for kitchen & drivers. |

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.10+ (tested on Python 3.13)
- Modern web browser

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Launch ChatLedger
```bash
python run.py
```
This automatically starts the FastAPI server and opens `http://localhost:8000` in your default browser.

---

## 🧪 Testing

Run the automated unit test suite:
```bash
python -m unittest tests/test_chatledger.py
```
Tests cover:
- WhatsApp export parsing (Android & iOS formats, multiline preservation, phone normalization).
- 48-hour thread grouping.
- English extraction (quantities: *one, two, 1, 2, box of 6, pack of 12*; dates: *today, tomorrow, Sunday evening*; delivery areas; custom icing text).
- Cancellation detection (*cancel the order, event cancelled*).
- Date change & rescheduling detection (*postponed, reschedule to Monday*).
- Deterministic catalog matching & pricing.
- `openpyxl` Excel file generation.

---

## 📋 Week-One Feature Deliverables

- [x] **WhatsApp .txt Export Parser**: Android 12h/24h, iOS bracketed timestamps, system notice stripping, multiline preservation.
- [x] **48-Hour Thread Grouper**: Automatically partitions multi-order chat histories into distinct order threads.
- [x] **Extraction Engine**:
  - Ollama integration with strict JSON schema.
  - Built-in High-Accuracy Local English Heuristic Extractor fallback.
- [x] **Deterministic Catalog Matcher**:
  - Pre-seeded with baker's favorites (Chocolate Fudge Cake, Butter Cake, Ribbon Cake, Brownies, Fish Patties, Chicken Rolls, Eclairs).
  - Aliases, variant multipliers, and real-time LKR price calculations.
- [x] **Dual-Pane Interactive Review Workspace**:
  - Real WhatsApp message bubbles (customer vs. seller).
  - Source message highlight linkage with 1-click inspection (`🔍`).
  - Interactive item editor with live price calculation.
  - Warning badges for ambiguous delivery dates, cancellations, and custom inscriptions.
- [x] **Three Executive Excel Exports (`openpyxl`)**:
  - `Production_Sheet_YYYY-MM-DD.xlsx` (baker's morning kitchen checklist, items, notes, icing text).
  - `Delivery_Sheet_YYYY-MM-DD.xlsx` (route sheet grouped by Area, customer contact, COD amounts).
  - `Payment_Pending_Sheet.xlsx` (outstanding balances and advance tracker).
- [x] **Continuous Learning & LoRA Training Exporter**:
  - Saves all confirmed corrections to SQLite.
  - Dynamically feeds them into future prompts as few-shot context.
  - Exports Alpaca / ShareGPT `.jsonl` datasets for fine-tuning Qwen3-8B.
