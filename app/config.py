"""Paths for credentials and cookies (relative to project root)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_FILE = ROOT / "credentials.json"
COOKIES_FILE = ROOT / "cookies.json"
TOKEN_FILE = ROOT / "token.json"

LOGIN_URL = "http://salchimonster.restaurant.pe/restaurant/#!/login"
LOGIN_API_URL = "http://salchimonster.restaurant.pe/restaurant/m/rest/usuario/login"

REPORT_URL = "http://salchimonster.restaurant.pe/restaurant/api/reports/report.php"
LOCALES_API_URL = "http://salchimonster.restaurant.pe/restaurant/api/rest/local/getLocalesPermitidos/0"
REPORTS_DIR = ROOT / "reports"
REPORTS_LOCALES_JSON = REPORTS_DIR / "locales.json"
REPORTS_CANALES_DELIVERY_JSON = REPORTS_DIR / "canales_delivery.json"
# API deliverys por local (cada 5 min); cache: reports/deliverys/{local_id}.json
DELIVERY_API_BASE = "http://salchimonster.restaurant.pe/restaurant/api/rest/delivery"
DELIVERYS_CACHE_DIR = REPORTS_DIR / "deliverys"
UPLOADS_DIR = ROOT / "uploads"  # fotos por orden: uploads/{codigo_integracion}/{entrega|apelacion|respuestas}/
NO_ENTREGADAS_JSON = REPORTS_DIR / "no_entregadas.json"  # lista de delivery_id marcados como no entregada
# Horarios de apertura (hora Colombia): solo se consultan órdenes dentro de este horario
HORARIOS_JSON = REPORTS_DIR / "horarios.json"
