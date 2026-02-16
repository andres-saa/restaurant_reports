<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'
import Dialog from 'primevue/dialog'
import Timeline from 'primevue/timeline'

const API = import.meta.env.VITE_API_URL ?? ''

interface ReporteRow {
  local: string
  fecha: string
  codigo: string
  canal: string
  cliente?: string
  monto_pagado?: string
  hora?: string
  has_entrega_photo: boolean
  fotos_entrega: string[]
  fotos_apelacion: Record<string, string[]>
  fotos_respuestas: string[]
  apelacion: {
    monto_descontado?: number
    monto_devuelto?: number
    monto_reembolsado?: number
    fecha_apelado?: string
    fecha_estimada_devolucion?: string
    reembolsado?: boolean
    fecha_reembolso?: string
    descuento_confirmado?: boolean
    fecha_descuento_confirmado?: string
    fecha_marcado?: string
    sede_decidio_no_apelar?: boolean
  } | null
  estado_apelacion: string
  estados_apelacion?: string[]
  perdida: number
}

interface LocaleItem {
  id: string
  name: string
}

const locales = ref<LocaleItem[]>([])
const selectedLocal = ref<string | null>(null)
const fechaDesde = ref('')
const fechaHasta = ref('')
const rows = ref<ReporteRow[]>([])
const loading = ref(false)
const orderError = ref('')
const globalFilter = ref('')

const MIN_DATE = new Date(2026, 1, 11)
const todayStr = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Bogota' })
function lastTwoWeeksRange(): { desde: string; hasta: string } {
  const today = new Date()
  const hasta = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  const desde = new Date(hasta)
  desde.setDate(desde.getDate() - 13)
  return { desde: desde.toISOString().slice(0, 10), hasta: hasta.toISOString().slice(0, 10) }
}

const fechaDesdeAsDate = computed({
  get: () => (fechaDesde.value ? new Date(fechaDesde.value + 'T12:00:00') : null),
  set: (v: Date | null) => { fechaDesde.value = v ? v.toISOString().slice(0, 10) : '' }
})
const fechaHastaAsDate = computed({
  get: () => (fechaHasta.value ? new Date(fechaHasta.value + 'T12:00:00') : null),
  set: (v: Date | null) => { fechaHasta.value = v ? v.toISOString().slice(0, 10) : '' }
})

const localeOptions = computed(() => [
  { label: 'Todas las sedes', value: null },
  ...locales.value.map((l) => ({ label: l.name, value: l.name }))
])

const tableFilters = computed(() => ({
  global: { value: globalFilter.value, matchMode: 'contains' as const }
}))

const estadoLabels: Record<string, string> = {
  pendiente_apelar: 'Pend. apelar',
  apelada: 'Apelada',
  reembolsada: 'Reembolsada',
  descuento_confirmado: 'Descontado',
  sede_decidio_no_apelar: 'La sede decidió no apelar'
}

const estadoSeverity: Record<string, string> = {
  pendiente_apelar: 'warn',
  apelada: 'info',
  reembolsada: 'success',
  descuento_confirmado: 'secondary',
  sede_decidio_no_apelar: 'secondary'
}

function fullPhotoUrl(path: string): string {
  if (!path || path.startsWith('http')) return path || ''
  const base = API ? API.replace(/\/$/, '') : (typeof window !== 'undefined' ? window.location.origin : '')
  return base + (path.startsWith('/') ? path : '/' + path)
}

const photoModalVisible = ref(false)
const photoModalUrl = ref<string | null>(null)
function openPhoto(url: string) {
  photoModalUrl.value = url
  photoModalVisible.value = true
}
function closePhoto() {
  photoModalVisible.value = false
  photoModalUrl.value = null
}

function allFotosRespuestas(row: ReporteRow): string[] {
  return row.fotos_respuestas || []
}

function allFotosApelacion(row: ReporteRow): string[] {
  const ap = row.fotos_apelacion || {}
  return Object.values(ap).flat()
}

async function load() {
  if (!fechaDesde.value || !fechaHasta.value) return
  loading.value = true
  orderError.value = ''
  try {
    const params = new URLSearchParams()
    if (selectedLocal.value) params.set('local', selectedLocal.value)
    params.set('fecha_desde', fechaDesde.value)
    params.set('fecha_hasta', fechaHasta.value)
    const r = await fetch(`${API}/api/reporte-maestro?${params.toString()}`)
    const data = await r.json()
    rows.value = data.rows ?? []
  } catch (err) {
    orderError.value = (err as Error).message
    rows.value = []
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    const r = await fetch(`${API}/report/locales`)
    const data = await r.json()
    const raw = data.locales ?? []
    locales.value = raw.map((x: LocaleItem | string) =>
      typeof x === 'object' && x && 'name' in x ? { id: (x as LocaleItem).id || '', name: (x as LocaleItem).name } : { id: '', name: String(x) }
    )
  } catch {
    locales.value = []
  }
  const range = lastTwoWeeksRange()
  fechaDesde.value = range.desde
  fechaHasta.value = range.hasta
  await load()
})

watch([selectedLocal, fechaDesde, fechaHasta], () => load())

const CANAL_LOGOS: Record<string, string> = {
  'Rappi': '/logos/rappi.png',
  'Didi Food': '/logos/didi.png',
  'Menú Online': '/logos/menu_online.png'
}
function canalLogoUrl(canal: string | undefined): string | null {
  if (!canal?.trim()) return null
  return CANAL_LOGOS[canal.trim()] ?? null
}

function formatMonto(val: string | number | null | undefined): string {
  const n = typeof val === 'number' ? val : parseFloat(String(val || '0').replace(/[^\d.-]/g, '')) || 0
  return new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n)
}

function formatDate(d: string | null | undefined): string {
  if (!d) return '—'
  try {
    return new Date(d).toLocaleDateString('es-CO')
  } catch {
    return d
  }
}

function formatFechaIso(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return String(iso).slice(0, 16)
  }
}

const historialVisible = ref(false)
const historialRow = ref<ReporteRow | null>(null)
function openHistorial(row: ReporteRow) {
  historialRow.value = row
  historialVisible.value = true
}
function closeHistorial() {
  historialVisible.value = false
  historialRow.value = null
}

interface HistorialEvent {
  status: string
  date: string
  icon: string
  color: string
}
function buildHistorialEvents(row: ReporteRow | null): HistorialEvent[] {
  if (!row?.apelacion) return []
  const ap = row.apelacion
  const events: HistorialEvent[] = []
  if (ap.fecha_marcado || row.fecha) {
    events.push({ status: 'Marcado para apelación', date: formatFechaIso(ap.fecha_marcado) || row.fecha || '—', icon: 'pi pi-flag', color: '#6366f1' })
  }
  if (ap.sede_decidio_no_apelar) {
    events.push({ status: 'La sede decidió no apelar', date: '—', icon: 'pi pi-times-circle', color: '#64748b' })
  }
  if (ap.fecha_apelado) {
    events.push({ status: 'Apelado', date: formatFechaIso(ap.fecha_apelado), icon: 'pi pi-send', color: '#3b82f6' })
  }
  if (ap.reembolsado || ap.fecha_reembolso) {
    events.push({ status: 'Reembolsado', date: formatFechaIso(ap.fecha_reembolso), icon: 'pi pi-wallet', color: '#22c55e' })
  }
  if (ap.descuento_confirmado) {
    events.push({ status: 'Descontado a la sede', date: ap.fecha_descuento_confirmado || '—', icon: 'pi pi-check-circle', color: '#16a34a' })
  }
  return events
}
const historialEvents = computed(() => buildHistorialEvents(historialRow.value))
</script>

<template>
  <div class="reporte-maestro-view">
    <Card class="mb-3">
      <template #title>Reporte maestro</template>
      <template #content>
        <p class="text-color-secondary mt-0 mb-3">
          Tabla completa: órdenes, fotos de entrega y apelaciones, reembolsos y descuentos a sedes.
        </p>
        <div class="flex flex-wrap gap-3 align-items-end mb-2">
          <div class="flex flex-column gap-2">
            <label>Sede</label>
            <Select
              v-model="selectedLocal"
              :options="localeOptions"
              option-label="label"
              option-value="value"
              placeholder="Todas"
              class="w-full"
              filter
              filter-placeholder="Buscar sede..."
            />
          </div>
          <div class="flex flex-column gap-2">
            <label>Desde</label>
            <DatePicker v-model="fechaDesdeAsDate" :minDate="MIN_DATE" dateFormat="dd/mm/yy" showIcon />
          </div>
          <div class="flex flex-column gap-2">
            <label>Hasta</label>
            <DatePicker v-model="fechaHastaAsDate" :minDate="MIN_DATE" dateFormat="dd/mm/yy" showIcon />
          </div>
          <Button label="Cargar" icon="pi pi-refresh" :loading="loading" @click="load" />
        </div>
        <div class="mt-2">
          <input v-model="globalFilter" type="text" placeholder="Filtrar tabla..." class="p-inputtext p-component w-full" />
        </div>
      </template>
    </Card>

    <Message v-if="orderError" severity="error" class="mb-3">{{ orderError }}</Message>

    <Card>
      <template #title>Órdenes ({{ rows.length }})</template>
      <template #content>
        <DataTable
          :value="rows"
          :loading="loading"
          data-key="codigo"
          :filters="tableFilters"
          :globalFilterFields="['local', 'codigo', 'canal', 'cliente']"
          class="p-datatable-sm p-datatable-striped reporte-maestro-table"
          scrollable
          scroll-height="600px"
          :paginator="true"
          :rows="20"
          :rows-per-page-options="[10, 20, 50, 100]"
          paginator-template="CurrentPageReport FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown"
          current-page-report-template="Mostrando {first} a {last} de {totalRecords} registros — Página {currentPage} de {totalPages}"
        >
          <Column field="local" header="Sede" frozen sortable />
          <Column field="fecha" header="Fecha" sortable style="min-width: 100px" />
          <Column field="canal" header="Canal" style="min-width: 120px">
            <template #body="{ data }">
              <div class="flex align-items-center gap-2">
                <img v-if="canalLogoUrl(data.canal)" :src="canalLogoUrl(data.canal)!" :alt="data.canal" class="canal-logo-mini" />
                <span>{{ data.canal || '—' }}</span>
              </div>
            </template>
          </Column>
          <Column field="codigo" header="Código" sortable style="min-width: 140px" />
          <Column field="cliente" header="Cliente" style="min-width: 120px" />
          <Column header="Valor del pedido" style="min-width: 100px">
            <template #body="{ data }">{{ formatMonto(data.monto_pagado) }}</template>
          </Column>
          <Column header="Entrega" style="min-width: 80px">
            <template #body="{ data }">
              <div v-if="data.fotos_entrega?.length" class="fotos-thumbs">
                <button
                  v-for="(url, i) in (data.fotos_entrega || []).slice(0, 2)"
                  :key="i"
                  type="button"
                  class="foto-thumb-btn"
                  @click.stop="openPhoto(url)"
                >
                  <img :src="fullPhotoUrl(url)" alt="Entrega" />
                </button>
              </div>
              <span v-else class="text-color-secondary">—</span>
            </template>
          </Column>
          <Column header="Apelación" style="min-width: 80px">
            <template #body="{ data }">
              <div v-if="allFotosApelacion(data).length" class="fotos-thumbs">
                <button
                  v-for="(url, i) in allFotosApelacion(data).slice(0, 2)"
                  :key="i"
                  type="button"
                  class="foto-thumb-btn"
                  @click.stop="openPhoto(url)"
                >
                  <img :src="fullPhotoUrl(url)" alt="Apelación" />
                </button>
              </div>
              <span v-else class="text-color-secondary">—</span>
            </template>
          </Column>
          <Column header="Respuestas" style="min-width: 80px">
            <template #body="{ data }">
              <div v-if="allFotosRespuestas(data).length" class="fotos-thumbs">
                <button
                  v-for="(url, i) in allFotosRespuestas(data).slice(0, 2)"
                  :key="i"
                  type="button"
                  class="foto-thumb-btn"
                  @click.stop="openPhoto(url)"
                >
                  <img :src="fullPhotoUrl(url)" alt="Respuesta" />
                </button>
              </div>
              <span v-else class="text-color-secondary">—</span>
            </template>
          </Column>
          <Column header="Descontado por canal" style="min-width: 110px">
            <template #body="{ data }">{{ data.apelacion?.monto_descontado != null ? formatMonto(data.apelacion.monto_descontado) : '—' }}</template>
          </Column>
          <Column header="Reconocido por canal" style="min-width: 110px">
            <template #body="{ data }">
              <span v-if="(data.apelacion?.monto_devuelto ?? data.apelacion?.monto_reembolsado) != null && (data.apelacion?.monto_devuelto ?? data.apelacion?.monto_reembolsado) > 0" class="text-green font-semibold">{{ formatMonto(data.apelacion?.monto_reembolsado ?? data.apelacion?.monto_devuelto) }}</span>
              <span v-else class="text-color-secondary">—</span>
            </template>
          </Column>
          <Column header="Estado del reembolso" style="min-width: 120px">
            <template #body="{ data }">
              <Tag v-if="data.apelacion?.reembolsado" severity="success" value="Reembolsado" />
              <Tag v-else-if="data.apelacion?.monto_devuelto != null" severity="warn" value="Pendiente" />
              <span v-else class="text-color-secondary">—</span>
            </template>
          </Column>
          <Column header="No reconocido por canal" style="min-width: 120px">
            <template #body="{ data }">
              <span v-if="data.perdida > 0" class="text-red font-semibold">{{ formatMonto(data.perdida) }}</span>
              <span v-else class="text-color-secondary">—</span>
            </template>
          </Column>
          <Column header="Estado del descuento a la sede" style="min-width: 160px">
            <template #body="{ data }">
              <Tag v-if="data.apelacion?.descuento_confirmado && data.perdida > 0" severity="success" value="Descontado" />
              <Tag v-else-if="data.perdida > 0" severity="warn" value="Pendiente" />
              <span v-else class="text-color-secondary">—</span>
            </template>
          </Column>
          <Column header="Descontado a la sede" style="min-width: 120px">
            <template #body="{ data }">
              <span v-if="data.apelacion?.descuento_confirmado && data.perdida > 0" class="text-green font-semibold">{{ formatMonto(data.perdida) }}</span>
              <span v-else class="text-color-secondary">—</span>
            </template>
          </Column>
          <Column header="Pérdida empresa" style="min-width: 120px">
            <template #body="{ data }">
              <span v-if="!data.apelacion?.descuento_confirmado && data.perdida > 0" class="text-red font-semibold">{{ formatMonto(data.perdida) }}</span>
              <span v-else class="text-color-secondary">—</span>
            </template>
          </Column>
          <Column header="Estado apelación" style="min-width: 140px">
            <template #body="{ data }">
              <div v-if="(data.estados_apelacion ?? (data.estado_apelacion ? [data.estado_apelacion] : [])).length" class="flex flex-wrap gap-1">
                <Tag
                  v-for="e in (data.estados_apelacion ?? [data.estado_apelacion])"
                  :key="e"
                  :severity="estadoSeverity[e]"
                  :value="estadoLabels[e] || e"
                />
              </div>
              <span v-else class="text-color-secondary">—</span>
            </template>
          </Column>
          <Column header="Historial" style="min-width: 90px">
            <template #body="{ data }">
              <Button label="Ver" icon="pi pi-history" size="small" text @click="openHistorial(data)" />
            </template>
          </Column>
          <template #empty>
            <span class="text-color-secondary">Selecciona fechas y pulsa Cargar.</span>
          </template>
          <template #loading>
            <ProgressSpinner style="width: 40px; height: 40px" stroke-width="4" />
          </template>
        </DataTable>
      </template>
    </Card>

    <Dialog v-model:visible="photoModalVisible" modal header="Foto" class="photo-dialog" @hide="closePhoto">
      <template #default>
        <div v-if="photoModalUrl" class="photo-modal-body">
          <img :src="fullPhotoUrl(photoModalUrl)" alt="Foto" class="photo-modal-img" />
        </div>
      </template>
      <template #footer>
        <Button label="Cerrar" icon="pi pi-times" @click="closePhoto" />
      </template>
    </Dialog>

    <Dialog
      v-model:visible="historialVisible"
      modal
      header="Historial de la orden"
      class="historial-dialog"
      @hide="closeHistorial"
    >
      <template #default>
        <div v-if="historialRow" class="historial-timeline">
          <p class="mb-3 font-semibold">{{ historialRow.codigo }} — {{ historialRow.canal }}</p>
          <Timeline v-if="historialEvents.length" :value="historialEvents" align="alternate">
            <template #opposite="{ item: ev }">
              <small class="text-surface-500">{{ ev.date }}</small>
            </template>
            <template #content="{ item: ev }">
              <strong>{{ ev.status }}</strong>
            </template>
            <template #marker="{ item: ev }">
              <span class="historial-marker" :style="{ background: ev.color }">
                <i :class="ev.icon"></i>
              </span>
            </template>
          </Timeline>
          <p v-else class="text-color-secondary">Sin eventos registrados.</p>
        </div>
      </template>
      <template #footer>
        <Button label="Cerrar" icon="pi pi-times" @click="closeHistorial" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.reporte-maestro-view {
  padding: 0.5rem;
}
.canal-logo-mini {
  width: 22px;
  height: 22px;
  object-fit: contain;
}
.fotos-thumbs {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.foto-thumb-btn {
  width: 32px;
  height: 32px;
  padding: 0;
  border: 1px solid var(--p-content-border-color);
  border-radius: 4px;
  overflow: hidden;
  cursor: pointer;
  background: transparent;
}
.foto-thumb-btn:hover {
  border-color: var(--p-primary-color);
}
.foto-thumb-btn img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.photo-modal-body {
  display: flex;
  justify-content: center;
  min-height: 40vh;
}
.photo-modal-img {
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
}
.text-red {
  color: var(--p-red-600, #dc2626);
}
.text-green {
  color: var(--p-green-600, #16a34a);
}
.reporte-maestro-table :deep(.p-datatable-wrapper) {
  max-height: 600px;
}
.historial-timeline {
  padding: 0.75rem 0.5rem;
}
.historial-marker {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  color: white;
}
.historial-marker i {
  font-size: 0.875rem;
}
</style>
