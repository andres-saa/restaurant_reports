#!/usr/bin/env python3
"""Consulta deliverys de la sede 12 al API del restaurante y guarda en reports/deliverys/12/{fecha_consulta}.json.
Ejecutar desde la raíz del proyecto: python3 scripts/consultar_sede_12.py
"""
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import DELIVERY_API_BASE, DELIVERYS_CACHE_DIR, COOKIES_FILE, TOKEN_FILE

def _read_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    token_data = _read_json(TOKEN_FILE, {})
    token = token_data.get("token") if isinstance(token_data, dict) else None
    if not token:
        print("No hay token. Haz login primero (POST /login).")
        return 1
    cookies_list = _read_json(COOKIES_FILE, [])
    cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies_list if isinstance(c, dict) and c.get("name") and c.get("value"))

    headers = {"Authorization": f'Token token="{token}"', "Accept": "application/json"}
    if cookie_header:
        headers["Cookie"] = cookie_header
    local_id = "12"
    page = 1
    page_size = 50
    offset = 0
    all_data = []
    max_per_local = 100

    while len(all_data) < max_per_local:
        url = f"{DELIVERY_API_BASE}/obtenerDeliverysPorLocalSimple/{local_id}/{page}/{page_size}/{offset}"
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"HTTP {e.code}: {url}")
            break
        except Exception as e:
            print(f"Error de conexión: {e}")
            break
        if isinstance(body, list):
            all_data.extend(body)
            if len(all_data) > max_per_local:
                all_data = all_data[:max_per_local]
            break
        if not isinstance(body, dict):
            break
        if body.get("tipo") == "401":
            print("No autorizado (token inválido o expirado).")
            return 1
        data = body.get("data") if isinstance(body.get("data"), list) else []
        if not data:
            break
        all_data.extend(data)
        if len(all_data) >= max_per_local:
            all_data = all_data[:max_per_local]
            break
        if len(data) < page_size:
            break
        offset += page_size
        page += 1

    # Fecha de hoy (Colombia) para el nombre del archivo
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime
        tz = ZoneInfo("America/Bogota")
        fecha_hoy = datetime.now(tz).strftime("%Y-%m-%d")
        fetched_at = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S") + " (Colombia)"
    except Exception:
        from datetime import datetime
        fecha_hoy = datetime.utcnow().strftime("%Y-%m-%d")
        fetched_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") + " (UTC)"

    local_dir = DELIVERYS_CACHE_DIR / local_id
    local_dir.mkdir(parents=True, exist_ok=True)
    filepath = local_dir / f"{fecha_hoy}.json"
    existing = _read_json(filepath, {})
    existing_list = existing.get("data", []) if isinstance(existing.get("data"), list) else []
    by_id = {}
    for i, r in enumerate(existing_list):
        if isinstance(r, dict):
            did = (r.get("delivery_id") or "").strip()
            by_id[did or f"__{i}"] = r
    for r in all_data:
        if isinstance(r, dict):
            did = (r.get("delivery_id") or "").strip()
            if did:
                by_id[did] = r
            else:
                by_id[f"__new_{len(by_id)}"] = r
    out = {"fetched_at": fetched_at, "data": list(by_id.values())}
    _write_json(filepath, out)
    print(f"Sede 12: {len(all_data)} deliverys obtenidos, {len(out['data'])} en archivo.")
    print(f"Guardado: {filepath}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
