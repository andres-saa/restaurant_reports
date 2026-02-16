<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MultiSelect from 'primevue/multiselect'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import DatePicker from 'primevue/datepicker'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'
import Dialog from 'primevue/dialog'

const API = import.meta.env.VITE_API_URL ?? ''

interface Order {
  'Codigo integracion': string
  'Cliente': string
  'Canal de delivery': string
  'Monto pagado': string
  'Fecha'?: string
  Local?: string
  delivery_id?: string
  has_entrega_photo?: boolean
  fotos_entrega?: string[]
  rowKey?: string
}

interface LocaleItem {
  id: string
  name: string
}

const locales = ref<LocaleItem[]>([])
const selectedLocals = ref<string[]>([])
const fechaDesde = ref('')
const fechaHasta = ref('')
const orders = ref<Order[]>([])
const loadingOrders = ref(false)
const orderError = ref('')
const globalFilterText = ref('')

const MIN_DATE = new Date(2026, 1, 11)

function lastTwoWeeksRange(): { desde: string; hasta: string } {
  const today = new Date()
  const hasta = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  const desde = new Date(hasta)
  desde.setDate(desde.getDate() - 13) // 14 days including today = last 2 weeks
  return {
    desde: desde.toISOString().slice(0, 10),
    hasta: hasta.toISOString().slice(0, 10)
  }
}

const fechaDesdeAsDate = computed({
  get: () => (fechaDesde.value ? new Date(fechaDesde.value + 'T12:00:00') : null),
  set: (v: Date | null) => { fechaDesde.value = v ? dateToYMD(v) : '' }
})
const fechaHastaAsDate = computed({
  get: () => (fechaHasta.value ? new Date(fechaHasta.value + 'T12:00:00') : null),
  set: (v: Date | null) => { fechaHasta.value = v ? dateToYMD(v) : '' }
})

const tableFilters = computed(() => ({
  global: { value: globalFilterText.value, matchMode: 'contains' as const }
}))

const localeOptions = computed(() =>
  locales.value.map((l) => ({ label: l.name, value: l.name }))
)

function todayStr() {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'America/Bogota' })
}

/** Formatea una Date a YYYY-MM-DD usando la fecha local (evita desfase por timezone con el DatePicker). */
function dateToYMD(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const route = useRoute()
const router = useRouter()

function resolveSedeFromQuery(sede: string | undefined): string | null {
  if (!sede || !locales.value.length) return null
  const byId = locales.value.find((l) => l.id && String(l.id) === String(sede))
  if (byId) return byId.name
  const byName = locales.value.find((l) => l.name === sede)
  if (byName) return byName.name
  return sede
}

function applyQueryParams() {
  const sedeParam = (route.query.sede as string) || ''
  if (sedeParam && locales.value.length) {
    const ids = sedeParam.split(',').map((s) => s.trim()).filter(Boolean)
    const names: string[] = []
    for (const id of ids) {
      const resolved = resolveSedeFromQuery(id)
      if (resolved) names.push(resolved)
    }
    if (names.length) selectedLocals.value = names
  } else if (!selectedLocals.value.length && locales.value.length) {
    selectedLocals.value = [locales.value[0]?.name ?? ''].filter(Boolean)
  }
  const desde = (route.query.fecha_desde as string)?.slice(0, 10)
  const hasta = (route.query.fecha_hasta as string)?.slice(0, 10)
  if (desde) fechaDesde.value = desde
  if (hasta) fechaHasta.value = hasta
  if (selectedLocals.value.length && fechaDesde.value && fechaHasta.value) loadOrders()
}

const selectedSedeParam = computed(() =>
  selectedLocals.value
    .map((name) => {
      const loc = locales.value.find((l) => l.name === name)
      return loc?.id ? loc.id : name
    })
    .filter(Boolean)
    .join(',')
)

function syncQueryToUrl() {
  const query: Record<string, string> = { ...(route.query as Record<string, string>) }
  if (selectedSedeParam.value) query.sede = selectedSedeParam.value
  if (fechaDesde.value) query.fecha_desde = fechaDesde.value
  if (fechaHasta.value) query.fecha_hasta = fechaHasta.value
  router.replace({ path: route.path, query }).catch(() => {})
}

// Marcar para apelación
const marcaDialogVisible = ref(false)
const marcaOrder = ref<Order | null>(null)
const marcaMontoDescontado = ref<number | null>(null)
const marcaLoading = ref(false)

function openMarcaDialog(order: Order) {
  marcaOrder.value = order
  marcaMontoDescontado.value = null
  marcaDialogVisible.value = true
}

function closeMarcaDialog() {
  marcaDialogVisible.value = false
  marcaOrder.value = null
  marcaMontoDescontado.value = null
}

async function confirmMarca() {
  const order = marcaOrder.value
  if (!order || marcaMontoDescontado.value == null) return
  marcaLoading.value = true
  try {
    const body = {
      codigo: (order['Codigo integracion'] || '').trim(),
      canal: (order['Canal de delivery'] || '').trim(),
      delivery_id: (order.delivery_id || '').trim(),
      monto_descontado: marcaMontoDescontado.value,
      local: order.Local || '',
      fecha: order.Fecha || ''
    }
    const r = await fetch(`${API}/api/apelaciones/marcar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    if (!r.ok) {
      const err = await r.json().catch(() => ({}))
      throw new Error(err.detail || 'Error al marcar')
    }
    closeMarcaDialog()
    await loadOrders()
  } catch (e) {
    orderError.value = (e as Error).message
  } finally {
    marcaLoading.value = false
  }
}

async function loadOrders() {
  if (!selectedLocals.value.length || !fechaDesde.value || !fechaHasta.value) return
  loadingOrders.value = true
  orderError.value = ''
  try {
    const params = new URLSearchParams()
    params.set('locales', selectedLocals.value.join(','))
    params.set('fecha_desde', fechaDesde.value)
    params.set('fecha_hasta', fechaHasta.value)
    params.set('exclude_marcadas_apelacion', '1')
    const r = await fetch(`${API}/api/orders?${params.toString()}`)
    if (!r.ok) {
      const err = await r.json().catch(() => ({}))
      throw new Error(err.detail || r.statusText)
    }
    const data = await r.json()
    orders.value = (data.orders ?? []) as Order[]
  } catch (err) {
    orderError.value = (err as Error).message
    orders.value = []
  } finally {
    loadingOrders.value = false
  }
}

onMounted(async () => {
  const { desde, hasta } = lastTwoWeeksRange()
  if (!fechaDesde.value) fechaDesde.value = desde
  if (!fechaHasta.value) fechaHasta.value = hasta
  try {
    const r = await fetch(`${API}/report/locales`)
    const data = await r.json()
    const raw = data.locales ?? []
    locales.value = raw.map((x: LocaleItem | string) =>
      typeof x === 'object' && x && 'name' in x ? { id: (x as LocaleItem).id || '', name: (x as LocaleItem).name } : { id: '', name: String(x) }
    )
    if (!route.query.sede && locales.value.length) selectedLocals.value = [locales.value[0]?.name ?? ''].filter(Boolean)
  } catch {
    locales.value = []
  }
  applyQueryParams()
})

watch([selectedLocals, fechaDesde, fechaHasta], () => {
  if (locales.value.length && selectedLocals.value.length && fechaDesde.value && fechaHasta.value) syncQueryToUrl()
}, { flush: 'post' })

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

function fullPhotoUrl(path: string): string {
  if (!path || path.startsWith('http')) return path || ''
  const base = API ? API.replace(/\/$/, '') : (typeof window !== 'undefined' ? window.location.origin : '')
  return base + (path.startsWith('/') ? path : '/' + path)
}

const photoModalVisible = ref(false)
const photoModalUrl = ref<string | null>(null)
function openPhotoModal(url: string) {
  photoModalUrl.value = url
  photoModalVisible.value = true
}
function closePhotoModal() {
  photoModalVisible.value = false
  photoModalUrl.value = null
}
</script>

<template>
  <div class="marcar-apelacion-view">
    <Card class="mb-3">
      <template #title>Marcar para apelación</template>
      <template #content>
        <p class="text-color-secondary mt-0 mb-3">
          Selecciona la sede y rango de fechas (por defecto últimas 2 semanas), luego marca los pedidos que el canal nos descontó.
        </p>
        <div class="flex flex-wrap gap-3 align-items-end mb-3">
          <div class="flex flex-column gap-2">
            <label for="sede">Sedes</label>
            <MultiSelect
              id="sede"
              v-model="selectedLocals"
              :options="localeOptions"
              option-label="label"
              option-value="value"
              placeholder="Seleccionar una o más sedes"
              class="w-full"
              filter
              filter-placeholder="Buscar sede..."
              :max-selected-labels="3"
              @change="loadOrders"
            />
          </div>
          <div class="flex flex-column gap-2">
            <label for="fecha-desde">Desde</label>
            <DatePicker
              id="fecha-desde"
              v-model="fechaDesdeAsDate"
              :minDate="MIN_DATE"
              dateFormat="dd/mm/yy"
              showIcon
              @update:modelValue="loadOrders"
            />
          </div>
          <div class="flex flex-column gap-2">
            <label for="fecha-hasta">Hasta</label>
            <DatePicker
              id="fecha-hasta"
              v-model="fechaHastaAsDate"
              :minDate="MIN_DATE"
              dateFormat="dd/mm/yy"
              showIcon
              @update:modelValue="loadOrders"
            />
          </div>
          <Button label="Cargar pedidos" icon="pi pi-refresh" :loading="loadingOrders" @click="loadOrders" />
        </div>
      </template>
    </Card>

    <Message v-if="orderError" severity="error" class="mb-3">{{ orderError }}</Message>

    <Card>
      <template #title>Pedidos ({{ fechaDesde }} – {{ fechaHasta }})</template>
      <template #content>
        <div class="mb-2">
          <InputText v-model="globalFilterText" placeholder="Filtrar por canal o código..." class="w-full" />
        </div>
        <DataTable
          :value="orders"
          :loading="loadingOrders"
          data-key="rowKey"
          :filters="tableFilters"
          :globalFilterFields="['Codigo integracion', 'Canal de delivery', 'Fecha', 'Local']"
          class="p-datatable-sm p-datatable-striped"
          :paginator="true"
          :rows="10"
          paginator-template="CurrentPageReport FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink"
          current-page-report-template="Mostrando {first} a {last} de {totalRecords} registros — Página {currentPage} de {totalPages}"
        >
          <Column field="Fecha" header="Fecha" sortable style="min-width: 100px" />
          <Column field="Local" header="Sede" sortable style="min-width: 120px" />
          <Column field="Canal de delivery" header="Canal">
            <template #body="{ data }">
              <div class="flex align-items-center gap-2">
                <img
                  v-if="canalLogoUrl(data['Canal de delivery'])"
                  :src="canalLogoUrl(data['Canal de delivery'])!"
                  :alt="data['Canal de delivery']"
                  class="canal-logo-table"
                  style="width: 24px; height: 24px; object-fit: contain"
                />
                <span>{{ data['Canal de delivery'] || '—' }}</span>
              </div>
            </template>
          </Column>
          <Column field="Codigo integracion" header="Código" sortable />
          <Column header="Foto entrega" style="min-width: 100px">
            <template #body="{ data }">
              <div v-if="(data.fotos_entrega ?? []).length" class="fotos-entrega-thumbs">
                <button
                  v-for="url in (data.fotos_entrega ?? []).slice(0, 3)"
                  :key="url"
                  type="button"
                  class="foto-thumb-mini"
                  @click.stop="openPhotoModal(url)"
                >
                  <img :src="fullPhotoUrl(url)" alt="Entrega" />
                </button>
              </div>
              <span v-else class="text-color-secondary">—</span>
            </template>
          </Column>
          <Column field="Monto pagado" header="Valor del pedido">
            <template #body="{ data }">{{ formatMonto(data['Monto pagado']) }}</template>
          </Column>
          <Column header="Acción">
            <template #body="{ data }">
              <Button
                label="Marcar para apelación"
                icon="pi pi-flag"
                severity="warn"
                size="small"
                class="btn-touch"
                @click="openMarcaDialog(data)"
              />
            </template>
          </Column>
          <template #empty>
            <span class="text-color-secondary">Selecciona una o más sedes y rango de fechas y pulsa Cargar pedidos.</span>
          </template>
          <template #loading>
            <ProgressSpinner style="width: 40px; height: 40px" stroke-width="4" />
          </template>
        </DataTable>
      </template>
    </Card>

    <Dialog
      v-model:visible="marcaDialogVisible"
      modal
      header="Marcar para apelación"
      :closable="!marcaLoading"
      @hide="closeMarcaDialog"
    >
      <template #default>
        <div v-if="marcaOrder" class="mb-3">
          <p><strong>Pedido:</strong> {{ marcaOrder['Codigo integracion'] }}</p>
          <p><strong>Canal:</strong> {{ marcaOrder['Canal de delivery'] }}</p>
          <p><strong>Valor del pedido:</strong> {{ formatMonto(marcaOrder['Monto pagado']) }}</p>
          <div v-if="(marcaOrder.fotos_entrega ?? []).length" class="mt-2">
            <label class="block mb-1">Foto de entrega</label>
            <div class="flex flex-wrap gap-2 fotos-entrega-thumbs">
              <button
                v-for="url in (marcaOrder.fotos_entrega ?? [])"
                :key="url"
                type="button"
                class="foto-thumb-dialog"
                @click="openPhotoModal(url)"
              >
                <img :src="fullPhotoUrl(url)" alt="Entrega" />
              </button>
            </div>
          </div>
        </div>
        <div class="flex flex-column gap-2">
          <label for="monto-descontado">Valor del pedido que nos descontó el canal (COP)</label>
          <InputNumber
            id="monto-descontado"
            v-model="marcaMontoDescontado"
            mode="currency"
            currency="COP"
            locale="es-CO"
            :min-fraction-digits="0"
            :max-fraction-digits="0"
            class="w-full"
          />
        </div>
      </template>
      <template #footer>
        <Button label="Cancelar" severity="secondary" :disabled="marcaLoading" @click="closeMarcaDialog" />
        <Button
          label="Marcar"
          icon="pi pi-check"
          :loading="marcaLoading"
          :disabled="marcaMontoDescontado == null || marcaMontoDescontado < 0"
          @click="confirmMarca"
        />
      </template>
    </Dialog>

    <Dialog
      v-model:visible="photoModalVisible"
      modal
      header="Foto de entrega"
      class="photo-dialog"
      @hide="closePhotoModal"
    >
      <template #default>
        <div v-if="photoModalUrl" class="photo-modal-body">
          <img :src="fullPhotoUrl(photoModalUrl)" alt="Foto" class="photo-modal-img" />
        </div>
      </template>
      <template #footer>
        <Button label="Cerrar" icon="pi pi-times" @click="closePhotoModal" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.marcar-apelacion-view {
  padding: 0.5rem;
}
.btn-touch {
  min-height: 44px;
  min-width: 44px;
}
.fotos-entrega-thumbs {
  display: flex;
  gap: 0.25rem;
  flex-wrap: wrap;
}
.foto-thumb-mini {
  width: 36px;
  height: 36px;
  padding: 0;
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
  overflow: hidden;
  cursor: pointer;
  background: transparent;
}
.foto-thumb-mini:hover {
  border-color: var(--p-primary-color);
}
.foto-thumb-mini img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.foto-thumb-dialog {
  width: 80px;
  height: 80px;
  padding: 0;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  background: transparent;
}
.foto-thumb-dialog:hover {
  border-color: var(--p-primary-color);
}
.foto-thumb-dialog img {
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
</style>
