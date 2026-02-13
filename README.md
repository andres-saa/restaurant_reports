# Restaurant Scraper Login (FastAPI + Chromium)

API para hacer login en **salchimonster.restaurant.pe** usando Chromium (Playwright). Las credenciales se guardan en un JSON local y las cookies de sesión se persisten para reutilizar.

## Instalación

```bash
cd c:\Users\Ludi\Desktop\restaurantScrepper
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

## Ejecutar

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Documentación: **http://localhost:8000/docs**

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET`  | `/` | Info de la API |
| `GET`  | `/credentials` | Ver credenciales guardadas (clave ofuscada) |
| `PUT`  | `/credentials` | Actualizar credenciales (body JSON) |
| `POST` | `/login` | Hacer login con Chromium y guardar cookies |
| `GET`  | `/cookies` | Ver si hay cookies de sesión guardadas |
| `POST` | `/cookies/clear` | Borrar cookies guardadas |

## Credenciales

Por defecto se usan las de `credentials.json`. Para actualizarlas:

```bash
curl -X PUT http://localhost:8000/credentials -H "Content-Type: application/json" -d "{\"usuario_nick\": \"tu@email.com\", \"usuario_clave\": \"tu_clave\"}"
```

Campos que puedes enviar en `PUT /credentials`: `usuario_nick`, `usuario_clave`, `usuario_recordar`, `local_id`, `turno_id`, `caja_id`, `app`.

## Cookies

Tras un login exitoso, las cookies se guardan en `cookies.json`. En el siguiente `POST /login` se cargan automáticamente antes de hacer el nuevo login (útil si el sitio acepta sesión previa). Para forzar un login limpio, usa `POST /cookies/clear` y luego `POST /login`.
