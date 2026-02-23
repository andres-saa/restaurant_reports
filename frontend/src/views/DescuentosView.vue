<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Card from 'primevue/card'
import Checkbox from 'primevue/checkbox'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'
import Dialog from 'primevue/dialog'
import Timeline from 'primevue/timeline'

const API = import.meta.env.VITE_API_URL ?? ''

interface DescuentoQuincena {
  monto: number
  quincena: string
  fecha: string
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
  total_descuentos_sede?: number
  descuentos?: DescuentoQuincena[]
  descuento_confirmado?: boolean
  fecha_descuento_confirmado?: string
  sede_decidio_no_apelar?: boolean
  fecha_marcado?: string
  fecha_apelado?: string
  fecha_reembolso?: string
}

interface LocaleItem {
  id: string
  name: string
}

const locales = ref<LocaleItem[]>([])
const selectedLocal = ref<string | null>(null)
const fechaDesde = ref('')
const fechaHasta = ref('')
const soloPendientes = ref(true)
const items = ref<DescuentoItem[]>([])
const loading = ref(false)
const orderError = ref('')
const confirmingCodigo = ref<string | null>(null)
const descuentoDialogVisible = ref(false)
const descuentoDialogItem = ref<DescuentoItem | null>(null)
const descuentoMonto = ref<number | null>(null)
const descuentoQuincena = ref('')
const descuentoLoading = ref(false)
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

async function loadDescuentos() {
  loading.value = true
  orderError.value = ''
  try {
    const params = new URLSearchParams()
    if (selectedLocal.value) params.set('local', selectedLocal.value)
    params.set('fecha_desde', fechaDesde.value || todayStr())
    params.set('fecha_hasta', fechaHasta.value || todayStr())
    params.set('solo_pendientes', String(soloPendientes.value))
    const r = await fetch(`${API}/api/apelaciones/descuentos?${params.toString()}`)
    const data = await r.json()
    items.value = data.items ?? []
  } catch (err) {
    orderError.value = (err as Error).message
    items.value = []
  } finally {
    loading.value = false
  }
}

function openDescuentoDialog(item: DescuentoItem) {
  descuentoDialogItem.value = item
  descuentoMonto.value = (item.perdida_restante ?? item.perdida) > 0 ? (item.perdida_restante ?? item.perdida) : item.perdida
  descuentoQuincena.value = ''
  descuentoDialogVisible.value = true
}

function closeDescuentoDialog() {
  descuentoDialogVisible.value = false
  descuentoDialogItem.value = null
  descuentoMonto.value = null
  descuentoQuincena.value = ''
}

async function confirmarDescuento() {
  const item = descuentoDialogItem.value
  if (!item) return
  const monto = descuentoMonto.value ?? 0
  if (monto <= 0) {
    orderError.value = 'Indica el monto descontado en esta quincena'
    return
  }
  descuentoLoading.value = true
  orderError.value = ''
  try {
    const r = await fetch(`${API}/api/apelaciones/confirmar-descuento`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        codigo: item.codigo,
        monto,
        quincena: descuentoQuincena.value.trim() || undefined
      })
    })
    if (!r.ok) {
      const err = await r.json().catch(() => ({}))
      throw new Error(err.detail || 'Error al confirmar')
    }
    closeDescuentoDialog()
    await loadDescuentos()
  } catch (e) {
    orderError.value = (e as Error).message
  } finally {
    descuentoLoading.value = false
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
  await loadDescuentos()
})

watch([selectedLocal, fechaDesde, fechaHasta, soloPendientes], () => {
  loadDescuentos()
})

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
  try {
    const d = new Date(iso)
    return d.toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return String(iso).slice(0, 16)
  }
}

const historialVisible = ref(false)
const historialItem = ref<DescuentoItem | null>(null)
function openHistorial(item: DescuentoItem) {
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
}
function buildHistorialEvents(item: DescuentoItem | null): HistorialEvent[] {
  if (!item) return []
  const events: HistorialEvent[] = []
  if (item.fecha_marcado || item.fecha) {
    events.push({ status: 'Marcado para apelación', date: formatFechaIso(item.fecha_marcado) || item.fecha || '—', icon: 'pi pi-flag', color: '#6366f1' })
  }
  if (item.sede_decidio_no_apelar) {
    events.push({ status: 'La sede decidió no apelar', date: '—', icon: 'pi pi-times-circle', color: '#64748b' })
  }
  if (item.descuentos?.length) {
    for (const d of item.descuentos) {
      const quincenaLabel = d.quincena ? ` (quincena ${d.quincena})` : ''
      events.push({ status: `Descontado a la sede: ${formatMonto(d.monto)}${quincenaLabel}`, date: formatFechaIso(d.fecha), icon: 'pi pi-wallet', color: '#16a34a' })
    }
  }
  if (item.fecha_apelado) {
    events.push({ status: 'Apelado', date: formatFechaIso(item.fecha_apelado), icon: 'pi pi-send', color: '#3b82f6' })
  }
  if (item.reembolsado || item.fecha_reembolso) {
    events.push({ status: 'Reembolsado', date: formatFechaIso(item.fecha_reembolso), icon: 'pi pi-wallet', color: '#22c55e' })
  }
  if (item.descuento_confirmado && !(item.descuentos?.length)) {
    events.push({ status: 'Descontado a la sede', date: item.fecha_descuento_confirmado || '—', icon: 'pi pi-check-circle', color: '#16a34a' })
  }
  return events
}
const historialEvents = computed(() => buildHistorialEvents(historialItem.value))

const totalPerdida = computed(() =>
  items.value.reduce((sum, i) => sum + (i.perdida || 0), 0)
)
</script>

<template>
  <div class="descuentos-view">
    <Card class="mb-3">
      <template #title>Descuentos</template>
      <template #content>
        <p class="text-color-secondary mt-0 mb-3">
          Pedidos con pérdida a descontar a la sede (incluye los que la sede decidió no apelar). Marca «Confirmar descuento en nómina» cuando realmente descuentes el dinero a la sede.
        </p>
        <div class="flex flex-wrap gap-3 align-items-end mb-2">
          <div class="flex flex-column gap-2">
            <label for="desc-sede">Sede</label>
            <Select
              id="desc-sede"
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
            <label for="desc-desde">Desde</label>
            <DatePicker
              id="desc-desde"
              v-model="fechaDesdeAsDate"
              :minDate="MIN_DATE"
              dateFormat="dd/mm/yy"
              showIcon
            />
          </div>
          <div class="flex flex-column gap-2">
            <label for="desc-hasta">Hasta</label>
            <DatePicker
              id="desc-hasta"
              v-model="fechaHastaAsDate"
              :minDate="MIN_DATE"
              dateFormat="dd/mm/yy"
              showIcon
            />
          </div>
          <div class="flex align-items-center gap-2">
            <Checkbox id="solo-pendientes" v-model="soloPendientes" :binary="true" input-id="solo-pendientes" />
            <label for="solo-pendientes">Solo pendientes de confirmar</label>
          </div>
          <Button label="Cargar" icon="pi pi-refresh" :loading="loading" @click="loadDescuentos" />
        </div>
        <div v-if="items.length > 0" class="mt-2 text-color-secondary">
          Total pérdida mostrada: <strong>{{ formatMonto(totalPerdida) }}</strong>
        </div>
      </template>
    </Card>

    <Message v-if="orderError" severity="error" class="mb-3">{{ orderError }}</Message>

    <Card>
      <template #title>Pedidos con pérdida</template>
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
          <Column field="local" header="Sede">
            <template #body="{ data }">{{ data.local || '—' }}</template>
          </Column>
          <Column field="canal" header="Canal">
            <template #body="{ data }">
              <div class="flex align-items-center gap-2">
                <img
                  v-if="canalLogoUrl(data.canal)"
                  :src="canalLogoUrl(data.canal)!"
                  :alt="data.canal"
                  style="width: 24px; height: 24px; object-fit: contain"
                />
                <span>{{ data.canal || '—' }}</span>
              </div>
            </template>
          </Column>
          <Column field="codigo" header="Código" sortable />
          <Column field="fecha" header="Fecha" />
          <Column header="Observación" style="min-width: 180px">
            <template #body="{ data }">
              <Tag v-if="data.sede_decidio_no_apelar" severity="secondary" value="La sede decidió no apelar" />
              <span v-else class="text-color-secondary">—</span>
            </template>
          </Column>
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
              <span class="text-red font-semibold">{{ formatMonto(data.perdida) }}</span>
            </template>
          </Column>
          <Column header="Estado del descuento a la sede" style="min-width: 160px">
            <template #body="{ data }">
              <Tag v-if="data.descuento_confirmado && data.perdida > 0" severity="success" value="Descontado" />
              <Tag v-else-if="data.perdida > 0" severity="warn" value="Pendiente" />
              <span v-else>—</span>
            </template>
          </Column>
          <Column header="Descontado a la sede" style="min-width: 120px">
            <template #body="{ data }">
              <span v-if="data.descuento_confirmado && data.perdida > 0" class="text-green font-semibold">{{ formatMonto(data.perdida) }}</span>
              <span v-else>—</span>
            </template>
          </Column>
          <Column header="Pérdida empresa" style="min-width: 120px">
            <template #body="{ data }">
              <span v-if="!data.descuento_confirmado && data.perdida > 0" class="text-red font-semibold">{{ formatMonto(data.perdida) }}</span>
              <span v-else>—</span>
            </template>
          </Column>
          <Column header="Historial" style="min-width: 90px">
            <template #body="{ data }">
              <Button label="Ver" icon="pi pi-history" size="small" text @click="openHistorial(data)" />
            </template>
          </Column>
          <Column header="Acción">
            <template #body="{ data }">
              <Button
                v-if="(data.perdida_restante ?? data.perdida) > 0"
                :label="(data.descuentos?.length ?? 0) > 0 ? 'Registrar descuento (quincena)' : 'Confirmar descuento (quincena)'"
                icon="pi pi-check"
                severity="success"
                size="small"
                class="btn-touch"
                :loading="confirmingCodigo === data.codigo"
                @click="openDescuentoDialog(data)"
              />
              <span v-else-if="data.perdida > 0" class="text-green text-sm"><i class="pi pi-check-circle"></i> Confirmado</span>
              <span v-else>—</span>
            </template>
          </Column>
          <template #empty>
            <span class="text-color-secondary">No hay pedidos con pérdida pendientes de confirmar.</span>
          </template>
          <template #loading>
            <ProgressSpinner style="width: 40px; height: 40px" stroke-width="4" />
          </template>
        </DataTable>
      </template>
    </Card>

    <Dialog
      v-model:visible="descuentoDialogVisible"
      modal
      header="Registrar descuento por quincena"
      :closable="!descuentoLoading"
      @hide="closeDescuentoDialog"
    >
      <template #default>
        <div v-if="descuentoDialogItem" class="mb-3">
          <p><strong>Pedido:</strong> {{ descuentoDialogItem.codigo }}</p>
          <p><strong>Sede:</strong> {{ descuentoDialogItem.local || '—' }}</p>
          <p><strong>Pérdida total:</strong> {{ formatMonto(descuentoDialogItem.perdida) }}</p>
          <p v-if="(descuentoDialogItem.total_descuentos_sede ?? 0) > 0"><strong>Ya descontado:</strong> {{ formatMonto(descuentoDialogItem.total_descuentos_sede) }} — Pendiente: {{ formatMonto(descuentoDialogItem.perdida_restante ?? 0) }}</p>
        </div>
        <div class="flex flex-column gap-3">
          <div>
            <label class="block mb-1">Monto descontado en esta quincena (COP)</label>
            <InputNumber
              v-model="descuentoMonto"
              mode="currency"
              currency="COP"
              locale="es-CO"
              :min-fraction-digits="0"
              :max-fraction-digits="0"
              class="w-full"
            />
          </div>
          <div>
            <label class="block mb-1">Quincena (ej: 2026-02-1 primera quincena feb, 2026-02-2 segunda)</label>
            <InputText
              v-model="descuentoQuincena"
              placeholder="2026-02-1 o Feb 2026 - 1ra"
              class="w-full"
            />
          </div>
        </div>
      </template>
      <template #footer>
        <Button label="Cancelar" icon="pi pi-times" severity="secondary" :disabled="descuentoLoading" @click="closeDescuentoDialog" />
        <Button label="Registrar descuento" icon="pi pi-check" :loading="descuentoLoading" :disabled="(descuentoMonto ?? 0) <= 0" @click="confirmarDescuento" />
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
        <div v-if="historialItem" class="historial-timeline">
          <p class="mb-3 font-semibold">{{ historialItem.codigo }} — {{ historialItem.canal }}</p>
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
.descuentos-view {
  padding: 0.5rem;
}
.btn-touch {
  min-height: 44px;
  min-width: 44px;
}
.text-red {
  color: var(--p-red-600, #dc2626);
}
.text-green {
  color: var(--p-green-600, #16a34a);
}
.text-orange {
  color: var(--p-orange-600, #ea580c);
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
