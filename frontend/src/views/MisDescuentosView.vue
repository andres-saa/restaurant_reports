<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useRoleStore } from '@/stores/role'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'
import Timeline from 'primevue/timeline'
import Dialog from 'primevue/dialog'

const API = import.meta.env.VITE_API_URL ?? ''

// ─── Types ───────────────────────────────────────────────────────────────────
interface DescuentoQuincena {
  id?: string
  monto: number
  quincena: string
  fecha: string
  ejecutado?: boolean
}
interface DescuentoItem {
  codigo: string
  canal: string
  local?: string
  fecha?: string
  monto_descontado: number
  monto_devuelto?: number
  monto_reembolsado?: number
  reembolsado?: boolean
  perdida: number
  perdida_restante?: number
  perdida_restante_ejecutar?: number
  total_programado?: number
  total_descuentos_sede?: number
  monto_empresa_asume?: number
  empresa_asume?: boolean
  fecha_empresa_asume?: string
  descuentos?: DescuentoQuincena[]
  descuento_confirmado?: boolean
  fecha_descuento_confirmado?: string
  sede_decidio_no_apelar?: boolean
  fecha_marcado?: string
  fecha_apelado?: string
  fecha_reembolso?: string
}
interface LocaleItem { id: string; name: string }

// ─── State ───────────────────────────────────────────────────────────────────
const locales = ref<LocaleItem[]>([])
const selectedLocal = ref<string | null>(null)
const fechaDesde = ref('')
const fechaHasta = ref('')
const items = ref<DescuentoItem[]>([])
const loading = ref(false)
const orderError = ref('')

const route = useRoute()
const roleStore = useRoleStore()
const isUser = computed(() => roleStore.isUser())
const selectedSede = computed(() => (route.query.sede as string) || '')

const MIN_DATE = new Date(2026, 1, 11)
const todayStr = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Bogota' })
function lastTwoWeeksRange() {
  const today = new Date()
  const hasta = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  const desde = new Date(hasta); desde.setDate(desde.getDate() - 13)
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
const localeOptions = computed(() =>
  locales.value.map((l) => ({ label: l.name, value: l.name }))
)

function resolveLocalFromSede(sede: string): string | null {
  if (!sede || !locales.value.length) return null
  const byId = locales.value.find((l) => l.id && String(l.id) === String(sede))
  if (byId) return byId.name
  const byName = locales.value.find((l) => l.name === sede)
  if (byName) return byName.name
  return sede
}

// ─── Load ─────────────────────────────────────────────────────────────────────
async function load() {
  const local = selectedLocal.value || resolveLocalFromSede(selectedSede.value)
  if (!local) return
  loading.value = true
  orderError.value = ''
  try {
    const p = new URLSearchParams()
    p.set('local', local)
    p.set('fecha_desde', fechaDesde.value || todayStr())
    p.set('fecha_hasta', fechaHasta.value || todayStr())
    p.set('solo_pendientes', 'false')
    p.set('solo_confirmados', 'false')
    p.set('solo_programados', 'false')
    const r = await fetch(`${API}/api/apelaciones/descuentos?${p}`)
    items.value = (await r.json()).items ?? []
  } catch (e) {
    orderError.value = (e as Error).message
    items.value = []
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    const r = await fetch(`${API}/report/locales`)
    const data = await r.json()
    locales.value = (data.locales ?? []).map((x: LocaleItem | string) =>
      typeof x === 'object' && x && 'name' in x ? { id: (x as LocaleItem).id || '', name: (x as LocaleItem).name } : { id: '', name: String(x) }
    )
  } catch { locales.value = [] }
  selectedLocal.value = resolveLocalFromSede(selectedSede.value) || (locales.value[0]?.name ?? null)
  const range = lastTwoWeeksRange()
  fechaDesde.value = range.desde
  fechaHasta.value = range.hasta
  await load()
})

watch([selectedLocal, fechaDesde, fechaHasta], () => {
  if (selectedLocal.value || selectedSede.value) load()
})
watch(selectedSede, () => {
  if (selectedSede.value) selectedLocal.value = resolveLocalFromSede(selectedSede.value) || selectedSede.value || null
})

// ─── Estado de cada item ──────────────────────────────────────────────────────
function estadoItem(item: DescuentoItem): { label: string; severity: 'success' | 'warn' | 'danger' | 'secondary' | 'info' } {
  const totalProg = item.total_programado ?? 0
  const totalEje = item.total_descuentos_sede ?? 0
  const empresa = item.monto_empresa_asume ?? 0
  const perdida = item.perdida
  if (totalEje + empresa >= perdida) return { label: empresa > 0 && totalEje < perdida ? 'Empresa asumió' : 'Descontado', severity: 'success' }
  if (empresa > 0 && totalProg + empresa >= perdida) return { label: 'Empresa asumió (pendiente cobro)', severity: 'warn' }
  if (totalProg + empresa >= perdida && totalEje < perdida) return { label: 'Programado (pendiente cobro)', severity: 'warn' }
  if (totalProg + empresa > 0) return { label: 'Programado parcial', severity: 'info' }
  return { label: 'Sin programar', severity: 'danger' }
}

// ─── Historial dialog ─────────────────────────────────────────────────────────
const historialVisible = ref(false)
const historialItem = ref<DescuentoItem | null>(null)
function openHistorial(item: DescuentoItem) { historialItem.value = item; historialVisible.value = true }
function closeHistorial() { historialVisible.value = false; historialItem.value = null }

interface HistorialEvent { status: string; date: string; icon: string; color: string }
function buildHistorialEvents(item: DescuentoItem | null): HistorialEvent[] {
  if (!item) return []
  const events: HistorialEvent[] = []
  if (item.fecha_marcado || item.fecha)
    events.push({ status: 'Marcado para apelación', date: formatFechaIso(item.fecha_marcado) || item.fecha || '—', icon: 'pi pi-flag', color: '#6366f1' })
  if (item.sede_decidio_no_apelar)
    events.push({ status: 'La sede decidió no apelar', date: '—', icon: 'pi pi-times-circle', color: '#64748b' })
  if (item.descuentos?.length) {
    for (const d of item.descuentos) {
      const q = d.quincena ? ` (quincena ${d.quincena})` : ''
      const label = d.ejecutado === false ? 'Programado' : 'Descontado de nómina'
      const color = d.ejecutado === false ? '#f59e0b' : '#16a34a'
      const icon = d.ejecutado === false ? 'pi pi-clock' : 'pi pi-check-circle'
      events.push({ status: `${label}: ${formatMonto(d.monto)}${q}`, date: formatFechaIso(d.fecha), icon, color })
    }
  }
  if ((item.monto_empresa_asume ?? 0) > 0)
    events.push({ status: `Empresa asumió: ${formatMonto(item.monto_empresa_asume)}`, date: item.fecha_empresa_asume || '—', icon: 'pi pi-building', color: '#7c3aed' })
  if (item.fecha_apelado)
    events.push({ status: 'Apelado', date: formatFechaIso(item.fecha_apelado), icon: 'pi pi-send', color: '#3b82f6' })
  if (item.reembolsado || item.fecha_reembolso)
    events.push({ status: 'Reembolsado por el canal', date: formatFechaIso(item.fecha_reembolso), icon: 'pi pi-wallet', color: '#22c55e' })
  return events
}
const historialEvents = computed(() => buildHistorialEvents(historialItem.value))

// ─── Totales ──────────────────────────────────────────────────────────────────
const totalPerdida = computed(() => items.value.reduce((s, i) => s + (i.perdida || 0), 0))
const totalProgramado = computed(() => items.value.reduce((s, i) => s + (i.total_programado ?? 0), 0))
const totalEjecutado = computed(() => items.value.reduce((s, i) => s + (i.total_descuentos_sede ?? 0), 0))
const totalPendienteEjecutar = computed(() => items.value.reduce((s, i) => s + (i.perdida_restante_ejecutar ?? 0), 0))

// ─── Utils ────────────────────────────────────────────────────────────────────
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
function formatFechaIso(iso: string | null | undefined): string {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' }) } catch { return String(iso).slice(0, 16) }
}
</script>

<template>
  <div class="mis-descuentos-view">

    <!-- ── Filtros ── -->
    <Card class="mb-3">
      <template #title>Mis descuentos</template>
      <template #subtitle>
        Estado de los descuentos programados y aplicados a tu sede por pérdidas en pedidos.
      </template>
      <template #content>
        <div class="flex flex-wrap gap-3 align-items-end mb-3">
          <div v-if="!isUser" class="flex flex-column gap-2">
            <label>Sede</label>
            <Select
              v-model="selectedLocal"
              :options="localeOptions"
              option-label="label"
              option-value="value"
              placeholder="Seleccionar sede"
              style="min-width: 180px"
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
          <Button label="Actualizar" icon="pi pi-refresh" :loading="loading" @click="load" />
        </div>

        <!-- Resumen numérico -->
        <div v-if="items.length > 0" class="resumen-grid">
          <div class="resumen-item">
            <span class="resumen-label">Pérdida total período</span>
            <span class="resumen-valor text-red">{{ formatMonto(totalPerdida) }}</span>
          </div>
          <div class="resumen-item">
            <span class="resumen-label">Total programado</span>
            <span class="resumen-valor text-orange">{{ formatMonto(totalProgramado) }}</span>
          </div>
          <div class="resumen-item">
            <span class="resumen-label">Ya descontado (nómina)</span>
            <span class="resumen-valor text-green">{{ formatMonto(totalEjecutado) }}</span>
          </div>
          <div v-if="totalPendienteEjecutar > 0" class="resumen-item">
            <span class="resumen-label">Pendiente de cobro</span>
            <span class="resumen-valor text-orange">{{ formatMonto(totalPendienteEjecutar) }}</span>
          </div>
        </div>
      </template>
    </Card>

    <Message v-if="orderError" severity="error" class="mb-3">{{ orderError }}</Message>

    <!-- ── Tabla principal ── -->
    <Card>
      <template #title>Detalle por pedido</template>
      <template #content>
        <DataTable
          :value="items"
          :loading="loading"
          data-key="codigo"
          class="p-datatable-sm p-datatable-striped"
          :paginator="items.length > 10"
          :rows="10"
          paginator-template="CurrentPageReport FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink"
          current-page-report-template="{first}–{last} de {totalRecords}"
          scrollable
        >
          <Column field="canal" header="Canal" style="min-width: 100px">
            <template #body="{ data }">
              <div class="flex align-items-center gap-2">
                <img v-if="canalLogoUrl(data.canal)" :src="canalLogoUrl(data.canal)!" :alt="data.canal" style="width:22px;height:22px;object-fit:contain" />
                <span>{{ data.canal || '—' }}</span>
              </div>
            </template>
          </Column>
          <Column field="codigo" header="Código" sortable />
          <Column field="fecha" header="Fecha pedido" sortable />
          <Column header="Descontado por canal" style="min-width: 130px">
            <template #body="{ data }">{{ formatMonto(data.monto_descontado) }}</template>
          </Column>
          <Column header="Pérdida a descontar" style="min-width: 130px">
            <template #body="{ data }">
              <span class="text-red font-semibold">{{ formatMonto(data.perdida) }}</span>
            </template>
          </Column>
          <Column header="Programado" style="min-width: 120px">
            <template #body="{ data }">
              <span v-if="(data.total_programado ?? 0) > 0" class="text-orange font-semibold">{{ formatMonto(data.total_programado) }}</span>
              <span v-else class="text-color-secondary">—</span>
            </template>
          </Column>
          <Column header="Descontado" style="min-width: 120px">
            <template #body="{ data }">
              <span v-if="(data.total_descuentos_sede ?? 0) > 0" class="text-green font-semibold">{{ formatMonto(data.total_descuentos_sede) }}</span>
              <span v-else class="text-color-secondary">—</span>
            </template>
          </Column>
          <Column header="Quincenas / Empresa" style="min-width: 210px">
            <template #body="{ data }">
              <div class="flex flex-column gap-1">
                <div
                  v-for="(d, i) in (data.descuentos ?? [])"
                  :key="i"
                  class="quincena-chip"
                  :class="d.ejecutado === false ? 'mis-chip-pendiente' : 'mis-chip-ejecutado'"
                >
                  <i :class="d.ejecutado === false ? 'pi pi-clock' : 'pi pi-check'" class="mr-1 text-xs"></i>
                  <span>{{ d.quincena || d.fecha?.slice(0, 7) }} — {{ formatMonto(d.monto) }}</span>
                  <span class="chip-sublabel">{{ d.ejecutado === false ? 'pendiente' : 'pagado' }}</span>
                </div>
                <div v-if="(data.monto_empresa_asume ?? 0) > 0" class="quincena-chip mis-chip-empresa">
                  <i class="pi pi-building mr-1 text-xs"></i>
                  <span>Empresa asumió: {{ formatMonto(data.monto_empresa_asume) }}</span>
                </div>
                <span v-if="!(data.descuentos?.length) && !(data.monto_empresa_asume)" class="text-color-secondary text-sm">Sin quincenas</span>
              </div>
            </template>
          </Column>
          <Column header="Estado" style="min-width: 160px">
            <template #body="{ data }">
              <Tag :severity="estadoItem(data).severity" :value="estadoItem(data).label" />
            </template>
          </Column>
          <Column header="Historial" style="min-width: 80px">
            <template #body="{ data }">
              <Button label="Ver" icon="pi pi-history" size="small" text @click="openHistorial(data)" />
            </template>
          </Column>
          <template #empty>
            <div class="text-center py-4">
              <i class="pi pi-inbox text-color-secondary" style="font-size: 2rem"></i>
              <p class="text-color-secondary mt-2">No hay descuentos registrados en el período seleccionado.</p>
            </div>
          </template>
          <template #loading>
            <ProgressSpinner style="width: 40px; height: 40px" stroke-width="4" />
          </template>
        </DataTable>
      </template>
    </Card>

    <!-- ── Historial dialog ── -->
    <Dialog v-model:visible="historialVisible" modal header="Historial del pedido" @hide="closeHistorial">
      <template #default>
        <div v-if="historialItem" class="historial-timeline">
          <p class="mb-3 font-semibold">{{ historialItem.codigo }} — {{ historialItem.canal }}</p>
          <Timeline v-if="historialEvents.length" :value="historialEvents" align="alternate">
            <template #opposite="{ item: ev }"><small class="text-surface-500">{{ ev.date }}</small></template>
            <template #content="{ item: ev }"><strong>{{ ev.status }}</strong></template>
            <template #marker="{ item: ev }">
              <span class="historial-marker" :style="{ background: ev.color }"><i :class="ev.icon"></i></span>
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

<style>
/* Dark mode overrides — non-scoped para alcanzar .app-dark en <html> */
.app-dark .mis-chip-pendiente {
  background: #3d2000 !important; color: #fcd34d !important; border-color: #78350f !important;
}
.app-dark .mis-chip-ejecutado {
  background: #052e16 !important; color: #86efac !important; border-color: #166534 !important;
}
.app-dark .mis-chip-empresa {
  background: #2e1065 !important; color: #c4b5fd !important; border-color: #4c1d95 !important;
}
.app-dark .mis-descuentos-view .resumen-item {
  background: #18181b !important;
  border-color: #3f3f46 !important;
}
.app-dark .mis-descuentos-view .text-red   { color: #f87171 !important; }
.app-dark .mis-descuentos-view .text-green { color: #4ade80 !important; }
.app-dark .mis-descuentos-view .text-orange { color: #fb923c !important; }
</style>

<style scoped>
.mis-descuentos-view {
  padding: 0.5rem;
}

/* ── Resumen ── */
.resumen-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}
.resumen-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 140px;
  padding: 0.6rem 1rem;
  background: var(--p-surface-50);
  border: 1px solid var(--p-surface-200);
  border-radius: 8px;
}
.resumen-label {
  font-size: 0.78rem;
  color: var(--p-text-muted-color);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.resumen-valor {
  font-size: 1.1rem;
  font-weight: 700;
}

/* ── Chips ── */
.quincena-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 500;
  border: 1px solid transparent;
}
.mis-chip-pendiente {
  background: #fef3c7;
  color: #92400e;
  border-color: #fde68a;
}
.mis-chip-ejecutado {
  background: #dcfce7;
  color: #14532d;
  border-color: #bbf7d0;
}
.mis-chip-empresa {
  background: #f5f3ff;
  color: #5b21b6;
  border-color: #ddd6fe;
}
.chip-sublabel {
  font-size: 0.7rem;
  opacity: 0.7;
  font-weight: 400;
  margin-left: 2px;
}

/* ── Historial ── */
.historial-timeline { padding: 0.75rem 0.5rem; min-width: 300px; }
.historial-marker {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  color: white;
}
.historial-marker i { font-size: 0.875rem; }

/* ── Colors ── */
.text-red { color: var(--p-red-600, #dc2626); }
.text-green { color: var(--p-green-600, #16a34a); }
.text-orange { color: var(--p-orange-600, #ea580c); }
</style>
