# Instalar Capturador Didi (para cajeros)

App para abrir Didi Food y enviar sedes/órdenes al servidor.

## Instalación en cada PC de cajero

1. **Instalar Python** (si no está): https://www.python.org/downloads/
   - Marcar "Add Python to PATH"

2. **Abrir terminal** (cmd o PowerShell) en la carpeta del proyecto y ejecutar:
   ```bash
   pip install playwright httpx
   playwright install chromium
   ```

3. **Crear acceso directo** a `capturadorDidi.py`:
   - Clic derecho → Enviar a → Escritorio
   - O crear un `.bat` con: `python capturadorDidi.py` (ajustar ruta)

4. **Ejecutar**: doble clic en el acceso directo o en `capturadorDidi.py`

5. **En la ventana**: clic en "Abrir Didi Food" → se abre el navegador → iniciar sesión en Didi

## Configuración (opcional)

Crear `capturador_config.json` en la misma carpeta que el script para cambiar el servidor:

```json
{
  "backend_url": "https://restaurant.reports.salchimonster.com"
}
```
