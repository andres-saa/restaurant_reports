<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Card from 'primevue/card'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'

const API = import.meta.env.VITE_API_URL ?? ''

interface DescuentoItem {
  codigo: string
  canal: string
  fecha?: string
  monto_descontado: number
  perdida: number
  fecha_descuento_confirmado?: string
}

interface LocaleItem {
  id: string
  name: string
}

const locales = ref<LocaleItem[]>([])
const selectedLocal = ref<string | null>(null)
const fechaDesde = ref('')
const fechaHasta = ref('')
const items = ref<DescuentoItem[]>([])
const loading = ref(false)
const orderError = ref('')

const MIN_DATE = new Date(2026, 1, 11)
const todayStr = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Bogota' })

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

const route = useRoute()
const selectedSede = computed(() => (route.query.sede as string) || '')

function resolveLocalFromSede(sede: string): string | null {
  if (!sede || !locales.value.length) return null
  const byId = locales.value.find((l) => l.id && String(l.id) === String(sede))
  if (byId) return byId.name
  const byName = locales.value.find((l) => l.name === sede)
  if (byName) return byName.name
  return sede
}

async function load() {
  const local = selectedLocal.value || resolveLocalFromSede(selectedSede.value)
  if (!local) return
  loading.value = true
  orderError.value = ''
  try {
    const params = new URLSearchParams()
    params.set('local', local)
    params.set('fecha_desde', fechaDesde.value || todayStr())
    params.set('fecha_hasta', fechaHasta.value || todayStr())
    params.set('solo_confirmados', 'true')
    params.set('solo_pendientes', 'false')
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
  selectedLocal.value = resolveLocalFromSede(selectedSede.value) || (locales.value[0]?.name ?? null)
  fechaDesde.value = todayStr()
  fechaHasta.value = todayStr()
  await load()
})

watch([selectedSede, selectedLocal, fechaDesde, fechaHasta], () => {
  if (selectedLocal.value || selectedSede.value) load()
})

watch(selectedSede, () => {
  if (selectedSede.value) selectedLocal.value = resolveLocalFromSede(selectedSede.value) || selectedSede.value || null
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

function formatDate(d: string | null | undefined): string {
  if (!d) return '—'
  try {
    return new Date(d).toLocaleDateString('es-CO')
  } catch {
    return d
  }
}

const totalDescontado = computed(() => items.value.reduce((s, i) => s + (i.perdida || 0), 0))
</script>

<template>
  <div class="mis-descuentos-view">
    <Card class="mb-3">
      <template #title>Descuentos a mi sede</template>
      <template #content>
        <p class="text-color-secondary mt-0 mb-3">
          Pedidos cuya pérdida ya fue descontada de la nómina de esta sede.
        </p>
        <div class="flex flex-wrap gap-3 align-items-end mb-2">
          <div class="flex flex-column gap-2">
            <label>Sede</label>
            <Select
              v-model="selectedLocal"
              :options="localeOptions"
              option-label="label"
              option-value="value"
              placeholder="Seleccionar sede"
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
        <div v-if="items.length > 0" class="mt-2 text-color-secondary">
          Total descontado en período: <strong class="text-red">{{ formatMonto(totalDescontado) }}</strong>
        </div>
      </template>
    </Card>

    <Message v-if="orderError" severity="error" class="mb-3">{{ orderError }}</Message>

    <Card>
      <template #title>Descuentos aplicados</template>
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
          <Column header="Pérdida (descontada de nómina)">
            <template #body="{ data }">
              <span class="text-red font-semibold">{{ formatMonto(data.perdida) }}</span>
            </template>
          </Column>
          <Column header="Fecha descuento">
            <template #body="{ data }">{{ formatDate(data.fecha_descuento_confirmado) }}</template>
          </Column>
          <template #empty>
            <span class="text-color-secondary">No hay descuentos aplicados en el período seleccionado.</span>
          </template>
          <template #loading>
            <ProgressSpinner style="width: 40px; height: 40px" stroke-width="4" />
          </template>
        </DataTable>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.mis-descuentos-view {
  padding: 0.5rem;
}
.text-red {
  color: var(--p-red-600, #dc2626);
}
</style>
