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
import Checkbox from 'primevue/checkbox'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'
import Dialog from 'primevue/dialog'

const API = import.meta.env.VITE_API_URL ?? ''

interface ReembolsoEntry {
  monto: number
  fecha: string
}
interface ApelacionItem {
  codigo: string
  canal: string
  monto_descontado: number
  monto_devuelto: number
  total_reembolsado?: number
  reembolsos?: ReembolsoEntry[]
  fecha_estimada_devolucion?: string
  local?: string
  fecha?: string
}

interface LocaleItem {
  id: string
  name: string
}

const locales = ref<LocaleItem[]>([])
const selectedLocal = ref<string | null>(null)
const fechaDesde = ref('')
const fechaHasta = ref('')
const pendientes = ref<ApelacionItem[]>([])
const loadingPendientes = ref(false)
const orderError = ref('')

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

// Reembolsar dialog
const reembolsarDialogVisible = ref(false)
const reembolsarItem = ref<ApelacionItem | null>(null)
const reembolsarMismoValor = ref(true)
const reembolsarMontoDiferente = ref<number | null>(null)
const reembolsarFecha = ref('')
const reembolsarLoading = ref(false)

const reembolsarFechaAsDate = computed({
  get: () => (reembolsarFecha.value ? new Date(reembolsarFecha.value + 'T12:00:00') : null),
  set: (v: Date | null) => { reembolsarFecha.value = v ? v.toISOString().slice(0, 10) : '' }
})

const pendienteReembolso = computed(() => {
  const item = reembolsarItem.value
  if (!item) return 0
  return Math.max(0, (item.monto_devuelto ?? 0) - (item.total_reembolsado ?? 0))
})

function openReembolsarDialog(item: ApelacionItem) {
  reembolsarItem.value = item
  reembolsarMismoValor.value = true
  const pendiente = Math.max(0, (item.monto_devuelto ?? 0) - (item.total_reembolsado ?? 0))
  reembolsarMontoDiferente.value = pendiente
  reembolsarFecha.value = todayStr()
  reembolsarDialogVisible.value = true
}

function closeReembolsarDialog() {
  reembolsarDialogVisible.value = false
  reembolsarItem.value = null
  reembolsarMismoValor.value = true
  reembolsarMontoDiferente.value = null
  reembolsarFecha.value = ''
}

async function confirmReembolsar() {
  const item = reembolsarItem.value
  if (!item) return
  if (!reembolsarMismoValor.value && (reembolsarMontoDiferente.value == null || reembolsarMontoDiferente.value < 0)) {
    orderError.value = 'Indica el valor del pedido que te devolvieron'
    return
  }
  reembolsarLoading.value = true
  orderError.value = ''
  try {
    const body = {
      codigo: item.codigo,
      mismo_valor: reembolsarMismoValor.value,
      monto_reembolsado: reembolsarMismoValor.value ? undefined : reembolsarMontoDiferente.value,
      fecha_reembolso: reembolsarFecha.value || todayStr()
    }
    const r = await fetch(`${API}/api/apelaciones/reembolsar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    if (!r.ok) {
      const err = await r.json().catch(() => ({}))
      throw new Error(err.detail || 'Error al reembolsar')
    }
    closeReembolsarDialog()
    await loadPendientes()
  } catch (e) {
    orderError.value = (e as Error).message
  } finally {
    reembolsarLoading.value = false
  }
}

async function loadPendientes() {
  const local = selectedLocal.value || resolveLocalFromSede(selectedSede.value) || ''
  const desde = fechaDesde.value || todayStr()
  const hasta = fechaHasta.value || todayStr()
  loadingPendientes.value = true
  orderError.value = ''
  try {
    const params = new URLSearchParams()
    if (local) params.set('local', local)
    params.set('fecha_desde', desde)
    params.set('fecha_hasta', hasta)
    const r = await fetch(`${API}/api/apelaciones/reembolsos-pendientes?${params.toString()}`)
    const data = await r.json()
    pendientes.value = data.items ?? []
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
    selectedLocal.value = resolveLocalFromSede(selectedSede.value) || (locales.value[0]?.name ?? null)
  const range = lastTwoWeeksRange()
  fechaDesde.value = range.desde
  fechaHasta.value = range.hasta
  await loadPendientes()
})

watch([selectedLocal, fechaDesde, fechaHasta], () => {
  if (selectedLocal.value || fechaDesde.value || fechaHasta.value) loadPendientes()
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
</script>

<template>
  <div class="reembolsos-view">
    <Card class="mb-3">
      <template #title>Reembolsos</template>
      <template #content>
        <p class="text-color-secondary mt-0 mb-3">
          Órdenes apeladas que aún no han sido marcadas como reembolsadas. Marca cada una cuando efectivamente recibas el dinero.
        </p>
        <div class="flex flex-wrap gap-3 align-items-end mb-2">
          <div class="flex flex-column gap-2">
            <label for="reemb-sede">Sede</label>
            <Select
              id="reemb-sede"
              v-model="selectedLocal"
              :options="localeOptions"
              option-label="label"
              option-value="value"
              placeholder="Todas"
              class="w-full"
              filter
              filter-placeholder="Buscar sede..."
              show-clear
            />
          </div>
          <div class="flex flex-column gap-2">
            <label for="reemb-desde">Desde</label>
            <DatePicker
              id="reemb-desde"
              v-model="fechaDesdeAsDate"
              :minDate="MIN_DATE"
              dateFormat="dd/mm/yy"
              showIcon
            />
          </div>
          <div class="flex flex-column gap-2">
            <label for="reemb-hasta">Hasta</label>
            <DatePicker
              id="reemb-hasta"
              v-model="fechaHastaAsDate"
              :minDate="MIN_DATE"
              dateFormat="dd/mm/yy"
              showIcon
            />
          </div>
          <Button label="Cargar" icon="pi pi-refresh" :loading="loadingPendientes" @click="loadPendientes" />
        </div>
      </template>
    </Card>

    <Message v-if="orderError" severity="error" class="mb-3">{{ orderError }}</Message>

    <Card>
      <template #title>Pendientes de reembolso</template>
      <template #content>
        <DataTable
          :value="pendientes"
          :loading="loadingPendientes"
          data-key="codigo"
          class="p-datatable-sm p-datatable-striped"
          :paginator="pendientes.length > 10"
          :rows="10"
          paginator-template="CurrentPageReport FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink"
          current-page-report-template="Mostrando {first} a {last} de {totalRecords} registros — Página {currentPage} de {totalPages}"
        >
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
          <Column header="Descontado por canal">
            <template #body="{ data }">{{ formatMonto(data.monto_descontado) }}</template>
          </Column>
          <Column header="Reconocido por canal (a devolver)">
            <template #body="{ data }">{{ formatMonto(data.monto_devuelto) }}</template>
          </Column>
          <Column header="Ya reembolsado" style="min-width: 140px">
            <template #body="{ data }">
              <span v-if="(data.total_reembolsado ?? 0) > 0">{{ formatMonto(data.total_reembolsado) }} de {{ formatMonto(data.monto_devuelto) }}</span>
              <span v-else class="text-color-secondary">—</span>
            </template>
          </Column>
          <Column header="Fecha estimada">
            <template #body="{ data }">{{ data.fecha_estimada_devolucion || '—' }}</template>
          </Column>
          <Column header="Acción">
            <template #body="{ data }">
              <Button
                :label="(data.reembolsos?.length ?? 0) > 0 ? 'Registrar otro reembolso' : 'Registrar reembolso'"
                icon="pi pi-check"
                severity="success"
                size="small"
                class="btn-touch"
                @click="openReembolsarDialog(data)"
              />
            </template>
          </Column>
          <template #empty>
            <span class="text-color-secondary">No hay órdenes pendientes de reembolso.</span>
          </template>
          <template #loading>
            <ProgressSpinner style="width: 40px; height: 40px" stroke-width="4" />
          </template>
        </DataTable>
      </template>
    </Card>

    <Dialog
      v-model:visible="reembolsarDialogVisible"
      modal
      header="Marcar como reembolsado"
      :closable="!reembolsarLoading"
      @hide="closeReembolsarDialog"
    >
      <template #default>
        <div v-if="reembolsarItem" class="mb-3">
          <p><strong>Pedido:</strong> {{ reembolsarItem.codigo }}</p>
          <p><strong>Canal:</strong> {{ reembolsarItem.canal }}</p>
          <p><strong>Total comprometido por canal:</strong> {{ formatMonto(reembolsarItem.monto_devuelto) }}</p>
          <p v-if="(reembolsarItem.total_reembolsado ?? 0) > 0">
            <strong>Ya recibido:</strong> {{ formatMonto(reembolsarItem.total_reembolsado) }}
          </p>
          <p><strong>Pendiente de recibir:</strong> <span class="text-red font-semibold">{{ formatMonto(pendienteReembolso) }}</span></p>
        </div>
        <div class="flex flex-column gap-3">
          <div>
            <label class="block mb-1">Fecha en que recibiste el reembolso</label>
            <DatePicker
              v-model="reembolsarFechaAsDate"
              dateFormat="dd/mm/yy"
              showIcon
              class="w-full"
            />
          </div>
          <div class="flex align-items-center gap-2">
            <Checkbox
              id="mismo-valor"
              v-model="reembolsarMismoValor"
              :binary="true"
              input-id="mismo-valor"
            />
            <label for="mismo-valor">Sí nos devolvieron todo lo pendiente ({{ formatMonto(pendienteReembolso) }})</label>
          </div>
          <div class="flex align-items-center gap-2">
            <Checkbox
              id="valor-diferente"
              :model-value="!reembolsarMismoValor"
              :binary="true"
              @update:model-value="reembolsarMismoValor = !$event"
            />
            <label for="valor-diferente">Nos devolvieron un valor diferente</label>
          </div>
          <div v-if="!reembolsarMismoValor">
            <label for="monto-reembolsado" class="block mb-1">Valor del pedido que te devolvieron (COP)</label>
            <InputNumber
              id="monto-reembolsado"
              v-model="reembolsarMontoDiferente"
              mode="currency"
              currency="COP"
              locale="es-CO"
              :min-fraction-digits="0"
              :max-fraction-digits="0"
              class="w-full"
            />
          </div>
        </div>
      </template>
      <template #footer>
        <Button label="Cancelar" icon="pi pi-times" severity="secondary" :disabled="reembolsarLoading" @click="closeReembolsarDialog" />
        <Button
          :label="(reembolsarItem?.reembolsos?.length ?? 0) > 0 ? 'Registrar reembolso' : 'Marcar reembolsado'"
          icon="pi pi-check"
          :loading="reembolsarLoading"
          :disabled="!reembolsarMismoValor && (reembolsarMontoDiferente == null || reembolsarMontoDiferente <= 0)"
          @click="confirmReembolsar"
        />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.reembolsos-view {
  padding: 0.5rem;
}
.btn-touch {

  min-width: 44px;
}
</style>
