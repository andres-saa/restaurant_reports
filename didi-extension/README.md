# Didi Food Capture - Extensión de navegador

Captura automáticamente las respuestas de **getShops** y **newOrders** de Didi Food y las envía al backend local. Usa tu sesión normal del navegador (no abre otra sesión como Playwright).

## Requisitos

- Chrome, Edge o Brave (Chromium)
- Backend en ejecución (`uvicorn app.main:app` en `http://localhost:8000`)

## Instalación en Chrome / Edge / Brave

1. Abre el navegador y ve a:
   - **Chrome**: `chrome://extensions`
   - **Edge**: `edge://extensions`
   - **Brave**: `brave://extensions`

2. Activa el **modo desarrollador** (interruptor arriba a la derecha).

3. Pulsa **"Cargar descomprimida"** / **"Load unpacked"**.

4. Selecciona la carpeta `didi-extension` dentro del proyecto:
   ```
   C:\Users\Ludi\Desktop\restaurantScrepper\didi-extension
   ```

5. La extensión debería aparecer en la barra de extensiones.

6. (Opcional) Haz clic en el icono de la extensión para configurar la URL del backend si no usas `http://localhost:8000`.

## Uso

1. Inicia el backend: `uvicorn app.main:app --reload`

2. Entra en Didi Food con tu cuenta en el navegador:  
   https://didi-food.com/es-CO/store/pc/

3. Navega por la tienda (shop/select, órdenes, etc.). La extensión captura automáticamente:
   - **getShops** → guardado en `sedes_didi.json` (aplicando blacklist Salchimonster)
   - **newOrders** → guardado en `didi_new_orders.json`

4. Los datos se envían al endpoint `POST /didi/capture` del backend.

## Endpoint

- `POST /didi/capture`  
  Body: `{ "type": "getShops"|"newOrders", "data": {...} }`
