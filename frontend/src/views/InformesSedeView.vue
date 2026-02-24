<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import DatePicker from 'primevue/datepicker'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Chart from 'primevue/chart'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import Checkbox from 'primevue/checkbox'

const API = import.meta.env.VITE_API_URL ?? ''
const route = useRoute()

const sede = computed(() => (route.query.sede as string) || '')

// ── Métricas visibles + orden secciones (persistente en backend) ─────────────
const STORAGE_KEY = 'informes_sede_visible_v1'
const PREFS_KEY = 'sede_informes_v1'

interface VisibleMetrics {
  kpi_total_ordenes: boolean; kpi_con_problemas: boolean; kpi_sin_problemas: boolean
  kpi_sin_apelar: boolean; kpi_apeladas: boolean; kpi_sede_no_apelar: boolean
  kpi_reembolsadas: boolean; kpi_pendiente_reembolso: boolean; kpi_reembolso_retraso: boolean
  kpi_descontado: boolean; kpi_pendiente_descuento: boolean; kpi_descuento_retraso: boolean
  kpi_empresa_asume: boolean; kpi_perdida_neta: boolean
  chart_por_dia: boolean; chart_por_canal: boolean
  col_ordenes: boolean; col_con_problemas: boolean; col_sin_apelar: boolean
  col_apeladas: boolean; col_reembolsadas: boolean; col_pend_reembolso: boolean
  col_reembolso_retraso: boolean; col_pend_descuento: boolean; col_descuento_retraso: boolean
  col_empresa_asume: boolean; col_perdida: boolean
}

const DEFAULT_METRICS: VisibleMetrics = {
  kpi_total_ordenes: true, kpi_con_problemas: true, kpi_sin_problemas: true,
  kpi_sin_apelar: true, kpi_apeladas: true, kpi_sede_no_apelar: true,
  kpi_reembolsadas: true, kpi_pendiente_reembolso: true, kpi_reembolso_retraso: true,
  kpi_descontado: true, kpi_pendiente_descuento: true, kpi_descuento_retraso: true,
  kpi_empresa_asume: true, kpi_perdida_neta: true,
  chart_por_dia: true, chart_por_canal: true,
  col_ordenes: true, col_con_problemas: true, col_sin_apelar: true,
  col_apeladas: true, col_reembolsadas: true, col_pend_reembolso: true,
  col_reembolso_retraso: true, col_pend_descuento: true, col_descuento_retraso: true,
  col_empresa_asume: true, col_perdida: true,
}

const DEFAULT_SECTIONS_ORDER = ['ordenes', 'apelaciones', 'reembolsos', 'descuentos', 'graficos']

const DEFAULT_KPI_ORDERS: Record<string, string[]> = {
  ordenes:     ['kpi_total_ordenes', 'kpi_con_problemas', 'kpi_sin_problemas'],
  apelaciones: ['kpi_sin_apelar', 'kpi_apeladas', 'kpi_sede_no_apelar'],
  reembolsos:  ['kpi_reembolsadas', 'kpi_pendiente_reembolso', 'kpi_reembolso_retraso'],
  descuentos:  ['kpi_descontado', 'kpi_pendiente_descuento', 'kpi_descuento_retraso', 'kpi_empresa_asume', 'kpi_perdida_neta'],
}

function cloneKpiOrders() {
  return Object.fromEntries(Object.entries(DEFAULT_KPI_ORDERS).map(([k, v]) => [k, [...v]]))
}

const visible = ref<VisibleMetrics>({ ...DEFAULT_METRICS })
const sectionsOrder = ref<string[]>([...DEFAULT_SECTIONS_ORDER])
const kpiOrders = ref<Record<string, string[]>>(cloneKpiOrders())
const settingsOpen = ref(false)

let saveTimer: ReturnType<typeof setTimeout> | null = null

async function loadPrefs() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      visible.value = { ...DEFAULT_METRICS, ...(parsed.visible ?? parsed) }
      if (Array.isArray(parsed.sections_order)) sectionsOrder.value = parsed.sections_order
      if (parsed.kpi_orders && typeof parsed.kpi_orders === 'object')
        kpiOrders.value = { ...cloneKpiOrders(), ...parsed.kpi_orders }
    }
  } catch {}
  try {
    const r = await fetch(`${API}/api/preferencias/${PREFS_KEY}`)
    if (r.ok) {
      const body = await r.json()
      if (body.data) {
        visible.value = { ...DEFAULT_METRICS, ...(body.data.visible ?? {}) }
        if (Array.isArray(body.data.sections_order)) sectionsOrder.value = body.data.sections_order
        if (body.data.kpi_orders && typeof body.data.kpi_orders === 'object')
          kpiOrders.value = { ...cloneKpiOrders(), ...body.data.kpi_orders }
      }
    }
  } catch {}
}

function savePrefs() {
  const payload = { visible: visible.value, sections_order: sectionsOrder.value, kpi_orders: kpiOrders.value }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(async () => {
    try {
      await fetch(`${API}/api/preferencias/${PREFS_KEY}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
    } catch {}
  }, 600)
}

watch(visible, savePrefs, { deep: true })
watch(sectionsOrder, savePrefs, { deep: true })
watch(kpiOrders, savePrefs, { deep: true })
function resetMetrics() {
  visible.value = { ...DEFAULT_METRICS }
  sectionsOrder.value = [...DEFAULT_SECTIONS_ORDER]
  kpiOrders.value = cloneKpiOrders()
}

// Drag & drop vertical de secciones
const dragSrcIdx = ref(-1)
const dragOverIdx = ref(-1)
function onDragStart(idx: number, e: DragEvent) {
  dragSrcIdx.value = idx
  if (e.dataTransfer) { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', String(idx)) }
}
function onDragOver(idx: number, e: DragEvent) {
  e.preventDefault()
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'
  dragOverIdx.value = idx
}
function onDrop(idx: number) {
  const src = dragSrcIdx.value
  if (src === -1 || src === idx) { onDragEnd(); return }
  const arr = [...sectionsOrder.value]
  const [moved] = arr.splice(src, 1)
  arr.splice(idx, 0, moved)
  sectionsOrder.value = arr
  onDragEnd()
}
function onDragEnd() { dragSrcIdx.value = -1; dragOverIdx.value = -1 }

// Drag & drop horizontal de KPI cards
const hSection = ref('')
const hSrcIdx  = ref(-1)
const hOverIdx = ref(-1)
function onHDragStart(section: string, idx: number, e: DragEvent) {
  hSection.value = section; hSrcIdx.value = idx
  if (e.dataTransfer) { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', `h:${section}:${idx}`) }
}
function onHDragOver(section: string, idx: number) {
  if (section !== hSection.value) return
  hOverIdx.value = idx
}
function onHDrop(section: string, idx: number) {
  const src = hSrcIdx.value
  if (hSection.value !== section || src === -1 || src === idx) { onHDragEnd(); return }
  const arr = [...(kpiOrders.value[section] ?? [])]
  const [moved] = arr.splice(src, 1)
  arr.splice(idx, 0, moved)
  kpiOrders.value = { ...kpiOrders.value, [section]: arr }
  onHDragEnd()
}
function onHDragEnd() { hSection.value = ''; hSrcIdx.value = -1; hOverIdx.value = -1 }

interface MetricGroup { label: string; items: { key: keyof VisibleMetrics; label: string }[] }
const metricGroups: MetricGroup[] = [
  { label: 'KPIs — Órdenes', items: [
    { key: 'kpi_total_ordenes', label: 'Total órdenes' },
    { key: 'kpi_con_problemas', label: 'Con problemas' },
    { key: 'kpi_sin_problemas', label: 'Sin problemas' },
  ]},
  { label: 'KPIs — Estado apelaciones', items: [
    { key: 'kpi_sin_apelar', label: 'Sin apelar' },
    { key: 'kpi_apeladas', label: 'Apeladas' },
    { key: 'kpi_sede_no_apelar', label: 'Sede no apelar' },
  ]},
  { label: 'KPIs — Reembolsos', items: [
    { key: 'kpi_reembolsadas', label: 'Reembolsadas' },
    { key: 'kpi_pendiente_reembolso', label: 'Pendiente reembolso' },
    { key: 'kpi_reembolso_retraso', label: 'Reembolso con retraso' },
  ]},
  { label: 'KPIs — Descuentos', items: [
    { key: 'kpi_descontado', label: 'Descontado' },
    { key: 'kpi_pendiente_descuento', label: 'Pendiente descuento' },
    { key: 'kpi_descuento_retraso', label: 'Descuento con retraso' },
    { key: 'kpi_empresa_asume', label: 'Empresa asume' },
    { key: 'kpi_perdida_neta', label: 'Pérdida neta' },
  ]},
  { label: 'Gráficos', items: [
    { key: 'chart_por_dia', label: 'Problemas por día' },
    { key: 'chart_por_canal', label: 'Pérdida por canal' },
  ]},
  { label: 'Columnas de tabla', items: [
    { key: 'col_ordenes', label: 'Órdenes' },
    { key: 'col_con_problemas', label: 'Con problemas' },
    { key: 'col_sin_apelar', label: 'Sin apelar' },
    { key: 'col_apeladas', label: 'Apeladas' },
    { key: 'col_reembolsadas', label: 'Reembolsadas' },
    { key: 'col_pend_reembolso', label: 'Pend. reembolso' },
    { key: 'col_reembolso_retraso', label: 'Reembolso retraso' },
    { key: 'col_pend_descuento', label: 'Pend. descuento' },
    { key: 'col_descuento_retraso', label: 'Descuento retraso' },
    { key: 'col_empresa_asume', label: 'Empresa asume' },
    { key: 'col_perdida', label: 'Pérdida' },
  ]},
]

const anyKpiOrdenes = computed(() => visible.value.kpi_total_ordenes || visible.value.kpi_con_problemas || visible.value.kpi_sin_problemas)
const anyKpiApelaciones = computed(() => visible.value.kpi_sin_apelar || visible.value.kpi_apeladas || visible.value.kpi_sede_no_apelar)
const anyKpiReembolsos = computed(() => visible.value.kpi_reembolsadas || visible.value.kpi_pendiente_reembolso || visible.value.kpi_reembolso_retraso)
const anyKpiDescuentos = computed(() => visible.value.kpi_descontado || visible.value.kpi_pendiente_descuento || visible.value.kpi_descuento_retraso || visible.value.kpi_empresa_asume || visible.value.kpi_perdida_neta)
const anyChart = computed(() => visible.value.chart_por_dia || visible.value.chart_por_canal)

// ── Interfaces ────────────────────────────────────────────────────────────────
interface Resumen {
  total_ordenes: number; ordenes_con_apelacion: number; ordenes_sin_apelacion: number; pct_con_problemas: number
  sin_apelar: number; apeladas: number; sede_no_apelar: number
  total_descontado_canal: number; total_devuelto: number; total_reembolsos: number
  pendiente_reembolso: number; monto_pendiente_reembolso: number; reembolso_retraso: number
  total_descuentos_sede: number; monto_pendiente_descuento: number; empresa_asume: number
  descuento_retraso: number; total_perdida: number
}
interface DiaItem { fecha: string; ordenes: number; apelaciones: number; reembolsos: number; perdida: number }
interface SedeItem {
  local: string; ordenes: number; apelaciones: number; pct_problemas: number
  sin_apelar: number; apeladas: number; sede_no_apelar: number
  reembolsadas: number; pendiente_reembolso: number; reembolso_retraso: number
  pendiente_descuento: number; descuento_retraso: number; empresa_asume: number; perdida: number
}
interface CanalItem { canal: string; ordenes: number; apelaciones: number; perdida: number }
interface InformesData { resumen: Resumen; por_dia: DiaItem[]; por_sede: SedeItem[]; por_canal: CanalItem[] }

// ── Estado ────────────────────────────────────────────────────────────────────
const fechaDesde = ref('')
const fechaHasta = ref('')
const loading = ref(false)
const error = ref('')
const data = ref<InformesData | null>(null)

const MIN_DATE = new Date(2026, 1, 11)
function lastTwoWeeksRange() {
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

function formatMonto(val: number) {
  return new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(val)
}
function formatShortDate(s: string) {
  if (!s || s.length < 10) return s
  return new Date(s + 'T12:00:00').toLocaleDateString('es-CO', { day: '2-digit', month: '2-digit' })
}

// ── Definiciones de KPI cards ─────────────────────────────────────────────────
interface KpiDef {
  icon: string
  bg: (r: Resumen) => string
  label: string
  value: (r: Resumen) => string | number
  valueClass?: (r: Resumen) => string
  valueStyle?: string
  sub?: (r: Resumen) => string | null
  subClass?: string
  danger?: (r: Resumen) => boolean
}

const KPI_DEFS: Record<string, KpiDef> = {
  kpi_total_ordenes:      { icon: 'pi-shopping-cart',       bg: () => '#6366f1', label: 'Total órdenes',            value: (r) => r.total_ordenes },
  kpi_con_problemas:      { icon: 'pi-exclamation-circle',  bg: () => '#f97316', label: 'Con problemas',            value: (r) => r.ordenes_con_apelacion,       sub: (r) => `${r.pct_con_problemas}% del total` },
  kpi_sin_problemas:      { icon: 'pi-check-circle',        bg: () => '#22c55e', label: 'Sin problemas',            value: (r) => r.ordenes_sin_apelacion },
  kpi_sin_apelar:         { icon: 'pi-clock',               bg: () => '#eab308', label: 'Sin apelar',               value: (r) => r.sin_apelar,                  sub: () => 'Pendiente de acción',              subClass: 'kpi-warn' },
  kpi_apeladas:           { icon: 'pi-send',                bg: () => '#3b82f6', label: 'Apeladas',                 value: (r) => r.apeladas },
  kpi_sede_no_apelar:     { icon: 'pi-times-circle',        bg: () => '#64748b', label: 'Decidió no apelar',        value: (r) => r.sede_no_apelar },
  kpi_reembolsadas:       { icon: 'pi-wallet',              bg: () => '#16a34a', label: 'Reembolsadas',             value: (r) => r.total_reembolsos,            sub: (r) => formatMonto(r.total_devuelto),     subClass: 'kpi-ok' },
  kpi_pendiente_reembolso:{ icon: 'pi-hourglass',           bg: () => '#f97316', label: 'Pendiente por reembolsar', value: (r) => r.pendiente_reembolso,         sub: (r) => formatMonto(r.monto_pendiente_reembolso), subClass: 'kpi-warn' },
  kpi_reembolso_retraso:  { icon: 'pi-calendar-times',      bg: (r) => r.reembolso_retraso > 0 ? '#dc2626' : '#94a3b8', label: 'Reembolsos con retraso',   value: (r) => r.reembolso_retraso,           valueClass: (r) => r.reembolso_retraso > 0 ? 'text-red' : '', sub: (r) => r.reembolso_retraso > 0 ? 'Fecha est. vencida' : null, subClass: 'kpi-danger-text', danger: (r) => r.reembolso_retraso > 0 },
  kpi_descontado:         { icon: 'pi-check-circle',        bg: () => '#16a34a', label: 'Descontado',               value: (r) => formatMonto(r.total_descuentos_sede),  valueClass: () => 'kpi-ok' },
  kpi_pendiente_descuento:{ icon: 'pi-hourglass',           bg: () => '#f97316', label: 'Pendiente por descontar',  value: (r) => formatMonto(r.monto_pendiente_descuento), valueClass: () => 'kpi-warn' },
  kpi_descuento_retraso:  { icon: 'pi-calendar-times',      bg: (r) => r.descuento_retraso > 0 ? '#dc2626' : '#94a3b8', label: 'Descuentos con retraso',   value: (r) => r.descuento_retraso,           valueClass: (r) => r.descuento_retraso > 0 ? 'text-red' : '', sub: (r) => r.descuento_retraso > 0 ? 'Quincena vencida sin ejecutar' : null, subClass: 'kpi-danger-text', danger: (r) => r.descuento_retraso > 0 },
  kpi_empresa_asume:      { icon: 'pi-building',            bg: () => '#8b5cf6', label: 'Asumido por empresa',      value: (r) => formatMonto(r.empresa_asume),  valueStyle: 'color:#7c3aed' },
  kpi_perdida_neta:       { icon: 'pi-exclamation-triangle',bg: () => '#dc2626', label: 'Pérdida neta',             value: (r) => formatMonto(r.total_perdida),  valueClass: () => 'text-red' },
}

function isKpiVisible(key: string): boolean {
  return (visible.value as Record<string, boolean>)[key] ?? true
}

async function load() {
  if (!fechaDesde.value || !fechaHasta.value || !sede.value) return
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams()
    params.set('fecha_desde', fechaDesde.value)
    params.set('fecha_hasta', fechaHasta.value)
    params.append('local', sede.value)
    const r = await fetch(`${API}/api/informes?${params.toString()}`)
    if (!r.ok) throw new Error('Error al cargar informes')
    data.value = await r.json()
  } catch (e) {
    error.value = (e as Error).message
    data.value = null
  } finally {
    loading.value = false
  }
}

// ── Gráficos ──────────────────────────────────────────────────────────────────
const chartPorDiaData = computed(() => {
  const d = data.value?.por_dia
  if (!d?.length) return null
  return {
    labels: d.map((x) => formatShortDate(x.fecha)),
    datasets: [
      { label: 'Con problemas', data: d.map((x) => x.apelaciones), backgroundColor: 'rgba(251,146,60,0.7)', borderColor: 'rgb(251,146,60)', borderWidth: 1 },
      { label: 'Reembolsadas', data: d.map((x) => x.reembolsos), backgroundColor: 'rgba(34,197,94,0.7)', borderColor: 'rgb(34,197,94)', borderWidth: 1 },
    ],
  }
})
const chartPorDiaOptions = ref({ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top' as const } }, scales: { y: { beginAtZero: true } } })

const chartPorCanalData = computed(() => {
  const d = data.value?.por_canal?.filter((x) => x.perdida > 0)
  if (!d?.length) return null
  return {
    labels: d.map((x) => x.canal),
    datasets: [{ data: d.map((x) => x.perdida), backgroundColor: ['#ef4444', '#f97316', '#eab308', '#22c55e', '#3b82f6', '#8b5cf6'] }],
  }
})

onMounted(async () => {
  await loadPrefs()
  const range = lastTwoWeeksRange()
  fechaDesde.value = range.desde
  fechaHasta.value = range.hasta
  load()
})
watch([fechaDesde, fechaHasta, sede], () => {
  if (fechaDesde.value && fechaHasta.value && sede.value) load()
})
</script>

<template>
  <div class="informes-sede-view">
    <!-- Filtros -->
    <Card class="mb-3">
      <template #title>
        <div class="flex align-items-center justify-content-between">
          <span>Reportes<span v-if="sede" class="sede-badge">{{ sede }}</span></span>
          <Button icon="pi pi-sliders-h" text rounded v-tooltip.left="'Métricas visibles'" @click="settingsOpen = true" />
        </div>
      </template>
      <template #content>
        <p class="text-color-secondary mt-0 mb-3">
          Indicadores de apelaciones, reembolsos y descuentos de tu sede.
        </p>
        <div v-if="!sede" class="text-color-secondary">
          <i class="pi pi-info-circle mr-1"></i> No hay sede seleccionada. Accede desde el menú principal.
        </div>
        <div v-else class="flex flex-wrap gap-3 align-items-end">
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
      </template>
    </Card>

    <Message v-if="error" severity="error" class="mb-3">{{ error }}</Message>

    <div v-if="loading" class="flex justify-content-center py-5">
      <ProgressSpinner style="width: 48px; height: 48px" stroke-width="4" />
    </div>

    <template v-else-if="data?.resumen">
      <!-- Secciones reordenables con drag & drop -->
      <div
        v-for="(sId, idx) in sectionsOrder"
        :key="sId"
        class="draggable-section"
        :class="{
          'drag-over-top': dragOverIdx === idx && dragSrcIdx > idx,
          'drag-over-bottom': dragOverIdx === idx && dragSrcIdx < idx,
          'is-dragging': dragSrcIdx === idx,
        }"
        draggable="true"
        @dragstart="onDragStart(idx, $event)"
        @dragover="onDragOver(idx, $event)"
        @drop.prevent="onDrop(idx)"
        @dragend="onDragEnd"
      >
        <!-- Secciones KPI con drag horizontal -->
        <template v-if="sId !== 'graficos' && kpiOrders[sId] && kpiOrders[sId].some(k => isKpiVisible(k))">
          <div class="seccion-label">
            <i class="pi pi-ellipsis-v drag-handle-icon"></i>
            <span v-if="sId === 'ordenes'">Órdenes</span>
            <span v-else-if="sId === 'apelaciones'">Estado de apelaciones</span>
            <span v-else-if="sId === 'reembolsos'">Reembolsos del canal</span>
            <span v-else-if="sId === 'descuentos'">Descuentos a tu sede</span>
          </div>
          <div class="kpi-row mb-3">
            <template v-for="(kId, kIdx) in kpiOrders[sId]" :key="kId">
              <div
                v-if="isKpiVisible(kId) && KPI_DEFS[kId]"
                class="kpi-drag-item"
                :class="{
                  'h-drag-over-left':  hSection === sId && hOverIdx === kIdx && hSrcIdx > kIdx,
                  'h-drag-over-right': hSection === sId && hOverIdx === kIdx && hSrcIdx < kIdx,
                  'h-is-dragging':     hSection === sId && hSrcIdx === kIdx,
                }"
                draggable="true"
                @dragstart.stop="onHDragStart(sId, kIdx, $event)"
                @dragover.stop.prevent="onHDragOver(sId, kIdx)"
                @drop.stop.prevent="onHDrop(sId, kIdx)"
                @dragend.stop="onHDragEnd"
              >
                <Card class="kpi-card h-full" :class="{ 'kpi-danger': KPI_DEFS[kId].danger?.(data.resumen) }">
                  <template #content>
                    <div class="kpi-inner">
                      <span class="kpi-icon" :style="{ background: KPI_DEFS[kId].bg(data.resumen) }">
                        <i :class="`pi ${KPI_DEFS[kId].icon}`"></i>
                      </span>
                      <div>
                        <div class="kpi-label">{{ KPI_DEFS[kId].label }}</div>
                        <div
                          class="kpi-value"
                          :class="KPI_DEFS[kId].valueClass?.(data.resumen)"
                          :style="KPI_DEFS[kId].valueStyle"
                        >{{ KPI_DEFS[kId].value(data.resumen) }}</div>
                        <div
                          v-if="KPI_DEFS[kId].sub?.(data.resumen)"
                          class="kpi-sub"
                          :class="KPI_DEFS[kId].subClass"
                        >{{ KPI_DEFS[kId].sub?.(data.resumen) }}</div>
                      </div>
                    </div>
                  </template>
                </Card>
              </div>
            </template>
          </div>
        </template>

        <!-- Gráficos -->
        <template v-else-if="sId === 'graficos' && anyChart">
          <div class="seccion-label"><i class="pi pi-ellipsis-v drag-handle-icon"></i>Gráficos</div>
          <div class="grid mb-4">
            <div v-if="visible.chart_por_dia" class="col-12" :class="visible.chart_por_canal ? 'lg:col-8' : ''">
              <Card>
                <template #title>Órdenes con problemas y reembolsos por día</template>
                <template #content>
                  <div v-if="chartPorDiaData" class="chart-container"><Chart type="bar" :data="chartPorDiaData" :options="chartPorDiaOptions" /></div>
                  <p v-else class="text-color-secondary">No hay datos en el rango seleccionado.</p>
                </template>
              </Card>
            </div>
            <div v-if="visible.chart_por_canal" class="col-12" :class="visible.chart_por_dia ? 'lg:col-4' : 'lg:col-5'">
              <Card>
                <template #title>Pérdida por canal</template>
                <template #content>
                  <div v-if="chartPorCanalData" class="chart-container chart-dona"><Chart type="doughnut" :data="chartPorCanalData" :options="{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }" /></div>
                  <p v-else class="text-color-secondary">Sin pérdida por canal.</p>
                </template>
              </Card>
            </div>
          </div>
        </template>
      </div>

      <!-- Tabla detalle -->
      <Card>
        <template #title>Detalle</template>
        <template #content>
          <DataTable
            :value="data.por_sede"
            class="p-datatable-sm p-datatable-striped"
            scrollable
            scroll-height="60vh"
          >
            <Column field="local" header="Sede" frozen style="min-width:140px" />
            <Column v-if="visible.col_ordenes" field="ordenes" header="Órdenes" style="min-width:90px" />
            <Column v-if="visible.col_con_problemas" field="apelaciones" header="Con problemas" style="min-width:120px">
              <template #body="{ data: row }">
                <span>{{ row.apelaciones }}</span>
                <Tag v-if="row.pct_problemas >= 10" severity="danger" :value="row.pct_problemas + '%'" class="ml-1" />
                <Tag v-else-if="row.pct_problemas >= 5" severity="warn" :value="row.pct_problemas + '%'" class="ml-1" />
                <Tag v-else-if="row.pct_problemas > 0" severity="info" :value="row.pct_problemas + '%'" class="ml-1" />
              </template>
            </Column>
            <Column v-if="visible.col_sin_apelar" field="sin_apelar" header="Sin apelar" style="min-width:100px">
              <template #body="{ data: row }">
                <Tag v-if="row.sin_apelar > 0" severity="warn" :value="String(row.sin_apelar)" />
                <span v-else class="text-color-secondary">—</span>
              </template>
            </Column>
            <Column v-if="visible.col_apeladas" field="apeladas" header="Apeladas" style="min-width:90px">
              <template #body="{ data: row }">
                <span v-if="row.apeladas > 0">{{ row.apeladas }}</span>
                <span v-else class="text-color-secondary">—</span>
              </template>
            </Column>
            <Column v-if="visible.col_reembolsadas" field="reembolsadas" header="Reembolsadas" style="min-width:110px">
              <template #body="{ data: row }">
                <span v-if="row.reembolsadas > 0" class="text-green font-semibold">{{ row.reembolsadas }}</span>
                <span v-else class="text-color-secondary">—</span>
              </template>
            </Column>
            <Column v-if="visible.col_pend_reembolso" field="pendiente_reembolso" header="Pend. reembolso" style="min-width:120px">
              <template #body="{ data: row }">
                <Tag v-if="row.pendiente_reembolso > 0" severity="warn" :value="String(row.pendiente_reembolso)" />
                <span v-else class="text-color-secondary">—</span>
              </template>
            </Column>
            <Column v-if="visible.col_reembolso_retraso" field="reembolso_retraso" header="Reembolso retraso" style="min-width:130px">
              <template #body="{ data: row }">
                <Tag v-if="row.reembolso_retraso > 0" severity="danger" :value="String(row.reembolso_retraso)" />
                <span v-else class="text-color-secondary">—</span>
              </template>
            </Column>
            <Column v-if="visible.col_pend_descuento" field="pendiente_descuento" header="Pend. descuento" style="min-width:130px">
              <template #body="{ data: row }">
                <span v-if="row.pendiente_descuento > 0" class="text-warn font-semibold">{{ formatMonto(row.pendiente_descuento) }}</span>
                <span v-else class="text-color-secondary">—</span>
              </template>
            </Column>
            <Column v-if="visible.col_descuento_retraso" field="descuento_retraso" header="Descuento retraso" style="min-width:130px">
              <template #body="{ data: row }">
                <Tag v-if="row.descuento_retraso > 0" severity="danger" :value="String(row.descuento_retraso)" />
                <span v-else class="text-color-secondary">—</span>
              </template>
            </Column>
            <Column v-if="visible.col_empresa_asume" field="empresa_asume" header="Empresa asume" style="min-width:120px">
              <template #body="{ data: row }">
                <span v-if="row.empresa_asume > 0" class="text-purple font-semibold">{{ formatMonto(row.empresa_asume) }}</span>
                <span v-else class="text-color-secondary">—</span>
              </template>
            </Column>
            <Column v-if="visible.col_perdida" field="perdida" header="Pérdida" style="min-width:110px">
              <template #body="{ data: row }">
                <span v-if="row.perdida > 0" class="text-red font-semibold">{{ formatMonto(row.perdida) }}</span>
                <span v-else class="text-color-secondary">—</span>
              </template>
            </Column>
          </DataTable>
        </template>
      </Card>
    </template>

    <!-- Dialog métricas visibles -->
    <Dialog v-model:visible="settingsOpen" modal header="Métricas visibles" style="width: min(560px, 95vw)">
      <div class="metrics-settings">
        <div v-for="group in metricGroups" :key="group.label" class="metrics-group">
          <div class="metrics-group-header">{{ group.label }}</div>
          <div class="metrics-grid">
            <label v-for="item in group.items" :key="item.key" class="metric-item">
              <Checkbox v-model="visible[item.key]" :binary="true" />
              <span>{{ item.label }}</span>
            </label>
          </div>
        </div>
      </div>
      <template #footer>
        <Button label="Restaurar todo" icon="pi pi-refresh" text severity="secondary" @click="resetMetrics" />
        <Button label="Cerrar" icon="pi pi-check" @click="settingsOpen = false" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.informes-sede-view { padding: 0.5rem; }
.sede-badge {
  display: inline-block;
  margin-left: 0.6rem;
  font-size: 0.75rem;
  font-weight: 600;
  background: var(--p-highlight-background);
  color: var(--p-primary-color);
  border-radius: 6px;
  padding: 2px 8px;
  vertical-align: middle;
}
.draggable-section { border-radius: 8px; transition: opacity 0.15s, box-shadow 0.15s; cursor: grab; user-select: none; }
.draggable-section:active { cursor: grabbing; }
.draggable-section.is-dragging { opacity: 0.4; }
.draggable-section.drag-over-top { box-shadow: 0 -3px 0 0 var(--p-primary-color, #6366f1); }
.draggable-section.drag-over-bottom { box-shadow: 0 3px 0 0 var(--p-primary-color, #6366f1); }
.drag-handle-icon { margin-right: 0.4rem; opacity: 0.4; font-size: 0.7rem; cursor: grab; }
.draggable-section:hover .drag-handle-icon { opacity: 0.75; }

.seccion-label {
  font-size: 0.75rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--p-text-muted-color, #94a3b8);
  margin-bottom: 0.5rem; padding-left: 0.25rem;
  display: flex; align-items: center;
}
.kpi-row { display: flex; flex-wrap: wrap; gap: 0.75rem; }
.kpi-drag-item {
  flex: 1 1 160px; min-width: 140px;
  cursor: grab; user-select: none; border-radius: 10px;
  transition: opacity 0.15s, box-shadow 0.15s;
}
.kpi-drag-item:active { cursor: grabbing; }
.kpi-drag-item.h-is-dragging { opacity: 0.35; }
.kpi-drag-item.h-drag-over-left  { box-shadow: -3px 0 0 0 var(--p-primary-color, #6366f1); }
.kpi-drag-item.h-drag-over-right { box-shadow:  3px 0 0 0 var(--p-primary-color, #6366f1); }
.kpi-card { flex: unset; min-width: unset; width: 100%; }
.kpi-card :deep(.p-card-content) { padding: 0.875rem 1rem; }
.kpi-card.kpi-danger :deep(.p-card-body) { border-left: 3px solid #dc2626; }
.kpi-inner { display: flex; align-items: center; gap: 0.75rem; }
.kpi-icon { width: 2.5rem; height: 2.5rem; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.1rem; color: white; flex-shrink: 0; }
.kpi-label { font-size: 0.78rem; color: var(--p-text-muted-color, #94a3b8); line-height: 1.2; margin-bottom: 2px; }
.kpi-value { font-size: 1.3rem; font-weight: 700; line-height: 1.1; }
.kpi-sub { font-size: 0.75rem; margin-top: 2px; }
.kpi-ok { color: var(--p-green-600, #16a34a); }
.kpi-warn { color: #f97316; }
.kpi-danger-text { color: #dc2626; font-weight: 600; }
.text-red { color: var(--p-red-600, #dc2626); }
.text-green { color: var(--p-green-600, #16a34a); }
.text-purple { color: #7c3aed; }
.text-warn { color: #f97316; }
.chart-container { height: 280px; position: relative; }
.chart-container.chart-dona { height: 260px; }
.metrics-settings { display: flex; flex-direction: column; gap: 1.25rem; }
.metrics-group-header { font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--p-text-muted-color, #94a3b8); margin-bottom: 0.5rem; padding-bottom: 0.25rem; border-bottom: 1px solid var(--p-content-border-color, #e2e8f0); }
.metrics-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 0.5rem 1rem; }
.metric-item { display: flex; align-items: center; gap: 0.5rem; cursor: pointer; font-size: 0.875rem; user-select: none; }
</style>
