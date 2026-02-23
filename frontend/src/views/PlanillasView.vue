<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Card from 'primevue/card'
import Button from 'primevue/button'
import DatePicker from 'primevue/datepicker'
import ProgressSpinner from 'primevue/progressspinner'
import Message from 'primevue/message'
import InputText from 'primevue/inputtext'
import Badge from 'primevue/badge'

const API = import.meta.env.VITE_API_URL ?? ''

interface PlanillaArchivo {
  nombre: string
  tamanio: number
  fecha_subida: number
}

interface SedePlanilla {
  local_id: string
  local_name: string
  subida: boolean
  archivos: PlanillaArchivo[]
}

const MIN_DATE = new Date(2026, 1, 11)

function todayStr() {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'America/Bogota' })
}

const selectedDate = ref(todayStr())
const selectedDateAsDate = computed({
  get: () => (selectedDate.value ? new Date(selectedDate.value + 'T12:00:00') : null),
  set: (v: Date | null) => {
    selectedDate.value = v ? v.toISOString().slice(0, 10) : ''
  }
})

const sedes = ref<SedePlanilla[]>([])
const loading = ref(false)
const error = ref('')
const filterText = ref('')

const countSubidas = computed(() => sedes.value.filter((s) => s.subida).length)
const countPendientes = computed(() => sedes.value.filter((s) => !s.subida).length)

const filteredSedes = computed(() => {
  const q = filterText.value.trim().toLowerCase()
  if (!q) return sedes.value
  return sedes.value.filter(
    (s) => s.local_name.toLowerCase().includes(q) || s.local_id.toLowerCase().includes(q)
  )
})

async function load() {
  if (!selectedDate.value) return
  loading.value = true
  error.value = ''
  try {
    const r = await fetch(`${API}/api/planilla/estado-sedes?fecha=${selectedDate.value}`)
    if (!r.ok) throw new Error(`Error ${r.status}`)
    const data = await r.json()
    sedes.value = data.sedes ?? []
  } catch (e) {
    error.value = (e as Error).message
    sedes.value = []
  } finally {
    loading.value = false
  }
}

function formatFileSize(bytes: number | null): string {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatTimestamp(ts: number | null): string {
  if (!ts) return ''
  return new Date(ts * 1000).toLocaleString('es-CO', {
    timeZone: 'America/Bogota',
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function downloadUrl(sede: SedePlanilla, archivo: PlanillaArchivo): string {
  return `${API}/api/planilla/${encodeURIComponent(sede.local_id)}/${selectedDate.value}/archivo/${encodeURIComponent(archivo.nombre)}`
}

onMounted(load)
</script>

<template>
  <div class="planillas-view">
    <Card class="mb-3">
      <template #title>
        <div class="flex align-items-center gap-2">
          <i class="pi pi-file-excel"></i>
          Planillas diarias por sede
        </div>
      </template>
      <template #content>
        <div class="flex flex-wrap align-items-end gap-3">
          <div class="flex flex-column gap-1">
            <label class="font-medium text-sm">Fecha</label>
            <DatePicker
              v-model="selectedDateAsDate"
              :minDate="MIN_DATE"
              dateFormat="dd/mm/yy"
              showIcon
              class="date-picker-resp"
              @update:modelValue="load"
            />
          </div>
          <Button
            label="Actualizar"
            icon="pi pi-refresh"
            :loading="loading"
            class="btn-touch"
            @click="load"
          />
        </div>

        <div v-if="sedes.length" class="flex flex-wrap gap-3 mt-3 summary-row">
          <div class="summary-chip summary-chip-ok">
            <i class="pi pi-check-circle"></i>
            <span>{{ countSubidas }} subidas</span>
          </div>
          <div class="summary-chip summary-chip-pending">
            <i class="pi pi-clock"></i>
            <span>{{ countPendientes }} pendientes</span>
          </div>
          <div class="summary-chip summary-chip-total">
            <i class="pi pi-building"></i>
            <span>{{ sedes.length }} sedes</span>
          </div>
        </div>
      </template>
    </Card>

    <Message v-if="error" severity="error" class="mb-3">{{ error }}</Message>

    <Card v-if="!loading || sedes.length">
      <template #content>
        <div class="mb-3">
          <InputText
            v-model="filterText"
            placeholder="Filtrar sede..."
            class="w-full"
          />
        </div>

        <div v-if="loading" class="flex justify-content-center align-items-center py-4 gap-2">
          <ProgressSpinner style="width:32px;height:32px" stroke-width="4" />
          <span class="text-color-secondary">Cargando...</span>
        </div>

        <div v-else-if="filteredSedes.length === 0" class="text-color-secondary text-center py-4">
          No hay sedes que coincidan.
        </div>

        <ul v-else class="sedes-list">
          <li
            v-for="sede in filteredSedes"
            :key="sede.local_id"
            class="sede-item"
            :class="{ 'sede-item-ok': sede.subida, 'sede-item-pending': !sede.subida }"
          >
            <div class="sede-main">
              <span class="sede-status-dot" :class="sede.subida ? 'dot-ok' : 'dot-pending'" />
              <span class="sede-name">{{ sede.local_name }}</span>
              <Badge
                v-if="sede.subida"
                :value="`${sede.archivos.length} archivo${sede.archivos.length !== 1 ? 's' : ''}`"
                severity="success"
                class="sede-badge"
              />
              <Badge
                v-else
                value="Pendiente"
                severity="warn"
                class="sede-badge"
              />
            </div>

            <ul v-if="sede.subida" class="archivos-list">
              <li
                v-for="archivo in sede.archivos"
                :key="archivo.nombre"
                class="archivo-item"
              >
                <span class="archivo-info text-sm text-color-secondary">
                  <i class="pi pi-file mr-1"></i>{{ archivo.nombre }}
                  <span v-if="archivo.tamanio"> · {{ formatFileSize(archivo.tamanio) }}</span>
                  <span v-if="archivo.fecha_subida"> · {{ formatTimestamp(archivo.fecha_subida) }}</span>
                </span>
                <a
                  :href="downloadUrl(sede, archivo)"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="download-link"
                >
                  <i class="pi pi-download mr-1"></i>Descargar
                </a>
              </li>
            </ul>
          </li>
        </ul>
      </template>
    </Card>

    <div v-else-if="loading" class="flex justify-content-center align-items-center py-6 gap-2">
      <ProgressSpinner style="width:32px;height:32px" stroke-width="4" />
      <span class="text-color-secondary">Cargando...</span>
    </div>
  </div>
</template>

<style scoped>
.planillas-view {
  max-width: 900px;
  margin: 0 auto;
  padding: 1rem;
  padding-bottom: env(safe-area-inset-bottom);
}
.btn-touch {
  min-width: 44px;
}
.date-picker-resp {
  width: 12rem;
}
.summary-row {
  gap: 0.5rem 1rem;
}
.summary-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.3rem 0.85rem;
  border-radius: 9999px;
  font-weight: 600;
  font-size: 0.875rem;
}
.planillas-view {
  --chip-ok-bg: #dcfce7;
  --chip-ok-fg: #15803d;
  --chip-pending-bg: #ffedd5;
  --chip-pending-fg: #c2410c;
  --chip-total-bg: #f4f4f5;
}
.app-dark .planillas-view {
  --chip-ok-bg: rgba(34, 197, 94, 0.15);
  --chip-ok-fg: #4ade80;
  --chip-pending-bg: rgba(249, 115, 22, 0.15);
  --chip-pending-fg: #fb923c;
  --chip-total-bg: rgba(255, 255, 255, 0.06);
}
.summary-chip-ok {
  background: var(--chip-ok-bg);
  color: var(--chip-ok-fg);
}
.summary-chip-pending {
  background: var(--chip-pending-bg);
  color: var(--chip-pending-fg);
}
.summary-chip-total {
  background: var(--chip-total-bg);
  color: var(--p-text-color);
}

.sedes-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.sede-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.75rem 0.5rem;
  border-bottom: 1px solid var(--p-content-border-color);
  border-radius: 6px;
  transition: background 0.15s;
}
.sede-item:last-child {
  border-bottom: none;
}
.sede-item:hover {
  background: var(--p-content-hover-background, rgba(0,0,0,0.03));
}
.sede-main {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}
.sede-status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot-ok {
  background: var(--p-green-500, #22c55e);
}
.dot-pending {
  background: var(--p-orange-400, #fb923c);
}
.sede-name {
  font-weight: 500;
  flex: 1;
  min-width: 8rem;
}
.sede-badge {
  flex-shrink: 0;
}

.archivos-list {
  list-style: none;
  padding: 0;
  margin: 0.25rem 0 0 1.4rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.archivo-item {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 1rem;
}
.archivo-info {
  flex: 1;
  min-width: 0;
  word-break: break-word;
}
.download-link {
  font-size: 0.85rem;
  color: var(--p-primary-color);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
}
.download-link:hover {
  text-decoration: underline;
}

@media (max-width: 767px) {
  .planillas-view {
    padding: 0.75rem;
  }
  .date-picker-resp {
    width: 100%;
  }
}
</style>
