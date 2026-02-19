"""
Capturador Didi - App para cajeros.
Abre Didi Food en un navegador integrado y envía sedes/órdenes al servidor.
Instalar: pip install playwright httpx
Ejecutar: python capturadorDidi.py
Para .exe: pyinstaller --onefile --name CapturadorDidi capturadorDidi.py
"""
import json
import sys
import threading
from pathlib import Path

import httpx

# Config: carpeta del ejecutable o del script
_IS_FROZEN = getattr(sys, "frozen", False)
_APP_DIR = Path(sys.executable).parent if _IS_FROZEN else Path(__file__).resolve().parent
CONFIG_FILE = _APP_DIR / "capturador_config.json"
DEFAULT_BACKEND = "https://restaurant.reports.salchimonster.com"

CAPTURE_PATTERNS = ["getshops", "neworders", "dailyorders"]
DIDI_URL = "https://didi-food.com/es-CO/store/pc/"


def _get_config():
    data = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "backend_url": data.get("backend_url", DEFAULT_BACKEND).rstrip("/"),
    }


def _get_type(url: str) -> str | None:
    u = url.lower()
    if "dailyorders" in u:
        return "dailyOrders"
    if "getshops" in u:
        return "getShops"
    if "neworders" in u:
        return "newOrders"
    return None


def _send_to_backend(backend_url: str, capture_type: str, data: dict, on_status):
    try:
        r = httpx.post(
            f"{backend_url}/didi/capture",
            json={"type": capture_type, "data": data},
            timeout=10.0,
        )
        if r.status_code == 200:
            on_status(f"{capture_type} enviado OK", "ok")
        else:
            on_status(f"{capture_type}: error {r.status_code}", "error")
    except Exception as e:
        on_status(f"Error: {e}", "error")


def run_browser(on_status):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        on_status("Instalar: pip install playwright && playwright install chromium", "error")
        return

    config = _get_config()
    backend = config["backend_url"]
    on_status(f"Abriendo Didi... (servidor: {backend})", "info")

    def handle_response(response):
        url = response.url
        if "b.didi-food.com" not in url.lower():
            return
        if not any(p in url.lower() for p in CAPTURE_PATTERNS):
            return
        try:
            body = response.json()
        except Exception:
            return
        ct = _get_type(url)
        if ct:
            _send_to_backend(backend, ct, body, on_status)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=["--start-maximized"],
            )
            context = browser.new_context(
                viewport=None,
                no_viewport=True,
                ignore_https_errors=True,
            )
            page = context.new_page()
            page.on("response", handle_response)
            page.goto(DIDI_URL, wait_until="domcontentloaded", timeout=60000)
            on_status("Didi abierto. Usa la ventana del navegador.", "ok")
            page.wait_for_event("close", timeout=86400000)
        on_status("Navegador cerrado.", "info")
    except Exception as e:
        on_status(f"Error: {e}", "error")


def main():
    try:
        import tkinter as tk
        from tkinter import font as tkfont
    except ImportError:
        print("Se requiere Python con tkinter. En Windows suele venir instalado.")
        return

    root = tk.Tk()
    root.title("Capturador Didi - Salchi Monster")
    root.geometry("420x200")
    root.resizable(True, True)

    config = _get_config()
    status_var = tk.StringVar(value=f"Servidor: {config['backend_url']}")
    status_color = {"ok": "#0a0", "error": "#c00", "info": "#00a"}

    def set_status(msg, kind="info"):
        def _do():
            status_var.set(msg)
            lbl_status.config(fg=status_color.get(kind, "#000"))
        root.after(0, _do)

    def abrir_didi():
        btn.config(state="disabled", text="Abriendo...")
        set_status("Iniciando navegador...", "info")
        root.update()
        threading.Thread(target=run_browser, args=(set_status,), daemon=True).start()
        btn.config(state="normal", text="Abrir Didi Food")

    f = tk.Frame(root, padx=20, pady=20)
    f.pack(fill="both", expand=True)

    tk.Label(f, text="Capturador Didi", font=tkfont.Font(size=16, weight="bold")).pack(pady=(0, 10))
    tk.Label(f, text="Abre Didi Food y captura sedes y órdenes automáticamente.").pack(pady=(0, 15))

    btn = tk.Button(f, text="Abrir Didi Food", command=abrir_didi, font=tkfont.Font(size=12), width=20, height=2, cursor="hand2")
    btn.pack(pady=10)

    lbl_status = tk.Label(f, textvariable=status_var, fg="#666", wraplength=360, justify="left")
    lbl_status.pack(pady=10, fill="x")

    root.mainloop()


if __name__ == "__main__":
    main()
