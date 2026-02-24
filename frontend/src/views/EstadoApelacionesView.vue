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

interface ApelacionItem {
  codigo: string
  canal: string
  local?: string
  fecha?: string
  monto_descontado: number
  monto_devuelto?: number
  monto_reembolsado?: number
  fecha_marcado?: string
  fecha_apelado?: string
  fecha_reembolso?: string
  reembolsado?: boolean
  reembolsos?: Array<{ monto: number; fecha: string }>
  descuento_confirmado?: boolean
  fecha_descuento_confirmado?: string
  descuentos?: Array<{ monto: number; quincena?: string; fecha: string }>
  total_descuentos_sede?: number
  sede_decidio_no_apelar?: boolean
  perdida: number
  no_reconocido_canal: number
  estado: string
  estados?: string[]
}

interface LocaleItem {
  id: string
  name: string
}

const locales = ref<LocaleItem[]>([])
const selectedLocal = ref<string | null>(null)
const fechaDesde = ref('')
const fechaHasta = ref('')
const items = ref<ApelacionItem[]>([])
const loading = ref(false)
const orderError = ref('')

const MIN_DATE = new Date(2026, 1, 11)
const todayStr = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Bogota' })

function lastFifteenDaysRange(): { desde: string; hasta: string } {
  const today = new Date()
  const hasta = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  const desde = new Date(hasta)
  desde.setDate(desde.getDate() - 14) // 15 días incluyendo hoy
  return {
    desde: desde.toISOString().slice(0, 10),
    hasta: hasta.toISOString().slice(0, 10)
  }
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

const estadoLabels: Record<string, string> = {
  pendiente_apelar: 'Pendiente de apelar',
  apelada: 'Apelada',
  reembolsada: 'Reembolsada',
  descuento_confirmado: 'Descuento en nómina',
  sede_decidio_no_apelar: 'La sede decidió no apelar'
}

const estadoSeverity: Record<string, string> = {
  pendiente_apelar: 'warn',
  apelada: 'info',
  reembolsada: 'success',
  descuento_confirmado: 'secondary',
  sede_decidio_no_apelar: 'secondary'
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
const historialItem = ref<ApelacionItem | null>(null)
function openHistorial(item: ApelacionItem) {
  historialItem.value = item
  historialVisible.value = true
}
function closeHistorial() {
  historialVisible.value = false
  historialItem.value = null
}

interface HistorialEvent {
  status: string
  date: string
  icon: string
  color: string
  amount?: string
  detail?: string
}
function buildHistorialEvents(item: ApelacionItem | null): HistorialEvent[] {
  if (!item) return []
  const events: HistorialEvent[] = []
  if (item.fecha_marcado || item.fecha) {
    const detail = item.monto_descontado != null ? `Descontado: ${formatMonto(item.monto_descontado)}` : undefined
    events.push({ status: 'Marcado para apelación', date: formatFechaIso(item.fecha_marcado) || item.fecha || '—', icon: 'pi pi-flag', color: '#6366f1', detail })
  }
  if (item.sede_decidio_no_apelar) {
    events.push({ status: 'La sede decidió no apelar', date: '—', icon: 'pi pi-times-circle', color: '#64748b' })
  }
  if (item.fecha_apelado) {
    const detail = item.monto_devuelto != null ? `Canal reconoce: ${formatMonto(item.monto_devuelto)}` : undefined
    events.push({ status: 'Apelado', date: formatFechaIso(item.fecha_apelado), icon: 'pi pi-send', color: '#3b82f6', detail })
  }
  const reembolsos = item.reembolsos ?? []
  if (reembolsos.length > 0) {
    reembolsos.forEach((r, i) => {
      events.push({
        status: reembolsos.length > 1 ? `Reembolso del canal #${i + 1}` : 'Reembolso del canal',
        date: formatFechaIso(r.fecha) || '—',
        icon: 'pi pi-wallet',
        color: '#22c55e',
        amount: formatMonto(r.monto),
      })
    })
  } else if (item.reembolsado || item.fecha_reembolso) {
    events.push({ status: 'Reembolso del canal', date: formatFechaIso(item.fecha_reembolso) || '—', icon: 'pi pi-wallet', color: '#22c55e', amount: item.monto_reembolsado != null ? formatMonto(item.monto_reembolsado) : undefined })
  }
  const descuentos = item.descuentos ?? []
  if (descuentos.length > 0) {
    descuentos.forEach((d, i) => {
      const detail = d.quincena ? `Quincena: ${d.quincena}` : undefined
      events.push({
        status: descuentos.length > 1 ? `Descuento a la sede #${i + 1}` : 'Descuento a la sede',
        date: formatFechaIso(d.fecha) || '—',
        icon: 'pi pi-check-circle',
        color: '#16a34a',
        amount: formatMonto(d.monto),
        detail,
      })
    })
  } else if (item.descuento_confirmado) {
    events.push({ status: 'Descuento a la sede', date: formatFechaIso(item.fecha_descuento_confirmado) || '—', icon: 'pi pi-check-circle', color: '#16a34a' })
  }
  return events
}
const historialEvents = computed(() => buildHistorialEvents(historialItem.value))

async function load() {
  loading.value = true
  orderError.value = ''
  try {
    const params = new URLSearchParams()
    if (selectedLocal.value) params.set('local', selectedLocal.value)
    params.set('fecha_desde', fechaDesde.value || todayStr())
    params.set('fecha_hasta', fechaHasta.value || todayStr())
    const r = await fetch(`${API}/api/apelaciones/estado-admin?${params.toString()}`)
    const data = await r.json()
    items.value = data.items ?? []
  } catch (err) {
    orderError.value = (err as Error).message
    items.value = []
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
  const { desde, hasta } = lastFifteenDaysRange()
  fechaDesde.value = desde
  fechaHasta.value = hasta
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

const countPendientes = computed(() => items.value.filter((i) => (i.estados ?? [i.estado]).includes('pendiente_apelar')).length)
const countApeladas = computed(() => items.value.filter((i) => (i.estados ?? [i.estado]).includes('apelada')).length)
const countReembolsadas = computed(() => items.value.filter((i) => (i.estados ?? [i.estado]).includes('reembolsada')).length)
const countDescuento = computed(() => items.value.filter((i) => (i.estados ?? [i.estado]).includes('descuento_confirmado')).length)
</script>

<template>
  <div class="estado-apelaciones-view">
    <Card class="mb-3">
      <template #title>Estado de apelaciones</template>
      <template #content>
        <p class="text-color-secondary mt-0 mb-3">
          Ver si las sedes ya apelaron. Estado de cada pedido marcado para apelación.
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
        <div v-if="items.length > 0" class="flex flex-wrap gap-2 mt-2">
          <Tag severity="warn" :value="`Pendientes: ${countPendientes}`" />
          <Tag severity="info" :value="`Apeladas: ${countApeladas}`" />
          <Tag severity="success" :value="`Reembolsadas: ${countReembolsadas}`" />
          <Tag severity="secondary" :value="`Descuento: ${countDescuento}`" />
        </div>
      </template>
    </Card>

    <Message v-if="orderError" severity="error" class="mb-3">{{ orderError }}</Message>

    <Card>
      <template #title>Apelaciones</template>
      <template #content>
        <DataTable
          :value="items"
          :loading="loading"
          data-key="codigo"
          class="p-datatable-sm p-datatable-striped"
          :paginator="items.length > 10"
          :rows="10"
          paginator-template="CurrentPageReport FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink"
          current-page-report-template="Mostrando {first} a {last} de {totalRecords} registros — Página {currentPage} de {totalPages}"
        >
          <Column field="local" header="Sede" sortable />
          <Column field="fecha" header="Fecha" sortable />
          <Column field="canal" header="Canal">
            <template #body="{ data }">
              <div class="flex align-items-center gap-2">
                <img v-if="canalLogoUrl(data.canal)" :src="canalLogoUrl(data.canal)!" :alt="data.canal" style="width: 24px; height: 24px; object-fit: contain" />
                <span>{{ data.canal || '—' }}</span>
              </div>
            </template>
          </Column>
          <Column field="codigo" header="Código" sortable />
          <Column header="Descontado por canal">
            <template #body="{ data }">{{ formatMonto(data.monto_descontado) }}</template>
          </Column>
          <Column header="Reconocido por canal">
            <template #body="{ data }">
              <span v-if="(data.monto_devuelto ?? data.monto_reembolsado) != null && (data.monto_devuelto ?? data.monto_reembolsado) > 0" class="text-green font-semibold">{{ formatMonto(data.monto_devuelto ?? data.monto_reembolsado) }}</span>
              <span v-else>—</span>
            </template>
          </Column>
          <Column header="Estado del reembolso" style="min-width: 120px">
            <template #body="{ data }">
              <Tag v-if="data.reembolsado" severity="success" value="Reembolsado" />
              <Tag v-else-if="data.monto_devuelto != null" severity="warn" value="Pendiente" />
              <span v-else>—</span>
            </template>
          </Column>
          <Column header="No reconocido por canal">
            <template #body="{ data }">
              <span v-if="(data.no_reconocido_canal ?? 0) > 0" class="text-red font-semibold">{{ formatMonto(data.no_reconocido_canal) }}</span>
              <span v-else>—</span>
            </template>
          </Column>
          <Column header="Estado del descuento a la sede" style="min-width: 160px">
            <template #body="{ data }">
              <Tag v-if="data.descuento_confirmado && (data.perdida ?? 0) > 0" severity="success" value="Descontado" />
              <Tag v-else-if="(data.perdida ?? 0) > 0" severity="warn" value="Pendiente" />
              <span v-else>—</span>
            </template>
          </Column>
          <Column header="Descontado a la sede" style="min-width: 120px">
            <template #body="{ data }">
              <span v-if="data.descuento_confirmado && (data.perdida ?? 0) > 0" class="text-green font-semibold">{{ formatMonto(data.perdida) }}</span>
              <span v-else>—</span>
            </template>
          </Column>
          <Column header="Pérdida empresa" style="min-width: 120px">
            <template #body="{ data }">
              <span v-if="!data.descuento_confirmado && (data.perdida ?? 0) > 0" class="text-red font-semibold">{{ formatMonto(data.perdida) }}</span>
              <span v-else>—</span>
            </template>
          </Column>
          <Column header="Estado apelación">
            <template #body="{ data }">
              <div class="flex flex-wrap gap-1">
                <Tag
                  v-for="e in (data.estados ?? [data.estado])"
                  :key="e"
                  :severity="estadoSeverity[e]"
                  :value="estadoLabels[e] || e"
                />
              </div>
            </template>
          </Column>
          <Column header="Apelado">
            <template #body="{ data }">{{ data.fecha_apelado ? new Date(data.fecha_apelado).toLocaleDateString('es-CO') : '—' }}</template>
          </Column>
          <Column header="Historial" style="min-width: 90px">
            <template #body="{ data }">
              <Button label="Ver" icon="pi pi-history" size="small" text @click="openHistorial(data)" />
            </template>
          </Column>
          <template #empty>
            <span class="text-color-secondary">No hay apelaciones en el rango seleccionado.</span>
          </template>
          <template #loading>
            <ProgressSpinner style="width: 40px; height: 40px" stroke-width="4" />
          </template>
        </DataTable>
      </template>
    </Card>

    <Dialog
      v-model:visible="historialVisible"
      modal
      header="Historial de la orden"
      class="historial-dialog"
      style="width: 90vw; max-width: 480px"
      @hide="closeHistorial"
    >
      <template #default>
        <div v-if="historialItem" class="historial-timeline">
          <p class="mb-3 font-semibold">{{ historialItem.codigo }} — {{ historialItem.canal }}</p>
          <Timeline v-if="historialEvents.length" :value="historialEvents" align="left">
            <template #opposite="{ item: ev }">
              <small class="text-surface-500 white-space-nowrap">{{ ev.date }}</small>
            </template>
            <template #content="{ item: ev }">
              <div class="historial-event-content">
                <strong>{{ ev.status }}</strong>
                <span v-if="ev.amount" class="historial-amount">{{ ev.amount }}</span>
                <small v-if="ev.detail" class="text-surface-500">{{ ev.detail }}</small>
              </div>
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
.estado-apelaciones-view {
  padding: 0.5rem;
}
.text-red {
  color: var(--p-red-600, #dc2626);
}
.text-green {
  color: var(--p-green-600, #16a34a);
}
.historial-timeline {
  padding: 0.75rem 0.5rem;
  min-width: 300px;
}
.historial-event-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-bottom: 0.5rem;
}
.historial-amount {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--p-green-600, #16a34a);
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
