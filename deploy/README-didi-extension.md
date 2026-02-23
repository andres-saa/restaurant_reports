# Despliegue Didi Extension (didi-extension.salchimonster.com)

App mínima que recibe el JSON de **dailyOrders** y actualiza el mapa en `reports/didi/didi_restaurant_map_YYYY-MM-DD.json`.

## Requisitos

- Proyecto en `/var/www/restaurant_reports`
- Python con venv en `venv/` (o ajusta la ruta en el servicio)
- Nginx instalado
- DNS: registro A/CNAME de `didi-extension.salchimonster.com` apuntando al servidor

## Pasos

### 1. Servicio systemd

```bash
sudo cp /var/www/restaurant_reports/deploy/didi-extension.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable didi-extension
sudo systemctl start didi-extension
sudo systemctl status didi-extension
```

Si el venv está en otra ruta, edita `ExecStart` y `Environment` en el `.service`.

### 2. Nginx

```bash
sudo cp /var/www/restaurant_reports/deploy/nginx-didi-extension.salchimonster.com.conf /etc/nginx/sites-available/
sudo ln -sf /etc/nginx/sites-available/nginx-didi-extension.salchimonster.com.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 3. HTTPS (recomendado)

```bash
sudo certbot --nginx -d didi-extension.salchimonster.com
```

## Endpoints

| Método | Ruta | Uso |
|--------|------|-----|
| GET | `/` | Info de la app |
| GET | `/docs` | Swagger UI |
| GET | `/health` | Estado |
| **POST** | **`/didi/daily-orders-payload`** | Enviar JSON de dailyOrders (extensión) |

**URL base:** `https://didi-extension.salchimonster.com`

Ejemplo:

```bash
curl -X POST https://didi-extension.salchimonster.com/didi/daily-orders-payload \
  -H "Content-Type: application/json" \
  -d @daily_orders.json
```

El mapa se guarda en `reports/didi/` (mismo directorio que usa la API principal en restaurant.reports.salchimonster.com).
