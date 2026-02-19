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
APELACIONES_JSON = REPORTS_DIR / "apelaciones.json"  # {items: [{codigo, canal, monto_descontado, monto_devuelto?, ...}]}
# Horarios de apertura (hora Colombia): solo se consultan órdenes dentro de este horario
HORARIOS_JSON = REPORTS_DIR / "horarios.json"

# Didi Food: login por navegador (correo + contraseña)
# URL con country_id=170, lang=es-MX (usar la misma URL que abre Didi en el navegador)
DIDI_LOGIN_URL = (
    "https://page.didiglobal.com/public-biz/pc-login/3.0.1/index.html"
    "?source=70001&appid=50002&role=13&country_id=170&lang=es-MX"
    "&redirectUrl=https%3A%2F%2Fb.didi-food.com%2Fpassport%2Fpassport%2FsetCookieV2"
    "%3FjumpPage%3Dhttps%253A%252F%252Fdidi-food.com%252Fes-CO%252Fstore%252Fpc%252F"
)
DIDI_CREDENTIALS_FILE = ROOT / "didi_credentials.json"
DIDI_COOKIES_FILE = ROOT / "didi_cookies.json"
DIDI_STORE_URL = "https://didi-food.com/es-CO/store/pc/"  # URL tras login, establece sesión en b.didi-food.com
DIDI_SHOPS_URL = "https://didi-food.com/es-CO/store/pc/shop/select"  # página de selección de sedes (locales + excepciones blacklist)
DIDI_STORE_ORDER_HISTORY_URL = "https://didi-food.com/es-CO/store/pc/order/history"  # historial por sede; al elegir sede se pide dailyOrders
DIDI_SHOPS_JSON = ROOT / "sedes_didi.json"  # respuesta de b.didi-food.com/auth/getShops
DIDI_NEW_ORDERS_JSON = ROOT / "didi_new_orders.json"  # respuesta de b.didi-food.com/bench/order/newOrders
DIDI_DAILY_ORDERS_JSON = ROOT / "didi_daily_orders.json"  # respuesta de b.didi-food.com/bench/order/dailyOrders
DIDI_BLACKLIST_FILE = ROOT / "sedes_didi_blacklist.json"  # shopId a excluir (sedes que NO son Salchimonster)
DIDI_MANAGER_ORDER_URL = "https://didi-food.com/es-CO/manager/order"  # con cookies de login; el SPA hace POST a b.didi-food.com/order/border/historyList (didi/headers.txt), respuesta como orders_didi_query.json -> didi_system_map.json
DIDI_ORDER_LIST_JSON = REPORTS_DIR / "didi" / "order_list.json"  # última consulta manager/order (para ver qué trae Didi)
DIDI_SYSTEM_MAP_JSON = ROOT / "didi" / "didi_system_map.json"  # mapa orderId (largo) -> displayText (#357002) actualizado cada 3 min
