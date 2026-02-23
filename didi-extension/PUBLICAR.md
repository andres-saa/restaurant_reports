# Publicar extensión Didi Capture en producción

## Opción 1: Chrome Web Store

1. **Cuenta de desarrollador**
   - Entra en https://chrome.google.com/webstore/devconsole
   - Inicia sesión con una cuenta Google
   - Paga la cuota única de **$5 USD** (si es la primera vez)

2. **Empaquetar la extensión**
   - Ve a `chrome://extensions`
   - Activa "Modo desarrollador"
   - Clic en "Empaquetar extensión"
   - Carpeta raíz: `didi-extension`
   - Se generará `didi-extension.zip` (o `.crx` + `.pem`)

   O desde terminal (PowerShell, en la raíz del proyecto):
   ```powershell
   Compress-Archive -Path didi-extension\* -DestinationPath didi-extension.zip -Force
   ```
   O excluyendo docs: copia solo los archivos necesarios (manifest.json, *.js, *.html) a una carpeta temporal y comprime esa carpeta.

3. **Subir a la tienda**
   - En el Developer Dashboard: "Nueva extensión" → Subir ZIP
   - Completa: descripción, iconos (128x128), capturas de pantalla
   - Política de privacidad (URL) – necesaria si envías datos a un servidor
   - Acepta los términos

4. **Revisión**
   - Google revisa (suele tardar 1–3 días)
   - Pueden rechazarla si:
     - Falta política de privacidad
     - El propósito no queda claro
     - Hay permisos excesivos

---

## Opción 2: Microsoft Edge Add-ons

1. **Cuenta de desarrollador**
   - https://partner.microsoft.com/dashboard/microsoftedge/overview
   - Inicia sesión con cuenta Microsoft (gratis)

2. **Empaquetar** (mismo ZIP que para Chrome)

3. **Subir**
   - "Crear nueva extensión" → Subir el ZIP
   - Datos obligatorios: descripción, iconos, capturas

---

## Opción 3: Distribución interna (sin tienda)

1. **Crear ZIP** con el contenido de `didi-extension` (sin `.md`, `.git`)
2. **Enviar el ZIP** por email, USB, Drive, etc.
3. **Instrucciones para el usuario**
   - Descomprimir en una carpeta
   - `chrome://extensions` → Modo desarrollador → Cargar descomprimida → Elegir carpeta

---

## Checklist antes de publicar

- [ ] `manifest.json`: versión correcta (ej. 1.0.0)
- [ ] `host_permissions`: incluir URL del backend de producción
- [ ] Popup: URL del backend por defecto (editar `popup.js` si hace falta)
- [ ] Icono: 128x128 px (añadir en `manifest.json` → `action.default_icon`)
- [ ] Política de privacidad: si se usa Chrome Web Store, página web que explique qué datos se envían

---

## URL del backend

La extensión usa `chrome.storage.sync` para guardar la URL del backend. **Por defecto:** `https://restaurant.reports.salchimonster.com`. El usuario puede cambiarla en el popup si usa otro servidor.
