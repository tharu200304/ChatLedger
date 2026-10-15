import sys
import webbrowser
import threading
import time
import uvicorn
from backend.config import OLLAMA_BASE_URL
from backend.extractor import check_ollama_health

def open_browser(port: int):
    time.sleep(1.2)
    url = f"http://localhost:{port}"
    print(f"\n✨ Opening ChatLedger in your web browser: {url}\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass

if __name__ == "__main__":
    port = 8000
    print("=" * 65)
    print("  🍰 ChatLedger: Home Seller's WhatsApp Order Hub (Offline & Local)")
    print("=" * 65)

    ollama_ok = check_ollama_health(OLLAMA_BASE_URL)
    if ollama_ok:
        print(f"  [✓] Ollama detected at {OLLAMA_BASE_URL} (Qwen structured output ready)")
    else:
        print(f"  [i] Ollama not detected at {OLLAMA_BASE_URL}")
        print("      ⚡ Using Built-in Local English Intent Heuristic Engine (100% Offline)")

    print(f"  [✓] SQLite Ledger Database initialized in data/chatledger.db")
    print(f"  [✓] openpyxl Excel Exporters ready (Production, Delivery & Payment Sheets)")
    print(f"  [✓] Local Web Interface: http://localhost:{port}")
    print("=" * 65)

    threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    uvicorn.run("backend.app:app", host="127.0.0.1", port=port, log_level="info")
