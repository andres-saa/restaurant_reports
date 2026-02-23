<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import Card from 'primevue/card'
import ProgressSpinner from 'primevue/progressspinner'
import Message from 'primevue/message'
import Button from 'primevue/button'

/** API base URL. En producción si no está definida, usar el backend conocido para no pedir al mismo origen. */
const API = computed(() => {
  const env = import.meta.env.VITE_API_URL ?? ''
  if (env) return env
  if (typeof window !== 'undefined' && window.location.hostname === 'fotopedidos.salchimonster.com') {
    return 'https://restaurant.reports.salchimonster.com'
  }
  return ''
})

interface LocaleItem {
  id: string
  name: string
}

const locales = ref<LocaleItem[]>([])
const loading = ref(true)
const error = ref('')
const copiedId = ref<string | null>(null)

/** Origen de la app (fotopedidos.salchimonster.com en producción). */
const baseUrl = computed(() =>
  typeof window !== 'undefined' ? window.location.origin : 'https://fotopedidos.salchimonster.com'
)

const sedeParam = (loc: LocaleItem) => (loc.id ? loc.id : encodeURIComponent(loc.name))

/** Link por sede: /pedidos/hoy?sede=id&user. Siempre user para que el cajero entre directo. */
function linkHoy(loc: LocaleItem): string {
  return `${baseUrl.value}/pedidos/hoy?sede=${sedeParam(loc)}&user`
}

function normalizeLocale(x: LocaleItem | Record<string, unknown> | string): LocaleItem {
  if (typeof x === 'string') {
    return { id: '', name: x.trim() || 'Sede' }
  }
  if (typeof x !== 'object' || !x) {
    return { id: '', name: 'Sede' }
  }
  const obj = x as Record<string, unknown>
  const name =
    (typeof obj.name === 'string' && obj.name) ||
    (typeof obj.local_descripcion === 'string' && obj.local_descripcion) ||
    ''
  const id =
    (typeof obj.id === 'string' && obj.id) ||
    (typeof obj.id === 'number' && String(obj.id)) ||
    (typeof obj.local_id === 'string' && obj.local_id) ||
    (typeof obj.local_id === 'number' && String(obj.local_id)) ||
    ''
  return { id, name: name || 'Sede' }
}

async function loadLocales() {
  loading.value = true
  error.value = ''
  try {
    const base = API.value
    const url = base ? `${base.replace(/\/$/, '')}/report/locales` : '/report/locales'
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 15000)
    const r = await fetch(url, { signal: controller.signal })
    clearTimeout(timeoutId)
    const contentType = r.headers.get('content-type') || ''
    if (!contentType.includes('application/json')) {
      throw new Error('El servidor no devolvió JSON. ¿La URL del API está bien configurada?')
    }
    const data = await r.json()
    if (!r.ok) {
      throw new Error(data.detail || data.message || `Error ${r.status}`)
    }
    const raw = Array.isArray(data) ? data : (data.locales ?? [])
    if (!Array.isArray(raw)) {
      throw new Error('Formato de respuesta inválido')
    }
    locales.value = raw.map((x) => normalizeLocale(x as LocaleItem | Record<string, unknown> | string))
  } catch (e) {
    if ((e as Error).name === 'AbortError') {
      error.value = 'Tiempo de espera agotado. Comprueba que el backend esté en marcha y la URL del API.'
    } else {
      error.value = e instanceof Error ? e.message : 'No se pudieron cargar las sedes'
    }
    locales.value = []
  } finally {
    loading.value = false
  }
}

function copyLink(loc: LocaleItem) {
  const url = linkHoy(loc)
  navigator.clipboard.writeText(url).catch(() => {})
  copiedId.value = loc.id || loc.name
  setTimeout(() => { copiedId.value = null }, 1800)
}

onMounted(() => loadLocales())
</script>

<template>
  <div class="links-sedes">
    <Card class="links-sedes-card">
      <template #title>Links sedes</template>
      <template #subtitle>Copia el enlace de acceso directo para cada sede.</template>
    </Card>

    <div class="links-sedes-body">
      <Message v-if="error" severity="error" class="mb-3">{{ error }}</Message>

      <div v-if="loading" class="links-sedes-loading">
        <ProgressSpinner style="width: 2.5rem; height: 2.5rem" />
        <span class="ml-2">Cargando sedes…</span>
      </div>

      <p v-else-if="locales.length === 0" class="links-sedes-empty">
        No hay sedes cargadas.
      </p>

      <ul v-else class="links-sedes-list">
        <li
          v-for="(loc, index) in locales"
          :key="loc.id || loc.name || index"
          class="links-sedes-item"
        >
          <span class="links-sedes-name">{{ loc.name }}</span>
          <Button
            :icon="copiedId === (loc.id || loc.name) ? 'pi pi-check' : 'pi pi-copy'"
            :label="copiedId === (loc.id || loc.name) ? 'Copiado' : 'Copiar'"
            :severity="copiedId === (loc.id || loc.name) ? 'success' : 'secondary'"
            size="small"
            outlined
            @click="copyLink(loc)"
          />
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.links-sedes {
  max-width: 36rem;
  margin: 0 auto;
}
.links-sedes-body {
  margin-top: 0;
  padding: .5rem 1.25rem .75rem;
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius);
  border-top: none;
}
.links-sedes-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem 0;
}
.links-sedes-empty {
  padding: .75rem 0;
  color: var(--p-text-muted-color);
  font-size: .9rem;
}
.links-sedes-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.links-sedes-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: .75rem;
  padding: .65rem 0;
  border-bottom: 1px solid var(--p-content-border-color);
}
.links-sedes-item:last-child {
  border-bottom: none;
}
.links-sedes-name {
  font-weight: 500;
  font-size: .95rem;
}
</style>
