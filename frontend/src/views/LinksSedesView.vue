<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import Card from 'primevue/card'
import ProgressSpinner from 'primevue/progressspinner'
import Message from 'primevue/message'
import InputText from 'primevue/inputtext'
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
const filterText = ref('')

/** Origen de la app (fotopedidos.salchimonster.com en producción). */
const baseUrl = computed(() =>
  typeof window !== 'undefined' ? window.location.origin : 'https://fotopedidos.salchimonster.com'
)

const sedeParam = (loc: LocaleItem) => (loc.id ? loc.id : encodeURIComponent(loc.name))

/** Link por sede: /pedidos/hoy?sede=id&user. Siempre user para que el cajero entre directo. */
function linkHoy(loc: LocaleItem): string {
  return `${baseUrl.value}/pedidos/hoy?sede=${sedeParam(loc)}&user`
}

function linkMisDescuentos(loc: LocaleItem): string {
  return `${baseUrl.value}/pedidos/mis-descuentos?sede=${sedeParam(loc)}&user`
}

const filteredLocales = computed(() => {
  const q = filterText.value.trim().toLowerCase()
  if (!q) return locales.value
  return locales.value.filter(
    (l) => l.name.toLowerCase().includes(q) || (l.id && String(l.id).toLowerCase().includes(q))
  )
})

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

function copyLink(url: string) {
  navigator.clipboard.writeText(url).catch(() => {})
}

onMounted(() => loadLocales())
</script>

<template>
  <div class="links-sedes">
    <Card class="links-sedes-card">
      <template #title>Links sedes</template>
      <template #subtitle>
        Enlaces por sede para que el cajero entre directo a Hoy o Mis descuentos.
      </template>
    </Card>

    <div class="links-sedes-body">
      <Message v-if="error" severity="error" class="mb-3">{{ error }}</Message>

        <div v-if="loading" class="links-sedes-loading">
          <ProgressSpinner style="width: 2.5rem; height: 2.5rem" />
          <span class="ml-2">Cargando sedes…</span>
        </div>

        <div v-else>
          <div class="mb-3">
          <label for="filter-sedes" class="block mb-1 font-medium">Buscar sede</label>
          <InputText
            id="filter-sedes"
            v-model="filterText"
            placeholder="Filtrar por nombre o id..."
            class="w-full"
          />
        </div>

        <p v-if="locales.length === 0" class="links-sedes-empty text-color-secondary">
          No hay sedes cargadas. Comprueba que el backend esté en marcha y que la URL del API (credenciales o .env) sea correcta.
        </p>
        <ul v-else class="links-sedes-list">
          <li v-for="(loc, index) in filteredLocales" :key="loc.id || loc.name || index" class="links-sedes-item">
            <span class="links-sedes-name">{{ loc.name }}</span>
            <div class="links-sedes-links">
              <a :href="linkHoy(loc)" target="_blank" rel="noopener noreferrer" class="links-sedes-link" title="Hoy">Hoy</a>
              <a :href="linkMisDescuentos(loc)" target="_blank" rel="noopener noreferrer" class="links-sedes-link" title="Mis descuentos">Mis descuentos</a>
            </div>
            <Button
              icon="pi pi-copy"
              severity="secondary"
              size="small"
              text
              rounded
              aria-label="Copiar enlace Hoy"
              @click="copyLink(linkHoy(loc))"
            />
          </li>
        </ul>
        <p v-if="filteredLocales.length === 0 && locales.length > 0" class="text-color-secondary mt-2">
          No hay sedes que coincidan con el filtro.
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.links-sedes {
  max-width: 48rem;
  margin: 0 auto;
}
.links-sedes-body {
  min-height: 2rem;
  margin-top: 0;
  padding: 1rem 1.25rem;
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
  margin-top: 0.5rem;
  padding: 0.5rem 0;
}
.links-sedes-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.links-sedes-item {
  display: flex;
  align-items: center;
  gap: 0.5rem 1rem;
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--p-content-border-color);
  flex-wrap: wrap;
}
.links-sedes-links {
  display: flex;
  gap: 0.5rem 1rem;
  flex-wrap: wrap;
}
.links-sedes-item:last-child {
  border-bottom: none;
}
.links-sedes-name {
  font-weight: 500;
  min-width: 10rem;
}
.links-sedes-link {
  font-size: 0.875rem;
  color: var(--p-primary-color);
  text-decoration: none;
}
.links-sedes-link:hover {
  text-decoration: underline;
}
</style>
