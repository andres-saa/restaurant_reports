<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Card from 'primevue/card'
import InputNumber from 'primevue/inputnumber'
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
  delivery_id?: string
  apelacion_monto_descontado?: number
  apelacion_canal?: string
  fotos_entrega?: string[]
}

interface LocaleItem {
  id: string
  name: string
}

const route = useRoute()
const locales = ref<LocaleItem[]>([])
const selectedLocal = ref<string | null>(null)
const fechaDesde = ref('')
const fechaHasta = ref('')
const pendientes = ref<Order[]>([])
const loadingPendientes = ref(false)
const orderError = ref('')
const MIN_DATE = new Date(2026, 1, 11)
const selectedSede = computed(() => (route.query.sede as string) || '')

function lastThirtyDaysRange(): { desde: string; hasta: string } {
  const today = new Date()
  const hasta = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  const desde = new Date(hasta)
  desde.setDate(desde.getDate() - 29)
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

function todayStr() {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'America/Bogota' })
}

// No apelar, asumir descuento en nómina
const noApelarDialogVisible = ref(false)
const noApelarOrder = ref<Order | null>(null)
const noApelarLoading = ref(false)
function openNoApelarDialog(order: Order) {
  noApelarOrder.value = order
  noApelarDialogVisible.value = true
}
function closeNoApelarDialog() {
  noApelarDialogVisible.value = false
  noApelarOrder.value = null
}
async function confirmNoApelar() {
  const order = noApelarOrder.value
  if (!order) return
  noApelarLoading.value = true
  orderError.value = ''
  try {
    const r = await fetch(`${API}/api/apelaciones/no-apelar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codigo: (order['Codigo integracion'] || '').trim() })
    })
    if (!r.ok) {
      const err = await r.json().catch(() => ({}))
      throw new Error(err.detail || 'Error al confirmar')
    }
    closeNoApelarDialog()
    await loadPendientes()
  } catch (e) {
    orderError.value = (e as Error).message
  } finally {
    noApelarLoading.value = false
  }
}

// Apelar: subir foto + monto_devuelto + fecha estimada devolución
const apelarDialogVisible = ref(false)
const apelarOrder = ref<Order | null>(null)
const apelarMontoDevuelto = ref<number | null>(null)
const apelarFechaEstimada = ref<string>('')
const apelarFiles = ref<File[]>([])
const apelarLoading = ref(false)

function openApelarDialog(order: Order) {
  apelarOrder.value = order
  apelarMontoDevuelto.value = null
  apelarFechaEstimada.value = ''
  apelarFiles.value = []
  apelarDialogVisible.value = true
}

function closeApelarDialog() {
  apelarDialogVisible.value = false
  apelarOrder.value = null
  apelarMontoDevuelto.value = null
  apelarFechaEstimada.value = ''
  apelarFiles.value = []
  photoModalUrl.value = null
}

function onApelarFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const files = input.files
  if (!files?.length) return
  apelarFiles.value = Array.from(files)
  input.value = ''
}

const apelarFechaEstimadaAsDate = computed({
  get: () => apelarFechaEstimada.value ? new Date(apelarFechaEstimada.value + 'T12:00:00') : null,
  set: (v: Date | null) => { apelarFechaEstimada.value = v ? v.toISOString().slice(0, 10) : '' }
})

async function confirmApelar() {
  const order = apelarOrder.value
  if (!order || apelarMontoDevuelto.value == null) return
  apelarLoading.value = true
  orderError.value = ''
  try {
    const codigo = (order['Codigo integracion'] || '').trim()
    const params = new URLSearchParams()
    params.set('codigo', codigo)
    params.set('monto_devuelto', String(apelarMontoDevuelto.value))
    if (apelarFechaEstimada.value) params.set('fecha_estimada_devolucion', apelarFechaEstimada.value)
    const fd = new FormData()
    apelarFiles.value.forEach((f) => fd.append('files', f))
    const r = await fetch(`${API}/api/apelaciones/apelar?${params.toString()}`, {
      method: 'POST',
      body: fd
    })
    if (!r.ok) {
      const err = await r.json().catch(() => ({}))
      throw new Error(err.detail || 'Error al apelar')
    }
    closeApelarDialog()
    await loadPendientes()
  } catch (e) {
    orderError.value = (e as Error).message
  } finally {
    apelarLoading.value = false
  }
}

async function loadPendientes() {
  const local = selectedLocal.value || resolveLocalFromSede(selectedSede.value) || selectedSede.value
  if (!local || !fechaDesde.value || !fechaHasta.value) return
  loadingPendientes.value = true
  orderError.value = ''
  try {
    const params = new URLSearchParams()
    params.set('local', local)
    params.set('fecha_desde', fechaDesde.value)
    params.set('fecha_hasta', fechaHasta.value)
    const r = await fetch(`${API}/api/apelaciones/pendientes?${params.toString()}`)
    const data = await r.json()
    pendientes.value = data.orders ?? []
  } catch (err) {
    orderError.value = (err as Error).message
    pendientes.value = []
  } finally {
    loadingPendientes.value = false
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
  const resolved = resolveLocalFromSede(selectedSede.value) || selectedSede.value
  selectedLocal.value = resolved || (locales.value[0]?.name ?? null)
  const { desde, hasta } = lastThirtyDaysRange()
  if (!fechaDesde.value) fechaDesde.value = desde
  if (!fechaHasta.value) fechaHasta.value = hasta
  await loadPendientes()
})

watch([selectedLocal, fechaDesde, fechaHasta], () => {
  if (selectedLocal.value && fechaDesde.value && fechaHasta.value) loadPendientes()
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

function fullPhotoUrl(path: string): string {
  if (!path || path.startsWith('http')) return path || ''
  const base = API ? API.replace(/\/$/, '') : (typeof window !== 'undefined' ? window.location.origin : '')
  return base + (path.startsWith('/') ? path : '/' + path)
}

// Dialog para ver fotos de entrega
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
  <div class="apelar-view">
    <Card class="mb-3">
      <template #title>Apelar</template>
      <template #content>
        <p class="text-color-secondary mt-0 mb-3">
          Pedidos marcados por el admin para apelación. Sube la foto de la respuesta del canal y el valor del pedido que te van a devolver.
        </p>
        <p class="text-color-secondary mb-3">
          Elige la sede y el rango de fechas. Las órdenes ya apeladas o marcadas como "no apelar" no aparecen en pendientes.
        </p>
        <div class="flex flex-wrap gap-3 align-items-end mb-2">
          <div class="flex flex-column gap-2">
            <label for="apelar-sede">Sede</label>
            <Select
              id="apelar-sede"
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
            <label for="apelar-desde">Desde</label>
            <DatePicker
              id="apelar-desde"
              v-model="fechaDesdeAsDate"
              :minDate="MIN_DATE"
              dateFormat="dd/mm/yy"
              showIcon
            />
          </div>
          <div class="flex flex-column gap-2">
            <label for="apelar-hasta">Hasta</label>
            <DatePicker
              id="apelar-hasta"
              v-model="fechaHastaAsDate"
              :minDate="MIN_DATE"
              dateFormat="dd/mm/yy"
              showIcon
            />
          </div>
          <Button label="Actualizar" icon="pi pi-refresh" :loading="loadingPendientes" @click="loadPendientes" />
        </div>
      </template>
    </Card>

    <Message v-if="orderError" severity="error" class="mb-3">{{ orderError }}</Message>

    <Card>
      <template #title>Pendientes de apelar</template>
      <template #content>
        <DataTable
          :value="pendientes"
          :loading="loadingPendientes"
          data-key="Codigo integracion"
          class="p-datatable-sm p-datatable-striped"
          :paginator="pendientes.length > 10"
          :rows="10"
          paginator-template="CurrentPageReport FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink"
          current-page-report-template="Mostrando {first} a {last} de {totalRecords} registros — Página {currentPage} de {totalPages}"
        >
          <Column field="Fecha" header="Fecha" sortable style="min-width: 100px" />
          <Column field="Canal de delivery" header="Canal">
            <template #body="{ data }">
              <div class="flex align-items-center gap-2">
                <img
                  v-if="canalLogoUrl(data['Canal de delivery'])"
                  :src="canalLogoUrl(data['Canal de delivery'])!"
                  :alt="data['Canal de delivery']"
                  style="width: 24px; height: 24px; object-fit: contain"
                />
                <span>{{ data['Canal de delivery'] || '—' }}</span>
              </div>
            </template>
          </Column>
          <Column field="Codigo integracion" header="Código" sortable />
          <Column header="Fotos entrega">
            <template #body="{ data }">
              <div v-if="data.fotos_entrega?.length" class="fotos-entrega-thumbs">
                <button
                  v-for="url in (data.fotos_entrega || []).slice(0, 3)"
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
          <Column header="Descontado por canal">
            <template #body="{ data }">{{ formatMonto(data.apelacion_monto_descontado) }}</template>
          </Column>
          <Column header="Acción" style="min-width: 280px">
            <template #body="{ data }">
              <div class="flex flex-wrap gap-1">
                <Button
                  label="Apelar"
                  icon="pi pi-upload"
                  severity="success"
                  size="small"
                  class="btn-touch"
                  @click="openApelarDialog(data)"
                />
                <Button
                  label="No apelar"
                  icon="pi pi-minus-circle"
                  severity="secondary"
                  size="small"
                  class="btn-touch"
                  @click="openNoApelarDialog(data)"
                />
              </div>
            </template>
          </Column>
          <template #empty>
            <span class="text-color-secondary">No hay pedidos pendientes de apelar para esta sede en el rango de fechas.</span>
          </template>
          <template #loading>
            <ProgressSpinner style="width: 40px; height: 40px" stroke-width="4" />
          </template>
        </DataTable>
      </template>
    </Card>

    <Dialog
      v-model:visible="noApelarDialogVisible"
      modal
      header="No apelar"
      :closable="!noApelarLoading"
      @hide="closeNoApelarDialog"
    >
      <template #default>
        <p v-if="noApelarOrder">
          ¿No vas a apelar este pedido? Se enviará al apartado Descuentos con la etiqueta «La sede decidió no apelar» para que admin confirme el descuento en nómina cuando corresponda.
        </p>
        <p v-if="noApelarOrder" class="text-color-secondary">
          Pedido: <strong>{{ noApelarOrder['Codigo integracion'] }}</strong> — Canal: {{ noApelarOrder['Canal de delivery'] }}
        </p>
      </template>
      <template #footer>
        <Button label="Cancelar" icon="pi pi-times" severity="secondary" :disabled="noApelarLoading" @click="closeNoApelarDialog" />
        <Button label="Sí, no apelar" icon="pi pi-check" :loading="noApelarLoading" @click="confirmNoApelar" />
      </template>
    </Dialog>

    <Dialog
      v-model:visible="apelarDialogVisible"
      modal
      header="Apelar"
      :closable="!apelarLoading"
      class="apelar-dialog"
      @hide="closeApelarDialog"
    >
      <template #default>
        <div v-if="apelarOrder" class="mb-3">
          <p><strong>Pedido:</strong> {{ apelarOrder['Codigo integracion'] }}</p>
          <p><strong>Canal:</strong> {{ apelarOrder['Canal de delivery'] }}</p>
          <p><strong>Descontado por canal:</strong> {{ formatMonto(apelarOrder.apelacion_monto_descontado) }}</p>
        </div>
        <div class="flex flex-column gap-3">
          <div>
            <label for="monto-devuelto" class="block mb-1">Valor del pedido que te van a devolver (COP)</label>
            <InputNumber
              id="monto-devuelto"
              v-model="apelarMontoDevuelto"
              mode="currency"
              currency="COP"
              locale="es-CO"
              :min-fraction-digits="0"
              :max-fraction-digits="0"
              class="w-full"
            />
          </div>
          <div>
            <label for="fecha-estimada" class="block mb-1">¿Cuándo nos van a devolver el dinero?</label>
            <DatePicker
              id="fecha-estimada"
              v-model="apelarFechaEstimadaAsDate"
              dateFormat="dd/mm/yy"
              showIcon
              class="w-full"
            />
          </div>
          <div>
            <label class="block mb-1">Foto de la respuesta del canal</label>
            <input
              type="file"
              accept="image/*,image/heic,.heic,.heif"
              multiple
              class="w-full"
              @change="onApelarFileChange"
            />
            <small v-if="apelarFiles.length" class="text-color-secondary">{{ apelarFiles.length }} archivo(s) seleccionado(s)</small>
          </div>
        </div>
      </template>
      <template #footer>
        <Button label="Cancelar" icon="pi pi-times" severity="secondary" :disabled="apelarLoading" @click="closeApelarDialog" />
        <Button
          label="Enviar apelación"
          icon="pi pi-check"
          :loading="apelarLoading"
          :disabled="apelarMontoDevuelto == null || apelarMontoDevuelto < 0"
          @click="confirmApelar"
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
.apelar-view {
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
