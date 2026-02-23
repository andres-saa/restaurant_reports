<script setup lang="ts">
import Card from 'primevue/card'

const CHROME_STORE_DIDI_URL = 'https://chromewebstore.google.com/detail/jbfjmccnfmpciehmmiigokdklpaohfom'
</script>

<template>
  <div class="extensiones-view">
    <Card class="extensiones-card">
      <template #title>Extensiones</template>
      <template #subtitle>
        Instala aquí las extensiones que necesita tu sede. No necesitas pedir nada al admin.
      </template>
      <template #content>
        <div class="extensiones-list">
          <div class="extensiones-item">
            <div class="extensiones-item-header">
              <span class="extensiones-item-title">Didi Food Capture</span>
            </div>
            <p class="extensiones-item-desc">
              Para que los pedidos de Didi Food de esta sede se envíen al servidor y puedas ver el estado en la app.
              Instala la extensión en Chrome en el equipo donde se abre Didi Food (tienda/sede).
            </p>
            <a
              :href="CHROME_STORE_DIDI_URL"
              target="_blank"
              rel="noopener noreferrer"
              class="extensiones-link"
            >
              <i class="pi pi-download"></i>
              Descargar Didi Food Capture en la Chrome Web Store
            </a>
          </div>
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.extensiones-view {
  max-width: 40rem;
  margin: 0 auto;
  padding: 1rem;
}
.extensiones-card {
  margin-bottom: 1rem;
}
.extensiones-list {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}
.extensiones-item {
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--p-content-border-color);
}
.extensiones-item:last-child {
  border-bottom: none;
}
.extensiones-item-header {
  margin-bottom: 0.5rem;
}
.extensiones-item-title {
  font-weight: 600;
  font-size: 1.05rem;
}
.extensiones-item-desc {
  margin: 0 0 0.75rem 0;
  color: var(--p-text-muted-color);
  font-size: 0.9rem;
  line-height: 1.5;
}
.extensiones-link {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--p-primary-color);
  font-weight: 500;
  text-decoration: none;
}
.extensiones-link:hover {
  text-decoration: underline;
}
</style>
