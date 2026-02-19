"""Script para probar la API newOrders de Didi usando cookies guardadas."""
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
COOKIES_FILE = ROOT / "didi_cookies.json"

URL = (
    "https://b.didi-food.com/bench/order/newOrders"
    "?wsgsig=dd03-Pb6mN6F9fUmbFFM3naBfcIHFEEfdB9k4mF9DGO6CEEfeEdAcUrZfb2dcekmeEVI2%2FVd3aI59eVvfb%2FFFlaMc9IM0BBQMGVdJqrTdbPaGdBub9lF4ldMN0PFGedU"
)


def main() -> None:
    if not COOKIES_FILE.exists():
        print("No existe didi_cookies.json. Ejecuta primero POST /didi/login")
        sys.exit(1)

    cookies_data = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))

    def domain_matches(d: str) -> bool:
        d = (d or "").lower()
        return any(
            d == x or d.endswith("." + x.lstrip("."))
            for x in ("b.didi-food.com", "didi-food.com", "didiglobal.com")
        )

    cookies = {
        c["name"]: c["value"]
        for c in cookies_data
        if isinstance(c, dict) and domain_matches(c.get("domain", ""))
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://didi-food.com/",
    }

    print(f"GET {URL[:80]}...")
    print(f"Cookies enviadas: {list(cookies.keys())}")

    with httpx.Client(timeout=30.0) as client:
        resp = client.get(URL, cookies=cookies, headers=headers)

    print(f"Status: {resp.status_code}")
    print(resp.text[:2000] if len(resp.text) > 2000 else resp.text)


if __name__ == "__main__":
    main()
