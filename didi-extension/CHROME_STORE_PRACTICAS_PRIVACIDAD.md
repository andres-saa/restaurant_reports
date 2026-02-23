# Chrome Web Store – Prácticas de privacidad y justificaciones

Copia y pega cada bloque en la pestaña correspondiente al publicar la extensión **Didi Food Capture**.

---

## 1. Descripción de la finalidad única

**Campo: Finalidad única de la extensión**

```
Didi Food Capture es una extensión de uso interno para el equipo de Salchimonster. Su única finalidad es capturar en didi-food.com (con sesión iniciada del usuario) las respuestas de las APIs de Didi Food (órdenes del día e información de la tienda seleccionada) y enviarlas de forma segura al servidor de reportes de la empresa (restaurant.reports.salchimonster.com), para mantener actualizado el mapa de órdenes y el estado de conexión de cada sede. No recopila datos personales del usuario más allá de lo que Didi ya muestra en la página; no vende ni comparte datos con terceros.
```

---

## 2. Justificación del permiso **storage**

**Campo: Justificación para el permiso "storage"**

```
El permiso storage (chrome.storage.sync) se utiliza exclusivamente para guardar la URL del backend configurada por el usuario en el popup de la extensión (por defecto https://restaurant.reports.salchimonster.com). Así cada instalación puede apuntar al mismo servidor de la empresa sin hardcodear la URL. No se almacenan datos personales ni de navegación; solo esta preferencia de configuración.
```

---

## 3. Justificación del uso de **código remoto**

**Campo: Justificación para el uso de código remoto**

```
La extensión no ejecuta código remoto dinámico (no carga scripts desde URLs externas ni evalúa código descargado). La única comunicación con un servidor remoto es mediante peticiones HTTP POST (fetch) desde el service worker hacia el backend de la empresa (restaurant.reports.salchimonster.com), enviando únicamente los datos que el usuario ya tiene abiertos en didi-food.com (respuestas de las APIs de Didi: órdenes del día e información de la tienda). No se inyecta ni se ejecuta código procedente del servidor.
```

---

## 4. Justificación de los **permisos de host**

**Campo: Justificación para el uso del permiso de host**

```
Host permissions utilizados:

- https://didi-food.com/* y https://b.didi-food.com/*: la extensión solo actúa cuando el usuario está en la web de Didi Food; es necesario para inyectar el script que captura las respuestas de las APIs (getShopByID, dailyOrders, getShops, newOrders) que la propia página de Didi ya solicita. Sin estos permisos la extensión no podría cumplir su función.

- https://restaurant.reports.salchimonster.com/* y localhost (puertos 8000, 8009): la extensión envía los datos capturados al servidor de reportes de la empresa (o a un servidor local en desarrollo). El usuario puede cambiar la URL del backend en el popup. No se envían datos a otros dominios.
```

---

## 5. Declaración de cumplimiento de políticas (certificación)

**Campo: Certificar que el uso de datos cumple las Políticas del Programa**

Puedes marcar la casilla y, si te piden texto adicional, usar:

```
Certifico que el uso de datos de esta extensión cumple las Políticas del Programa para Desarrolladores de Chrome: la extensión solo envía al servidor de la empresa (restaurant.reports.salchimonster.com) los datos que el usuario ya tiene visibles en didi-food.com (respuestas de API de Didi). No se recopilan ni almacenan datos personales más allá de lo necesario para este fin; no se venden ni comparten con terceros; no se usa para publicidad ni tracking. Es de uso interno para el equipo de Salchimonster.
```

---

## 6. Correo electrónico de contacto

**Pestaña: Cuenta**

- Indica una dirección de correo electrónico de contacto (ej. `soporte@salchimonster.com` o el que use tu equipo).
- Completa el proceso de **verificación** que Google envía a ese correo (enlace o código en la pestaña Cuenta).

*(No se incluye aquí la dirección; debes escribirla y verificarla tú en el panel.)*

---

## 7. Captura de pantalla o vídeo

**Requisito:** Al menos una captura de pantalla o un vídeo.

**Qué capturar (recomendado):**

1. **Captura 1 – Popup de la extensión**  
   - Clic en el icono de la extensión en la barra de Chrome.  
   - Que se vea el popup (título “Didi Capture”, campo URL del backend, botón Guardar, estado).

2. **Captura 2 – Extensión en uso**  
   - Pestaña abierta en `https://didi-food.com/es-CO/store/pc/shop/select` (o store/pc/order) con sesión iniciada.  
   - Opcional: consola del navegador (F12) mostrando un mensaje `[Didi Capture] dailyOrders -> backend: OK` para demostrar que envía datos al backend.

**Especificaciones sugeridas:** 1280×800 o 640×400 px, formato PNG o JPG. Si subes vídeo, que sea corto (por ejemplo 30 s) mostrando: abrir Didi → elegir sede → ver que el popup muestra “Última captura OK” o similar.

---

## Resumen de pestañas

| Pestaña              | Qué rellenar |
|----------------------|--------------|
| **Prácticas de privacidad** | Finalidad única, justificación storage, justificación código remoto, justificación host, certificación |
| **Cuenta**           | Correo de contacto + verificación del correo |
| **Capturas / Vídeo** | Al menos 1 captura (popup o página Didi con extensión activa) |

Guardar este archivo como referencia y copiar cada bloque en el formulario de la Chrome Web Store.
