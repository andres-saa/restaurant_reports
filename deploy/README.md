# Despliegue en 104.248.177.53

- **Ruta en servidor:** `/var/www/restaurant_reports`
- **Usuario:** root

## Subir variables y archivos

Desde la raíz del proyecto (donde está `app/` y `frontend/`):

```bash
# Aceptar host key y crear carpeta en el servidor
ssh -o StrictHostKeyChecking=accept-new root@104.248.177.53 "mkdir -p /var/www/restaurant_reports"

# Subir .env de producción del frontend (para referencia en el servidor)
scp -o StrictHostKeyChecking=accept-new frontend/.env.production root@104.248.177.53:/var/www/restaurant_reports/

# Subir ejemplo de env del servidor
scp -o StrictHostKeyChecking=accept-new deploy/server.env.example root@104.248.177.53:/var/www/restaurant_reports/
```

Te pedirá la contraseña al conectar.

## Variables de entorno en producción

- **Frontend (build):** `frontend/.env.production` tiene `VITE_API_URL=https://restaurant.reports.salchimonster.com`. El build de Vite ya las incluye.
- **Servidor:** En `/var/www/restaurant_reports/` puedes crear `.env` con variables que use tu proceso (systemd, etc.) si las necesitas.
