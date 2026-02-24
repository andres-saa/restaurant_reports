<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Card from 'primevue/card'
import Checkbox from 'primevue/checkbox'
import InputNumber from 'primevue/inputnumber'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'
import Dialog from 'primevue/dialog'
import Timeline from 'primevue/timeline'
import { useConfirm } from 'primevue/useconfirm'

const API = import.meta.env.VITE_API_URL ?? ''
const confirm = useConfirm()

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
  apelacion_vencida?: boolean
  fecha_marcado?: string
  fecha_apelado?: string
  fecha_reembolso?: string
}
interface LocaleItem { id: string; name: string }

// ─── Tab ─────────────────────────────────────────────────────────────────────
type Tab = 'programar' | 'ejecutar' | 'empresa'
const activeTab = ref<Tab>('programar')

// ─── Shared state ────────────────────────────────────────────────────────────
const locales = ref<LocaleItem[]>([])
const selectedLocal = ref<string | null>(null)
const fechaDesde = ref('')
const fechaHasta = ref('')
const orderError = ref('')
const isMobile = ref(typeof window !== 'undefined' && window.innerWidth < 768)
function onResize() { isMobile.value = window.innerWidth < 768 }

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
const localeOptions = computed(() => [
  { label: 'Todas las sedes', value: null },
  ...locales.value.map((l) => ({ label: l.name, value: l.name }))
])

// ─── TAB 1: Programar ────────────────────────────────────────────────────────
const programarItems = ref<DescuentoItem[]>([])
const programarLoading = ref(false)
const soloPendientesProgramar = ref(true)

async function loadProgramar() {
  programarLoading.value = true
  orderError.value = ''
  try {
    const p = new URLSearchParams()
    if (selectedLocal.value) p.set('local', selectedLocal.value)
    p.set('fecha_desde', fechaDesde.value || todayStr())
    p.set('fecha_hasta', fechaHasta.value || todayStr())
    p.set('solo_pendientes', String(soloPendientesProgramar.value))
    const r = await fetch(`${API}/api/apelaciones/descuentos?${p}`)
    programarItems.value = (await r.json()).items ?? []
  } catch (e) {
    orderError.value = (e as Error).message
    programarItems.value = []
  } finally {
    programarLoading.value = false
  }
}

// ── Dialog programar quincenas ──
const programarDialogVisible = ref(false)
const programarDialogItem = ref<DescuentoItem | null>(null)
const programarDialogLoading = ref(false)
const numQuincenas = ref<number | null>(null)
const quincenasDefinidas = ref(false)
interface QuincenaEntrada { fecha: Date | null; monto: number | null }
const quincenaEntradas = ref<QuincenaEntrada[]>([])

function openProgramarDialog(item: DescuentoItem) {
  programarDialogItem.value = item; numQuincenas.value = null
  quincenasDefinidas.value = false; quincenaEntradas.value = []
  programarDialogVisible.value = true
}
function closeProgramarDialog() {
  programarDialogVisible.value = false; programarDialogItem.value = null
  numQuincenas.value = null; quincenasDefinidas.value = false; quincenaEntradas.value = []
}
function definirQuincenas() {
  const n = numQuincenas.value ?? 0; if (n <= 0) return
  const montoRestante = programarDialogItem.value
    ? (programarDialogItem.value.perdida_restante ?? programarDialogItem.value.perdida) : 0
  const base = montoRestante > 0 ? Math.floor(montoRestante / n) : null
  const ultimo = montoRestante > 0 ? montoRestante - (base ?? 0) * (n - 1) : null
  quincenaEntradas.value = Array.from({ length: n }, (_, i) => ({
    fecha: null,
    monto: montoRestante > 0 ? (i === n - 1 ? ultimo : base) : null
  }))
  quincenasDefinidas.value = true
}

const montoMaximoQuincenas = computed(() => {
  if (!programarDialogItem.value) return 0
  return programarDialogItem.value.perdida_restante ?? programarDialogItem.value.perdida
})
const excedeTotal = computed(() => montoMaximoQuincenas.value > 0 && totalMontoQuincenas.value > montoMaximoQuincenas.value)
function quincenaLabelFromDate(d: Date | null): string {
  if (!d) return ''
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${d.getDate() <= 15 ? '1' : '2'}`
}
const totalMontoQuincenas = computed(() => quincenaEntradas.value.reduce((s, e) => s + (e.monto ?? 0), 0))

async function confirmarProgramar() {
  const item = programarDialogItem.value; if (!item) return
  for (let i = 0; i < quincenaEntradas.value.length; i++) {
    const e = quincenaEntradas.value[i]
    if (!e.fecha) { orderError.value = `Selecciona la fecha para la quincena ${i + 1}`; return }
    if ((e.monto ?? 0) <= 0) { orderError.value = `Ingresa el monto para la quincena ${i + 1}`; return }
  }
  if (excedeTotal.value) {
    orderError.value = `La suma de las quincenas (${formatMonto(totalMontoQuincenas.value)}) supera el monto pendiente (${formatMonto(montoMaximoQuincenas.value)})`
    return
  }
  programarDialogLoading.value = true; orderError.value = ''
  try {
    for (const e of quincenaEntradas.value) {
      const fechaStr = e.fecha!.toLocaleDateString('en-CA', { timeZone: 'America/Bogota' })
      const r = await fetch(`${API}/api/apelaciones/programar-descuento`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ codigo: item.codigo, monto: e.monto, quincena: quincenaLabelFromDate(e.fecha), fecha: fechaStr })
      })
      if (!r.ok) { const err = await r.json().catch(() => ({})); throw new Error(err.detail || 'Error al programar') }
    }
    closeProgramarDialog(); await reloadAll()
  } catch (e) { orderError.value = (e as Error).message } finally { programarDialogLoading.value = false }
}

const totalPerdidaProgramar = computed(() => programarItems.value.reduce((s, i) => s + (i.perdida || 0), 0))

// ─── TAB 2: Hacer efectivo ───────────────────────────────────────────────────
const ejecutarItems = ref<DescuentoItem[]>([])
const ejecutarLoading = ref(false)

async function loadEjecutar() {
  ejecutarLoading.value = true; orderError.value = ''
  try {
    const p = new URLSearchParams()
    if (selectedLocal.value) p.set('local', selectedLocal.value)
    p.set('fecha_desde', fechaDesde.value || todayStr())
    p.set('fecha_hasta', fechaHasta.value || todayStr())
    p.set('solo_pendientes', 'false'); p.set('solo_programados', 'true')
    const r = await fetch(`${API}/api/apelaciones/descuentos?${p}`)
    ejecutarItems.value = (await r.json()).items ?? []
  } catch (e) { orderError.value = (e as Error).message; ejecutarItems.value = [] } finally { ejecutarLoading.value = false }
}

interface QuincenaRow {
  codigo: string; canal: string; local: string; fechaPedido: string
  perdida: number; id: string; monto: number; quincena: string; fechaDescuento: string
}
const quincenaRows = computed<QuincenaRow[]>(() => {
  const rows: QuincenaRow[] = []
  for (const item of ejecutarItems.value) {
    for (const d of (item.descuentos ?? [])) {
      if (d.ejecutado === false) {
        rows.push({ codigo: item.codigo, canal: item.canal, local: item.local ?? '—',
          fechaPedido: item.fecha ?? '—', perdida: item.perdida,
          id: d.id ?? '', monto: d.monto, quincena: d.quincena, fechaDescuento: d.fecha })
      }
    }
  }
  return rows
})
const ejecutandoId = ref<string | null>(null)

async function _ejecutarDescuento(row: QuincenaRow) {
  if (!row.id) { orderError.value = 'Sin ID (programado con versión antigua).'; return }
  ejecutandoId.value = row.id; orderError.value = ''
  try {
    const r = await fetch(`${API}/api/apelaciones/ejecutar-descuento`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codigo: row.codigo, descuento_id: row.id })
    })
    if (!r.ok) { const err = await r.json().catch(() => ({})); throw new Error(err.detail || 'Error') }
    await reloadAll()
  } catch (e) { orderError.value = (e as Error).message } finally { ejecutandoId.value = null }
}

function hacerEfectivo(row: QuincenaRow) {
  confirm.require({
    header: 'Confirmar descuento',
    message: `¿Confirmas que ya descontaste ${formatMonto(row.monto)} de la nómina de ${row.local}?\n\nPedido: ${row.codigo} · Quincena: ${row.quincena || row.fechaDescuento}`,
    icon: 'pi pi-check-circle',
    acceptLabel: 'Sí, hacer efectivo',
    rejectLabel: 'Cancelar',
    acceptClass: 'p-button-success',
    accept: () => _ejecutarDescuento(row),
  })
}
const totalPendienteEjecutar = computed(() => quincenaRows.value.reduce((s, r) => s + r.monto, 0))

// ─── TAB 3: Empresa asume ─────────────────────────────────────────────────────
const empresaItems = ref<DescuentoItem[]>([])
const empresaLoading = ref(false)

async function loadEmpresa() {
  empresaLoading.value = true; orderError.value = ''
  try {
    const p = new URLSearchParams()
    if (selectedLocal.value) p.set('local', selectedLocal.value)
    p.set('fecha_desde', fechaDesde.value || todayStr())
    p.set('fecha_hasta', fechaHasta.value || todayStr())
    p.set('solo_pendientes', 'false'); p.set('solo_empresa_asume', 'true')
    const r = await fetch(`${API}/api/apelaciones/descuentos?${p}`)
    empresaItems.value = (await r.json()).items ?? []
  } catch (e) { orderError.value = (e as Error).message; empresaItems.value = [] } finally { empresaLoading.value = false }
}

// ── Dialog empresa asume ──
const empresaDialogVisible = ref(false)
const empresaDialogItem = ref<DescuentoItem | null>(null)
const empresaDialogLoading = ref(false)
const montoEmpresa = ref<number | null>(null)

function openEmpresaDialog(item: DescuentoItem) {
  empresaDialogItem.value = item
  montoEmpresa.value = item.perdida_restante ?? item.perdida
  empresaDialogVisible.value = true
}
function closeEmpresaDialog() {
  empresaDialogVisible.value = false; empresaDialogItem.value = null; montoEmpresa.value = null
}
async function confirmarEmpresaAsume() {
  const item = empresaDialogItem.value; if (!item) return
  if ((montoEmpresa.value ?? 0) <= 0) { orderError.value = 'Ingresa el monto a asumir'; return }
  empresaDialogLoading.value = true; orderError.value = ''
  try {
    const r = await fetch(`${API}/api/apelaciones/asumir-empresa`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codigo: item.codigo, monto: montoEmpresa.value })
    })
    if (!r.ok) { const err = await r.json().catch(() => ({})); throw new Error(err.detail || 'Error') }
    closeEmpresaDialog(); await reloadAll()
  } catch (e) { orderError.value = (e as Error).message } finally { empresaDialogLoading.value = false }
}

const deshacienndoCodigo = ref<string | null>(null)
async function deshacerEmpresaAsume(item: DescuentoItem) {
  deshacienndoCodigo.value = item.codigo; orderError.value = ''
  try {
    const r = await fetch(`${API}/api/apelaciones/deshacer-empresa-asume`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codigo: item.codigo })
    })
    if (!r.ok) { const err = await r.json().catch(() => ({})); throw new Error(err.detail || 'Error') }
    await reloadAll()
  } catch (e) { orderError.value = (e as Error).message } finally { deshacienndoCodigo.value = null }
}

const totalEmpresaAsume = computed(() => empresaItems.value.reduce((s, i) => s + (i.monto_empresa_asume ?? 0), 0))

// ─── Historial ───────────────────────────────────────────────────────────────
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
      const label = d.ejecutado === false ? 'Programado' : 'Descontado a la sede'
      events.push({ status: `${label}: ${formatMonto(d.monto)}${q}`, date: formatFechaIso(d.fecha),
        icon: d.ejecutado === false ? 'pi pi-clock' : 'pi pi-wallet',
        color: d.ejecutado === false ? '#f59e0b' : '#16a34a' })
    }
  }
  if ((item.monto_empresa_asume ?? 0) > 0)
    events.push({ status: `Empresa asumió: ${formatMonto(item.monto_empresa_asume)}`, date: item.fecha_empresa_asume || '—', icon: 'pi pi-building', color: '#7c3aed' })
  if (item.fecha_apelado)
    events.push({ status: 'Apelado', date: formatFechaIso(item.fecha_apelado), icon: 'pi pi-send', color: '#3b82f6' })
  if (item.reembolsado || item.fecha_reembolso)
    events.push({ status: 'Reembolsado', date: formatFechaIso(item.fecha_reembolso), icon: 'pi pi-wallet', color: '#22c55e' })
  return events
}
const historialEvents = computed(() => buildHistorialEvents(historialItem.value))

// ─── Utils ───────────────────────────────────────────────────────────────────
const CANAL_LOGOS: Record<string, string> = {
  'Rappi': '/logos/rappi.png', 'Didi Food': '/logos/didi.png', 'Menú Online': '/logos/menu_online.png'
}
function canalLogoUrl(canal: string | undefined): string | null {
  if (!canal?.trim()) return null; return CANAL_LOGOS[canal.trim()] ?? null
}
function formatMonto(val: string | number | null | undefined): string {
  const n = typeof val === 'number' ? val : parseFloat(String(val || '0').replace(/[^\d.-]/g, '')) || 0
  return new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n)
}
function formatFechaIso(iso: string | null | undefined): string {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' }) } catch { return String(iso).slice(0, 16) }
}

// ─── Init ────────────────────────────────────────────────────────────────────
async function reloadAll() {
  await Promise.all([loadProgramar(), loadEjecutar(), loadEmpresa()])
}

onMounted(async () => {
  if (typeof window !== 'undefined') window.addEventListener('resize', onResize)
  try {
    const r = await fetch(`${API}/report/locales`)
    const data = await r.json()
    locales.value = (data.locales ?? []).map((x: LocaleItem | string) =>
      typeof x === 'object' && x && 'name' in x ? { id: (x as LocaleItem).id || '', name: (x as LocaleItem).name } : { id: '', name: String(x) }
    )
  } catch { locales.value = [] }
  const range = lastTwoWeeksRange()
  fechaDesde.value = range.desde; fechaHasta.value = range.hasta
  await reloadAll()
})
onBeforeUnmount(() => { if (typeof window !== 'undefined') window.removeEventListener('resize', onResize) })

watch([selectedLocal, fechaDesde, fechaHasta], reloadAll)
watch(soloPendientesProgramar, loadProgramar)
</script>

<template>
  <div class="descuentos-view">

    <!-- ── Barra de sub-navegación ── -->
    <div class="desc-subnav">
      <button class="desc-subnav-btn" :class="{ active: activeTab === 'programar' }" @click="activeTab = 'programar'">
        <i class="pi pi-calendar-plus"></i>
        Programar descuentos
      </button>
      <button class="desc-subnav-btn" :class="{ active: activeTab === 'ejecutar' }" @click="activeTab = 'ejecutar'">
        <i class="pi pi-check-circle"></i>
        Hacer efectivo
        <span v-if="quincenaRows.length > 0" class="desc-subnav-badge">{{ quincenaRows.length }}</span>
      </button>
      <button class="desc-subnav-btn" :class="{ active: activeTab === 'empresa' }" @click="activeTab = 'empresa'">
        <i class="pi pi-building"></i>
        Empresa asume
        <span v-if="empresaItems.length > 0" class="desc-subnav-badge desc-subnav-badge-purple">{{ empresaItems.length }}</span>
      </button>
    </div>

    <!-- ── Filtros comunes ── -->
    <Card class="mb-3">
      <template #content>
        <div class="flex flex-wrap gap-3 align-items-end">
          <div class="flex flex-column gap-2">
            <label for="desc-sede">Sede</label>
            <Select id="desc-sede" v-model="selectedLocal" :options="localeOptions" option-label="label" option-value="value" placeholder="Todas" class="w-full" filter filter-placeholder="Buscar sede..." />
          </div>
          <div class="flex flex-column gap-2">
            <label for="desc-desde">Desde</label>
            <DatePicker id="desc-desde" v-model="fechaDesdeAsDate" :minDate="MIN_DATE" dateFormat="dd/mm/yy" showIcon />
          </div>
          <div class="flex flex-column gap-2">
            <label for="desc-hasta">Hasta</label>
            <DatePicker id="desc-hasta" v-model="fechaHastaAsDate" :minDate="MIN_DATE" dateFormat="dd/mm/yy" showIcon />
          </div>
          <Button label="Actualizar" icon="pi pi-refresh" :loading="programarLoading || ejecutarLoading || empresaLoading" @click="reloadAll" />
        </div>
      </template>
    </Card>

    <Message v-if="orderError" severity="error" class="mb-3">{{ orderError }}</Message>

    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- TAB 1: Programar descuentos                                           -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <template v-if="activeTab === 'programar'">
      <Card>
        <template #title>
          <div class="flex align-items-center justify-content-between flex-wrap gap-2">
            <span><i class="pi pi-calendar-plus mr-2"></i>Programar descuentos</span>
            <div class="flex align-items-center gap-2">
              <Checkbox id="solo-pendientes-prog" v-model="soloPendientesProgramar" :binary="true" />
              <label for="solo-pendientes-prog" class="text-sm font-normal">Solo sin cubrir</label>
            </div>
          </div>
        </template>
        <template #subtitle>
          Define cuándo y cuánto descontar a cada sede, o registra que la empresa asume la pérdida.
        </template>
        <template #content>
          <div v-if="programarItems.length > 0" class="mb-3 text-color-secondary text-sm">
            Total pérdida mostrada: <strong>{{ formatMonto(totalPerdidaProgramar) }}</strong>
          </div>
          <DataTable :value="programarItems" :loading="programarLoading" data-key="codigo"
            class="p-datatable-sm p-datatable-striped"
            :paginator="programarItems.length > 10" :rows="10"
            paginator-template="CurrentPageReport FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink"
            current-page-report-template="{first}–{last} de {totalRecords}" scrollable>
            <Column field="local" header="Sede">
              <template #body="{ data }">
                <div class="flex flex-column gap-1">
                  <span>{{ data.local || '—' }}</span>
                  <span v-if="data.apelacion_vencida" class="badge-vencida">
                    <i class="pi pi-clock mr-1 text-xs"></i>Plazo vencido
                  </span>
                </div>
              </template>
            </Column>
            <Column field="canal" header="Canal">
              <template #body="{ data }">
                <div class="flex align-items-center gap-2">
                  <img v-if="canalLogoUrl(data.canal)" :src="canalLogoUrl(data.canal)!" :alt="data.canal" style="width:22px;height:22px;object-fit:contain" />
                  <span>{{ data.canal || '—' }}</span>
                </div>
              </template>
            </Column>
            <Column field="codigo" header="Código" sortable />
            <Column field="fecha" header="Fecha pedido" />
            <Column header="Pérdida total">
              <template #body="{ data }"><span class="text-red font-semibold">{{ formatMonto(data.perdida) }}</span></template>
            </Column>
            <Column header="Ya programado / Empresa">
              <template #body="{ data }">
                <div class="flex flex-column gap-1">
                  <span v-if="(data.total_programado ?? 0) > 0" class="text-orange font-semibold text-sm">
                    <i class="pi pi-calendar text-xs mr-1"></i>{{ formatMonto(data.total_programado) }}
                  </span>
                  <span v-if="(data.monto_empresa_asume ?? 0) > 0" class="text-purple font-semibold text-sm">
                    <i class="pi pi-building text-xs mr-1"></i>{{ formatMonto(data.monto_empresa_asume) }}
                  </span>
                  <span v-if="(data.total_programado ?? 0) === 0 && (data.monto_empresa_asume ?? 0) === 0">—</span>
                </div>
              </template>
            </Column>
            <Column header="Pendiente">
              <template #body="{ data }">
                <span v-if="(data.perdida_restante ?? 0) > 0" class="text-red font-semibold">{{ formatMonto(data.perdida_restante) }}</span>
                <span v-else class="text-green font-semibold"><i class="pi pi-check-circle mr-1"></i>Cubierto</span>
              </template>
            </Column>
            <Column header="Quincenas" style="min-width:180px">
              <template #body="{ data }">
                <div v-if="data.descuentos?.length" class="flex flex-column gap-1">
                  <div v-for="(d, i) in data.descuentos" :key="i" class="quincena-chip" :class="d.ejecutado === false ? 'desc-chip-pendiente' : 'desc-chip-ejecutado'">
                    <i :class="d.ejecutado === false ? 'pi pi-clock' : 'pi pi-check'" class="mr-1 text-xs"></i>
                    <span>{{ d.quincena || d.fecha?.slice(0,7) }} — {{ formatMonto(d.monto) }}</span>
                  </div>
                </div>
                <span v-else class="text-color-secondary text-sm">Sin quincenas</span>
              </template>
            </Column>
            <Column header="Historial" style="min-width:80px">
              <template #body="{ data }"><Button label="Ver" icon="pi pi-history" size="small" text @click="openHistorial(data)" /></template>
            </Column>
            <Column header="Acción" :frozen="!isMobile" align-frozen="right" style="min-width:220px">
              <template #body="{ data }">
                <div class="flex gap-1 flex-wrap">
                  <Button
                    v-if="(data.perdida_restante ?? data.perdida) > 0"
                    label="Programar"
                    icon="pi pi-calendar-plus"
                    severity="warn"
                    size="small"
                    class="btn-touch"
                    @click="openProgramarDialog(data)"
                  />
                  <Button
                    v-if="(data.perdida_restante ?? data.perdida) > 0"
                    label="Empresa asume"
                    icon="pi pi-building"
                    severity="secondary"
                    size="small"
                    class="btn-touch btn-empresa"
                    @click="openEmpresaDialog(data)"
                  />
                  <span v-if="(data.perdida_restante ?? 0) === 0" class="text-green text-sm align-self-center">
                    <i class="pi pi-check-circle"></i> Cubierto
                  </span>
                </div>
              </template>
            </Column>
            <template #empty><span class="text-color-secondary">No hay pedidos con pérdida pendiente de cubrir.</span></template>
            <template #loading><ProgressSpinner style="width:40px;height:40px" stroke-width="4" /></template>
          </DataTable>
        </template>
      </Card>
    </template>

    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- TAB 2: Hacer efectivo                                                 -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <template v-else-if="activeTab === 'ejecutar'">
      <Card>
        <template #title><span><i class="pi pi-check-circle mr-2"></i>Hacer efectivo</span></template>
        <template #subtitle>Descuentos programados pendientes de cobro. Márcalos cuando realmente los apliques en nómina.</template>
        <template #content>
          <div v-if="quincenaRows.length > 0" class="mb-3 text-color-secondary text-sm">
            Total pendiente de ejecutar: <strong class="text-red">{{ formatMonto(totalPendienteEjecutar) }}</strong>
          </div>
          <DataTable :value="quincenaRows" :loading="ejecutarLoading"
            class="p-datatable-sm p-datatable-striped"
            :paginator="quincenaRows.length > 15" :rows="15"
            paginator-template="CurrentPageReport FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink"
            current-page-report-template="{first}–{last} de {totalRecords}" scrollable>
            <Column field="local" header="Sede" />
            <Column field="canal" header="Canal">
              <template #body="{ data }">
                <div class="flex align-items-center gap-2">
                  <img v-if="canalLogoUrl(data.canal)" :src="canalLogoUrl(data.canal)!" :alt="data.canal" style="width:22px;height:22px;object-fit:contain" />
                  <span>{{ data.canal }}</span>
                </div>
              </template>
            </Column>
            <Column field="codigo" header="Código" sortable />
            <Column field="fechaPedido" header="Fecha pedido" />
            <Column header="Pérdida pedido"><template #body="{ data }"><span class="text-red font-semibold">{{ formatMonto(data.perdida) }}</span></template></Column>
            <Column field="quincena" header="Quincena" />
            <Column header="Monto a descontar"><template #body="{ data }"><span class="font-semibold text-orange">{{ formatMonto(data.monto) }}</span></template></Column>
            <Column field="fechaDescuento" header="Fecha programada" />
            <Column header="Estado"><template #body><Tag severity="warn" value="Pendiente" /></template></Column>
            <Column header="Acción" :frozen="!isMobile" align-frozen="right" style="min-width:150px">
              <template #body="{ data }">
                <Button label="Hacer efectivo" icon="pi pi-check" severity="success" size="small" class="btn-touch"
                  :loading="ejecutandoId === data.id" @click="hacerEfectivo(data)" />
              </template>
            </Column>
            <template #empty>
              <div class="text-center py-3">
                <i class="pi pi-check-circle text-green" style="font-size:2rem"></i>
                <p class="text-color-secondary mt-2">No hay descuentos programados pendientes.</p>
              </div>
            </template>
            <template #loading><ProgressSpinner style="width:40px;height:40px" stroke-width="4" /></template>
          </DataTable>
        </template>
      </Card>
    </template>

    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- TAB 3: Empresa asume                                                  -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <template v-else-if="activeTab === 'empresa'">
      <Card>
        <template #title><span><i class="pi pi-building mr-2"></i>Empresa asume</span></template>
        <template #subtitle>Pedidos cuya pérdida (total o parcial) fue absorbida por la empresa y no descontada a ninguna sede.</template>
        <template #content>
          <div v-if="empresaItems.length > 0" class="mb-3 text-color-secondary text-sm">
            Total asumido por la empresa: <strong class="text-purple">{{ formatMonto(totalEmpresaAsume) }}</strong>
          </div>
          <DataTable :value="empresaItems" :loading="empresaLoading" data-key="codigo"
            class="p-datatable-sm p-datatable-striped"
            :paginator="empresaItems.length > 10" :rows="10"
            paginator-template="CurrentPageReport FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink"
            current-page-report-template="{first}–{last} de {totalRecords}" scrollable>
            <Column field="local" header="Sede"><template #body="{ data }">{{ data.local || '—' }}</template></Column>
            <Column field="canal" header="Canal">
              <template #body="{ data }">
                <div class="flex align-items-center gap-2">
                  <img v-if="canalLogoUrl(data.canal)" :src="canalLogoUrl(data.canal)!" :alt="data.canal" style="width:22px;height:22px;object-fit:contain" />
                  <span>{{ data.canal || '—' }}</span>
                </div>
              </template>
            </Column>
            <Column field="codigo" header="Código" sortable />
            <Column field="fecha" header="Fecha pedido" />
            <Column header="Pérdida total"><template #body="{ data }"><span class="text-red font-semibold">{{ formatMonto(data.perdida) }}</span></template></Column>
            <Column header="Empresa asumió" style="min-width:130px">
              <template #body="{ data }">
                <span class="text-purple font-semibold"><i class="pi pi-building mr-1"></i>{{ formatMonto(data.monto_empresa_asume) }}</span>
              </template>
            </Column>
            <Column header="También descontado a sede" style="min-width:150px">
              <template #body="{ data }">
                <span v-if="(data.total_descuentos_sede ?? 0) > 0" class="text-green font-semibold">{{ formatMonto(data.total_descuentos_sede) }}</span>
                <span v-else class="text-color-secondary">—</span>
              </template>
            </Column>
            <Column header="Fecha registro">
              <template #body="{ data }">{{ data.fecha_empresa_asume || '—' }}</template>
            </Column>
            <Column header="Estado" style="min-width:120px">
              <template #body="{ data }">
                <Tag v-if="(data.perdida_restante_ejecutar ?? data.perdida) <= 0" severity="success" value="Cubierto" />
                <Tag v-else severity="warn" :value="`Pendiente: ${formatMonto(data.perdida_restante_ejecutar)}`" />
              </template>
            </Column>
            <Column header="Historial" style="min-width:80px">
              <template #body="{ data }"><Button label="Ver" icon="pi pi-history" size="small" text @click="openHistorial(data)" /></template>
            </Column>
            <Column header="Acción" :frozen="!isMobile" align-frozen="right" style="min-width:120px">
              <template #body="{ data }">
                <Button label="Deshacer" icon="pi pi-undo" severity="danger" size="small" text
                  :loading="deshacienndoCodigo === data.codigo" @click="deshacerEmpresaAsume(data)" />
              </template>
            </Column>
            <template #empty>
              <div class="text-center py-3">
                <i class="pi pi-building text-color-secondary" style="font-size:2rem"></i>
                <p class="text-color-secondary mt-2">No hay pérdidas asumidas por la empresa en este período.</p>
              </div>
            </template>
            <template #loading><ProgressSpinner style="width:40px;height:40px" stroke-width="4" /></template>
          </DataTable>
        </template>
      </Card>
    </template>

    <!-- ── Dialog: Programar quincenas ── -->
    <Dialog v-model:visible="programarDialogVisible" modal header="Programar descuento a la sede"
      :closable="!programarDialogLoading" style="min-width:360px;max-width:540px;width:95vw" @hide="closeProgramarDialog">
      <template #default>
        <div v-if="programarDialogItem" class="mb-3">
          <p class="m-0"><strong>Pedido:</strong> {{ programarDialogItem.codigo }}</p>
          <p class="m-0 mt-1"><strong>Sede:</strong> {{ programarDialogItem.local || '—' }}</p>
          <p class="m-0 mt-1"><strong>Pérdida total:</strong> {{ formatMonto(programarDialogItem.perdida) }}</p>
          <p v-if="(programarDialogItem.total_programado ?? 0) > 0" class="m-0 mt-1">
            <strong>Ya programado:</strong> {{ formatMonto(programarDialogItem.total_programado) }}
            — <strong>Pendiente:</strong> {{ formatMonto(programarDialogItem.perdida_restante ?? 0) }}
          </p>
        </div>
        <div v-if="!quincenasDefinidas" class="flex flex-column gap-3 mt-3">
          <div>
            <label class="block mb-1 font-semibold">¿En cuántas quincenas se va a realizar el descuento?</label>
            <InputNumber v-model="numQuincenas" :min="1" :max="12" :show-buttons="true" button-layout="horizontal" class="w-full" placeholder="Ej: 2" />
          </div>
          <Button label="Continuar" icon="pi pi-arrow-right" icon-pos="right" :disabled="!numQuincenas || numQuincenas < 1" @click="definirQuincenas" />
        </div>
        <div v-else class="flex flex-column gap-3 mt-3">
          <div v-for="(entrada, idx) in quincenaEntradas" :key="idx" class="quincena-row p-3">
            <p class="m-0 mb-2 font-semibold text-color-secondary">Quincena {{ idx + 1 }}</p>
            <div class="flex flex-column gap-2">
              <div>
                <label class="block mb-1">Fecha del descuento</label>
                <DatePicker v-model="entrada.fecha" :minDate="MIN_DATE" dateFormat="dd/mm/yy" showIcon class="w-full" :placeholder="`Seleccionar fecha — quincena ${idx + 1}`" />
                <small v-if="entrada.fecha" class="text-color-secondary mt-1 block">Quincena: {{ quincenaLabelFromDate(entrada.fecha) }}</small>
              </div>
              <div>
                <label class="block mb-1">Monto (COP)</label>
                <InputNumber v-model="entrada.monto" mode="currency" currency="COP" locale="es-CO" :min-fraction-digits="0" :max-fraction-digits="0" class="w-full" />
              </div>
            </div>
          </div>
          <div class="quincenas-total-row text-sm mt-1" :class="excedeTotal ? 'text-red' : 'text-color-secondary'">
            <span>Total a programar: <strong>{{ formatMonto(totalMontoQuincenas) }}</strong></span>
            <span v-if="montoMaximoQuincenas > 0">
              &nbsp;/ Pendiente: <strong>{{ formatMonto(montoMaximoQuincenas) }}</strong>
            </span>
            <span v-if="excedeTotal" class="ml-2">
              <i class="pi pi-exclamation-triangle mr-1"></i>Supera el monto permitido
            </span>
          </div>
          <Button icon="pi pi-arrow-left" label="Cambiar número de quincenas" severity="secondary" text size="small" :disabled="programarDialogLoading" @click="quincenasDefinidas = false" />
        </div>
      </template>
      <template #footer>
        <Button label="Cancelar" icon="pi pi-times" severity="secondary" :disabled="programarDialogLoading" @click="closeProgramarDialog" />
        <Button v-if="quincenasDefinidas"
          :label="quincenaEntradas.length === 1 ? 'Guardar programación' : `Guardar ${quincenaEntradas.length} quincenas`"
          icon="pi pi-calendar-plus" severity="warn" :loading="programarDialogLoading"
          :disabled="quincenaEntradas.some(e => !e.fecha || (e.monto ?? 0) <= 0) || excedeTotal"
          @click="confirmarProgramar" />
      </template>
    </Dialog>

    <!-- ── Dialog: Empresa asume ── -->
    <Dialog v-model:visible="empresaDialogVisible" modal header="Empresa asume la pérdida"
      :closable="!empresaDialogLoading" style="min-width:340px;max-width:480px;width:95vw" @hide="closeEmpresaDialog">
      <template #default>
        <div v-if="empresaDialogItem">
          <div class="empresa-info-box mb-3">
            <p class="m-0"><strong>Pedido:</strong> {{ empresaDialogItem.codigo }}</p>
            <p class="m-0 mt-1"><strong>Sede:</strong> {{ empresaDialogItem.local || '—' }}</p>
            <p class="m-0 mt-1"><strong>Pérdida total:</strong> <span class="text-red font-semibold">{{ formatMonto(empresaDialogItem.perdida) }}</span></p>
            <p v-if="(empresaDialogItem.total_programado ?? 0) > 0" class="m-0 mt-1">
              <strong>Ya programado a sede:</strong> {{ formatMonto(empresaDialogItem.total_programado) }}
            </p>
            <p v-if="(empresaDialogItem.monto_empresa_asume ?? 0) > 0" class="m-0 mt-1">
              <strong>Empresa ya asumió:</strong> {{ formatMonto(empresaDialogItem.monto_empresa_asume) }}
            </p>
          </div>
          <div class="flex flex-column gap-2">
            <label class="font-semibold">Monto que asume la empresa (COP)</label>
            <InputNumber v-model="montoEmpresa" mode="currency" currency="COP" locale="es-CO"
              :min-fraction-digits="0" :max-fraction-digits="0" class="w-full"
              :min="1" :max="empresaDialogItem.perdida" />
            <small class="text-color-secondary">
              Pendiente restante: <strong>{{ formatMonto(empresaDialogItem.perdida_restante ?? empresaDialogItem.perdida) }}</strong>
            </small>
          </div>
        </div>
      </template>
      <template #footer>
        <Button label="Cancelar" icon="pi pi-times" severity="secondary" :disabled="empresaDialogLoading" @click="closeEmpresaDialog" />
        <Button label="Confirmar — Empresa asume" icon="pi pi-building" severity="secondary"
          class="btn-empresa-confirm" :loading="empresaDialogLoading"
          :disabled="(montoEmpresa ?? 0) <= 0" @click="confirmarEmpresaAsume" />
      </template>
    </Dialog>

    <!-- ── Dialog: Historial ── -->
    <Dialog v-model:visible="historialVisible" modal header="Historial de la orden" @hide="closeHistorial">
      <template #default>
        <div v-if="historialItem" class="historial-timeline">
          <p class="mb-3 font-semibold">{{ historialItem.codigo }} — {{ historialItem.canal }}</p>
          <Timeline v-if="historialEvents.length" :value="historialEvents" align="left">
            <template #opposite="{ item: ev }"><small class="text-surface-500">{{ ev.date }}</small></template>
            <template #content="{ item: ev }"><strong>{{ ev.status }}</strong></template>
            <template #marker="{ item: ev }">
              <span class="historial-marker" :style="{ background: ev.color }"><i :class="ev.icon"></i></span>
            </template>
          </Timeline>
          <p v-else class="text-color-secondary">Sin eventos registrados.</p>
        </div>
      </template>
      <template #footer><Button label="Cerrar" icon="pi pi-times" @click="closeHistorial" /></template>
    </Dialog>
  </div>
</template>

<style>
/* Dark mode — non-scoped para alcanzar .app-dark en <html> */
.app-dark .desc-subnav {
  background: var(--p-surface-800) !important;
  border-color: var(--p-surface-700) !important;
}
.app-dark .desc-subnav-btn {
  color: var(--p-text-muted-color) !important;
}
.app-dark .desc-subnav-btn:hover {
  background: var(--p-surface-700) !important;
  color: var(--p-text-color) !important;
}
.app-dark .desc-subnav-btn.active {
  background: var(--p-surface-600) !important;
  color: #fff !important;
  box-shadow: 0 1px 4px rgba(0,0,0,.4) !important;
}
.app-dark .desc-chip-pendiente {
  background: #3d2000 !important; color: #fcd34d !important; border-color: #78350f !important;
}
.app-dark .desc-chip-ejecutado {
  background: #052e16 !important; color: #86efac !important; border-color: #166534 !important;
}
.app-dark .quincena-row {
  background: var(--p-surface-800) !important;
  border-color: var(--p-surface-600) !important;
}
.app-dark .empresa-info-box {
  background: var(--p-surface-800) !important;
  border-color: var(--p-surface-600) !important;
}
.app-dark .badge-vencida {
  background: #3f0f0f !important; color: #fca5a5 !important; border-color: #7f1d1d !important;
}
</style>

<style scoped>
.descuentos-view { padding: 0.5rem; }

/* ── Sub-nav ── */
.desc-subnav {
  display: flex; gap: 0; margin-bottom: 1rem;
  background: var(--p-surface-100); border-radius: 10px;
  padding: 4px; border: 1px solid var(--p-surface-200);
}
.desc-subnav-btn {
  flex: 1; display: flex; align-items: center; justify-content: center;
  gap: 0.5rem; padding: 0.55rem 0.75rem; border: none; border-radius: 8px;
  background: transparent; color: var(--p-text-muted-color); font-weight: 500;
  font-size: 0.9rem; cursor: pointer; transition: background 0.15s, color 0.15s;
  position: relative; font-family: inherit;
}
.desc-subnav-btn:hover { background: var(--p-surface-200); color: var(--p-text-color); }
.desc-subnav-btn.active {
  background: var(--p-surface-0); color: #000;
  font-weight: 600; box-shadow: 0 1px 4px rgba(0,0,0,.15);
}
.desc-subnav-badge {
  background: var(--p-primary-color); color: #fff; border-radius: 999px;
  font-size: 0.72rem; font-weight: 700; padding: 0 6px;
  min-width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center; line-height: 1;
}
.desc-subnav-badge-purple { background: #7c3aed; }

/* ── Chips ── */
.quincena-chip {
  display: inline-flex; align-items: center; padding: 2px 8px;
  border-radius: 999px; font-size: 0.78rem; font-weight: 500;
}
.desc-chip-pendiente { background: #fef3c7; color: #92400e; border: 1px solid #fde68a; }
.desc-chip-ejecutado { background: #dcfce7; color: #14532d; border: 1px solid #bbf7d0; }

/* ── Quincena row dialog ── */
.quincena-row {
  background: var(--p-surface-50); border: 1px solid var(--p-surface-200); border-radius: 6px;
}

/* ── Empresa info box ── */
.empresa-info-box {
  background: var(--p-surface-50); border: 1px solid var(--p-surface-200);
  border-radius: 8px; padding: 0.75rem 1rem;
}

/* ── Quincenas total row ── */
.quincenas-total-row { padding: 0.4rem 0.6rem; border-radius: 6px; background: var(--p-surface-50); border: 1px solid var(--p-surface-200); }
.quincenas-total-row.text-red { background: #fef2f2; border-color: #fecaca; }

/* ── Badge plazo vencido ── */
.badge-vencida {
  display: inline-flex; align-items: center; padding: 2px 7px;
  border-radius: 999px; font-size: 0.72rem; font-weight: 600;
  background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca;
}

/* ── Misc ── */
.btn-touch { min-height: 40px; min-width: 40px; }
.btn-empresa { border-color: #7c3aed !important; color: #7c3aed !important; }
.btn-empresa:hover { background: rgba(124, 58, 237, 0.12) !important; }
.btn-empresa-confirm { background: #7c3aed !important; border-color: #7c3aed !important; color: #fff !important; }
.btn-empresa-confirm:hover { background: #6d28d9 !important; }
.text-red { color: var(--p-red-600, #dc2626); }
.text-green { color: var(--p-green-600, #16a34a); }
.text-orange { color: var(--p-orange-600, #ea580c); }
.text-purple { color: #7c3aed; }
.historial-timeline { padding: 0.75rem 0.5rem; }
.historial-marker {
  display: flex; align-items: center; justify-content: center;
  width: 2rem; height: 2rem; border-radius: 50%; color: white;
}
.historial-marker i { font-size: 0.875rem; }

:deep(.p-datepicker-input), :deep(.p-inputnumber-input) {
  background: var(--p-form-field-background, var(--p-surface-0));
  color: var(--p-form-field-color, var(--p-text-color));
  border-color: var(--p-form-field-border-color, var(--p-surface-300));
}

@media (max-width: 640px) {
  .desc-subnav-btn { font-size: 0.78rem; padding: 0.5rem 0.35rem; gap: 0.3rem; }
  .desc-subnav-btn .pi { font-size: 0.85rem; }
}
</style>
