"""
APIRouter para recibir JSON de dailyOrders y actualizar el mapa orderId -> displayNum.
También: heartbeat de sedes Didi (extensión) cada ~30 s y WebSocket para listar sedes conectadas.
Incluir en una app FastAPI: app.include_router(didi_capture.router, tags=["didi-capture"]).
Opcional: app.state.didi_capture_maps_dir = Path("/ruta/carpeta") para guardar los mapas.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

_DEFAULT_MAPS_DIR = Path(__file__).resolve().parent / "maps"

# Sedes Didi: extensión envía heartbeat cada ~30 s; si no llega en 36 s se marca desconectada (no se quita de la lista)
_DIDI_STALE_SECONDS = 36
_didi_sedes: dict[str, dict] = {}  # shopId -> { "last_seen": unix_ts, "data": dict }; las sedes no se eliminan
_didi_ws_clients: list[WebSocket] = []
# Blacklist: shopId en este archivo no se muestran ni conectadas ni desconectadas
_DIDI_BLACKLIST_PATH = Path(__file__).resolve().parent.parent / "reports" / "didi" / "sedes_blacklist.json"
# Mapa restaurant_id <-> didi shopId (reports/didi/mapa_restaurant_didi.json)
_DIDI_MAPA_PATH = Path(__file__).resolve().parent.parent / "reports" / "didi" / "mapa_restaurant_didi.json"
# Persistencia: sedes que han enviado al menos un heartbeat (no se pierden al reiniciar)
_DIDI_PERSISTENT_PATH = Path(__file__).resolve().parent.parent / "reports" / "didi" / "sedes_heartbeats_persistent.json"

router = APIRouter()


def _now_colombia() -> datetime:
    if ZoneInfo:
        try:
            return datetime.now(ZoneInfo("America/Bogota"))
        except Exception:
            pass
    return datetime.utcnow()


def _maps_dir(request: Request) -> Path:
    return getattr(request.app.state, "didi_capture_maps_dir", None) or _DEFAULT_MAPS_DIR


def _extract_order_id_to_display(body: dict) -> dict[str, str]:
    out = {}
    data = body.get("data") or {}
    for order in (data.get("serving") or []) + (data.get("highlight") or []):
        if not isinstance(order, dict):
            continue
        oid = str(order.get("orderId") or "").strip()
        display = (order.get("displayNum") or "").strip()
        if oid and display:
            out[oid] = display
    return out


def _update_map(body: dict, map_path: Path) -> int:
    new_map = _extract_order_id_to_display(body)
    if not new_map:
        return 0
    existing = {}
    if map_path.exists():
        try:
            data = json.loads(map_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                existing = data
        except Exception:
            pass
    merged = {**existing, **new_map}
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(merged)


@router.post("/didi/daily-orders-payload")
async def daily_orders_payload(request: Request):
    """
    Recibe el JSON de b.didi-food.com/bench/order/dailyOrders y actualiza
    didi_restaurant_map_YYYY-MM-DD.json (orderId -> displayNum) en la carpeta de mapas.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body debe ser JSON válido")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body debe ser un objeto JSON")

    maps_dir = _maps_dir(request)
    date_str = _now_colombia().strftime("%Y-%m-%d")
    map_path = maps_dir / f"didi_restaurant_map_{date_str}.json"
    map_size = _update_map(body, map_path)

    # Disparar merge (restaurant_map + didi_restaurant_map) y notificar frontend
    on_merge = getattr(request.app.state, "on_didi_map_updated", None)
    if callable(on_merge):
        await on_merge(date_str)

    data = body.get("data") or {}
    orders_count = len(data.get("serving") or []) + len(data.get("highlight") or [])
    shop_id = (body.get("shop_id") or "").strip()
    if not shop_id and (data.get("serving") or []):
        first = (data.get("serving") or [])[0]
        if isinstance(first, dict):
            shop_id = str(first.get("shopId") or "").strip()

    return {
        "ok": True,
        "orders_count": orders_count,
        "shop_id": shop_id or None,
        "map_file": map_path.name,
        "map_entries": map_size,
    }


@router.api_route("/didi/merge-now", methods=["GET", "POST"])
async def merge_now(request: Request):
    """
    Ejecuta el merge (restaurant_map + didi_restaurant_map) para hoy y notifica al frontend.
    Útil cuando hay datos sin actualizar y no quieres esperar al scheduler o a la extensión.
    """
    date_str = _now_colombia().strftime("%Y-%m-%d")
    on_merge = getattr(request.app.state, "on_didi_map_updated", None)
    if not callable(on_merge):
        raise HTTPException(status_code=503, detail="Merge no disponible (app no iniciada)")
    await on_merge(date_str)
    return {"ok": True, "fecha": date_str}


# --- Sedes Didi (extensión: heartbeat cada ~30 s, desconectada si no llega en 36 s; no se quitan de la lista) ---


def _load_didi_persistent() -> None:
    """Carga desde disco las sedes que han enviado al menos un heartbeat (para no mostrar 'Nunca instalada' tras reinicio)."""
    if not _DIDI_PERSISTENT_PATH.exists():
        return
    try:
        raw = json.loads(_DIDI_PERSISTENT_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(v, dict) and "last_seen" in v and "data" in v:
                    _didi_sedes[k] = {"last_seen": float(v["last_seen"]), "data": v.get("data") or {}}
    except Exception:
        pass


def _save_didi_persistent() -> None:
    """Guarda en disco el estado de heartbeats para que persista tras reiniciar el servidor."""
    try:
        _DIDI_PERSISTENT_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {k: {"last_seen": v["last_seen"], "data": v.get("data") or {}} for k, v in _didi_sedes.items()}
        _DIDI_PERSISTENT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _get_didi_blacklist() -> set[str]:
    """ShopIds en la blacklist no se muestran (ni conectadas ni desconectadas)."""
    path = _DIDI_BLACKLIST_PATH
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {str(x).strip() for x in data if x}
        if isinstance(data, dict) and "shopIds" in data:
            return {str(x).strip() for x in data["shopIds"] if x}
        return set()
    except Exception:
        return set()


def _load_didi_mapa() -> dict:
    """Carga el mapa restaurant_id <-> didi shopId desde reports/didi/mapa_restaurant_didi.json."""
    if not _DIDI_MAPA_PATH.exists():
        return {"restaurant_id_to_didi": {}, "didi_to_restaurant_id": {}, "sedes": []}
    try:
        data = json.loads(_DIDI_MAPA_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"restaurant_id_to_didi": {}, "didi_to_restaurant_id": {}, "sedes": []}


def _didi_sedes_list_payload() -> list[dict]:
    """Lista de sedes con lastSeen y connected; incluye las del mapa que nunca han instalado (neverInstalled). Excluye blacklist."""
    now = time.time()
    blacklist = _get_didi_blacklist()
    mapa = _load_didi_mapa()
    # Sedes que han enviado al menos un heartbeat
    out = [
        {
            "shopId": k,
            "shopName": (v.get("data") or {}).get("shopName") or k,
            "lastSeen": v["last_seen"],
            "connected": (now - v["last_seen"]) < _DIDI_STALE_SECONDS,
            "neverInstalled": False,
            "restaurant_id": mapa.get("didi_to_restaurant_id") or {} and (mapa.get("didi_to_restaurant_id") or {}).get(k),
        }
        for k, v in _didi_sedes.items()
        if k not in blacklist
    ]
    didi_ids_in_list = {s["shopId"] for s in out}
    # Añadir sedes del mapa que nunca han enviado heartbeat (neverInstalled)
    for s in mapa.get("sedes") or []:
        if not isinstance(s, dict):
            continue
        rid = s.get("restaurant_id")
        didi_id = str(s.get("didi_shop_id") or "").strip()
        if not didi_id or didi_id in blacklist or didi_id in didi_ids_in_list:
            continue
        if rid is None:
            continue
        out.append({
            "shopId": didi_id,
            "shopName": s.get("name_restaurant") or s.get("name_didi") or didi_id,
            "lastSeen": 0,
            "connected": False,
            "neverInstalled": True,
            "restaurant_id": str(rid),
        })
        didi_ids_in_list.add(didi_id)
    # Asegurar restaurant_id en los que ya teníamos
    for s in out:
        if "restaurant_id" not in s or s.get("restaurant_id") is None:
            s["restaurant_id"] = didi_to_rest.get(s["shopId"])
    return out


async def _didi_sedes_broadcast() -> None:
    dead = []
    payload = _didi_sedes_list_payload()
    for ws in _didi_ws_clients:
        try:
            await ws.send_json({"sedes": payload})
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _didi_ws_clients:
            _didi_ws_clients.remove(ws)


@router.post("/didi/sede-heartbeat")
async def didi_sede_heartbeat(request: Request):
    """
    Recibe cada ~30 s el JSON de la tienda Didi (shopName, shopId, etc.).
    Si una sede no envía en 36 s se considera extensión desconectada.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body debe ser JSON válido")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body debe ser un objeto JSON")
    data = body.get("data")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Falta 'data' con shopId y shopName")
    shop_id = str(data.get("shopId") or "").strip()
    if not shop_id:
        raise HTTPException(status_code=400, detail="data.shopId es requerido")
    now = time.time()
    _didi_sedes[shop_id] = {"last_seen": now, "data": data}
    _save_didi_persistent()
    await _didi_sedes_broadcast()
    return {"ok": True, "shopId": shop_id}


@router.get("/didi/mapa-restaurant")
def didi_mapa_restaurant():
    """
    Mapa restaurant_id <-> didi shopId y lista de sedes.
    Ruta conveniente: reports/didi/mapa_restaurant_didi.json
    """
    return _load_didi_mapa()


@router.get("/didi/extension-status")
def didi_extension_status(restaurant_id: str = Query(..., description="Id del local/sede (restaurant_id)")):
    """
    Indica si la extensión Didi está activa para esta sede.
    Usado en la vista de cada sede para mostrar el punto verde/rojo.
    """
    mapa = _load_didi_mapa()
    rest_to_didi = mapa.get("restaurant_id_to_didi") or {}
    didi_shop_id = rest_to_didi.get(str(restaurant_id).strip())
    if not didi_shop_id:
        return {"hasDidi": False, "active": False}
    entry = _didi_sedes.get(didi_shop_id)
    if not entry:
        return {"hasDidi": True, "active": False}
    active = (time.time() - entry["last_seen"]) < _DIDI_STALE_SECONDS
    return {"hasDidi": True, "active": active}


@router.websocket("/didi/sedes/ws")
async def didi_sedes_websocket(websocket: WebSocket):
    """
    WebSocket para recibir en tiempo real la lista de sedes (con extensión conectada o no).
    Envía { "sedes": [ { shopId, shopName, lastSeen, connected } ] } al conectar y en cada cambio.
    """
    await websocket.accept()
    _didi_ws_clients.append(websocket)
    try:
        await websocket.send_json({"sedes": _didi_sedes_list_payload()})
        while True:
            await asyncio.wait_for(websocket.receive_text(), timeout=300)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        if websocket in _didi_ws_clients:
            _didi_ws_clients.remove(websocket)


# --- Política de privacidad (extensión Didi Food Capture) ---

_DIDI_PRIVACY_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Política de privacidad – Didi Food Capture</title>
  <style>
    body { font-family: system-ui, -apple-system, sans-serif; line-height: 1.6; max-width: 42rem; margin: 0 auto; padding: 1.5rem; color: #1a1a1a; }
    h1 { font-size: 1.5rem; margin-top: 0; }
    h2 { font-size: 1.1rem; margin-top: 1.5rem; }
    p, ul { margin: 0.5rem 0; }
    ul { padding-left: 1.5rem; }
    .updated { color: #666; font-size: 0.9rem; }
  </style>
</head>
<body>
  <h1>Política de privacidad – Didi Food Capture</h1>
  <p class="updated">Extensión de uso interno para el equipo de Salchimonster. Última actualización: febrero 2026.</p>

  <h2>1. Finalidad única</h2>
  <p>Didi Food Capture es una extensión de uso interno para el equipo de Salchimonster. Su única finalidad es capturar en didi-food.com (con sesión iniciada del usuario) las respuestas de las APIs de Didi Food (órdenes del día e información de la tienda seleccionada) y enviarlas de forma segura al servidor de reportes de la empresa (restaurant.reports.salchimonster.com), para mantener actualizado el mapa de órdenes y el estado de conexión de cada sede.</p>
  <p>No recopila datos personales del usuario más allá de lo que Didi ya muestra en la página. No vende ni comparte datos con terceros.</p>

  <h2>2. Datos que se envían al servidor</h2>
  <p>La extensión envía al servidor de la empresa únicamente:</p>
  <ul>
    <li>Información de la tienda (shopId, shopName y datos similares que devuelve la API de Didi) para el heartbeat de conexión.</li>
    <li>Datos de órdenes del día (dailyOrders) que la propia página de Didi ya solicita y muestra al usuario.</li>
  </ul>
  <p>No se envían credenciales, contraseñas ni datos que el usuario no tenga ya visibles en la interfaz de Didi Food.</p>

  <h2>3. Permiso de almacenamiento (storage)</h2>
  <p>El permiso <strong>storage</strong> (chrome.storage.sync) se utiliza exclusivamente para guardar la URL del backend configurada por el usuario en el popup de la extensión (por defecto https://restaurant.reports.salchimonster.com). Así cada instalación puede apuntar al mismo servidor de la empresa sin hardcodear la URL.</p>
  <p>No se almacenan datos personales ni de navegación; solo esta preferencia de configuración.</p>

  <h2>4. Código remoto</h2>
  <p>La extensión <strong>no ejecuta código remoto dinámico</strong>: no carga scripts desde URLs externas ni evalúa código descargado. La única comunicación con un servidor remoto es mediante peticiones HTTP POST (fetch) desde el service worker hacia el backend de la empresa, enviando únicamente los datos que el usuario ya tiene abiertos en didi-food.com. No se inyecta ni se ejecuta código procedente del servidor.</p>

  <h2>5. Permisos de host</h2>
  <ul>
    <li><strong>https://didi-food.com/* y https://b.didi-food.com/*</strong>: la extensión solo actúa cuando el usuario está en la web de Didi Food; es necesario para capturar las respuestas de las APIs (getShopByID, dailyOrders, getShops, newOrders) que la propia página de Didi ya solicita. Sin estos permisos la extensión no podría cumplir su función.</li>
    <li><strong>https://restaurant.reports.salchimonster.com/* y localhost (puertos 8000, 8009)</strong>: la extensión envía los datos capturados al servidor de reportes de la empresa (o a un servidor local en desarrollo). El usuario puede cambiar la URL del backend en el popup. No se envían datos a otros dominios.</li>
  </ul>

  <h2>6. Cumplimiento de políticas</h2>
  <p>El uso de datos de esta extensión cumple las Políticas del Programa para Desarrolladores de Chrome: la extensión solo envía al servidor de la empresa los datos que el usuario ya tiene visibles en didi-food.com. No se recopilan ni almacenan datos personales más allá de lo necesario para este fin; no se venden ni comparten con terceros; no se usa para publicidad ni tracking. Es de uso interno para el equipo de Salchimonster.</p>

  <h2>7. Contacto</h2>
  <p>Para consultas sobre esta política o la extensión Didi Food Capture, utiliza el correo de contacto indicado en la ficha de la extensión en la Chrome Web Store o el canal de soporte interno de Salchimonster.</p>
</body>
</html>
"""


@router.get("/didi/privacy-policy", response_class=HTMLResponse)
def didi_privacy_policy():
    """
    Política de privacidad de la extensión Didi Food Capture.
    Enlazable desde la Chrome Web Store y desde el popup de la extensión.
    """
    return HTMLResponse(_DIDI_PRIVACY_HTML)


async def run_didi_sedes_prune_loop() -> None:
    """Tarea que cada 5 s hace broadcast para actualizar estado conectada/desconectada. Las sedes no se eliminan."""
    while True:
        await asyncio.sleep(5)
        await _didi_sedes_broadcast()


# Al cargar el módulo, restaurar desde disco las sedes que ya habían enviado heartbeat
_load_didi_persistent()
