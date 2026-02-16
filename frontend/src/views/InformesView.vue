<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import DatePicker from 'primevue/datepicker'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Chart from 'primevue/chart'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'

const API = import.meta.env.VITE_API_URL ?? ''

interface Resumen {
  total_ordenes: number
  total_apelaciones: number
  total_reembolsos: number
  total_descontado_canal: number
  total_devuelto: number
  total_perdida: number
}

interface DiaItem {
  fecha: string
  ordenes: number
  apelaciones: number
  reembolsos: number
  perdida: number
}

interface SedeItem {
  local: string
  ordenes: number
  apelaciones: number
  perdida: number
}

interface CanalItem {
  canal: string
  ordenes: number
  apelaciones: number
  perdida: number
}

interface InformesData {
  resumen: Resumen
  por_dia: DiaItem[]
  por_sede: SedeItem[]
  por_canal: CanalItem[]
}

const fechaDesde = ref('')
const fechaHasta = ref('')
const loading = ref(false)
const error = ref('')
const data = ref<InformesData | null>(null)

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

function formatMonto(val: number): string {
  return new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(val)
}

function formatShortDate(s: string): string {
  if (!s || s.length < 10) return s
  const d = new Date(s + 'T12:00:00')
  return d.toLocaleDateString('es-CO', { day: '2-digit', month: '2-digit' })
}

async function load() {
  if (!fechaDesde.value || !fechaHasta.value) return
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams()
    params.set('fecha_desde', fechaDesde.value)
    params.set('fecha_hasta', fechaHasta.value)
    const r = await fetch(`${API}/api/informes?${params.toString()}`)
    if (!r.ok) throw new Error('Error al cargar informes')
    const json = await r.json()
    data.value = json
  } catch (e) {
    error.value = (e as Error).message
    data.value = null
  } finally {
    loading.value = false
  }
}

// Gráfico: Órdenes y apelaciones por día
const chartPorDiaData = computed(() => {
  const d = data.value?.por_dia
  if (!d?.length) return null
  return {
    labels: d.map((x) => formatShortDate(x.fecha)),
    datasets: [
      { label: 'Órdenes', data: d.map((x) => x.ordenes), backgroundColor: 'rgba(99, 102, 241, 0.6)', borderColor: 'rgb(99, 102, 241)' },
      { label: 'Apelaciones', data: d.map((x) => x.apelaciones), backgroundColor: 'rgba(251, 146, 60, 0.6)', borderColor: 'rgb(251, 146, 60)' },
      { label: 'Reembolsos', data: d.map((x) => x.reembolsos), backgroundColor: 'rgba(34, 197, 94, 0.6)', borderColor: 'rgb(34, 197, 94)' }
    ]
  }
})

const chartPorDiaOptions = ref({
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { position: 'top' as const } },
  scales: { y: { beginAtZero: true } }
})

// Gráfico: Pérdida por día
const chartPerdidaPorDiaData = computed(() => {
  const d = data.value?.por_dia
  if (!d?.length) return null
  return {
    labels: d.map((x) => formatShortDate(x.fecha)),
    datasets: [
      { label: 'Pérdida (COP)', data: d.map((x) => x.perdida), fill: true, borderColor: 'rgb(220, 38, 38)', backgroundColor: 'rgba(220, 38, 38, 0.2)' }
    ]
  }
})

// Gráfico: Órdenes por sede (barras)
const chartPorSedeData = computed(() => {
  const d = data.value?.por_sede
  if (!d?.length) return null
  return {
    labels: d.map((x) => x.local),
    datasets: [
      { label: 'Órdenes', data: d.map((x) => x.ordenes), backgroundColor: 'rgba(99, 102, 241, 0.6)' },
      { label: 'Apelaciones', data: d.map((x) => x.apelaciones), backgroundColor: 'rgba(251, 146, 60, 0.6)' }
    ]
  }
})

const chartPorSedeOptions = ref({
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { position: 'top' as const } },
  scales: { y: { beginAtZero: true } },
  indexAxis: 'y' as const
})

// Gráfico: Pérdida por canal (dona)
const chartPorCanalData = computed(() => {
  const d = data.value?.por_canal
  if (!d?.length) return null
  const withPerdida = d.filter((x) => x.perdida > 0)
  if (!withPerdida.length) return null
  return {
    labels: withPerdida.map((x) => x.canal),
    datasets: [{ data: withPerdida.map((x) => x.perdida), backgroundColor: ['#ef4444', '#f97316', '#eab308', '#22c55e', '#3b82f6', '#8b5cf6'] }]
  }
})

onMounted(() => {
  const range = lastTwoWeeksRange()
  fechaDesde.value = range.desde
  fechaHasta.value = range.hasta
  load()
})

watch([fechaDesde, fechaHasta], () => {
  if (fechaDesde.value && fechaHasta.value) load()
})
</script>

<template>
  <div class="informes-view">
    <Card class="mb-3">
      <template #title>Reportes</template>
      <template #content>
        <p class="text-color-secondary mt-0 mb-3">
          Métricas e indicadores por rango de fechas: órdenes, apelaciones, reembolsos y pérdidas.
        </p>
        <div class="flex flex-wrap gap-3 align-items-end mb-2">
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
      <!-- KPIs -->
      <div class="grid mb-4">
        <div class="col-12 sm:col-6 lg:col-4">
          <Card class="kpi-card">
            <template #content>
              <div class="flex align-items-center gap-2">
                <span class="kpi-icon kpi-ordenes"><i class="pi pi-shopping-cart"></i></span>
                <div>
                  <div class="text-color-secondary text-sm">Total órdenes</div>
                  <div class="text-xl font-bold">{{ data.resumen.total_ordenes }}</div>
                </div>
              </div>
            </template>
          </Card>
        </div>
        <div class="col-12 sm:col-6 lg:col-4">
          <Card class="kpi-card">
            <template #content>
              <div class="flex align-items-center gap-2">
                <span class="kpi-icon kpi-apelaciones"><i class="pi pi-flag"></i></span>
                <div>
                  <div class="text-color-secondary text-sm">Apelaciones</div>
                  <div class="text-xl font-bold">{{ data.resumen.total_apelaciones }}</div>
                </div>
              </div>
            </template>
          </Card>
        </div>
        <div class="col-12 sm:col-6 lg:col-4">
          <Card class="kpi-card">
            <template #content>
              <div class="flex align-items-center gap-2">
                <span class="kpi-icon kpi-reembolsos"><i class="pi pi-wallet"></i></span>
                <div>
                  <div class="text-color-secondary text-sm">Reembolsos</div>
                  <div class="text-xl font-bold">{{ data.resumen.total_reembolsos }}</div>
                </div>
              </div>
            </template>
          </Card>
        </div>
        <div class="col-12 sm:col-6 lg:col-4">
          <Card class="kpi-card">
            <template #content>
              <div class="flex align-items-center gap-2">
                <span class="kpi-icon kpi-descontado"><i class="pi pi-minus-circle"></i></span>
                <div>
                  <div class="text-color-secondary text-sm">Descontado por canal</div>
                  <div class="text-xl font-bold">{{ formatMonto(data.resumen.total_descontado_canal) }}</div>
                </div>
              </div>
            </template>
          </Card>
        </div>
        <div class="col-12 sm:col-6 lg:col-4">
          <Card class="kpi-card">
            <template #content>
              <div class="flex align-items-center gap-2">
                <span class="kpi-icon kpi-devuelto"><i class="pi pi-check-circle"></i></span>
                <div>
                  <div class="text-color-secondary text-sm">Devuelto</div>
                  <div class="text-xl font-bold text-green">{{ formatMonto(data.resumen.total_devuelto) }}</div>
                </div>
              </div>
            </template>
          </Card>
        </div>
        <div class="col-12 sm:col-6 lg:col-4">
          <Card class="kpi-card">
            <template #content>
              <div class="flex align-items-center gap-2">
                <span class="kpi-icon kpi-perdida"><i class="pi pi-exclamation-triangle"></i></span>
                <div>
                  <div class="text-color-secondary text-sm">Pérdida</div>
                  <div class="text-xl font-bold text-red">{{ formatMonto(data.resumen.total_perdida) }}</div>
                </div>
              </div>
            </template>
          </Card>
        </div>
      </div>

      <!-- Gráficos -->
      <div class="grid">
        <div class="col-12 lg:col-8">
          <Card>
            <template #title>Órdenes, apelaciones y reembolsos por día</template>
            <template #content>
              <div v-if="chartPorDiaData" class="chart-container">
                <Chart type="bar" :data="chartPorDiaData" :options="chartPorDiaOptions" />
              </div>
              <p v-else class="text-color-secondary">No hay datos en el rango seleccionado.</p>
            </template>
          </Card>
        </div>
        <div class="col-12 lg:col-4">
          <Card>
            <template #title>Pérdida por día</template>
            <template #content>
              <div v-if="chartPerdidaPorDiaData" class="chart-container chart-sm">
                <Chart type="line" :data="chartPerdidaPorDiaData" :options="{ responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true } } }" />
              </div>
              <p v-else class="text-color-secondary">Sin pérdida en el rango.</p>
            </template>
          </Card>
        </div>
        <div class="col-12 lg:col-7">
          <Card>
            <template #title>Órdenes y apelaciones por sede</template>
            <template #content>
              <div v-if="chartPorSedeData" class="chart-container chart-horizontal">
                <Chart type="bar" :data="chartPorSedeData" :options="chartPorSedeOptions" />
              </div>
              <p v-else class="text-color-secondary">No hay datos por sede.</p>
            </template>
          </Card>
        </div>
        <div class="col-12 lg:col-5">
          <Card>
            <template #title>Pérdida por canal</template>
            <template #content>
              <div v-if="chartPorCanalData" class="chart-container chart-dona">
                <Chart type="doughnut" :data="chartPorCanalData" :options="{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }" />
              </div>
              <p v-else class="text-color-secondary">Sin pérdida por canal.</p>
            </template>
          </Card>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.informes-view {
  padding: 0.5rem;
}
.kpi-card :deep(.p-card-content) {
  padding: 1rem;
}
.kpi-icon {
  width: 3rem;
  height: 3rem;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
  color: white;
}
.kpi-ordenes { background: #6366f1; }
.kpi-apelaciones { background: #f97316; }
.kpi-reembolsos { background: #22c55e; }
.kpi-descontado { background: #64748b; }
.kpi-devuelto { background: #16a34a; }
.kpi-perdida { background: #dc2626; }
.chart-container {
  height: 280px;
  position: relative;
}
.chart-container.chart-sm { height: 220px; }
.chart-container.chart-horizontal { height: 320px; }
.chart-container.chart-dona { height: 260px; }
.text-red { color: var(--p-red-600, #dc2626); }
.text-green { color: var(--p-green-600, #16a34a); }
</style>
