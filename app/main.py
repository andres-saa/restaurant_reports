"""
FastAPI app: login a Salchi Monster Restaurant con Chromium,
credenciales en JSON local y cookies de sesión.
"""
from __future__ import annotations

import asyncio
import json
import logging
import queue
import re
import sys
import traceback
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("restaurant_scraper")

# Asegurar que el proyecto root esté en el path (funciona aunque uvicorn se ejecute desde otra carpeta)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from datetime import datetime, timedelta
from urllib.parse import urlencode

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.config import (
    CREDENTIALS_FILE,
    COOKIES_FILE,
    TOKEN_FILE,
    LOGIN_URL,
    LOGIN_API_URL,
    REPORT_URL,
    LOCALES_API_URL,
    REPORTS_DIR,
    REPORTS_LOCALES_JSON,
    REPORTS_CANALES_DELIVERY_JSON,
    DELIVERY_API_BASE,
    DELIVERYS_CACHE_DIR,
    UPLOADS_DIR,
    NO_ENTREGADAS_JSON,
    APELACIONES_JSON,
    HORARIOS_JSON,
    DIDI_LOGIN_URL,
    DIDI_CREDENTIALS_FILE,
    DIDI_COOKIES_FILE,
    DIDI_STORE_URL,
    DIDI_SHOPS_URL,
    DIDI_SHOPS_JSON,
    DIDI_NEW_ORDERS_JSON,
    DIDI_DAILY_ORDERS_JSON,
    DIDI_BLACKLIST_FILE,
    DIDI_MANAGER_ORDER_URL,
    DIDI_STORE_ORDER_HISTORY_URL,
    DIDI_ORDER_LIST_JSON,
    DIDI_SYSTEM_MAP_JSON,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ya no se usa el reporte Excel automático; datos desde API deliverys cada 5 min
    # Locales desde API cada 10 min; primera carga al arranque
    locales_task = asyncio.create_task(_locales_scheduler_loop())
    asyncio.create_task(_fetch_and_save_locales())  # primera vez sin esperar
    logger.info("Locales scheduler: iniciado (cada 10 min)")
    # Migrar deliverys antiguos (un archivo por local) a estructura por fecha
    try:
        _migrate_old_deliverys_to_per_date()
    except Exception as e:
        logger.warning("Migración deliverys: %s", e)
    # Deliverys por local cada 2 min (obtenerDeliverysPorLocalSimple; 5 s entre cada sede)
    deliverys_task = asyncio.create_task(_deliverys_scheduler_loop())
    logger.info("Deliverys scheduler: iniciado (cada 2 min, fecha hoy; 5 s entre sedes)")
    # Login cada 12 h para renovar sesión
    login_refresh_task = asyncio.create_task(_login_refresh_loop())
    logger.info("Login refresh: iniciado (cada 12 h)")
    # Didi: captura daily-orders cada 5 min (solo en horario de apertura) y aplica reemplazos
    didi_daily_task = asyncio.create_task(_didi_daily_orders_scheduler_loop())
    logger.info("Didi daily-orders: iniciado (cada 5 min, respetando horario de apertura)")
    asyncio.create_task(_run_didi_daily_orders_once())  # ejecutar una vez al arranque (si en horario)
    yield
    locales_task.cancel()
    deliverys_task.cancel()
    login_refresh_task.cancel()
    didi_daily_task.cancel()
    try:
        await locales_task
    except asyncio.CancelledError:
        pass
    try:
        await deliverys_task
    except asyncio.CancelledError:
        pass
    try:
        await login_refresh_task
    except asyncio.CancelledError:
        pass
    try:
        await didi_daily_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Restaurant Scraper Login",
    description="Login con Chromium a salchimonster.restaurant.pe",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://fotopedidos.salchimonster.com",
        "http://fotopedidos.salchimonster.com",
        "null",  # extensión de navegador (Didi Capture)
    ],
    allow_origin_regex=r"chrome-extension://[a-zA-Z0-9]+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Credenciales ---

def _read_json(path: Path, default: dict | list) -> dict | list:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def _write_json(path: Path, data: dict | list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_credentials() -> dict[str, Any]:
    data = _read_json(CREDENTIALS_FILE, {})
    if not data:
        raise HTTPException(status_code=503, detail="No hay credenciales. Usa PUT /credentials para configurarlas.")
    return data


def save_credentials(data: dict[str, Any]) -> dict[str, Any]:
    CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _write_json(CREDENTIALS_FILE, data)
    return data


def get_cookies() -> list[dict]:
    return _read_json(COOKIES_FILE, [])


def save_cookies(cookies: list[dict]) -> None:
    COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _write_json(COOKIES_FILE, cookies)


def get_didi_credentials() -> dict[str, Any]:
    """Credenciales Didi (email + password). Por defecto admon.salchimonster@gmail.com / Didi2024."""
    data = _read_json(DIDI_CREDENTIALS_FILE, {})
    if data:
        return data
    return {"email": "admon.salchimonster@gmail.com", "password": "Didi2024"}


def save_didi_credentials(data: dict[str, Any]) -> None:
    DIDI_CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _write_json(DIDI_CREDENTIALS_FILE, data)


def get_didi_cookies() -> list[dict]:
    return _read_json(DIDI_COOKIES_FILE, [])


def save_didi_cookies(cookies: list[dict]) -> None:
    DIDI_COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _write_json(DIDI_COOKIES_FILE, cookies)


def get_didi_blacklist() -> set[str]:
    """Devuelve shopId a excluir (sedes que no son Salchimonster)."""
    data = _read_json(DIDI_BLACKLIST_FILE, {})
    ids = data.get("shop_ids") if isinstance(data, dict) else []
    return set(str(x) for x in ids) if ids else set()


def get_token() -> str | None:
    """Devuelve el token guardado (data.token del login) o None."""
    data = _read_json(TOKEN_FILE, {})
    if isinstance(data, dict):
        return data.get("token")
    return None


def save_token(token: str | None) -> None:
    """Guarda el token del login en token.json."""
    if not token:
        return
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    _write_json(TOKEN_FILE, {"token": token, "updated_at": datetime.utcnow().isoformat() + "Z"})


# --- Pydantic models ---

class CredentialsUpdate(BaseModel):
    usuario_nick: str | None = None
    usuario_clave: str | None = None
    usuario_recordar: str | None = None
    local_id: str | None = None
    turno_id: str | None = None
    caja_id: str | None = None
    app: str | None = None


class DidiCredentialsUpdate(BaseModel):
    email: str | None = None
    password: str | None = None


class DidiCaptureBody(BaseModel):
    """Body de POST /didi/capture (extensión del navegador)."""
    type: str  # "getShops" | "newOrders"
    data: dict | None = None


def _clean_server_error_message(raw: str) -> str:
    """Convierte HTML/errores del servidor (ej. Slim PHP) en un mensaje corto y legible."""
    if not raw or not isinstance(raw, str):
        return "Error desconocido del servidor"
    raw = raw.strip()
    # Es una página de error HTML (Slim, etc.)
    if "<html" in raw.lower() or "slim application error" in raw.lower() or "application error" in raw.lower():
        # Extraer el mensaje después de "Message:</strong>" o "Details" (ej. get_object_vars()...)
        m = re.search(r"<strong>\s*Message:\s*</strong>\s*([^<]+)", raw, re.IGNORECASE | re.DOTALL)
        if m:
            detail = m.group(1).strip()
            detail = re.sub(r"\s+", " ", detail)[:200]
            # Mensaje más amigable para el error típico del PHP del restaurante
            if "get_object_vars" in detail and "null given" in detail:
                return (
                    "El servidor del restaurante falló al procesar el login (error interno). "
                    "Comprueba que usuario y clave sean correctos. Si sigue fallando, usa «Probar login por formulario»."
                )
            return f"Error del servidor del restaurante: {detail}"
        m = re.search(r"<strong>\s*Details:\s*</strong>\s*([^<]+)", raw, re.IGNORECASE | re.DOTALL)
        if m:
            detail = m.group(1).strip()
            detail = re.sub(r"\s+", " ", detail)[:200]
            if "get_object_vars" in detail and "null given" in detail:
                return (
                    "El servidor del restaurante falló al procesar el login (error interno). "
                    "Comprueba que usuario y clave sean correctos. Si sigue fallando, usa «Probar login por formulario»."
                )
            return f"Error del servidor del restaurante: {detail}"
        return "Error del servidor del restaurante (página de error). Intenta de nuevo más tarde."
    # Si ya es texto corto sin HTML, detectar el mismo error PHP
    if "get_object_vars" in raw and "null given" in raw:
        return (
            "El servidor del restaurante falló al procesar el login (error interno). "
            "Comprueba que usuario y clave sean correctos. Si sigue fallando, usa «Probar login por formulario»."
        )
    if len(raw) > 400:
        raw = raw[:397] + "..."
    return raw


# --- Endpoints ---

@app.get("/")
def root():
    return {"message": "Restaurant Scraper Login API", "docs": "/docs"}


@app.get("/credentials")
def read_credentials():
    """Devuelve las credenciales guardadas (sin exponer la clave en logs)."""
    cred = get_credentials()
    # Opcional: ofuscar clave en respuesta
    out = cred.copy()
    if out.get("usuario_clave"):
        out["usuario_clave"] = "********"
    return out


# WebSocket y cola para notificar progreso de login (credenciales)
_credentials_ws_clients: list[WebSocket] = []
_login_status_queue: queue.Queue = queue.Queue()


def _login_status_push(step: str, message: str, **extra: Any) -> None:
    """Envía un paso del login a la cola para que se emita por WebSocket (thread-safe)."""
    try:
        _login_status_queue.put_nowait({"step": step, "message": message, **extra})
    except Exception:
        pass


@app.put("/credentials")
def update_credentials(update: CredentialsUpdate):
    """Actualiza las credenciales en credentials.json."""
    current = _read_json(CREDENTIALS_FILE, {})
    payload = update.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="Envía al menos un campo para actualizar.")
    current.update(payload)
    save_credentials(current)
    return {"message": "Credenciales actualizadas", "credentials": {k: "********" if k == "usuario_clave" else v for k, v in current.items()}}


@app.websocket("/credentials/ws")
async def credentials_status_websocket(websocket: WebSocket):
    """
    WebSocket para recibir en tiempo real el progreso al actualizar credenciales y hacer login.
    Mensajes: step, message y opcionalmente success, credentials.
    """
    await websocket.accept()
    _credentials_ws_clients.append(websocket)
    try:
        while True:
            await asyncio.wait_for(websocket.receive_text(), timeout=300)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        if websocket in _credentials_ws_clients:
            _credentials_ws_clients.remove(websocket)


async def _broadcast_credentials_status(payload: dict) -> None:
    """Envía un mensaje a todos los clientes del WebSocket de credenciales."""
    dead: list[WebSocket] = []
    for ws in list(_credentials_ws_clients):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _credentials_ws_clients:
            _credentials_ws_clients.remove(ws)


@app.post("/credentials/update-and-login")
async def update_credentials_and_login(update: CredentialsUpdate):
    """
    Actualiza las credenciales, intenta login y notifica el progreso por WebSocket (/credentials/ws).
    Si el login es correcto, devuelve las credenciales actuales (clave enmascarada) y la opción de actualizarlas.
    """
    payload = update.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="Envía al menos un campo (usuario_nick, usuario_clave, etc.).")
    current = _read_json(CREDENTIALS_FILE, {})
    current.update(payload)
    save_credentials(current)
    cred_masked = {k: "********" if k == "usuario_clave" else v for k, v in current.items()}
    await _broadcast_credentials_status({
        "step": "credentials_saved",
        "message": "Credenciales guardadas. Iniciando login...",
    })
    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(_get_executor(), _do_login_sync)
    while not future.done():
        try:
            while True:
                msg = _login_status_queue.get_nowait()
                await _broadcast_credentials_status(msg)
        except queue.Empty:
            pass
        await asyncio.sleep(0.05)
    while True:
        try:
            msg = _login_status_queue.get_nowait()
            await _broadcast_credentials_status(msg)
        except queue.Empty:
            break
    result = future.result()
    success = result.get("success", False) and not result.get("_is_error", False)
    await _broadcast_credentials_status({
        "step": "result",
        "message": result.get("message", "Listo."),
        "success": success,
        "credentials": cred_masked,
    })
    if result.get("_is_error"):
        code = result.get("status_code", 500)
        return JSONResponse(status_code=code, content={
            "message": result.get("message", "Error en login"),
            "success": False,
            "credentials": cred_masked,
        })
    return {
        "message": result.get("message", "Login realizado"),
        "success": True,
        "credentials": cred_masked,
    }


def _value_for_select(cred_value: str) -> str:
    """En el HTML los options tienen value 'string:1'; la API acepta '1'. Intentamos ambos."""
    if not cred_value:
        return cred_value
    return f"string:{cred_value}"


def _do_login_form_sync() -> dict:
    """Login rellenando el formulario de la página (como un usuario). Usa el HTML del login."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "_is_error": True,
            "status_code": 503,
            "success": False,
            "message": "Playwright no instalado.",
            "saved_cookies": 0,
        }

    cred = get_credentials()
    logger.info("Login (form): inicio - usuario=%s", cred.get("usuario_nick", "?"))

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                ignore_https_errors=True,
            )
            saved_cookies = get_cookies()
            if saved_cookies:
                context.add_cookies(saved_cookies)

            page = context.new_page()
            page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)

            # Esperar al formulario (Angular)
            page.wait_for_selector('select[name="local_id"]', state="visible", timeout=15000)
            logger.info("Login (form): formulario visible")

            local_val = _value_for_select(cred.get("local_id", "1"))
            caja_val = _value_for_select(cred.get("caja_id", "29"))
            turno_val = _value_for_select(cred.get("turno_id", "1"))

            # Orden: local (dispara carga de caja/turno), luego caja, turno, usuario, clave
            page.select_option('select[name="local_id"]', value=local_val)
            page.wait_for_timeout(1500)  # fnCambiarLocal() carga cajas/turnos

            try:
                page.select_option('select[name="caja_id"]', value=caja_val)
            except Exception as e:
                logger.warning("Login (form): caja_id %s no encontrado, intentando por índice: %s", caja_val, e)
                page.select_option('select[name="caja_id"]', index=1)
            try:
                page.select_option('select[name="turno_id"]', value=turno_val)
            except Exception as e:
                logger.warning("Login (form): turno_id %s no encontrado: %s", turno_val, e)
                page.select_option('select[name="turno_id"]', index=1)

            page.fill('input[name="usuario_nick"]', cred.get("usuario_nick", ""))
            page.fill('input[name="usuario_clave"]', cred.get("usuario_clave", ""))

            # Esperar a que el botón esté habilitado (vm.cargaDataCaja && vm.cargaDataTurno)
            submit = page.locator('button[type="submit"]')
            try:
                submit.wait_for(state="visible", timeout=5000)
                page.wait_for_selector('button[type="submit"]:not([disabled])', timeout=10000)
            except Exception as e:
                logger.warning("Login (form): botón no se habilitó (caja/turno?): %s", e)
            page.wait_for_timeout(500)

            # Esperar respuesta del login al hacer clic (Angular llama al API)
            login_resp_status = None
            token_from_form = None
            try:
                with page.expect_response(lambda r: "usuario/login" in r.url) as resp_info:
                    submit.click()
                    logger.info("Login (form): clic en Iniciar sesión")
                resp = resp_info.value
                login_resp_status = resp.status
                logger.info("Login (form): respuesta login API status=%s", login_resp_status)
                if resp.status == 200:
                    try:
                        body_form = resp.json()
                        if isinstance(body_form, dict) and body_form.get("data") and body_form.get("data").get("token"):
                            token_from_form = body_form["data"]["token"]
                            save_token(token_from_form)
                            logger.info("Login (form): token guardado")
                    except Exception:
                        pass
            except Exception as e:
                logger.warning("Login (form): no se capturó respuesta del API: %s", e)

            # Dar tiempo a redirección / actualización de la vista
            page.wait_for_timeout(5000)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass

            current_url = page.url
            cookies = context.cookies()
            save_cookies(cookies)

            # Si sigue en login, intentar leer mensaje de error de la página (toast, .has-error, etc.)
            error_hint = ""
            if "#!/login" in current_url:
                try:
                    toast = page.locator(".toast-message, .toast-error, [class*='error']").first
                    if toast.count() > 0 and toast.is_visible():
                        error_hint = " " + (toast.text_content() or "")[:150]
                except Exception:
                    pass
                if not error_hint:
                    try:
                        err_el = page.locator(".has-error .help-block, .alert-danger").first
                        if err_el.count() > 0 and err_el.is_visible():
                            error_hint = " " + (err_el.text_content() or "")[:150]
                    except Exception:
                        pass

            browser.close()

            # Éxito si ya no estamos en la ruta de login
            if "#!/login" in current_url:
                msg = "El formulario se envió pero la página sigue en login (revisa usuario/clave o captcha)."
                if login_resp_status == 500:
                    msg = "El servidor del restaurante respondió 500 al login (mismo error que por API)." + error_hint
                elif error_hint:
                    msg = msg.rstrip(".") + "." + error_hint
                return {
                    "_is_error": True,
                    "status_code": 401,
                    "success": False,
                    "message": msg.strip(),
                    "saved_cookies": len(cookies),
                }

            logger.info("Login (form): éxito, cookies guardadas (%s)", len(cookies))
            return {
                "_is_error": False,
                "success": True,
                "message": "Login realizado (formulario).",
                "token": token_from_form or get_token(),
                "saved_cookies": len(cookies),
            }

    except Exception as e:
        logger.exception("Login (form): excepción %s", e)
        return {
            "_is_error": True,
            "status_code": 500,
            "success": False,
            "message": f"{type(e).__name__}: {e}",
            "saved_cookies": 0,
            "detail": traceback.format_exc(),
        }


def _do_login_sync() -> dict:
    """Ejecuta el login con Playwright síncrono (en proceso separado en Windows para evitar NotImplementedError)."""
    _login_status_push("start", "Iniciando login...")
    logger.info("Login: inicio")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        logger.error("Playwright no instalado: %s", e)
        _login_status_push("error", "Playwright no instalado.", success=False)
        return {
            "_is_error": True,
            "status_code": 503,
            "success": False,
            "message": "Playwright no instalado. Ejecuta: pip install playwright && playwright install chromium",
            "saved_cookies": 0,
        }

    cred = get_credentials()
    _login_status_push("credentials_loaded", "Credenciales cargadas. Lanzando navegador...")
    logger.info("Login: credenciales cargadas (usuario=%s)", cred.get("usuario_nick", "?"))
    form_data = {
        "usuario_nick": cred.get("usuario_nick", ""),
        "usuario_clave": cred.get("usuario_clave", ""),
        "usuario_recordar": cred.get("usuario_recordar", "1"),
        "local_id": cred.get("local_id", "1"),
        "turno_id": cred.get("turno_id", "1"),
        "caja_id": cred.get("caja_id", "29"),
        "app": cred.get("app", "Web"),
    }

    try:
        with sync_playwright() as p:
            _login_status_push("browser_start", "Lanzando Chromium...")
            logger.info("Login: lanzando Chromium")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                ignore_https_errors=True,
            )

            saved_cookies = get_cookies()
            if saved_cookies:
                context.add_cookies(saved_cookies)

            page = context.new_page()
            _login_status_push("navigating", "Navegando a la página de login...")
            logger.info("Login: navegando a %s", LOGIN_URL)
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)

            _login_status_push("sending_login", "Enviando credenciales al servidor...")
            logger.info("Login: POST a %s", LOGIN_API_URL)
            response = page.request.post(
                LOGIN_API_URL,
                form=form_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
            )

            status = response.status
            logger.info("Login: respuesta HTTP %s", status)
            body = None
            try:
                body = response.json()
                logger.info("Login: body JSON keys=%s", list(body.keys())[:15] if isinstance(body, dict) else "n/a")
            except Exception as e:
                logger.warning("Login: no se pudo parsear JSON: %s", e)
                try:
                    raw = response.text()
                    if raw and raw.strip():
                        body = {"_raw": raw}
                        logger.info("Login: body raw (primeros 200 chars): %s", raw[:200])
                except Exception as e2:
                    logger.warning("Login: no se pudo leer body: %s", e2)

            cookies = context.cookies()
            save_cookies(cookies)
            _login_status_push("saving_session", "Guardando sesión y cookies...")
            logger.info("Login: cookies guardadas (%s)", len(cookies))
            browser.close()

    except Exception as e:
        logger.exception("Login: excepción en Playwright/request: %s", e)
        _login_status_push("error", f"Error: {e}", success=False)
        return {
            "_is_error": True,
            "status_code": 500,
            "success": False,
            "message": f"{type(e).__name__}: {e}",
            "saved_cookies": 0,
            "detail": traceback.format_exc(),
        }

    def _msg(b: dict | None, default: str = "Error desconocido") -> str:
        if not b or not isinstance(b, dict):
            return default
        for key in ("mensajes", "message", "detail", "error"):
            val = b.get(key)
            if isinstance(val, list) and val:
                return _clean_server_error_message(str(val[0]))
            if isinstance(val, str) and val:
                return _clean_server_error_message(val)
        if b.get("_raw"):
            return _clean_server_error_message(str(b["_raw"])[:2000])
        return default

    # Detectar respuesta HTML de error (Slim/PHP) aunque venga con 200
    raw_body = (body or {}).get("_raw", "") if isinstance(body, dict) else ""
    is_html_error = (
        isinstance(raw_body, str)
        and ("<html" in raw_body.lower() or "slim application error" in raw_body.lower())
    )

    if status != 200 or is_html_error:
        msg = _msg(body, f"Login falló (HTTP {status})" if status != 200 else "Error del servidor del restaurante")
        if is_html_error:
            msg = _clean_server_error_message(raw_body)
        _login_status_push("error", msg, success=False)
        logger.warning("Login: falló HTTP %s - %s", status, msg[:200])
        return {
            "_is_error": True,
            "status_code": status if status != 200 else 502,
            "success": False,
            "message": msg,
            "saved_cookies": len(cookies),
        }

    mensaje = "Login realizado"
    if body and isinstance(body, dict) and body.get("mensajes"):
        mensaje = body["mensajes"][0] if body["mensajes"] else mensaje
    else:
        mensaje = _msg(body, mensaje)

    # Extraer y guardar token (data.token) del JSON de login
    token = None
    if isinstance(body, dict) and body.get("data"):
        token = body["data"].get("token")
    if token:
        save_token(token)
        logger.info("Login: token guardado")

    _login_status_push("done", mensaje, success=True)
    logger.info("Login: éxito - %s", mensaje)
    return {
        "_is_error": False,
        "success": True,
        "message": mensaje,
        "tipo": body.get("tipo") if isinstance(body, dict) else None,
        "token": token,
        "saved_cookies": len(cookies),
        "data_preview": list(body.get("data", {}).keys())[:10] if isinstance(body, dict) and body.get("data") else None,
    }


def _do_didi_login_sync() -> dict:
    """Login a Didi Food por navegador: correo + contraseña en page.didiglobal.com. Guarda cookies en didi_cookies.json."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        logger.error("Playwright no instalado: %s", e)
        return {
            "_is_error": True,
            "success": False,
            "message": "Playwright no instalado. pip install playwright && playwright install chromium",
            "saved_cookies": 0,
        }

    cred = get_didi_credentials()
    email = (cred.get("email") or "").strip()
    password = (cred.get("password") or "").strip()
    if not email or not password:
        return {
            "_is_error": True,
            "success": False,
            "message": "Faltan email o contraseña en didi_credentials.json",
            "saved_cookies": 0,
        }

    logger.info("Didi login: inicio (email=%s)", email[:20] + "..." if len(email) > 20 else email)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                ignore_https_errors=True,
            )
            existing = get_didi_cookies()
            if existing:
                context.add_cookies(existing)

            page = context.new_page()
            page.goto(DIDI_LOGIN_URL, wait_until="load", timeout=45000)
            page.wait_for_timeout(4000)  # SPA Vue: esperar nav-tab y formulario inicial

            # Paso 1: La página inicia con "Ingresar con contraseña" (teléfono). Debemos clicar
            # "Iniciar sesión con el correo electrónico" para que aparezca el formulario email/password.
            tab_email_texts = ("Iniciar sesión con el correo electrónico", "Sign in with email", "correo electrónico")
            tab_clicked = False
            for tab_text in tab_email_texts:
                try:
                    tab = page.get_by_text(tab_text, exact=True).first
                    tab.wait_for(state="visible", timeout=5000)
                    tab.click()
                    tab_clicked = True
                    logger.info("Didi: clic en tab '%s'", tab_text[:40])
                    break
                except Exception:
                    try:
                        tab = page.locator("li.nav-tab li", has_text=tab_text).first
                        tab.wait_for(state="visible", timeout=3000)
                        tab.click()
                        tab_clicked = True
                        logger.info("Didi: clic en tab li '%s'", tab_text[:40])
                        break
                    except Exception:
                        continue
            if not tab_clicked:
                try:
                    # Fallback: clic en la tercera pestaña (correo electrónico) por índice
                    page.locator(".nav-tab li").nth(2).click()
                    tab_clicked = True
                    logger.info("Didi: clic en tab por índice 2")
                except Exception:
                    pass
            if not tab_clicked:
                logger.warning("Didi: no se encontró tab correo electrónico, continuando...")
            page.wait_for_timeout(2000)  # Esperar a que Vue muestre el formulario email

            # Paso 2: Campos email y password (solo visibles tras clicar la tab correo)
            email_selectors = [
                'input[placeholder="Ingresa tu correo electrónico"]',
                'input[placeholder*="correo"]',
                'input[placeholder*="Ingresa tu correo"]',
                'input[placeholder*="email"]',
                'input[placeholder*="Email"]',
                ".input-email input[type='text']",
                ".email-login-form input[type='text']",
            ]
            pwd_selectors = [
                'input[placeholder="Ingresa tu contraseña"]',
                'input[placeholder*="contraseña"]',
                'input[placeholder*="password"]',
                'input[placeholder*="Password"]',
                ".input-pwd input[type='password']",
                ".email-login-form input[type='password']",
            ]
            email_loc = page.locator(", ".join(email_selectors)).first
            pwd_loc = page.locator(", ".join(pwd_selectors)).first
            email_loc.wait_for(state="visible", timeout=15000)
            email_loc.fill(email)
            page.wait_for_timeout(400)
            pwd_loc.fill(password)
            page.wait_for_timeout(500)

            # Botón "Iniciar sesión" / "Sign in" / "Log in" (es un div con clase button)
            btn = page.locator("div.button.actived").filter(
                has=page.locator("text=/Iniciar sesión|Sign in|Log in/i")
            ).first
            btn.click()

            # Esperar redirección (Didi puede tardar o usar SPA; no depender de expect_navigation)
            current_url = page.url
            for _ in range(30):  # hasta 30 s
                page.wait_for_timeout(1000)
                current_url = page.url
                if "didi-food.com" in current_url or "setCookieV2" in current_url:
                    logger.info("Didi: redirección detectada a %s", current_url[:60])
                    break
                if "page.didiglobal.com" not in current_url:
                    break  # ya salió del login

            # Navegar a la store para establecer sesión completa en b.didi-food.com
            # (la cookie "ticket" y el wsgsig se asocian ahí; sin esto, newOrders devuelve session expired)
            if "didi-food.com" in current_url or "setCookieV2" in current_url:
                try:
                    page.goto(DIDI_STORE_URL, wait_until="domcontentloaded", timeout=20000)
                    page.wait_for_timeout(5000)  # esperar que carguen APIs (newOrders, etc.)
                except Exception as nav_err:
                    logger.warning("Didi: navegación a store: %s", nav_err)

            cookies = context.cookies()
            save_didi_cookies(cookies)
            browser.close()

            success = "didi-food.com" in current_url or "setCookieV2" in current_url or "didi" in current_url.lower()
            logger.info("Didi login: url final=%s, cookies=%s", current_url[:80], len(cookies))
            return {
                "_is_error": False,
                "success": success,
                "message": "Login Didi realizado" if success else "Comprueba si la sesión se abrió correctamente.",
                "saved_cookies": len(cookies),
                "final_url": current_url[:200],
            }
    except Exception as e:
        logger.exception("Didi login: %s", e)
        return {
            "_is_error": True,
            "success": False,
            "message": f"{type(e).__name__}: {e}",
            "saved_cookies": 0,
        }


def _fetch_didi_new_orders_sync() -> dict:
    """
    Obtiene newOrders de Didi usando Playwright con las cookies guardadas.
    El navegador carga la store, hace la petición real (con wsgsig correcto) y devuelve la respuesta.
    Evita 'session expired' porque usa la misma sesión que un usuario real.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        logger.error("Playwright no instalado: %s", e)
        return {"_is_error": True, "success": False, "message": str(e), "data": None}

    cookies = get_didi_cookies()
    if not cookies:
        return {
            "_is_error": True,
            "success": False,
            "message": "No hay cookies Didi. Ejecuta POST /didi/login primero.",
            "data": None,
        }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                ignore_https_errors=True,
            )
            context.add_cookies(cookies)

            page = context.new_page()
            new_orders_response: list[dict] = []

            def on_response(resp):
                url = resp.url or ""
                if "newOrders" in url and resp.request.resource_type == "xhr":
                    try:
                        body = resp.json()
                        new_orders_response.append(body)
                    except Exception:
                        pass

            page.on("response", on_response)
            page.goto(DIDI_STORE_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            browser.close()

            if new_orders_response:
                data = new_orders_response[-1]
                errno = data.get("errno", 0)
                success = errno == 0
                return {
                    "_is_error": False,
                    "success": success,
                    "message": data.get("errmsg") if not success else "OK",
                    "data": data,
                }
            return {
                "_is_error": True,
                "success": False,
                "message": "No se capturó respuesta newOrders (¿sesión expirada?)",
                "data": None,
            }
    except Exception as e:
        logger.exception("Didi newOrders: %s", e)
        return {"_is_error": True, "success": False, "message": str(e), "data": None}


def _fetch_didi_shops_sync() -> dict:
    """
    Navega a shop/select, captura la respuesta de b.didi-food.com/auth/getShops
    y guarda el resultado en sedes_didi.json (shops = sedes).
    Requiere sesión iniciada (POST /didi/login).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        logger.error("Playwright no instalado: %s", e)
        return {"_is_error": True, "success": False, "message": str(e), "saved_path": None}

    cookies = get_didi_cookies()
    if not cookies:
        return {
            "_is_error": True,
            "success": False,
            "message": "No hay cookies Didi. Ejecuta POST /didi/login primero.",
            "saved_path": None,
        }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                ignore_https_errors=True,
            )
            context.add_cookies(cookies)

            page = context.new_page()
            get_shops_response: list[dict] = []

            def on_response(resp):
                url = resp.url or ""
                if "getShops" in url and resp.request.resource_type == "xhr":
                    try:
                        body = resp.json()
                        get_shops_response.append(body)
                    except Exception:
                        pass

            page.on("response", on_response)
            page.goto(DIDI_SHOPS_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)  # esperar que cargue getShops

            browser.close()

            if get_shops_response:
                data = get_shops_response[-1]
                errno = data.get("errno", -1)
                success = errno == 0
                if success:
                    # Filtrar sedes por lista negra (excluir Burger Monster, etc.)
                    blacklist = get_didi_blacklist()
                    shops_data = data.get("data", {}) or {}
                    shops = shops_data.get("shops") or []
                    if blacklist:
                        original_count = len(shops)
                        shops = [s for s in shops if str(s.get("shopId", "")) not in blacklist]
                        shops_data = {**shops_data, "shops": shops, "total": len(shops)}
                        data = {**data, "data": shops_data}
                        logger.info("Didi: excluidas %d sedes por blacklist (Salchimonster: %d)", original_count - len(shops), len(shops))
                    DIDI_SHOPS_JSON.parent.mkdir(parents=True, exist_ok=True)
                    _write_json(DIDI_SHOPS_JSON, data)
                    total = len(shops)
                    logger.info("Didi sedes guardadas: %d en %s", total, DIDI_SHOPS_JSON.name)
                return {
                    "_is_error": False,
                    "success": success,
                    "message": data.get("errmsg", "ok") if success else data.get("errmsg", "error"),
                    "total": data.get("data", {}).get("total", 0),
                    "saved_path": str(DIDI_SHOPS_JSON) if success else None,
                    "data": data,
                }
            return {
                "_is_error": True,
                "success": False,
                "message": "No se capturó respuesta getShops (¿sesión expirada?)",
                "saved_path": None,
            }
    except Exception as e:
        logger.exception("Didi getShops: %s", e)
        return {"_is_error": True, "success": False, "message": str(e), "saved_path": None}


def _fetch_didi_daily_orders_by_shop_sync() -> dict:
    """
    Estrategia sede a sede: va a shop/select (locales + excepciones blacklist),
    selecciona cada sede y captura respuestas de b.didi-food.com:
    - bench/order/history (data.orderList: orderId, displayNum, shopId, ver DIDI_SITE_EXAMPLE.JSON)
    - bench/order/dailyOrders (data.serving + data.highlight).
    Fusiona en didi_daily_orders.json y va alimentando didi_system_map.json por sede.
    Requiere POST /didi/login y sedes en sedes_didi.json (GET /didi/shops).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"_is_error": True, "success": False, "message": "Playwright no instalado", "collected": 0}

    raw = _read_json(DIDI_SHOPS_JSON, {})
    shops_data = (raw.get("data") or {}).get("shops") or []
    blacklist = get_didi_blacklist()
    if blacklist:
        shops_data = [s for s in shops_data if str(s.get("shopId", "")) not in blacklist]
    if not shops_data:
        return {
            "_is_error": True,
            "success": False,
            "message": "No hay sedes en sedes_didi.json (ejecuta GET /didi/shops antes).",
            "collected": 0,
        }

    cookies = get_didi_cookies()
    if not cookies:
        return {"_is_error": True, "success": False, "message": "No hay cookies Didi. POST /didi/login primero.", "collected": 0}

    shop_select_url = f"{DIDI_SHOPS_URL}?needback=1&from=order"
    index = _get_didi_orders_index()
    before_count = len(index)
    today_colombia = _get_today_colombia()
    map_path = _didi_system_map_path_for_date(today_colombia)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                ignore_https_errors=True,
            )
            context.add_cookies(cookies)
            page = context.new_page()
            daily_responses: list[dict] = []
            history_responses: list[dict] = []

            def on_response(resp):
                url = resp.url or ""
                if "didi-food" not in url:
                    return
                try:
                    body = resp.json()
                    if not isinstance(body, dict):
                        return
                    if "dailyOrders" in url:
                        daily_responses.append(body)
                    if "bench/order/history" in url:
                        history_responses.append(body)
                except Exception:
                    pass

            page.on("response", on_response)
            page.goto(shop_select_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)

            total_shops = len(shops_data)
            for i, shop in enumerate(shops_data):
                shop_id = str(shop.get("shopId", ""))
                shop_name = (shop.get("shopName") or "").strip()
                if not shop_name:
                    continue
                logger.info("Didi dailyOrders: sede %s/%s %s", i + 1, total_shops, shop_name[:40])
                daily_responses.clear()
                history_responses.clear()
                try:
                    if i > 0:
                        page.goto(shop_select_url, wait_until="domcontentloaded", timeout=12000)
                        page.wait_for_timeout(1500)
                    # Cerrar modal flotante que tapa la lista de sedes (el-floating is-fullscreen)
                    try:
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(300)
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(500)
                        close_btn = page.locator(".el-floating .el-dialog__headerbtn, .el-dialog__headerbtn").first
                        if close_btn.count() > 0:
                            close_btn.click(timeout=2000)
                            page.wait_for_timeout(400)
                    except Exception:
                        pass
                    loc = page.locator(f"text={shop_name}").first
                    if loc.count() == 0:
                        loc = page.get_by_text(shop_name, exact=False).first
                    if loc.count() == 0:
                        logger.warning("Didi dailyOrders: no se encontró sede %s, saltando", shop_name[:40])
                        continue
                    loc.scroll_into_view_if_needed()
                    page.wait_for_timeout(400)
                    loc.click(timeout=15000)
                    page.wait_for_timeout(1500)
                    page.goto(DIDI_STORE_ORDER_HISTORY_URL, wait_until="domcontentloaded", timeout=12000)
                    page.wait_for_timeout(2500)
                    try:
                        page.wait_for_response(
                            lambda r: "bench/order/history" in (r.url or "") or "dailyOrders" in (r.url or ""),
                            timeout=10000,
                        )
                    except Exception:
                        pass
                    page.wait_for_timeout(1500)
                except Exception as e:
                    logger.warning("Didi dailyOrders: sede %s (%s): %s, siguiendo con la siguiente", shop_name[:30], i + 1, e)
                    continue

                for body in daily_responses:
                    data = body.get("data") or {}
                    for order in (data.get("serving") or []) + (data.get("highlight") or []):
                        if not isinstance(order, dict):
                            continue
                        oid = str(order.get("orderId") or "").strip()
                        if not oid:
                            continue
                        display = (order.get("displayNum") or "").strip()
                        index[oid] = {"orderId": oid, "displayNum": display or oid, "shopId": order.get("shopId")}
                for body in history_responses:
                    data = body.get("data") or {}
                    for order in data.get("orderList") or []:
                        if not isinstance(order, dict):
                            continue
                        oid = str(order.get("orderId") or "").strip()
                        if not oid:
                            continue
                        display = (order.get("displayNum") or "").strip()
                        index[oid] = {"orderId": oid, "displayNum": display or oid, "shopId": order.get("shopId")}
                # Guardar órdenes y alimentar el mapa tras cada sede
                if True:
                    DIDI_DAILY_ORDERS_JSON.parent.mkdir(parents=True, exist_ok=True)
                    _write_json(DIDI_DAILY_ORDERS_JSON, index)
                    order_id_to_display_inc: dict[str, str] = {}
                    for oid, obj in index.items():
                        if not oid:
                            continue
                        display = (obj.get("displayNum") or "").strip()
                        if display:
                            order_id_to_display_inc[oid] = display
                    if order_id_to_display_inc:
                        existing_map = _read_json(map_path, {})
                        if isinstance(existing_map, dict):
                            order_id_to_display_inc = {**existing_map, **order_id_to_display_inc}
                        map_path.parent.mkdir(parents=True, exist_ok=True)
                        _write_json(map_path, order_id_to_display_inc)
                    logger.info("Didi dailyOrders: sede %s guardada (%d órdenes total), mapa %d entradas", shop_name[:35], len(index), len(order_id_to_display_inc))
                # Esperar 1 minuto antes de cambiar de sede
                if i < total_shops - 1:
                    page.wait_for_timeout(60000)

            browser.close()
    except Exception as e:
        logger.exception("Didi dailyOrders por sede: %s", e)
        return {"_is_error": True, "success": False, "message": str(e), "collected": 0}

    DIDI_DAILY_ORDERS_JSON.parent.mkdir(parents=True, exist_ok=True)
    _write_json(DIDI_DAILY_ORDERS_JSON, index)

    # Actualizar el mapa orderId -> displayText (didi_system_map_YYYY-MM-DD.json) para usar en deliverys
    order_id_to_display: dict[str, str] = {}
    for oid, obj in index.items():
        if not oid:
            continue
        display = (obj.get("displayNum") or "").strip()
        if display:
            order_id_to_display[oid] = display
    applied_to_deliverys = 0
    if order_id_to_display:
        existing = _read_json(map_path, {})
        if isinstance(existing, dict):
            order_id_to_display = {**existing, **order_id_to_display}
        map_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(map_path, order_id_to_display)
        logger.info("Didi dailyOrders: mapa actualizado %s (%d orderId -> displayNum)", map_path.name, len(order_id_to_display))
        applied_to_deliverys = _apply_didi_display_to_deliverys(today_colombia, order_id_to_display)
        if applied_to_deliverys:
            logger.info("Didi dailyOrders: aplicado a deliverys %s reemplazos", applied_to_deliverys)

    collected = len(index) - before_count
    logger.info("Didi dailyOrders: guardado %s (%d órdenes, +%d esta pasada)", DIDI_DAILY_ORDERS_JSON.name, len(index), collected)
    return {"_is_error": False, "success": True, "collected": collected, "total": len(index), "shops_visited": len(shops_data), "map_updated": len(order_id_to_display), "applied_to_deliverys": applied_to_deliverys}


def _fetch_didi_order_list_sync() -> dict[str, str]:
    """
    Genera didi_system_map.json consultando el endpoint de historial de órdenes.
    - Navega a https://didi-food.com/es-CO/manager/order con cookies de inicio de sesión.
    - Captura en la red las respuestas POST a order/border/historyList (forma en didi/headers.txt).
    - La respuesta tiene la forma de didi/orders_didi_query.json (data.orderList con orderId y orderIndex.displayText).
    - Arma didi/didi_system_map.json: { orderId -> displayText } (ej. "5764659591531007003" -> "#357002").
    Requiere sesión iniciada (POST /didi/login). Por ahora solo se genera con la(s) respuesta(s) del endpoint.
    """
    import re
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {}

    cookies = get_didi_cookies()
    if not cookies:
        return {}

    order_id_to_display: dict[str, str] = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                ignore_https_errors=True,
            )
            context.add_cookies(cookies)
            page = context.new_page()
            order_list_responses: list[dict] = []
            seen_urls: list[str] = []
            order_list_endpoint_seen: list[str] = []  # URLs que devolvieron data.orderList (aunque vacía)
            all_didi_urls: list[str] = []  # Cualquier respuesta a didi-food (para diagnóstico si no llega historyList)

            def on_response_log(resp):
                url = resp.url or ""
                if "didi-food" not in url:
                    return
                all_didi_urls.append(url[:220])
                if "historyList" not in url:
                    return
                seen_urls.append(url[:200])
                try:
                    body = resp.json()
                    if not isinstance(body, dict):
                        return
                    data = body.get("data")
                    if not isinstance(data, dict):
                        return
                    order_list = data.get("orderList")
                    # Forma de didi/orders_didi_query.json: data.total, data.totalPage, data.orderList[]
                    if isinstance(order_list, list):
                        order_list_endpoint_seen.append(url[:200])
                        total = data.get("total") or 0
                        if len(order_list) > 0 and total > 0:
                            order_list_responses.append(body)
                            logger.info("Didi order list: capturada respuesta historyList con %s órdenes desde %s", len(order_list), url[:120])
                        else:
                            logger.info("Didi order list: historyList con orderList vacía o total=0 desde %s total=%s len=%s", url[:120], total, len(order_list))
                except Exception as e:
                    logger.debug("Didi order list: respuesta no JSON o sin orderList - %s", e)

            page.on("response", on_response_log)
            # Ir solo con cookies a manager/order (sin clics)
            page.goto(DIDI_MANAGER_ORDER_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)
            current = (page.url or "").lower()
            # Si la SPA redirigió a overview, forzar la ruta manager/order vía History API para que dispare historyList
            if "manager/order" not in current or "overview" in current:
                try:
                    page.evaluate(
                        "() => { history.pushState({}, '', '/es-CO/manager/order'); window.dispatchEvent(new PopStateEvent('popstate', { state: {} })); }"
                    )
                    page.wait_for_timeout(6000)
                    logger.info("Didi order list: forzada ruta /es-CO/manager/order (estaba en %s)", current[:50])
                except Exception as e:
                    logger.debug("Didi order list: pushState: %s", e)
            # Esperar vista de pedidos (no aplicar filtro de fecha para no quedar en 0 órdenes; la página usa su rango por defecto)
            try:
                page.wait_for_selector(".order-page, .order-filter, .pb-pagination", timeout=30000)
            except Exception:
                pass
            page.wait_for_timeout(5000)
            try:
                page.wait_for_response(
                    lambda r: "didi-food" in (r.url or "") and "historyList" in (r.url or ""),
                    timeout=60000,
                )
            except Exception:
                pass
            page.wait_for_timeout(5000)

            total_page = 1
            if order_list_responses:
                data0 = order_list_responses[0].get("data") or {}
                total_page = data0.get("totalPage") or 1
            total_page = max(1, int(total_page) if isinstance(total_page, (int, float)) else 1)
            logger.info("Didi order list: totalPage=%s, obteniendo todas las páginas", total_page)

            # Traer todas las páginas: clic en "siguiente" hasta total_page
            for page_num in range(2, total_page + 1):
                prev_count = len(order_list_responses)
                next_btn = page.locator("div.pb-pagination button.btn-next")
                if next_btn.count() == 0:
                    logger.info("Didi order list: no hay botón siguiente (pág %s/%s)", page_num, total_page)
                    break
                if next_btn.is_disabled():
                    logger.info("Didi order list: botón siguiente deshabilitado (pág %s/%s)", page_num, total_page)
                    break
                try:
                    next_btn.scroll_into_view_if_needed()
                    page.wait_for_timeout(500)
                    next_btn.click()
                except Exception as e:
                    logger.debug("Didi pagination: clic en siguiente (pág %s) falló: %s", page_num, e)
                    break
                try:
                    page.wait_for_response(
                        lambda r: "didi-food" in (r.url or "") and "historyList" in (r.url or ""),
                        timeout=40000,
                    )
                except Exception:
                    pass
                page.wait_for_timeout(5000)
                if len(order_list_responses) <= prev_count:
                    page.wait_for_timeout(3000)
                if len(order_list_responses) <= prev_count:
                    logger.info("Didi order list: página %s/%s no añadió respuestas nuevas", page_num, total_page)
                else:
                    logger.info("Didi order list: página %s/%s capturada (%s respuestas)", page_num, total_page, len(order_list_responses))

            if not order_list_responses and order_list_endpoint_seen:
                logger.warning("Didi order list: el endpoint devolvió orderList vacía. URLs con orderList: %s", order_list_endpoint_seen[:5])
            elif not order_list_responses and seen_urls:
                logger.warning("Didi order list: no se capturó ninguna respuesta con forma orderList. URLs historyList vistas: %s", seen_urls[:25])
            elif not order_list_responses and all_didi_urls:
                logger.warning(
                    "Didi order list: hubo respuestas didi-food pero ninguna historyList (¿redirigió a login?). URLs vistas: %s",
                    all_didi_urls[:20],
                )
            elif not order_list_responses:
                logger.warning(
                    "Didi order list: no se recibió ninguna respuesta de didi-food (¿sesión expirada? Haz POST /didi/login de nuevo)."
                )

            # Armar mapa orderId -> displayText solo para Salchimonster (excluir blacklist = Burger Monster etc.)
            blacklist = get_didi_blacklist()
            orders_list: list[dict] = []
            for resp_data in order_list_responses:
                data = resp_data.get("data") or {}
                for o in data.get("orderList") or []:
                    if not isinstance(o, dict):
                        continue
                    shop_id = str((o.get("shopInfo") or {}).get("shopId") or "")
                    if blacklist and shop_id in blacklist:
                        continue
                    oid = (o.get("orderId") or "").strip()
                    order_index = o.get("orderIndex")
                    if isinstance(order_index, dict):
                        display = (order_index.get("displayText") or "").strip()
                    else:
                        display = ""
                    if oid and display and oid not in order_id_to_display:
                        order_id_to_display[oid] = display
                        orders_list.append({"orderId": oid, "displayText": display})

            if blacklist:
                logger.info("Didi order list: filtro Salchimonster aplicado (excluir %d shopIds de blacklist)", len(blacklist))

            final_url = page.url or ""
            # Siempre guardar order_list.json con diagnóstico para saber si se llegó al endpoint
            DIDI_ORDER_LIST_JSON.parent.mkdir(parents=True, exist_ok=True)
            diagnostic = {
                "reached_url": final_url,
                "cookies_used": len(cookies),
                "historyList_responses_count": len(seen_urls),
                "all_didi_urls_count": len(all_didi_urls),
                "urls_seen_sample": seen_urls[:15],
                "order_list_endpoint_seen_sample": order_list_endpoint_seen[:5],
                "all_didi_urls_sample": all_didi_urls[:25],
            }
            payload = {
                "fetched_at": _now().isoformat(),
                "count": len(order_id_to_display),
                "order_id_to_display": order_id_to_display,
                "orders": orders_list,
                "pages_captured": len(order_list_responses),
                "diagnostic": diagnostic,
            }

            # Si no trajo nada en vivo, usar didi/orders_didi_query.json como respaldo (también filtrado Salchimonster)
            if not order_id_to_display:
                fallback_path = DIDI_SYSTEM_MAP_JSON.parent / "orders_didi_query.json"
                if fallback_path.exists():
                    try:
                        fallback_data = json.loads(fallback_path.read_text(encoding="utf-8"))
                        data_fb = (fallback_data or {}).get("data") or {}
                        for o in data_fb.get("orderList") or []:
                            if not isinstance(o, dict):
                                continue
                            shop_id_fb = str((o.get("shopInfo") or {}).get("shopId") or "")
                            if blacklist and shop_id_fb in blacklist:
                                continue
                            oid = (o.get("orderId") or "").strip()
                            order_index = o.get("orderIndex")
                            if isinstance(order_index, dict):
                                display = (order_index.get("displayText") or "").strip()
                            else:
                                display = ""
                            if oid and display:
                                order_id_to_display[oid] = display
                        if order_id_to_display:
                            _map_path = _didi_system_map_path_for_date(_get_today_colombia())
                            _map_path.parent.mkdir(parents=True, exist_ok=True)
                            _write_json(_map_path, order_id_to_display)
                            payload["from_fallback_file"] = True
                            payload["count"] = len(order_id_to_display)
                            payload["order_id_to_display"] = order_id_to_display
                            payload["orders"] = [{"orderId": k, "displayText": v} for k, v in order_id_to_display.items()]
                            logger.info("Didi order list: 0 en vivo; usado respaldo orders_didi_query.json -> %s órdenes", len(order_id_to_display))
                    except Exception as e:
                        logger.warning("Didi order list: fallback orders_didi_query.json falló: %s", e)

            # Poblar didi_system_map_YYYY-MM-DD.json siempre que haya órdenes (de live o fallback)
            if order_id_to_display:
                _map_path = _didi_system_map_path_for_date(_get_today_colombia())
                _map_path.parent.mkdir(parents=True, exist_ok=True)
                _write_json(_map_path, order_id_to_display)
                logger.info(
                    "Didi order list: guardado %s en %s y %s (%s órdenes, %s páginas)",
                    "respaldo" if payload.get("from_fallback_file") else "live",
                    _map_path.name,
                    DIDI_ORDER_LIST_JSON.name,
                    len(order_id_to_display),
                    len(order_list_responses),
                )

            _write_json(DIDI_ORDER_LIST_JSON, payload)
            browser.close()
    except Exception as e:
        logger.warning("Didi order list: %s", e)
    return order_id_to_display


def _is_didi_channel(row: dict) -> bool:
    """True si la fila es del canal Didi Food (canaldelivery_id 505)."""
    cid = (row.get("canaldelivery_id") or "").strip()
    if cid == "505":
        return True
    canal = row.get("canaldelivery")
    if isinstance(canal, dict):
        if str(canal.get("canaldelivery_id") or "").strip() == "505":
            return True
        if (canal.get("canaldelivery_descripcion") or "").strip() == "Didi Food":
            return True
    return (row.get("canaldelivery_descripcion") or "").strip() == "Didi Food"


def _apply_didi_display_to_deliverys(date_str: str, order_id_to_display: dict[str, str]) -> int:
    """
    En deliverys/{local_id}/{date_str}.json reemplaza delivery_codigolimadelivery
    (ID largo Didi) por el displayText (ej. #357002) solo en órdenes del canal Didi Food
    (canaldelivery_id 505), haciendo el cruce con el mapa orderId -> displayNum.
    Devuelve número de reemplazos hechos.
    """
    if not order_id_to_display or not DELIVERYS_CACHE_DIR.exists():
        return 0
    total_replaced = 0
    for local_dir in DELIVERYS_CACHE_DIR.iterdir():
        if not local_dir.is_dir():
            continue
        filepath = local_dir / f"{date_str}.json"
        if not filepath.exists():
            continue
        cached = _read_json(filepath, {})
        data = cached.get("data")
        if not isinstance(data, list):
            continue
        changed = False
        file_replaced = 0
        for row in data:
            if not _is_didi_channel(row):
                continue
            cod = (row.get("delivery_codigolimadelivery") or "").strip()
            if cod and cod in order_id_to_display:
                row["delivery_codigolimadelivery"] = order_id_to_display[cod]
                changed = True
                file_replaced += 1
                total_replaced += 1
        if changed:
            cached["data"] = data
            _write_json(filepath, cached)
            logger.info("Didi display: actualizado %s (%s reemplazos)", filepath.name, file_replaced)
    return total_replaced


_LOGIN_REFRESH_INTERVAL_SECONDS = 12 * 3600  # 12 horas: hacer login de nuevo para renovar sesión
_DIDI_ORDER_LIST_INTERVAL_SECONDS = 3 * 60  # 3 minutos: consultar órdenes Didi y actualizar deliverys
_DIDI_DAILY_ORDERS_INTERVAL_SECONDS = 5 * 60  # 5 minutos: captura sede a sede y aplica reemplazos (solo en horario de apertura)

_login_executor: Any = None

def _get_executor():
    """En Windows usa ProcessPoolExecutor para evitar NotImplementedError de Playwright con subprocesos en threads."""
    global _login_executor
    if _login_executor is None:
        import concurrent.futures
        if sys.platform == "win32":
            _login_executor = concurrent.futures.ProcessPoolExecutor(max_workers=2)
        else:
            _login_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    return _login_executor


async def _login_refresh_loop() -> None:
    """Cada 12 horas ejecuta login de nuevo para renovar la sesión."""
    import asyncio
    while True:
        await asyncio.sleep(_LOGIN_REFRESH_INTERVAL_SECONDS)
        logger.info("Login refresh: ejecutando login (cada 12 h)")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(_get_executor(), _do_login_sync)
            if result.get("_is_error"):
                logger.warning("Login refresh: falló - %s", result.get("message", result.get("detail", "error desconocido")))
            else:
                logger.info("Login refresh: OK, token renovado")
        except Exception as e:
            logger.warning("Login refresh: excepción - %s", e)


async def _refresh_deliverys_for_today() -> bool:
    """Actualiza pedidos del día (deliverys) para todos los locales desde la API. Devuelve True si se refrescó algo."""
    import httpx
    locales_data = _locales_list_for_iteration()
    local_ids = []
    for item in locales_data:
        lid = _locale_id(item) if isinstance(item, dict) else ""
        if lid:
            local_ids.append(lid)
    if not local_ids:
        return False
    token = get_token()
    cookies_dict = {c["name"]: c["value"] for c in get_cookies() if isinstance(c.get("name"), str) and isinstance(c.get("value"), str)}
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            fecha_hoy = _get_today_colombia()
            for i, local_id in enumerate(local_ids):
                data = await _fetch_deliverys_for_local(client, local_id, cookies_dict, token)
                _save_deliverys_for_local(local_id, data)
                if i < len(local_ids) - 1:
                    await asyncio.sleep(_DELIVERYS_DELAY_BETWEEN_LOCALS)
        _update_canales_from_deliverys_cache()
        return True
    except Exception as e:
        logger.warning("Didi: refresh deliverys antes de reemplazo - %s", e)
        return False


async def _run_didi_daily_orders_once() -> None:
    """Ejecuta una vez al arranque: actualiza deliverys del día, captura Didi y aplica reemplazos (solo si estamos en horario de apertura)."""
    if not _is_within_opening_hours():
        logger.debug("Didi daily-orders (arranque): fuera de horario, se omite")
        return
    try:
        await _refresh_deliverys_for_today()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_get_executor(), _fetch_didi_daily_orders_by_shop_sync)
        if result.get("_is_error"):
            logger.warning("Didi daily-orders (arranque): %s", result.get("message", "error"))
        else:
            n = result.get("applied_to_deliverys", 0)
            logger.info("Didi daily-orders (arranque): %s órdenes en mapa, %s reemplazos", result.get("map_updated", 0), n)
    except Exception as e:
        logger.warning("Didi daily-orders (arranque): %s", e)


async def _didi_daily_orders_scheduler_loop() -> None:
    """Cada 5 minutos actualiza deliverys del día, ejecuta captura Didi (sede a sede) y aplica reemplazos; solo en horario de apertura."""
    import asyncio
    await asyncio.sleep(90)  # espera inicial para no chocar con arranque
    while True:
        await asyncio.sleep(_DIDI_DAILY_ORDERS_INTERVAL_SECONDS)
        if not _is_within_opening_hours():
            logger.debug("Didi daily-orders: fuera de horario de apertura, se omite")
            continue
        try:
            await _refresh_deliverys_for_today()
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(_get_executor(), _fetch_didi_daily_orders_by_shop_sync)
            if result.get("_is_error"):
                logger.warning("Didi daily-orders: %s", result.get("message", "error"))
            else:
                n = result.get("applied_to_deliverys", 0)
                if n:
                    logger.info("Didi daily-orders: %s órdenes en mapa, %s reemplazos en deliverys", result.get("map_updated", 0), n)
                else:
                    logger.info("Didi daily-orders: %s órdenes en mapa", result.get("map_updated", 0))
        except Exception as e:
            logger.warning("Didi daily-orders scheduler: %s", e)


async def _didi_order_list_scheduler_loop() -> None:
    """Cada 3 minutos consulta la lista de órdenes en Didi (manager/order) y actualiza delivery_codigolimadelivery en deliverys con displayText."""
    import asyncio
    await asyncio.sleep(60)  # espera inicial 1 min para no chocar con arranque
    while True:
        await asyncio.sleep(_DIDI_ORDER_LIST_INTERVAL_SECONDS)
        try:
            loop = asyncio.get_event_loop()
            order_id_to_display = await loop.run_in_executor(_get_executor(), _fetch_didi_order_list_sync)
            if order_id_to_display:
                today = _now().strftime("%Y-%m-%d")
                n = _apply_didi_display_to_deliverys(today, order_id_to_display)
                if n:
                    logger.info("Didi order list: %s órdenes mapeadas, %s reemplazos en deliverys", len(order_id_to_display), n)
            else:
                logger.debug("Didi order list: sin datos (¿sesión expirada?)")
        except Exception as e:
            logger.warning("Didi order list scheduler: %s", e)


@app.post("/login")
async def login_with_chromium(method: str = "api"):
    """
    Login con las credenciales guardadas. Guarda las cookies de sesión.

    - **method=api** (por defecto): POST directo al API de login.
    - **method=form**: Rellena el formulario de la página (como un usuario) y hace clic en Iniciar sesión.
      Útil si el API devuelve error del servidor (Slim/PHP) y el flujo por formulario funciona.
    """
    import asyncio
    logger.info("POST /login recibido (method=%s)", method)
    worker = _do_login_form_sync if method == "form" else _do_login_sync
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_get_executor(), worker)
    except Exception as e:
        logger.exception("POST /login excepción: %s", e)
        raise

    if result.get("_is_error"):
        code = result.get("status_code", 500)
        content = {k: v for k, v in result.items() if k not in ("_is_error", "status_code", "detail")}
        if result.get("detail"):
            logger.error("Login error detail: %s", result["detail"])
            content["detail_traceback"] = result["detail"]
        logger.warning("POST /login respondiendo %s: %s", code, content.get("message", ""))
        return JSONResponse(status_code=code, content=content)
    logger.info("POST /login OK")
    return {k: v for k, v in result.items() if k != "_is_error"}


@app.get("/didi/credentials")
def read_didi_credentials():
    """Devuelve las credenciales Didi guardadas (clave enmascarada)."""
    cred = get_didi_credentials()
    out = cred.copy()
    if out.get("password"):
        out["password"] = "********"
    return out


@app.put("/didi/credentials")
def update_didi_credentials(update: DidiCredentialsUpdate):
    """Actualiza email y/o contraseña de Didi en didi_credentials.json."""
    current = get_didi_credentials()
    if update.email is not None:
        current["email"] = update.email
    if update.password is not None:
        current["password"] = update.password
    save_didi_credentials(current)
    out = current.copy()
    if out.get("password"):
        out["password"] = "********"
    return {"message": "Credenciales Didi actualizadas", "credentials": out}


@app.post("/didi/login")
async def didi_login():
    """
    Inicia sesión en Didi Food con el navegador (Playwright): correo + contraseña.
    Usa las credenciales de didi_credentials.json (por defecto admon.salchimonster@gmail.com / Didi2024).
    Guarda las cookies en didi_cookies.json para usarlas en otro proceso.
    """
    import asyncio
    logger.info("POST /didi/login recibido")
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_get_executor(), _do_didi_login_sync)
    except Exception as e:
        logger.exception("POST /didi/login excepción: %s", e)
        raise

    if result.get("_is_error"):
        return JSONResponse(
            status_code=result.get("status_code", 500),
            content={k: v for k, v in result.items() if k not in ("_is_error", "status_code")},
        )
    return {k: v for k, v in result.items() if k != "_is_error"}


@app.get("/didi/newOrders")
async def didi_new_orders():
    """
    Obtiene las órdenes nuevas de Didi Food usando Playwright con las cookies guardadas.
    Usa el navegador real para evitar 'session expired' (wsgsig y cookies correctas).
    Requiere haber hecho POST /didi/login antes.
    """
    import asyncio
    logger.info("GET /didi/newOrders recibido")
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_get_executor(), _fetch_didi_new_orders_sync)
    except Exception as e:
        logger.exception("GET /didi/newOrders excepción: %s", e)
        raise

    if result.get("_is_error"):
        return JSONResponse(status_code=500, content=result)
    return result


@app.get("/didi/shops")
async def didi_shops():
    """
    Captura las sedes Didi (getShops) con sesión iniciada, navega a shop/select
    y guarda el resultado en sedes_didi.json.
    Requiere POST /didi/login antes.
    """
    import asyncio
    logger.info("GET /didi/shops recibido")
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_get_executor(), _fetch_didi_shops_sync)
    except Exception as e:
        logger.exception("GET /didi/shops excepción: %s", e)
        raise

    if result.get("_is_error"):
        return JSONResponse(status_code=500, content=result)
    return result


def _get_didi_orders_index() -> dict:
    """Carga el índice de órdenes (formato: {orderId: {orderId, displayNum}}). Migra formato antiguo si existe."""
    raw = _read_json(DIDI_DAILY_ORDERS_JSON, {})
    if not isinstance(raw, dict):
        return {}
    if "orders" in raw:
        return {str(o.get("orderId", "")): o for o in (raw.get("orders") or []) if isinstance(o, dict) and o.get("orderId")}
    return raw


@app.get("/didi/daily-orders")
def list_didi_daily_orders():
    """Lista todas las órdenes Didi acumuladas (índice por orderId, O(1) acceso)."""
    index = _get_didi_orders_index()
    return {"count": len(index), "orders": list(index.values())}


@app.get("/didi/daily-orders-capture")
async def didi_daily_orders_capture():
    """
    Estrategia sede a sede: va a shop/select?needback=1&from=order,
    selecciona cada sede de sedes_didi.json (Salchimonster, sin blacklist),
    captura b.didi-food.com/bench/order/dailyOrders de cada una y fusiona en didi_daily_orders.json.
    Requiere POST /didi/login y sedes en sedes_didi.json (GET /didi/shops).
    """
    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_get_executor(), _fetch_didi_daily_orders_by_shop_sync)
    if result.get("_is_error"):
        return JSONResponse(status_code=500, content=result)
    return result


@app.get("/didi/daily-orders/{order_id}")
def get_didi_order(order_id: str):
    """Acceso O(1) a una orden por orderId."""
    index = _get_didi_orders_index()
    order = index.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Orden {order_id} no encontrada")
    return order


@app.get("/didi/order-list")
def didi_order_list(apply_to_deliverys: bool = False):
    """
    Devuelve el mapa orderId -> displayText desde didi_system_map_YYYY-MM-DD.json (hoy Colombia, actualizado por GET /didi/daily-orders-capture).
    Si apply_to_deliverys=true, actualiza delivery_codigolimadelivery en los JSON de deliverys de hoy.
    No usa manager/order; solo lectura del archivo generado por la captura sede a sede.
    """
    today_colombia = _get_today_colombia()
    map_path = _didi_system_map_path_for_date(today_colombia)
    order_id_to_display = _read_json(map_path, {})
    if not isinstance(order_id_to_display, dict):
        order_id_to_display = {}
    out = {"count": len(order_id_to_display), "order_id_to_display": order_id_to_display, "map_file": map_path.name}
    if apply_to_deliverys and order_id_to_display:
        n = _apply_didi_display_to_deliverys(today_colombia, order_id_to_display)
        out["applied_to_deliverys"] = n
    return out


@app.post("/didi/capture")
def didi_capture(body: DidiCaptureBody):
    """
    Recibe datos capturados por la extensión Didi Capture (getShops, newOrders).
    Guarda getShops en sedes_didi.json (con blacklist) y newOrders en didi_new_orders.json.
    """
    if not body.type or not body.data:
        return JSONResponse(status_code=400, content={"error": "Faltan type o data"})
    t = body.type.lower()
    data = body.data

    try:
        if t == "getshops":
            blacklist = get_didi_blacklist()
            shops_data = data.get("data", {}) or {}
            shops = shops_data.get("shops") or []
            if blacklist:
                shops = [s for s in shops if str(s.get("shopId", "")) not in blacklist]
                logger.info("Didi capture: getShops filtrado por blacklist, %d sedes Salchimonster", len(shops))
            out = {**data, "data": {**shops_data, "shops": shops, "total": len(shops)}}
            _write_json(DIDI_SHOPS_JSON, out)
            logger.info("Didi capture: sedes guardadas en %s (%d)", DIDI_SHOPS_JSON.name, len(shops))
        elif t == "neworders":
            _write_json(DIDI_NEW_ORDERS_JSON, data)
            logger.info("Didi capture: newOrders guardado en %s", DIDI_NEW_ORDERS_JSON.name)
        elif t == "dailyorders":
            serving = (data.get("data") or {}).get("serving") or []
            new_items = [(str(o.get("orderId", "")), {"orderId": o.get("orderId"), "displayNum": o.get("displayNum")}) for o in serving if isinstance(o, dict) and o.get("orderId")]
            if not new_items:
                return {"ok": True, "type": body.type}
            index = _get_didi_orders_index()
            for oid, order in new_items:
                if oid:
                    index[oid] = order
            _write_json(DIDI_DAILY_ORDERS_JSON, index)
            logger.info("Didi capture: dailyOrders fusionados en %s (+%d, total %d)", DIDI_DAILY_ORDERS_JSON.name, len(new_items), len(index))
        else:
            return JSONResponse(status_code=400, content={"error": f"Tipo desconocido: {body.type}"})

        return {"ok": True, "type": body.type}
    except Exception as e:
        logger.exception("Didi capture: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/cookies")
def read_cookies():
    """Lista si hay cookies guardadas (no expone valores sensibles)."""
    cookies = get_cookies()
    return {
        "count": len(cookies),
        "names": [c.get("name") for c in cookies],
    }


@app.post("/cookies/clear")
def clear_cookies():
    """Borra las cookies guardadas (útil para forzar nuevo login)."""
    save_cookies([])
    return {"message": "Cookies borradas"}


@app.get("/token")
def read_token():
    """Devuelve el token guardado (data.token del último login exitoso)."""
    token = get_token()
    if not token:
        raise HTTPException(status_code=404, detail="No hay token. Haz login primero (POST /login).")
    return {"token": token}


# --- Informe de ventas (Excel) ---

def _sanitize_path(name: str) -> str:
    """Nombre seguro para carpeta/archivo: sin caracteres inválidos."""
    if not name or not isinstance(name, str):
        return "sin_nombre"
    s = name.strip()
    for c in '\\/:*?"<>|':
        s = s.replace(c, "_")
    return s or "sin_nombre"


def _parse_fecha_to_date_str(fecha: Any) -> str | None:
    """Convierte Fecha (ej. '10-02-2026' o ISO) a 'YYYY-MM-DD'."""
    if not fecha:
        return None
    if hasattr(fecha, "strftime"):
        return fecha.strftime("%Y-%m-%d")
    s = str(fecha).strip()
    if not s:
        return None
    # DD-MM-YYYY
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# Columnas a extraer del Excel (solo filas con fecha). Nombres posibles por columna.
_REPORT_JSON_COLUMNS = [
    ("Fecha", ["Fecha", "fecha"]),
    ("Hora", ["Hora", "hora"]),
    ("Cliente", ["Cliente", "cliente"]),
    ("Local", ["Local", "local"]),
    ("Monto pagado", ["Monto pagado", "Monto pagado", "monto pagado"]),
    ("Canal de delivery", ["Canal de delivery", "canal de delivery"]),
    ("Codigo integracion", ["Codigo integracion", "Codigo integración delivery", "Codigo integración", "codigo integracion"]),
]


def _excel_row_to_json_row(row_values: list, col_indices: dict) -> dict:
    out = {}
    for key, idx in col_indices.items():
        if idx is None:
            out[key] = None
            continue
        val = row_values[idx] if idx < len(row_values) else None
        if key == "Monto pagado" and isinstance(val, (int, float)):
            out[key] = float(val)
        elif val is not None and hasattr(val, "isoformat"):
            try:
                out[key] = val.isoformat()
            except Exception:
                out[key] = str(val)
        else:
            out[key] = str(val).strip() if val is not None and str(val).strip() else None
    return out


def _extract_ventas_json_from_excel(filepath: Path) -> list[dict]:
    """Lee el Excel y devuelve lista de dicts con las columnas indicadas, solo filas con fecha."""
    import openpyxl
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active
    col_indices = {key: None for key, _ in _REPORT_JSON_COLUMNS}
    header_found = False
    out = []

    for row in ws.iter_rows(values_only=True):
        row_list = list(row) if row else []
        row_str = [str(c).strip() if c is not None else "" for c in row_list]

        if not header_found and ("Fecha" in row_str or "fecha" in row_str):
            for key, aliases in _REPORT_JSON_COLUMNS:
                for alias in aliases:
                    if alias in row_str:
                        col_indices[key] = row_str.index(alias)
                        break
            header_found = True
            continue

        if not header_found:
            continue

        idx_fecha = col_indices.get("Fecha")
        if idx_fecha is None or idx_fecha >= len(row_list):
            continue
        fecha_val = row_list[idx_fecha]
        if fecha_val is None or (isinstance(fecha_val, str) and not str(fecha_val).strip()):
            continue
        item = _excel_row_to_json_row(row_list, col_indices)
        item["Fecha"] = fecha_val.isoformat() if hasattr(fecha_val, "isoformat") else str(fecha_val).strip()
        out.append(item)

    wb.close()
    return out


def _save_filas_by_local_day_canal(filas: list[dict]) -> None:
    """
    Guarda las filas en estructura: reports/{Local}/{YYYY-MM-DD}/{Canal delivery}.json
    y actualiza locales.json y canales_delivery.json (listas sin repetir).
    """
    from collections import defaultdict
    groups = defaultdict(list)
    locales_set = set()
    canales_set = set()

    for row in filas:
        local = (row.get("Local") or "").strip() or "Sin local"
        fecha = row.get("Fecha")
        date_str = _parse_fecha_to_date_str(fecha)
        if not date_str:
            continue
        canal = (row.get("Canal de delivery") or "").strip() or "Sin canal"
        key = (local, date_str, canal)
        groups[key].append(row)
        locales_set.add(local)
        canales_set.add(canal)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    for (local, date_str, canal), rows in groups.items():
        dir_local = REPORTS_DIR / _sanitize_path(local) / date_str
        dir_local.mkdir(parents=True, exist_ok=True)
        filepath = dir_local / f"{_sanitize_path(canal)}.json"
        _write_json(filepath, rows)
        logger.info("Report: guardado %s (%s filas)", filepath, len(rows))

    # Actualizar índices: canales sin repetir; locales se fusionan (mantener id+name desde API)
    existing_locales = _locales_list_for_iteration()
    existing_names = {_locale_name(x) for x in existing_locales if _locale_name(x)}
    existing_dicts = []
    for x in existing_locales:
        if isinstance(x, dict) and x.get("name"):
            existing_dicts.append(x)
        elif isinstance(x, str) and x.strip():
            existing_dicts.append({"id": "", "name": x.strip()})
    for name in locales_set:
        if name and name not in existing_names:
            existing_dicts.append({"id": "", "name": name})
            existing_names.add(name)
    existing_dicts.sort(key=lambda x: (x.get("name") or "").lower())
    existing_canales = list(_read_json(REPORTS_CANALES_DELIVERY_JSON, []))
    all_canales = sorted(set(existing_canales) | canales_set)
    REPORTS_LOCALES_JSON.parent.mkdir(parents=True, exist_ok=True)
    _write_json(REPORTS_LOCALES_JSON, existing_dicts)
    _write_json(REPORTS_CANALES_DELIVERY_JSON, all_canales)
    logger.info("Report: índices actualizados (%s locales, %s canales)", len(existing_dicts), len(all_canales))


_REPORT_DEFAULT_PARAMS = {
    "page": "informeventasv3_informeventas",
    "type": "excel",
    "or": "L",
    "caja": "-1",
    "doc": "-1",
    "estado": "1",
    "turno": "-1",
    "ordenarDoc": "0",
    "local": "-1",
    "serie": "-1",
    "numero": "-1",
    "tipoventa": "-1",
    "filtroreservas": "-1",
    "tipoemision": "-1",
    "moneda_id": "1",
    "marca_id": "0",
    "pagina": "1",
    "complementoventa": "0",
    "registros": "20000",
    "soloAlCredito": "0",
    "ruc": "-1",
    "idmonedatc": "-1",
}

# Zona horaria Colombia para "hoy" (en Windows puede requerir pip install tzdata)
_COLOMBIA_TZ = None
if ZoneInfo:
    try:
        _COLOMBIA_TZ = ZoneInfo("America/Bogota")
    except Exception:
        pass


def _now() -> datetime:
    """Ahora en Colombia o UTC."""
    if _COLOMBIA_TZ:
        return datetime.now(_COLOMBIA_TZ)
    return datetime.utcnow()


def _get_today_colombia() -> str:
    """Fecha de hoy en Colombia (solo año-mes-día, sin hora)."""
    return _now().strftime("%Y-%m-%d")


def _didi_system_map_path_for_date(date_str: str) -> Path:
    """Ruta del mapa Didi por día: didi/didi_system_map_YYYY-MM-DD.json (evita crecimiento indefinido)."""
    return DIDI_SYSTEM_MAP_JSON.parent / f"didi_system_map_{date_str}.json"


def _parse_hhmm(s: str) -> tuple[int, int]:
    """Convierte 'HH:MM' o 'H:MM' en (hour, minute)."""
    s = (s or "").strip()
    if ":" in s:
        parts = s.split(":", 1)
        try:
            return int(parts[0].strip()) % 24, int(parts[1].strip()) % 60
        except ValueError:
            pass
    return 0, 0


def _is_within_opening_hours() -> bool:
    """
    True si la hora actual en Colombia está dentro del horario de apertura (horarios.json).
    Por defecto: 12:30 a 00:00 (medianoche). Fuera de ese horario el restaurante está cerrado.
    """
    data = _read_json(HORARIOS_JSON, {})
    if not isinstance(data, dict):
        return True
    open_at = (data.get("open_at") or "12:30").strip()
    close_at = (data.get("close_at") or "00:00").strip()
    now = _now()
    h, m = now.hour, now.minute
    open_h, open_m = _parse_hhmm(open_at)
    close_h, close_m = _parse_hhmm(close_at)
    now_minutes = h * 60 + m
    open_minutes = open_h * 60 + open_m
    close_minutes = close_h * 60 + close_m
    if close_minutes <= open_minutes:
        # Cierra a medianoche (ej. open 12:30, close 00:00): abierto si now >= open o now < close
        return now_minutes >= open_minutes or now_minutes < close_minutes
    return open_minutes <= now_minutes < close_minutes


async def _run_report_for_date(fecha: str) -> dict:
    """
    Descarga el reporte para una fecha (YYYY-MM-DD), guarda Excel y JSON por local/día/canal.
    Retorna {"success": bool, "error": str|None, "filas": int}.
    """
    import httpx
    token = get_token()
    if not token:
        return {"success": False, "error": "No hay token. Haz login (POST /login).", "filas": 0}
    f1 = f"{fecha} 00:00:00"
    f2 = f"{fecha} 23:59:59"
    name_suffix = datetime.utcnow().strftime("%d.%m.%Y_%H.%M.%S")
    report_name = f"InformeVentas_{name_suffix}"
    params = {**_REPORT_DEFAULT_PARAMS, "name": report_name, "f1": f1, "f2": f2, "token": token}
    url = f"{REPORT_URL}?{urlencode(params)}"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    cookies_dict = {c["name"]: c["value"] for c in get_cookies() if isinstance(c.get("name"), str) and isinstance(c.get("value"), str)}
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(url, cookies=cookies_dict)
    except Exception as e:
        return {"success": False, "error": str(e), "filas": 0}
    if resp.status_code != 200:
        return {"success": False, "error": f"HTTP {resp.status_code}", "filas": 0}
    ct = (resp.headers.get("content-type") or "").lower()
    is_html = "html" in ct or (len(resp.content) < 2000 and resp.content.strip()[:20].lower().startswith(b"<!doctype"))
    if is_html:
        return {"success": False, "error": "Servidor devolvió HTML (token/sesión inválidos).", "filas": 0}
    filename = f"InformeVentas_{fecha}_{fecha}.xlsx"
    filepath = REPORTS_DIR / filename
    filepath.write_bytes(resp.content)
    filas = []
    try:
        filas = _extract_ventas_json_from_excel(filepath)
        _save_filas_by_local_day_canal(filas)
        json_flat = REPORTS_DIR / filename.replace(".xlsx", ".json")
        _write_json(json_flat, filas)
    except Exception as e:
        logger.warning("Report automático: no se pudo generar JSON: %s", e)
    return {"success": True, "error": None, "filas": len(filas)}


# Estado compartido para el programador de reportes y el WebSocket
_report_scheduler_state: dict[str, Any] = {
    "next_run_at": None,  # datetime
    "status": "waiting",  # waiting | calling_report | report_ready
    "last_report_at": None,  # datetime
    "last_error": None,
    "last_filas": 0,
    "interval_seconds": 300,  # 5 min
}
_report_ws_clients: list[WebSocket] = []


async def _report_scheduler_loop() -> None:
    """Cada 5 minutos descarga el reporte del día (fecha hoy Colombia)."""
    state = _report_scheduler_state
    while True:
        now = _now()
        if state["next_run_at"] is None:
            state["next_run_at"] = now
        target = state["next_run_at"]
        if now < target:
            await asyncio.sleep(1)
            continue
        fecha = _get_today_colombia()
        state["status"] = "calling_report"
        state["last_error"] = None
        logger.info("Report automático: descargando reporte del día %s", fecha)
        result = await _run_report_for_date(fecha)
        state["last_report_at"] = _now()
        state["last_filas"] = result.get("filas", 0)
        if result.get("success"):
            state["status"] = "report_ready"
            state["last_error"] = None
            logger.info("Report automático: listo (%s filas)", state["last_filas"])
        else:
            state["status"] = "report_ready"
            state["last_error"] = result.get("error") or "Error desconocido"
            logger.warning("Report automático: falló - %s", state["last_error"])
        state["next_run_at"] = state["last_report_at"].replace(microsecond=0) + timedelta(seconds=state["interval_seconds"])
        await asyncio.sleep(1)


# --- Locales desde API (actualización cada 10 min) ---

_LOCALES_REFRESH_INTERVAL = 600  # 10 minutos


async def _fetch_and_save_locales() -> bool:
    """
    POST a getLocalesPermitidos/0 con Token token="...", parsea data[] y guarda
    en reports/locales.json como [{"id": local_id, "name": local_descripcion}, ...].
    """
    import httpx
    token = get_token()
    if not token:
        logger.debug("Locales API: no hay token, se omite actualización")
        return False
    auth_header = f'Token token="{token}"'
    REPORTS_LOCALES_JSON.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                LOCALES_API_URL,
                headers={"Authorization": auth_header},
                json={},
            )
    except Exception as e:
        logger.warning("Locales API: error de conexión - %s", e)
        return False
    if resp.status_code != 200:
        logger.warning("Locales API: HTTP %s", resp.status_code)
        return False
    try:
        body = resp.json()
    except Exception:
        logger.warning("Locales API: respuesta no es JSON")
        return False
    if body.get("tipo") == "401":
        logger.debug("Locales API: no autorizado (token inválido o expirado)")
        return False
    data = body.get("data")
    if not isinstance(data, list):
        logger.warning("Locales API: data no es lista")
        return False
    items = []
    for row in data:
        if not isinstance(row, dict):
            continue
        local_id = (row.get("local_id") or "").strip()
        local_descripcion = (row.get("local_descripcion") or "").strip()
        if not local_descripcion:
            continue
        items.append({"id": local_id, "name": local_descripcion})
    items.sort(key=lambda x: (x["name"].lower(), x["id"]))
    _write_json(REPORTS_LOCALES_JSON, items)
    logger.info("Locales API: actualizados %s locales", len(items))
    return True


async def _locales_scheduler_loop() -> None:
    """Cada 10 minutos obtiene la lista de locales desde la API y actualiza locales.json."""
    while True:
        await _fetch_and_save_locales()
        await asyncio.sleep(_LOCALES_REFRESH_INTERVAL)


_DELIVERYS_INTERVAL_SECONDS = 120  # 2 minutos
_DELIVERYS_DELAY_BETWEEN_LOCALS = 5  # segundos entre cada sede para no saturar la API
_DELIVERYS_MAX_PER_LOCAL = 100  # solo los primeros 100 resultados por sede

# Estado compartido para el scheduler de deliverys y el WebSocket /report/ws
_deliverys_scheduler_state: dict[str, Any] = {
    "next_run_at": None,
    "status": "waiting",  # waiting | calling_deliverys | deliverys_ready
    "last_report_at": None,  # datetime (nombre legacy para compat WS)
    "last_error": None,
    "last_filas": 0,  # total deliverys obtenidos en la última pasada
    "interval_seconds": _DELIVERYS_INTERVAL_SECONDS,
}


async def _deliverys_scheduler_loop() -> None:
    """Cada 2 minutos consulta obtenerDeliverysPorLocalSimple para cada local_id (fecha hoy); espera 5 s entre sedes."""
    import httpx
    state = _deliverys_scheduler_state
    while True:
        await asyncio.sleep(1)
        now = _now()
        if state["next_run_at"] is None:
            state["next_run_at"] = now
        if now < state["next_run_at"]:
            continue
        locales_data = _locales_list_for_iteration()
        local_ids = []
        for item in locales_data:
            lid = _locale_id(item) if isinstance(item, dict) else ""
            if lid:
                local_ids.append(lid)
        if not local_ids:
            state["next_run_at"] = now.replace(microsecond=0) + timedelta(seconds=_DELIVERYS_INTERVAL_SECONDS)
            await asyncio.sleep(1)
            continue
        if not _is_within_opening_hours():
            logger.debug("Deliverys scheduler: fuera de horario de apertura (restaurante cerrado), se omite")
            state["next_run_at"] = now.replace(microsecond=0) + timedelta(seconds=_DELIVERYS_INTERVAL_SECONDS)
            await asyncio.sleep(1)
            continue
        token = get_token()
        cookies_dict = {c["name"]: c["value"] for c in get_cookies() if isinstance(c.get("name"), str) and isinstance(c.get("value"), str)}
        if not token:
            logger.debug("Deliverys scheduler: sin token, se omite (haz login)")
            state["next_run_at"] = now.replace(microsecond=0) + timedelta(seconds=_DELIVERYS_INTERVAL_SECONDS)
            await asyncio.sleep(1)
            continue
        state["status"] = "calling_deliverys"
        state["last_error"] = None
        logger.info("Deliverys scheduler: consultando %s locales (fecha hoy)", len(local_ids))
        total_filas = 0
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                fecha_hoy = _get_today_colombia()
                for i, local_id in enumerate(local_ids):
                    data = await _fetch_deliverys_for_local(client, local_id, cookies_dict, token)
                    _save_deliverys_for_local(local_id, data)
                    total_filas += len(data)
                    # Notificar por WebSocket que esta sede está lista para refrescar órdenes en tiempo real
                    payload = {"type": "sede_ready", "local_id": local_id, "fecha": fecha_hoy}
                    for ws in list(_report_ws_clients):
                        try:
                            await ws.send_json(payload)
                        except Exception:
                            pass
                    if i < len(local_ids) - 1:
                        await asyncio.sleep(_DELIVERYS_DELAY_BETWEEN_LOCALS)
            _update_canales_from_deliverys_cache()
            state["status"] = "deliverys_ready"
            state["last_error"] = None
            state["last_filas"] = total_filas
            logger.info("Deliverys scheduler: listo (%s deliverys en total)", total_filas)
        except Exception as e:
            state["status"] = "deliverys_ready"
            state["last_error"] = str(e)
            logger.warning("Deliverys scheduler: error - %s", e)
        state["last_report_at"] = _now()
        state["next_run_at"] = state["last_report_at"].replace(microsecond=0) + timedelta(seconds=_DELIVERYS_INTERVAL_SECONDS)
        await asyncio.sleep(1)


def _locales_list_for_iteration() -> list[dict[str, str] | str]:
    """Devuelve la lista de locales tal como está en disco (dict con id/name o strings legacy)."""
    data = _read_json(REPORTS_LOCALES_JSON, [])
    if not isinstance(data, list):
        return []
    return data


def _locale_name(item: dict[str, str] | str) -> str:
    """Extrae el nombre del local de un ítem (dict con 'name' o string legacy)."""
    if isinstance(item, dict):
        return (item.get("name") or "").strip()
    return (item or "").strip()


@app.get("/report")
async def report_ventas(
    fecha_inicio: str = Query(..., description="Fecha inicio YYYY-MM-DD"),
    fecha_fin: str = Query(..., description="Fecha fin YYYY-MM-DD"),
):
    """
    Descarga el informe de ventas en Excel para el rango de fechas.
    Usa el token y las cookies guardadas. Guarda el archivo en la carpeta reports/ y lo devuelve.
    """
    import httpx

    token = get_token()
    if not token:
        raise HTTPException(status_code=401, detail="No hay token. Haz login primero (POST /login).")

    # Validar y formatear fechas
    try:
        d1 = datetime.strptime(fecha_inicio.strip(), "%Y-%m-%d")
        d2 = datetime.strptime(fecha_fin.strip(), "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Fechas deben ser YYYY-MM-DD (ej: 2026-02-01)")

    f1 = d1.strftime("%Y-%m-%d 00:00:00")
    f2 = d2.strftime("%Y-%m-%d 23:59:59")
    name_suffix = datetime.utcnow().strftime("%d.%m.%Y_%H.%M.%S")
    report_name = f"InformeVentas_{name_suffix}"

    params = {**_REPORT_DEFAULT_PARAMS, "name": report_name, "f1": f1, "f2": f2, "token": token}
    url = f"{REPORT_URL}?{urlencode(params)}"

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    cookies_list = get_cookies()
    cookies_dict = {c["name"]: c["value"] for c in cookies_list if isinstance(c.get("name"), str) and isinstance(c.get("value"), str)}

    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(url, cookies=cookies_dict)
    except Exception as e:
        logger.exception("Report: error de conexión %s", e)
        raise HTTPException(status_code=502, detail=f"Error al conectar con el servidor del reporte: {e}")

    if resp.status_code != 200:
        logger.warning("Report: respuesta %s", resp.status_code)
        raise HTTPException(
            status_code=502,
            detail=f"El servidor del reporte respondió {resp.status_code}. ¿Token o sesión expirados? Haz login de nuevo.",
        )

    content_type = (resp.headers.get("content-type") or "").lower()
    is_html = "html" in content_type or (len(resp.content) < 2000 and resp.content.strip()[:20].lower().startswith(b"<!doctype")) or resp.content.strip()[:10].lower().startswith(b"<html")
    if is_html:
        logger.warning("Report: respuesta HTML (posible error o login requerido)")
        raise HTTPException(
            status_code=502,
            detail="El servidor devolvió HTML en lugar de Excel (token/sesión inválidos o error del servidor).",
        )

    filename = f"InformeVentas_{fecha_inicio}_{fecha_fin}.xlsx"
    filepath = REPORTS_DIR / filename
    filepath.write_bytes(resp.content)
    logger.info("Report: guardado %s (%s bytes)", filepath, len(resp.content))

    # Extraer y guardar por carpeta: Local -> día -> archivo por canal delivery + índices
    try:
        filas = _extract_ventas_json_from_excel(filepath)
        _save_filas_by_local_day_canal(filas)
        # También guardar el JSON plano por compatibilidad (mismo nombre que el Excel)
        json_flat = REPORTS_DIR / filename.replace(".xlsx", ".json")
        _write_json(json_flat, filas)
        logger.info("Report: guardado %s (%s filas)", json_flat, len(filas))
    except Exception as e:
        logger.warning("Report: no se pudo generar JSON del Excel: %s", e)

    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/report/locales")
def get_report_locales():
    """Devuelve la lista de locales (sin repetir) registrados en los reportes."""
    data = _read_json(REPORTS_LOCALES_JSON, [])
    if not isinstance(data, list):
        return {"locales": []}
    return {"locales": data}


@app.get("/report/canales-delivery")
def get_report_canales_delivery():
    """Devuelve la lista de canales de delivery (sin repetir) registrados en los reportes."""
    data = _read_json(REPORTS_CANALES_DELIVERY_JSON, [])
    if not isinstance(data, list):
        return {"canales_delivery": []}
    return {"canales_delivery": data}


# --- Órdenes y fotos (frontend) ---

def _sanitize_codigo(codigo: str) -> str:
    """Código seguro para rutas de archivo."""
    s = (codigo or "").strip()
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in s) or "sin_codigo"


# --- Deliverys API (órdenes por local, cada 5 min; reemplaza Excel para listado) ---


def _clean_privacy_name(s: str) -> str:
    """Quita 'privacy protection' y asteriscos de nombres (ej. Didi). Deja solo la parte visible."""
    if not s or not isinstance(s, str):
        return ""
    s = s.strip()
    s = re.sub(r"privacy\s+protection\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\*+", "", s)
    return " ".join(s.split()).strip()


def _delivery_row_to_order(row: dict) -> dict:
    """Convierte un ítem de la API obtenerDeliverysPorLocalSimple al formato orden (frontend)."""
    nombres = _clean_privacy_name((row.get("delivery_nombres") or "").strip())
    apellidos = _clean_privacy_name((row.get("delivery_apellidos") or "").strip())
    if apellidos and apellidos != ".":
        cliente = f"{nombres} {apellidos}".strip()
    else:
        cliente = nombres or "—"
    canal_obj = row.get("canaldelivery") or {}
    canal = (canal_obj.get("canaldelivery_descripcion") or row.get("canaldelivery_descripcion") or "").strip() or "—"
    fecha_hora = (row.get("delivery_fecha") or "").strip()
    fecha = fecha_hora[:10] if len(fecha_hora) >= 10 else ""
    hora = fecha_hora[11:19] if len(fecha_hora) >= 19 else (fecha_hora[11:] if len(fecha_hora) > 10 else "")
    importe = (row.get("delivery_importe") or "").strip()
    try:
        monto_val = float(importe) if importe else None
    except (ValueError, TypeError):
        monto_val = None
    return {
        "Codigo integracion": (row.get("delivery_codigolimadelivery") or row.get("delivery_codigointegracion") or "").strip() or "—",
        "Cliente": cliente,
        "Canal de delivery": canal,
        "Monto pagado": importe if importe else None,
        "Fecha": fecha,
        "Hora": hora,
        "delivery_id": (row.get("delivery_id") or "").strip(),
        "delivery_identificadorunico": (row.get("delivery_identificadorunico") or "").strip(),
        "delivery_celular": (row.get("delivery_celular") or "").strip(),
    }


def _delivery_auth_header(token: str | None) -> dict[str, str]:
    """Header de autorización para la API de deliverys/reportes: Token token=\"...\"."""
    if not token:
        return {}
    return {"Authorization": f'Token token="{token}"'}


async def _fetch_deliverys_for_local(
    client: "httpx.AsyncClient",
    local_id: str,
    cookies_dict: dict[str, str],
    token: str | None,
) -> list[dict]:
    """Obtiene como máximo los primeros 100 deliverys del local (paginación 50 en 50)."""
    import httpx
    headers = _delivery_auth_header(token)
    page = 1
    page_size = 50
    offset = 0
    all_data: list[dict] = []
    while len(all_data) < _DELIVERYS_MAX_PER_LOCAL:
        url = f"{DELIVERY_API_BASE}/obtenerDeliverysPorLocalSimple/{local_id}/{page}/{page_size}/{offset}"
        try:
            resp = await client.get(url, cookies=cookies_dict, headers=headers)
        except Exception:
            break
        if resp.status_code != 200:
            break
        try:
            body = resp.json()
        except Exception:
            break
        if body.get("tipo") == "401":
            break
        data = body.get("data") if isinstance(body.get("data"), list) else []
        if not data:
            break
        all_data.extend(data)
        if len(all_data) >= _DELIVERYS_MAX_PER_LOCAL:
            all_data = all_data[:_DELIVERYS_MAX_PER_LOCAL]
            break
        if len(data) < page_size:
            break
        offset += page_size
        page += 1
    return all_data


def _migrate_old_deliverys_to_per_date() -> None:
    """Una vez: convierte deliverys/{local_id}.json antiguos a deliverys/{local_id}/{date}.json."""
    if not DELIVERYS_CACHE_DIR.exists():
        return
    for path in DELIVERYS_CACHE_DIR.iterdir():
        if not path.is_file() or path.suffix != ".json":
            continue
        local_id = path.stem
        cached = _read_json(path, {})
        data = cached.get("data") if isinstance(cached.get("data"), list) else []
        if not data:
            path.unlink()
            continue
        from collections import defaultdict
        by_date: dict[str, list[dict]] = defaultdict(list)
        for row in data:
            fecha = (row.get("delivery_fecha") or "").strip()[:10]
            if fecha:
                by_date[fecha].append(row)
        local_dir = DELIVERYS_CACHE_DIR / local_id
        local_dir.mkdir(parents=True, exist_ok=True)
        for date_str, rows in by_date.items():
            filepath = local_dir / f"{date_str}.json"
            out = {"fetched_at": cached.get("fetched_at") or _now().isoformat(), "data": rows}
            _write_json(filepath, out)
        path.unlink()
        logger.info("Deliverys: migrado %s -> %s fechas", path.name, len(by_date))


def _save_deliverys_for_local(local_id: str, data: list[dict]) -> None:
    """
    Guarda deliverys por fecha: reports/deliverys/{local_id}/{YYYY-MM-DD}.json.
    Solo agrega o actualiza órdenes con las que vienen del reporte; nunca borra
    las que ya estaban (no se reemplaza el JSON completo por el que llegó).
    """
    from collections import defaultdict
    DELIVERYS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    local_dir = DELIVERYS_CACHE_DIR / local_id
    local_dir.mkdir(parents=True, exist_ok=True)
    by_date: dict[str, list[dict]] = defaultdict(list)
    for row in data:
        fecha = (row.get("delivery_fecha") or "").strip()[:10]
        if fecha:
            by_date[fecha].append(row)
    fetched_at = _now().isoformat()
    for date_str, new_rows in by_date.items():
        filepath = local_dir / f"{date_str}.json"
        # Cargar siempre lo que ya existía (no reemplazar por el JSON que llegó)
        existing_by_id: dict[str, dict] = {}
        if filepath.exists():
            cached = _read_json(filepath, {})
            existing_list = (cached.get("data") or []) if isinstance(cached.get("data"), list) else []
            for i, r in enumerate(existing_list):
                did = (r.get("delivery_id") or "").strip()
                key = did if did else f"__existing_{i}"
                existing_by_id[key] = r
        # Solo agregar o actualizar con las nuevas; nunca borrar existentes
        for r in new_rows:
            did = (r.get("delivery_id") or "").strip()
            if did:
                existing_by_id[did] = r
            else:
                existing_by_id[f"__new_{len(existing_by_id)}"] = r
        out = {"fetched_at": fetched_at, "data": list(existing_by_id.values())}
        _write_json(filepath, out)
        logger.debug("Deliverys: fusionados %s ítems para local_id=%s fecha=%s", len(out["data"]), local_id, date_str)


def _update_canales_from_deliverys_cache() -> None:
    """Actualiza canales_delivery.json con los canales presentes en la cache de deliverys (por local/fecha)."""
    canales_set = set()
    if DELIVERYS_CACHE_DIR.exists():
        for json_file in DELIVERYS_CACHE_DIR.rglob("*.json"):
            if not json_file.is_file():
                continue
            cached = _read_json(json_file, {})
            data = cached.get("data") if isinstance(cached.get("data"), list) else []
            for row in data:
                canal_obj = row.get("canaldelivery") or {}
                desc = (canal_obj.get("canaldelivery_descripcion") or row.get("canaldelivery_descripcion") or "").strip()
                if desc:
                    canales_set.add(desc)
    if canales_set:
        existing = list(_read_json(REPORTS_CANALES_DELIVERY_JSON, []))
        all_canales = sorted(set(existing) | canales_set)
        REPORTS_CANALES_DELIVERY_JSON.parent.mkdir(parents=True, exist_ok=True)
        _write_json(REPORTS_CANALES_DELIVERY_JSON, all_canales)


def _locale_id(item: dict[str, str] | str) -> str:
    """Extrae el id del local de un ítem (dict con 'id' o vacío)."""
    if isinstance(item, dict):
        return (item.get("id") or "").strip()
    return ""


def _get_local_id_by_name(local_name: str) -> str | None:
    """Devuelve el local_id para un nombre de local (desde locales.json)."""
    for item in _locales_list_for_iteration():
        if _locale_name(item) == (local_name or "").strip():
            lid = _locale_id(item) if isinstance(item, dict) else ""
            return lid if lid else None
    return None


def _get_orders_for_local_date(local: str, fecha: str) -> list[dict]:
    """Órdenes para un local y fecha desde reports/deliverys/{local_id}/{YYYY-MM-DD}.json."""
    local_id = _get_local_id_by_name(local)
    if not local_id:
        return []
    date_str = fecha.strip()[:10]
    filepath = DELIVERYS_CACHE_DIR / local_id / f"{date_str}.json"
    if not filepath.exists():
        return []
    cached = _read_json(filepath, {})
    data = cached.get("data") if isinstance(cached.get("data"), list) else []
    return [_delivery_row_to_order(row) for row in data]


def _find_order_by_codigo(codigo: str) -> dict | None:
    """Busca una orden por código de integración o identificador único en deliverys/{local_id}/{fecha}.json."""
    cod = (codigo or "").strip().lstrip("#")
    if not cod:
        return None
    if not DELIVERYS_CACHE_DIR.exists():
        return None
    for local_dir in DELIVERYS_CACHE_DIR.iterdir():
        if not local_dir.is_dir():
            continue
        for json_file in local_dir.glob("*.json"):
            cached = _read_json(json_file, {})
            data = cached.get("data") if isinstance(cached.get("data"), list) else []
            for row in data:
                cod_lima = (row.get("delivery_codigolimadelivery") or row.get("delivery_codigointegracion") or "").strip()
                identificador = (row.get("delivery_identificadorunico") or "").strip()
                if cod_lima == cod or identificador == cod:
                    return _delivery_row_to_order(row)
    return None


def _get_fotos_for_codigo(codigo: str) -> dict:
    """Devuelve { entrega: [urls], apelacion: { canal: [urls] }, respuestas: [urls] }."""
    base = UPLOADS_DIR / _sanitize_codigo(codigo)
    out = {"entrega": [], "apelacion": {}, "respuestas": []}
    if not base.exists():
        return out
    for name in ("entrega", "respuestas"):
        folder = base / name
        if folder.is_dir():
            out[name] = [f"/api/orders/{codigo}/fotos/{name}/{f.name}" for f in folder.iterdir() if f.is_file()]
    apelacion_dir = base / "apelacion"
    if apelacion_dir.is_dir():
        for canal_dir in apelacion_dir.iterdir():
            if canal_dir.is_dir():
                out["apelacion"][canal_dir.name] = [f"/api/orders/{codigo}/fotos/apelacion/{canal_dir.name}/{f.name}" for f in canal_dir.iterdir() if f.is_file()]
    return out


def _get_no_entregadas_set() -> set[str]:
    """Lee la lista de delivery_id marcados como no entregada."""
    data = _read_json(NO_ENTREGADAS_JSON, [])
    if not isinstance(data, list):
        return set()
    return {str(x).strip() for x in data if x}


def _mark_no_entregada(delivery_id: str) -> None:
    """Marca una orden como no entregada (por delivery_id)."""
    did = (delivery_id or "").strip()
    if not did:
        return
    ids_set = _get_no_entregadas_set()
    ids_set.add(did)
    NO_ENTREGADAS_JSON.parent.mkdir(parents=True, exist_ok=True)
    _write_json(NO_ENTREGADAS_JSON, sorted(ids_set))
    logger.info("No entregada: marcado delivery_id=%s", did)


def _unmark_no_entregada(delivery_id: str) -> None:
    """Quita la marca de no entregada cuando se sube foto de entrega."""
    did = (delivery_id or "").strip()
    if not did:
        return
    ids_set = _get_no_entregadas_set()
    if did not in ids_set:
        return
    ids_set.discard(did)
    NO_ENTREGADAS_JSON.parent.mkdir(parents=True, exist_ok=True)
    _write_json(NO_ENTREGADAS_JSON, sorted(ids_set))
    logger.info("No entregada: quitada marca delivery_id=%s (foto de entrega subida)", did)


def _order_has_entrega_photo(codigo: str) -> bool:
    """True si la orden tiene al menos una foto en uploads/{codigo}/entrega/."""
    if not (codigo or "").strip() or (codigo or "").strip() == "—":
        return False
    base = UPLOADS_DIR / _sanitize_codigo(codigo) / "entrega"
    return base.is_dir() and any(base.iterdir())


# --- Apelaciones (marcar para apelar / apelar / reporte) ---

def _read_apelaciones() -> dict:
    data = _read_json(APELACIONES_JSON, {"items": []})
    if not isinstance(data, dict) or "items" not in data:
        return {"items": []}
    if not isinstance(data["items"], list):
        return {"items": []}
    return data


def _write_apelaciones(data: dict) -> None:
    APELACIONES_JSON.parent.mkdir(parents=True, exist_ok=True)
    _write_json(APELACIONES_JSON, data)


def _get_apelacion_by_codigo(codigo: str) -> dict | None:
    data = _read_apelaciones()
    cod = (codigo or "").strip()
    for item in data.get("items", []):
        if (item.get("codigo") or "").strip() == cod:
            return item
    return None


def _order_has_respuesta_foto(codigo: str) -> bool:
    """True si la orden tiene al menos una foto en respuestas (respuesta del canal)."""
    if not (codigo or "").strip():
        return False
    base = UPLOADS_DIR / _sanitize_codigo(codigo) / "respuestas"
    return base.is_dir() and any(f for f in base.iterdir() if f.is_file())


def _get_orders_for_local_date_range(local: str, fecha_desde: str, fecha_hasta: str) -> list[dict]:
    """Órdenes para un local en el rango de fechas (inclusive). Cada orden tiene Fecha del día."""
    desde = (fecha_desde or "").strip()[:10]
    hasta = (fecha_hasta or "").strip()[:10]
    if not desde or not hasta:
        return []
    if desde > hasta:
        desde, hasta = hasta, desde  # normalizar orden
    from datetime import datetime, timedelta
    try:
        d1 = datetime.strptime(desde, "%Y-%m-%d").date()
        d2 = datetime.strptime(hasta, "%Y-%m-%d").date()
    except ValueError:
        return []
    orders = []
    current = d1
    while current <= d2:
        date_str = current.strftime("%Y-%m-%d")
        day_orders = _get_orders_for_local_date(local, date_str)
        for o in day_orders:
            o["Fecha"] = date_str  # asegurar fecha del día
            orders.append(o)
        current += timedelta(days=1)
    return orders


@app.get("/api/orders")
def api_get_orders(
    local: str | None = Query(None, description="Nombre de un solo local/sede (opcional si se usa locales)"),
    locales: str | None = Query(None, description="Nombres de locales separados por coma; procesa todas las sedes en una sola petición"),
    fecha: str | None = Query(None, description="Fecha YYYY-MM-DD (un solo día); opcional si se usan fecha_desde y fecha_hasta"),
    fecha_desde: str = Query("", description="Inicio rango YYYY-MM-DD"),
    fecha_hasta: str = Query("", description="Fin rango YYYY-MM-DD"),
    exclude_marcadas_apelacion: bool = Query(False, description="Excluir órdenes ya marcadas para apelación"),
):
    """Lista órdenes. Con 'locales' se procesan todas las sedes en el backend (recomendado para marcar apelación)."""
    # Determinar lista de sedes: locales (varias) o local (una)
    sede_names: list[str] = []
    if (locales or "").strip():
        sede_names = [s.strip() for s in locales.strip().split(",") if s.strip()]
    if not sede_names and (local or "").strip():
        sede_names = [local.strip()]
    if not sede_names:
        raise HTTPException(status_code=400, detail="Indica 'local' o 'locales' (nombres separados por coma)")

    # Prioridad: rango (fecha_desde + fecha_hasta) sobre un solo día (fecha)
    use_range = (fecha_desde or "").strip() and (fecha_hasta or "").strip()
    desde = (fecha_desde or "").strip()[:10]
    hasta = (fecha_hasta or "").strip()[:10]
    f_single = (fecha or "").strip()[:10]

    orders: list[dict] = []
    for sede in sede_names:
        if use_range:
            site_orders = _get_orders_for_local_date_range(sede, desde, hasta)
        else:
            if not f_single:
                continue
            site_orders = _get_orders_for_local_date(sede, f_single)
        for o in site_orders:
            o["Local"] = sede
            o["rowKey"] = f"{sede}-{(o.get('Codigo integracion') or '').strip()}-{o.get('Fecha') or ''}"
            orders.append(o)

    if not use_range and not f_single:
        return {"orders": []}

    if exclude_marcadas_apelacion:
        apelaciones = _read_apelaciones()
        codigos_marcados = {(item.get("codigo") or "").strip() for item in apelaciones.get("items", [])}
        orders = [o for o in orders if (o.get("Codigo integracion") or "").strip() not in codigos_marcados]

    no_entregadas = _get_no_entregadas_set()
    for o in orders:
        cod = (o.get("Codigo integracion") or "").strip()
        if cod and cod != "—":
            o["has_entrega_photo"] = _order_has_entrega_photo(cod)
            fotos = _get_fotos_for_codigo(cod)
            o["fotos_entrega"] = fotos.get("entrega", [])
        else:
            o["has_entrega_photo"] = False
            o["fotos_entrega"] = []
        o["no_entregada"] = (o.get("delivery_id") or "").strip() in no_entregadas
    return {"orders": orders}


@app.get("/api/orders/by-codigo/{codigo:path}")
def api_get_order_by_codigo(codigo: str):
    """Devuelve la orden buscando por código de integración o identificador único; fotos y flags has_entrega_photo, no_entregada."""
    order = _find_order_by_codigo(codigo)
    cod_integ = (order.get("Codigo integracion") or "").strip() if order else ""
    fotos_codigo = cod_integ if (cod_integ and cod_integ != "—") else codigo
    fotos = _get_fotos_for_codigo(fotos_codigo)
    if order:
        order["has_entrega_photo"] = _order_has_entrega_photo(fotos_codigo) if fotos_codigo else False
        order["no_entregada"] = (order.get("delivery_id") or "").strip() in _get_no_entregadas_set()
    return {"order": order, "fotos": fotos}


class NoEntregadaBody(BaseModel):
    delivery_id: str


@app.post("/api/orders/no-entregada")
def api_mark_no_entregada(body: NoEntregadaBody):
    """Marca la orden como no entregada (para seguimiento del cajero)."""
    _mark_no_entregada(body.delivery_id)
    return {"ok": True, "delivery_id": body.delivery_id.strip()}


class MarcarApelacionBody(BaseModel):
    codigo: str
    canal: str
    delivery_id: str
    monto_descontado: float
    local: str = ""
    fecha: str = ""


class ApelarBody(BaseModel):
    codigo: str
    monto_devuelto: float


@app.post("/api/apelaciones/marcar")
def api_marcar_apelacion(body: MarcarApelacionBody):
    """Admin: marca una orden para apelación con el monto que nos descontó el canal."""
    data = _read_apelaciones()
    cod = (body.codigo or "").strip()
    if not cod:
        raise HTTPException(status_code=400, detail="codigo requerido")
    items = data.get("items", [])
    local = (body.local or "").strip()
    fecha = (body.fecha or "").strip()
    # Actualizar si ya existe
    for item in items:
        if (item.get("codigo") or "").strip() == cod:
            item["canal"] = (body.canal or "").strip()
            item["delivery_id"] = (body.delivery_id or "").strip()
            item["monto_descontado"] = float(body.monto_descontado) if body.monto_descontado is not None else 0
            item["fecha_marcado"] = _now().isoformat()
            item["local"] = local
            item["fecha"] = fecha
            _write_apelaciones(data)
            return {"ok": True}
    items.append({
        "codigo": cod,
        "canal": (body.canal or "").strip(),
        "delivery_id": (body.delivery_id or "").strip(),
        "monto_descontado": float(body.monto_descontado) if body.monto_descontado is not None else 0,
        "monto_devuelto": None,
        "fecha_marcado": _now().isoformat(),
        "fecha_apelado": None,
        "local": local,
        "fecha": fecha,
    })
    data["items"] = items
    _write_apelaciones(data)
    return {"ok": True}


@app.get("/api/apelaciones/pendientes")
def api_apelaciones_pendientes(
    local: str = Query(..., description="Nombre del local/sede"),
    fecha: str = Query("", description="Fecha YYYY-MM-DD (un día; opcional si usas fecha_desde/fecha_hasta)"),
    fecha_desde: str = Query("", description="Inicio rango YYYY-MM-DD"),
    fecha_hasta: str = Query("", description="Fin rango YYYY-MM-DD"),
):
    """Órdenes marcadas para apelación que aún no tienen respuesta (foto + monto_devuelto). Para la vista Apelar del user."""
    apelaciones = _read_apelaciones()
    if (fecha_desde or "").strip() and (fecha_hasta or "").strip():
        orders = _get_orders_for_local_date_range(local, fecha_desde.strip()[:10], fecha_hasta.strip()[:10])
    else:
        date_str = (fecha or "").strip()[:10] or _get_today_colombia()
        orders = _get_orders_for_local_date(local, date_str)
    codigos_marcados = {(item.get("codigo") or "").strip() for item in apelaciones.get("items", [])}
    pendientes = []
    for o in orders:
        cod = (o.get("Codigo integracion") or "").strip()
        if cod not in codigos_marcados:
            continue
        ap = _get_apelacion_by_codigo(cod)
        if not ap or ap.get("monto_devuelto") is not None:
            continue  # ya apelada
        if ap.get("descuento_confirmado"):
            continue
        if ap.get("sede_decidio_no_apelar"):
            continue  # sede decidió no apelar; va al apartado Descuentos
        o["apelacion_monto_descontado"] = ap.get("monto_descontado")
        o["apelacion_canal"] = ap.get("canal")
        fotos = _get_fotos_for_codigo(cod)
        o["fotos_entrega"] = fotos.get("entrega", [])
        pendientes.append(o)
    return {"orders": pendientes}


@app.post("/api/apelaciones/apelar")
async def api_apelar(
    codigo: str = Query(...),
    monto_devuelto: float = Query(...),
    fecha_estimada_devolucion: str = Query("", description="YYYY-MM-DD cuándo nos devolverán el dinero"),
    files: list[UploadFile] = File(default=[]),
):
    """User: sube foto de la respuesta del canal, monto que devolverán y fecha estimada de devolución."""
    cod = (codigo or "").strip()
    if not cod:
        raise HTTPException(status_code=400, detail="codigo requerido")
    ap = _get_apelacion_by_codigo(cod)
    if not ap:
        raise HTTPException(status_code=404, detail="Orden no marcada para apelación")
    if ap.get("monto_devuelto") is not None:
        raise HTTPException(status_code=400, detail="Esta orden ya fue apelada")
    data = _read_apelaciones()
    fecha_est = (fecha_estimada_devolucion or "").strip()[:10] or None
    for item in data.get("items", []):
        if (item.get("codigo") or "").strip() == cod:
            item["monto_devuelto"] = float(monto_devuelto)
            item["fecha_estimada_devolucion"] = fecha_est
            item["fecha_apelado"] = _now().isoformat()
            break
    _write_apelaciones(data)
    # Guardar fotos en respuestas
    if files:
        base = UPLOADS_DIR / _sanitize_codigo(cod) / "respuestas"
        base.mkdir(parents=True, exist_ok=True)
        for f in files:
            if f.filename:
                safe_name = _sanitize_path(f.filename) or "file"
                content = await f.read()
                (base / safe_name).write_bytes(content)
    return {"ok": True}


class NoApelarBody(BaseModel):
    codigo: str


@app.post("/api/apelaciones/no-apelar")
def api_no_apelar(body: NoApelarBody):
    """La sede decide no apelar: no se descuenta de una, pasa al apartado Descuentos con etiqueta 'La sede decidió no apelar'."""
    cod = (body.codigo or "").strip()
    if not cod:
        raise HTTPException(status_code=400, detail="codigo requerido")
    ap = _get_apelacion_by_codigo(cod)
    if not ap:
        raise HTTPException(status_code=404, detail="Orden no encontrada en apelaciones")
    if ap.get("monto_devuelto") is not None:
        raise HTTPException(status_code=400, detail="Esta orden ya fue apelada")
    data = _read_apelaciones()
    for item in data.get("items", []):
        if (item.get("codigo") or "").strip() == cod:
            item["sede_decidio_no_apelar"] = True
            break
    _write_apelaciones(data)
    return {"ok": True}


@app.get("/api/apelaciones/reembolsos-pendientes")
def api_reembolsos_pendientes(
    local: str = Query("", description="Filtrar por local"),
    fecha_desde: str = Query("", description="YYYY-MM-DD"),
    fecha_hasta: str = Query("", description="YYYY-MM-DD"),
):
    """Órdenes apeladas (con monto_devuelto) que aún no están marcadas como reembolsadas."""
    apelaciones = _read_apelaciones()
    items = [i for i in apelaciones.get("items", []) if i.get("monto_devuelto") is not None and i.get("reembolsado") is not True]
    if local:
        items = [i for i in items if (i.get("local") or "").strip() == local.strip()]
    if fecha_desde:
        items = [i for i in items if (i.get("fecha") or "") >= fecha_desde]
    if fecha_hasta:
        items = [i for i in items if (i.get("fecha") or "") <= fecha_hasta]
    return {"items": items}


class ReembolsarBody(BaseModel):
    codigo: str
    mismo_valor: bool = True  # True = nos devolvieron monto_devuelto; False = valor diferente
    monto_reembolsado: float | None = None  # Solo si mismo_valor=False
    fecha_reembolso: str = ""  # YYYY-MM-DD


@app.post("/api/apelaciones/reembolsar")
def api_reembolsar(body: ReembolsarBody):
    """Marca la orden como reembolsada."""
    cod = (body.codigo or "").strip()
    if not cod:
        raise HTTPException(status_code=400, detail="codigo requerido")
    ap = _get_apelacion_by_codigo(cod)
    if not ap:
        raise HTTPException(status_code=404, detail="Orden no encontrada en apelaciones")
    if ap.get("monto_devuelto") is None:
        raise HTTPException(status_code=400, detail="La orden no tiene monto_devuelto")
    if ap.get("reembolsado"):
        raise HTTPException(status_code=400, detail="Esta orden ya fue marcada como reembolsada")
    monto = float(ap.get("monto_devuelto", 0)) if body.mismo_valor else (float(body.monto_reembolsado or 0))
    data = _read_apelaciones()
    for item in data.get("items", []):
        if (item.get("codigo") or "").strip() == cod:
            item["reembolsado"] = True
            item["fecha_reembolso"] = (body.fecha_reembolso or "").strip()[:10] or _now().strftime("%Y-%m-%d")
            item["monto_reembolsado"] = monto
            item["mismo_valor"] = body.mismo_valor
            break
    _write_apelaciones(data)
    return {"ok": True}


def _calcular_perdida(item: dict) -> float:
    """Perdida = monto_descontado - lo que nos devolvieron (monto_reembolsado si reembolsado, else monto_devuelto)."""
    descontado = float(item.get("monto_descontado") or 0)
    if item.get("reembolsado"):
        devuelto = float(item.get("monto_reembolsado") or 0)
    else:
        devuelto = float(item.get("monto_devuelto") or 0) if item.get("monto_devuelto") is not None else 0
    return max(0, descontado - devuelto)


@app.get("/api/apelaciones/estado-admin")
def api_apelaciones_estado_admin(
    local: str = Query("", description="Filtrar por sede"),
    fecha_desde: str = Query("", description="YYYY-MM-DD"),
    fecha_hasta: str = Query("", description="YYYY-MM-DD"),
):
    """Admin: estado de todas las apelaciones (pendiente apelar, apelada, reembolsada, descuento confirmado)."""
    apelaciones = _read_apelaciones()
    items = []
    for item in apelaciones.get("items", []):
        if local and (item.get("local") or "").strip() != local.strip():
            continue
        if fecha_desde and (item.get("fecha") or "") < fecha_desde:
            continue
        if fecha_hasta and (item.get("fecha") or "") > fecha_hasta:
            continue
        out = dict(item)
        perdida = _calcular_perdida(item)
        out["perdida"] = round(perdida, 2)
        # Lista de estados: reembolso, descuento, y siempre mostrar "La sede decidió no apelar" si aplica
        estados = []
        if item.get("reembolsado"):
            estados.append("reembolsada")
        if item.get("descuento_confirmado"):
            estados.append("descuento_confirmado")
        if item.get("sede_decidio_no_apelar"):
            estados.append("sede_decidio_no_apelar")
        if not estados:
            if item.get("monto_devuelto") is not None:
                estados = ["apelada"]
            else:
                estados = ["pendiente_apelar"]
        out["estados"] = estados
        out["estado"] = estados[-1]  # último para compatibilidad y orden por defecto
        items.append(out)
    return {"items": items}


@app.get("/api/apelaciones/descuentos")
def api_apelaciones_descuentos(
    local: str = Query("", description="Filtrar por sede"),
    fecha_desde: str = Query("", description="YYYY-MM-DD"),
    fecha_hasta: str = Query("", description="YYYY-MM-DD"),
    solo_pendientes: bool = Query(True, description="Solo pendientes de confirmar descuento en nómina"),
    solo_confirmados: bool = Query(False, description="Solo ya descontados en nómina (para que la sede vea sus descuentos)"),
):
    """Órdenes con pérdida a descontar a la sede. Incluye las que la sede decidió no apelar (sede_decidio_no_apelar) y las apeladas con pérdida. El admin debe marcar 'Confirmar descuento en nómina' cuando realmente descuente el dinero."""
    apelaciones = _read_apelaciones()
    items = []
    for item in apelaciones.get("items", []):
        perdida = _calcular_perdida(item)
        if perdida <= 0:
            continue
        if local and (item.get("local") or "").strip() != local.strip():
            continue
        if fecha_desde and (item.get("fecha") or "") < fecha_desde:
            continue
        if fecha_hasta and (item.get("fecha") or "") > fecha_hasta:
            continue
        if solo_confirmados:
            if not item.get("descuento_confirmado"):
                continue
        elif solo_pendientes and item.get("descuento_confirmado"):
            continue
        out = dict(item)
        out["perdida"] = round(perdida, 2)
        items.append(out)
    return {"items": items}


class ConfirmarDescuentoBody(BaseModel):
    codigo: str


@app.post("/api/apelaciones/confirmar-descuento")
def api_confirmar_descuento(body: ConfirmarDescuentoBody):
    """Marca que ya se descontó en nómina a la sede por esta pérdida."""
    cod = (body.codigo or "").strip()
    if not cod:
        raise HTTPException(status_code=400, detail="codigo requerido")
    ap = _get_apelacion_by_codigo(cod)
    if not ap:
        raise HTTPException(status_code=404, detail="Orden no encontrada en apelaciones")
    perdida = _calcular_perdida(ap)
    if perdida <= 0:
        raise HTTPException(status_code=400, detail="Esta orden no tiene pérdida a descontar")
    data = _read_apelaciones()
    for item in data.get("items", []):
        if (item.get("codigo") or "").strip() == cod:
            item["descuento_confirmado"] = True
            item["fecha_descuento_confirmado"] = _now().strftime("%Y-%m-%d")
            break
    _write_apelaciones(data)
    return {"ok": True}


@app.get("/api/informes")
def api_informes(
    fecha_desde: str = Query(..., description="YYYY-MM-DD"),
    fecha_hasta: str = Query(..., description="YYYY-MM-DD"),
):
    """Métricas y series para la sección Reportes: órdenes, apelaciones, reembolsos, pérdida por día/sede/canal."""
    desde = (fecha_desde or "").strip()[:10]
    hasta = (fecha_hasta or "").strip()[:10]
    if not desde or not hasta:
        raise HTTPException(status_code=400, detail="fecha_desde y fecha_hasta requeridos (YYYY-MM-DD)")
    from collections import defaultdict

    # Órdenes por día, sede y canal (desde cache deliverys)
    ordenes_por_dia: dict[str, int] = defaultdict(int)
    ordenes_por_sede: dict[str, int] = defaultdict(int)
    ordenes_por_canal: dict[str, int] = defaultdict(int)
    locales_data = _locales_list_for_iteration()
    total_ordenes = 0
    for item in locales_data:
        local_id = _locale_id(item) if isinstance(item, dict) else ""
        local_name = _locale_name(item)
        if not local_id:
            continue
        local_dir = DELIVERYS_CACHE_DIR / local_id
        if not local_dir.is_dir():
            continue
        for json_file in sorted(local_dir.glob("*.json")):
            date_str = json_file.stem
            if date_str < desde or date_str > hasta:
                continue
            cached = _read_json(json_file, {})
            data = cached.get("data") if isinstance(cached.get("data"), list) else []
            for row in data:
                order = _delivery_row_to_order(row)
                cod = (order.get("Codigo integracion") or "").strip()
                if not cod or cod == "—":
                    continue
                total_ordenes += 1
                ordenes_por_dia[date_str] += 1
                ordenes_por_sede[local_name] += 1
                canal = (order.get("Canal de delivery") or "").strip() or "—"
                ordenes_por_canal[canal] += 1

    # Apelaciones en rango: totales y por día/sede/canal
    apelaciones = _read_apelaciones()
    items_ap = [i for i in apelaciones.get("items", []) if (i.get("fecha") or "") >= desde and (i.get("fecha") or "") <= hasta]
    apelaciones_por_dia: dict[str, int] = defaultdict(int)
    apelaciones_por_sede: dict[str, int] = defaultdict(int)
    apelaciones_por_canal: dict[str, int] = defaultdict(int)
    reembolsos_por_dia: dict[str, int] = defaultdict(int)
    perdida_por_dia: dict[str, float] = defaultdict(float)
    perdida_por_sede: dict[str, float] = defaultdict(float)
    perdida_por_canal: dict[str, float] = defaultdict(float)
    total_descontado = 0.0
    total_devuelto = 0.0
    total_reembolsos = 0
    for i in items_ap:
        f = (i.get("fecha") or "")[:10]
        loc = (i.get("local") or "").strip() or "—"
        can = (i.get("canal") or "").strip() or "—"
        apelaciones_por_dia[f] += 1
        apelaciones_por_sede[loc] += 1
        apelaciones_por_canal[can] += 1
        perd = _calcular_perdida(i)
        perdida_por_dia[f] += perd
        perdida_por_sede[loc] += perd
        perdida_por_canal[can] += perd
        total_descontado += float(i.get("monto_descontado") or 0)
        if i.get("monto_devuelto") is not None:
            total_devuelto += float(i.get("monto_devuelto") or 0)
        if i.get("reembolsado"):
            total_reembolsos += 1
            reembolsos_por_dia[f] += 1
    total_perdido = round(total_descontado - total_devuelto, 2)
    total_descontado = round(total_descontado, 2)
    total_devuelto = round(total_devuelto, 2)

    # Fechas en rango para por_dia
    start = datetime.strptime(desde, "%Y-%m-%d").date()
    end = datetime.strptime(hasta, "%Y-%m-%d").date()
    por_dia = []
    d = start
    while d <= end:
        key = d.strftime("%Y-%m-%d")
        por_dia.append({
            "fecha": key,
            "ordenes": ordenes_por_dia.get(key, 0),
            "apelaciones": apelaciones_por_dia.get(key, 0),
            "reembolsos": reembolsos_por_dia.get(key, 0),
            "perdida": round(perdida_por_dia.get(key, 0), 2),
        })
        d += timedelta(days=1)

    por_sede = [
        {
            "local": loc,
            "ordenes": ordenes_por_sede.get(loc, 0),
            "apelaciones": apelaciones_por_sede.get(loc, 0),
            "perdida": round(perdida_por_sede.get(loc, 0), 2),
        }
        for loc in sorted(set(ordenes_por_sede) | set(apelaciones_por_sede))
    ]
    por_canal = [
        {
            "canal": can,
            "ordenes": ordenes_por_canal.get(can, 0),
            "apelaciones": apelaciones_por_canal.get(can, 0),
            "perdida": round(perdida_por_canal.get(can, 0), 2),
        }
        for can in sorted(set(ordenes_por_canal) | set(apelaciones_por_canal))
    ]

    return {
        "resumen": {
            "total_ordenes": total_ordenes,
            "total_apelaciones": len(items_ap),
            "total_reembolsos": total_reembolsos,
            "total_descontado_canal": total_descontado,
            "total_devuelto": total_devuelto,
            "total_perdida": total_perdido,
        },
        "por_dia": por_dia,
        "por_sede": por_sede,
        "por_canal": por_canal,
    }


@app.get("/api/apelaciones/reporte")
def api_apelaciones_reporte(
    local: str = Query("", description="Filtrar por local"),
    fecha_desde: str = Query("", description="YYYY-MM-DD"),
    fecha_hasta: str = Query("", description="YYYY-MM-DD"),
):
    """Reporte: total descontado, devuelto y perdido."""
    apelaciones = _read_apelaciones()
    items = apelaciones.get("items", [])
    if local:
        items = [i for i in items if (i.get("local") or "").strip() == local.strip()]
    if fecha_desde:
        items = [i for i in items if (i.get("fecha") or "") >= fecha_desde]
    if fecha_hasta:
        items = [i for i in items if (i.get("fecha") or "") <= fecha_hasta]
    total_descontado = sum(float(item.get("monto_descontado") or 0) for item in items)
    total_devuelto = sum(float(item.get("monto_devuelto") or 0) for item in items if item.get("monto_devuelto") is not None)
    total_perdido = total_descontado - total_devuelto
    return {
        "total_descontado": round(total_descontado, 2),
        "total_devuelto": round(total_devuelto, 2),
        "total_perdido": round(total_perdido, 2),
        "items": items,
    }


@app.get("/api/reporte-maestro")
def api_reporte_maestro(
    local: str = Query("", description="Filtrar por sede (vacío = todas)"),
    fecha_desde: str = Query(..., description="YYYY-MM-DD"),
    fecha_hasta: str = Query(..., description="YYYY-MM-DD"),
):
    """Admin: reporte maestro con órdenes + apelaciones + fotos (entrega, respuestas) + reembolsos + descuentos."""
    desde = (fecha_desde or "").strip()[:10]
    hasta = (fecha_hasta or "").strip()[:10]
    if not desde or not hasta:
        raise HTTPException(status_code=400, detail="fecha_desde y fecha_hasta requeridos (YYYY-MM-DD)")
    locales_data = _locales_list_for_iteration()
    apelaciones = _read_apelaciones()
    apelaciones_by_cod = {(a.get("codigo") or "").strip(): a for a in apelaciones.get("items", []) if (a.get("codigo") or "").strip()}
    rows = []
    for item in locales_data:
        local_id = _locale_id(item) if isinstance(item, dict) else ""
        local_name = _locale_name(item)
        if not local_id:
            continue
        if local and local_name != local.strip():
            continue
        local_dir = DELIVERYS_CACHE_DIR / local_id
        if not local_dir.is_dir():
            continue
        for json_file in sorted(local_dir.glob("*.json")):
            date_str = json_file.stem
            if date_str < desde or date_str > hasta:
                continue
            cached = _read_json(json_file, {})
            data = cached.get("data") if isinstance(cached.get("data"), list) else []
            for row in data:
                order = _delivery_row_to_order(row)
                cod = (order.get("Codigo integracion") or "").strip()
                if not cod or cod == "—":
                    continue
                ap = apelaciones_by_cod.get(cod)
                fotos = _get_fotos_for_codigo(cod)
                perdida = round(_calcular_perdida(ap), 2) if ap else 0
                estados_apel = []
                if ap:
                    if ap.get("reembolsado"):
                        estados_apel.append("reembolsada")
                    if ap.get("descuento_confirmado"):
                        estados_apel.append("descuento_confirmado")
                    if not estados_apel:
                        if ap.get("sede_decidio_no_apelar"):
                            estados_apel = ["sede_decidio_no_apelar"]
                        elif ap.get("monto_devuelto") is not None:
                            estados_apel = ["apelada"]
                        else:
                            estados_apel = ["pendiente_apelar"]
                r = {
                    "local": local_name,
                    "fecha": date_str,
                    "codigo": cod,
                    "canal": order.get("Canal de delivery"),
                    "cliente": order.get("Cliente"),
                    "monto_pagado": order.get("Monto pagado"),
                    "hora": order.get("Hora"),
                    "delivery_id": order.get("delivery_id"),
                    "has_entrega_photo": _order_has_entrega_photo(cod),
                    "fotos_entrega": fotos.get("entrega", []),
                    "fotos_apelacion": fotos.get("apelacion", {}),
                    "fotos_respuestas": fotos.get("respuestas", []),
                    "apelacion": {
                        "monto_descontado": ap.get("monto_descontado"),
                        "monto_devuelto": ap.get("monto_devuelto"),
                        "monto_reembolsado": ap.get("monto_reembolsado"),
                        "fecha_apelado": ap.get("fecha_apelado"),
                        "fecha_estimada_devolucion": ap.get("fecha_estimada_devolucion"),
                        "reembolsado": ap.get("reembolsado"),
                        "fecha_reembolso": ap.get("fecha_reembolso"),
                        "descuento_confirmado": ap.get("descuento_confirmado"),
                        "fecha_descuento_confirmado": ap.get("fecha_descuento_confirmado"),
                        "fecha_marcado": ap.get("fecha_marcado"),
                        "sede_decidio_no_apelar": ap.get("sede_decidio_no_apelar"),
                    } if ap else None,
                    "estados_apelacion": estados_apel,
                    "estado_apelacion": estados_apel[-1] if estados_apel else "",
                    "perdida": perdida,
                }
                rows.append(r)
    rows.sort(key=lambda x: (x.get("fecha") or "", x.get("local") or "", x.get("codigo") or ""))
    return {"rows": rows}


@app.get("/api/orders/{codigo:path}/fotos")
def api_get_fotos(codigo: str):
    """Fotos de la orden agrupadas: entrega, apelación (por canal), respuestas."""
    return _get_fotos_for_codigo(codigo)


@app.post("/api/orders/{codigo:path}/fotos")
async def api_upload_fotos(
    codigo: str,
    group: str = Query(..., description="entrega | apelacion | respuestas"),
    canal: str = Query("", description="Canal de venta (para group=apelacion)"),
    files: list[UploadFile] = File(default=[]),
):
    """Sube fotos para una orden. group=entrega|apelacion|respuestas; canal solo para apelacion."""
    if group not in ("entrega", "apelacion", "respuestas"):
        raise HTTPException(status_code=400, detail="group debe ser entrega, apelacion o respuestas")
    if not files:
        raise HTTPException(status_code=400, detail="Envía al menos un archivo")
    base = UPLOADS_DIR / _sanitize_codigo(codigo)
    if group == "apelacion":
        canal_safe = _sanitize_path(canal) if canal else "general"
        base = base / "apelacion" / canal_safe
    else:
        base = base / group
    base.mkdir(parents=True, exist_ok=True)
    saved = []
    max_file_size = 50 * 1024 * 1024  # 50 MB por archivo (alineado con nginx client_max_body_size)
    for f in files:
        if not f.filename:
            continue
        content = await f.read()
        if len(content) > max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"Archivo '{f.filename}' demasiado grande. Máximo 50 MB por imagen.",
            )
        safe_name = _sanitize_path(f.filename) or "file"
        path = base / safe_name
        path.write_bytes(content)
        saved.append(safe_name)
    if group == "entrega" and saved:
        order = _find_order_by_codigo(codigo)
        if order:
            did = (order.get("delivery_id") or "").strip()
            if did:
                _unmark_no_entregada(did)
    return {"saved": saved, "group": group, "canal": canal or None}


def _foto_path(codigo: str, group: str, path_rest: str) -> Path:
    """Ruta física del archivo de foto. path_rest = filename (entrega/respuestas) o canal/filename (apelacion)."""
    base = UPLOADS_DIR / _sanitize_codigo(codigo)
    if group == "apelacion":
        return base / "apelacion" / path_rest
    return base / group / path_rest


@app.get("/api/orders/{codigo:path}/fotos/{group}/{path_rest:path}")
def api_serve_foto(codigo: str, group: str, path_rest: str):
    """Sirve un archivo de foto. path_rest = filename (entrega/respuestas) o canal/filename (apelacion)."""
    path = _foto_path(codigo, group, path_rest)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(path)


@app.delete("/api/orders/{codigo:path}/fotos/{group}/{path_rest:path}")
def api_delete_foto(codigo: str, group: str, path_rest: str):
    """Elimina un archivo de foto de la orden."""
    path = _foto_path(codigo, group, path_rest)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    path.unlink()
    return {"deleted": path_rest}


def _report_status_payload() -> dict:
    """Construye el objeto de estado para el WebSocket (datos desde API deliverys cada 5 min)."""
    state = _deliverys_scheduler_state
    now = _now()
    next_at = state.get("next_run_at")
    status = state.get("status", "waiting")
    last_at = state.get("last_report_at")
    last_error = state.get("last_error")
    last_filas = state.get("last_filas", 0)
    interval = state.get("interval_seconds", 300)

    if next_at is None:
        seconds_until_next = 0
        message = "Iniciando... Próxima consulta deliverys en breve."
    elif status == "calling_deliverys":
        seconds_until_next = interval
        message = "Llamando API deliverys (fecha hoy, todos los locales)..."
    elif status == "deliverys_ready":
        delta = (next_at - now).total_seconds()
        seconds_until_next = max(0, int(delta))
        if last_error:
            message = f"Última consulta deliverys: error ({last_error}). Próxima en {seconds_until_next} s."
        else:
            message = f"Deliverys listos ({last_filas} registros). Próxima consulta en {seconds_until_next} s."
    else:
        delta = (next_at - now).total_seconds()
        seconds_until_next = max(0, int(delta))
        message = f"Próxima consulta deliverys en {seconds_until_next} s."

    return {
        "status": status,
        "message": message,
        "seconds_until_next": seconds_until_next,
        "next_run_at": next_at.isoformat() if next_at and hasattr(next_at, "isoformat") else None,
        "last_report_at": last_at.isoformat() if last_at and hasattr(last_at, "isoformat") else None,
        "last_error": last_error,
        "last_filas": last_filas,
        "interval_seconds": interval,
    }


@app.websocket("/report/ws")
async def report_status_websocket(websocket: WebSocket):
    """
    WebSocket para seguir en tiempo real el programador de reportes.
    Envía cada segundo: estado, mensaje, segundos hasta la próxima consulta,
    cuándo se llamó el reporte y cuándo estará listo/siguiente consulta.
    """
    await websocket.accept()
    _report_ws_clients.append(websocket)
    try:
        while True:
            payload = _report_status_payload()
            await websocket.send_json(payload)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _report_ws_clients:
            _report_ws_clients.remove(websocket)
