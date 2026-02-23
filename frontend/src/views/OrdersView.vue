<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useConfirm } from 'primevue/useconfirm'
import Select from 'primevue/select'
import SelectButton from 'primevue/selectbutton'
import Badge from 'primevue/badge'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import DatePicker from 'primevue/datepicker'
import Message from 'primevue/message'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import Divider from 'primevue/divider'
import ProgressSpinner from 'primevue/progressspinner'
import Dialog from 'primevue/dialog'
import PhotoLightbox from '@/components/PhotoLightbox.vue'

const API = import.meta.env.VITE_API_URL ?? ''

interface Order {
  'Codigo integracion': string
  'Cliente': string
  'Canal de delivery': string
  'Monto pagado': string
  'Fecha': string
  'Hora': string
  delivery_id?: string
  delivery_identificadorunico?: string
  delivery_celular?: string
  has_entrega_photo?: boolean
  no_entregada?: boolean
  Local?: string
}

interface FotosByGroup {
  entrega: string[]
  apelacion: Record<string, string[]>
  respuestas: string[]
}

interface LocaleItem {
  id: string
  name: string
}
const locales = ref<LocaleItem[]>([])
const selectedLocal = ref<string | null>(null)
const selectedDate = ref('')

/** Fecha mínima seleccionable: después del 10 feb 2026 → desde el 11 feb 2026. */
const MIN_DATE = new Date(2026, 1, 11)

/** Valor en formato Date para el DatePicker; se mantiene selectedDate en YYYY-MM-DD para URL y API. */
const selectedDateAsDate = computed({
  get: () => (selectedDate.value ? new Date(selectedDate.value + 'T12:00:00') : null),
  set: (v: Date | null) => {
    selectedDate.value = v ? v.toISOString().slice(0, 10) : ''
  }
})
const orders = ref<Order[]>([])
const loadingOrders = ref(false)
const orderError = ref('')

const selectedOrder = ref<Order | null>(null)
/** Filtro global para la tabla de pedidos. */
const globalFilterText = ref('')
const tableFilters = computed(() => ({
  global: { value: globalFilterText.value, matchMode: 'contains' as const }
}))

type EstadoEntregaFilter = 'todas' | 'con_foto' | 'pendientes'
const estadoEntregaFilter = ref<EstadoEntregaFilter>('todas')
const countConFoto = computed(() =>
  orders.value.filter((o: Order) => o.has_entrega_photo === true || o.no_entregada === true).length
)
const countPendientes = computed(() =>
  orders.value.filter((o: Order) => !o.has_entrega_photo && !o.no_entregada).length
)
const ordersFiltered = computed(() => {
  const list = orders.value
  if (estadoEntregaFilter.value === 'todas') return list
  if (estadoEntregaFilter.value === 'con_foto') {
    return list.filter((o: Order) => o.has_entrega_photo === true || o.no_entregada === true)
  }
  return list.filter((o: Order) => !o.has_entrega_photo && !o.no_entregada)
})
const filterOptions = computed(() => [
  { label: 'Todas', value: 'todas' as const, count: orders.value.length, severity: 'secondary' as const },
  { label: 'Con foto', value: 'con_foto' as const, count: countConFoto.value, severity: 'success' as const },
  { label: 'Pendientes', value: 'pendientes' as const, count: countPendientes.value, severity: 'danger' as const }
])
const fotos = ref<FotosByGroup>({ entrega: [], apelacion: {}, respuestas: [] })
const searchCodigo = ref('')
const loadingOrder = ref(false)
const uploadGroup = ref<'entrega' | 'apelacion' | 'respuestas'>('entrega')
const uploading = ref(false)
const canalesDelivery = ref<string[]>([])

// Modal subir fotos: selección, previsualización y subida dentro del modal (array para poder agregar/quitar)
const uploadModalVisible = ref(false)
const modalFiles = ref<File[]>([])
const uploadPreviewUrls = ref<string[]>([])
const modalDropzoneActive = ref(false)
const uploadGroupLabels: Record<'entrega' | 'apelacion' | 'respuestas', string> = {
  entrega: 'Fotos al entregar',
  apelacion: 'Fotos apelación',
  respuestas: 'Respuestas del canal'
}
/** En móvil, si se abrió el modal desde el botón de la fila: solo cámara (no galería). */
const isMobile = ref(false)
const UPLOAD_MOBILE_BREAKPOINT = 768
function updateMobile() {
  isMobile.value = typeof window !== 'undefined' && window.innerWidth < UPLOAD_MOBILE_BREAKPOINT
}

const route = useRoute()
const router = useRouter()

/** Modo cajero "Hoy": true en /pedidos/hoy (sede y fecha por link). */
const uploadOnly = computed(() => (route.meta.uploadOnly as boolean) ?? false)
/** Modo cajero "Reportes": misma vista que consulta pero sede fija (solo puede cambiar fecha para días anteriores). */
const reportesCajero = computed(() => (route.meta.reportesCajero as boolean) ?? false)

const localeOptions = computed(() =>
  locales.value.map((l) => ({ label: l.name, value: l.name }))
)

/** Valor para query param sede: id si existe, sino nombre (para links estables por sede). */
const selectedSedeParam = computed(() => {
  if (!selectedLocal.value) return ''
  const loc = locales.value.find((l) => l.name === selectedLocal.value)
  return loc?.id ? loc.id : selectedLocal.value ?? ''
})

/** Id del local actual (para comparar con sede_ready del WebSocket). */
const currentSedeId = computed(() => {
  const loc = locales.value.find((l) => l.name === selectedLocal.value)
  return loc?.id ?? ''
})

// Estado extensión Didi para la sede actual (punto verde parpadeando + "Didi ext")
const didiHasDidi = ref(false)
const didiExtensionActive = ref<boolean | null>(null)
let didiExtensionPollTimer: ReturnType<typeof setInterval> | null = null
const DIDI_EXTENSION_POLL_MS = 15000

async function fetchDidiExtensionStatus() {
  const rid = currentSedeId.value
  if (!rid) {
    didiHasDidi.value = false
    didiExtensionActive.value = null
    return
  }
  try {
    const r = await fetch(`${API}/didi/extension-status?restaurant_id=${encodeURIComponent(rid)}`)
    const data = await r.json()
    didiHasDidi.value = data.hasDidi === true
    didiExtensionActive.value = data.active === true
  } catch {
    didiHasDidi.value = false
    didiExtensionActive.value = null
  }
}

function startDidiExtensionPoll() {
  if (didiExtensionPollTimer) return
  fetchDidiExtensionStatus()
  didiExtensionPollTimer = setInterval(fetchDidiExtensionStatus, DIDI_EXTENSION_POLL_MS)
}

function stopDidiExtensionPoll() {
  if (didiExtensionPollTimer) {
    clearInterval(didiExtensionPollTimer)
    didiExtensionPollTimer = null
  }
  didiHasDidi.value = false
  didiExtensionActive.value = null
}

const codigoIntegracion = computed(() =>
  selectedOrder.value?.['Codigo integracion'] ?? ''
)
/** Fotos de apelación para el canal de la orden (apelas a esa tienda). */
const apelacionUrls = computed(() => {
  const canal = selectedOrder.value?.['Canal de delivery']
  return canal ? (fotos.value.apelacion[canal] ?? []) : []
})

// WebSocket estado del reporte automático
interface ReportSocketStatus {
  status?: string
  message?: string
  seconds_until_next?: number
  next_run_at?: string
  last_report_at?: string
  last_error?: string | null
  last_filas?: number
  interval_seconds?: number
}
const reportSocketStatus = ref<ReportSocketStatus | null>(null)
const reportSocketConnected = ref(false)
let reportWs: WebSocket | null = null
let reportWsReconnectTimer: ReturnType<typeof setTimeout> | null = null
const REPORT_WS_RECONNECT_MS = 3000

function getReportWsUrl(): string {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  if (API && API.trim()) {
    try {
      const u = new URL(API)
      const wsProtocol = u.protocol === 'https:' ? 'wss:' : 'ws:'
      const path = (u.pathname || '/').replace(/\/+$/, '') // quitar trailing slash
      const base = path && path !== '/' ? path : ''
      return `${wsProtocol}//${u.host}${base}/report/ws`
    } catch {
      return `${protocol}//${location.hostname}:9400/report/ws`
    }
  }
  // Dev sin VITE_API_URL: asumir backend en puerto 9400
  return `${protocol}//${location.hostname}:9400/report/ws`
}

function connectReportWs() {
  if (reportWs?.readyState === WebSocket.OPEN) return
  const wsUrl = getReportWsUrl()
  reportWs = new WebSocket(wsUrl)
  reportWs.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data?.type === 'sede_ready') {
        const sameSede = String(data.local_id) === String(currentSedeId.value)
        const sameFecha = data.fecha && selectedDate.value && data.fecha.slice(0, 10) === selectedDate.value.slice(0, 10)
        if (sameSede && sameFecha) loadOrders()
        return
      }
      reportSocketStatus.value = data
    } catch {
      reportSocketStatus.value = null
    }
  }
  reportWs.onopen = () => { reportSocketConnected.value = true }
  reportWs.onclose = () => {
    reportSocketConnected.value = false
    reportWs = null
    if (typeof window !== 'undefined') {
      reportWsReconnectTimer = window.setTimeout(connectReportWs, REPORT_WS_RECONNECT_MS)
    }
  }
  reportWs.onerror = () => { reportSocketConnected.value = false }
}

/** Fecha de hoy en Colombia (YYYY-MM-DD) para "Hoy" y valor por defecto. */
function todayStr() {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'America/Bogota' })
}

/** Resuelve query param sede (id o nombre) al nombre del local. */
function resolveSedeFromQuery(sede: string | undefined): string | null {
  if (!sede || !locales.value.length) return null
  const byId = locales.value.find((l) => l.id && String(l.id) === String(sede))
  if (byId) return byId.name
  const byName = locales.value.find((l) => l.name === sede)
  if (byName) return byName.name
  return sede
}

/** Aplica query params de la URL (sede y fecha) y carga pedidos si aplica. */
function applyQueryParams() {
  const sede = route.query.sede as string | undefined
  const fecha = (route.query.fecha as string | undefined)?.slice(0, 10)
  if (fecha) selectedDate.value = fecha
  const resolved = resolveSedeFromQuery(sede)
  if (resolved) selectedLocal.value = resolved
  else if (!selectedLocal.value && locales.value.length) selectedLocal.value = locales.value[0]?.name ?? null
  if (selectedLocal.value && selectedDate.value) loadOrders()
}

/** Escribe sede y fecha en la URL sin recargar. */
function syncQueryToUrl() {
  const query: Record<string, string> = { ...(route.query as Record<string, string>) }
  query.sede = selectedSedeParam.value
  query.fecha = selectedDate.value || todayStr()
  router.replace({ path: route.path, query }).catch(() => {})
}

onMounted(async () => {
  updateMobile()
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', updateMobile)
  }
  selectedDate.value = todayStr()
  try {
    const r = await fetch(`${API}/report/locales`)
    const data = await r.json()
    const raw = data.locales ?? []
    locales.value = raw.map((x: LocaleItem | string) =>
      typeof x === 'object' && x && 'name' in x ? { id: (x as LocaleItem).id || '', name: (x as LocaleItem).name } : { id: '', name: String(x) }
    )
    if (!route.query.sede && locales.value.length) selectedLocal.value = locales.value[0]?.name ?? null
  } catch {
    locales.value = []
  }
  try {
    const r = await fetch(`${API}/report/canales-delivery`)
    const data = await r.json()
    canalesDelivery.value = data.canales_delivery ?? []
  } catch {
    canalesDelivery.value = []
  }
  applyQueryParams()
  connectReportWs()
  if (uploadOnly.value) loadPlanillaEstado()
})

watch([selectedLocal, selectedDate], () => {
  if (locales.value.length && (selectedLocal.value || selectedDate.value)) syncQueryToUrl()
  if (uploadOnly.value) loadPlanillaEstado()
}, { flush: 'post' })

watch(currentSedeId, (id) => {
  if (id) startDidiExtensionPoll()
  else stopDidiExtensionPoll()
}, { immediate: true })

// Reporte de apelaciones (modo Reportes)
const apelacionesReport = ref<{ total_descontado: number; total_devuelto: number; total_perdido: number } | null>(null)
const loadingApelaciones = ref(false)
async function loadApelacionesReport() {
  if (!reportesCajero.value || !selectedLocal.value || !selectedDate.value) return
  loadingApelaciones.value = true
  apelacionesReport.value = null
  try {
    const local = encodeURIComponent(selectedLocal.value)
    const fecha = selectedDate.value
    const r = await fetch(`${API}/api/apelaciones/reporte?local=${local}&fecha_desde=${fecha}&fecha_hasta=${fecha}`)
    const data = await r.json()
    apelacionesReport.value = {
      total_descontado: data.total_descontado ?? 0,
      total_devuelto: data.total_devuelto ?? 0,
      total_perdido: data.total_perdido ?? 0
    }
  } catch {
    apelacionesReport.value = null
  } finally {
    loadingApelaciones.value = false
  }
}

onBeforeUnmount(() => {
  stopDidiExtensionPoll()
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', updateMobile)
    if (reportWsReconnectTimer != null) {
      clearTimeout(reportWsReconnectTimer)
      reportWsReconnectTimer = null
    }
  }
  if (reportWs) {
    reportWs.close()
    reportWs = null
  }
})

async function loadOrders() {
  if (!selectedLocal.value || !selectedDate.value) return
  loadingOrders.value = true
  orderError.value = ''
  try {
    const r = await fetch(
      `${API}/api/orders?local=${encodeURIComponent(selectedLocal.value)}&fecha=${selectedDate.value}`
    )
    const data = await r.json()
    orders.value = data.orders ?? []
    if (reportesCajero.value) loadApelacionesReport()
  } catch (err) {
    orderError.value = (err as Error).message
    orders.value = []
  } finally {
    loadingOrders.value = false
  }
}

async function searchByCodigo() {
  const cod = searchCodigo.value.trim()
  if (!cod) return
  loadingOrder.value = true
  selectedOrder.value = null
  fotos.value = { entrega: [], apelacion: {}, respuestas: [] }
  try {
    const r = await fetch(`${API}/api/orders/by-codigo/${encodeURIComponent(cod)}`)
    const data = await r.json()
    selectedOrder.value = data.order ?? null
    fotos.value = data.fotos ?? { entrega: [], apelacion: {}, respuestas: [] }
  } catch {
    selectedOrder.value = null
    fotos.value = { entrega: [], apelacion: {}, respuestas: [] }
  } finally {
    loadingOrder.value = false
  }
}

function selectOrder(order: Order) {
  selectedOrder.value = order
  loadFotosForOrder(order['Codigo integracion'])
}

const markingNoEntregada = ref(false)
async function markNoEntregada() {
  const order = selectedOrder.value
  const deliveryId = order?.delivery_id?.trim()
  if (!deliveryId) return
  markingNoEntregada.value = true
  try {
    await fetch(`${API}/api/orders/no-entregada`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ delivery_id: deliveryId })
    })
    if (selectedOrder.value?.['Codigo integracion']) {
      const r = await fetch(`${API}/api/orders/by-codigo/${encodeURIComponent(selectedOrder.value['Codigo integracion'])}`)
      const data = await r.json()
      selectedOrder.value = data.order ?? selectedOrder.value
      const idx = orders.value.findIndex((o: Order) => (o.delivery_id || '').trim() === deliveryId)
      if (idx !== -1 && data.order) orders.value[idx] = { ...orders.value[idx], ...data.order }
    }
  } finally {
    markingNoEntregada.value = false
  }
}

async function loadFotosForOrder(codigo: string) {
  if (!codigo) return
  try {
    const r = await fetch(`${API}/api/orders/${encodeURIComponent(codigo)}/fotos`)
    const data = await r.json()
    fotos.value = data
  } catch {
    fotos.value = { entrega: [], apelacion: {}, respuestas: [] }
  }
}

/** Tras agregar o borrar fotos: recarga la orden actual y actualiza la fila en la lista (has_entrega_photo, no_entregada) sin recargar la página. */
async function refreshSelectedOrderAndList() {
  const cod = codigoIntegracion.value
  if (!cod) return
  try {
    const r = await fetch(`${API}/api/orders/by-codigo/${encodeURIComponent(cod)}`)
    const data = await r.json()
    if (data.order) {
      selectedOrder.value = data.order
      fotos.value = data.fotos ?? { entrega: [], apelacion: {}, respuestas: [] }
      const deliveryId = (data.order.delivery_id || '').trim()
      const idx = orders.value.findIndex((o: Order) => (o.delivery_id || '').trim() === deliveryId)
      if (idx !== -1) orders.value[idx] = { ...orders.value[idx], ...data.order }
    }
  } catch {
    await loadFotosForOrder(cod)
  }
}

// Modal foto: solo ver
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

const confirm = useConfirm()
const deletingPhoto = ref(false)

function confirmDeletePhoto(url: string, e: MouseEvent) {
  e.preventDefault()
  e.stopPropagation()
  confirm.require({
    message: '¿Eliminar esta foto?',
    header: 'Confirmar',
    icon: 'pi pi-exclamation-triangle',
    rejectLabel: 'Cancelar',
    acceptLabel: 'Eliminar',
    acceptClass: 'p-button-danger',
    accept: () => deletePhoto(url)
  })
}

async function deletePhoto(url: string) {
  if (!codigoIntegracion.value) return
  deletingPhoto.value = true
  try {
    const r = await fetch(fullPhotoUrl(url), { method: 'DELETE' })
    if (r.ok) await refreshSelectedOrderAndList()
  } finally {
    deletingPhoto.value = false
  }
}

function revokePreviewUrls() {
  uploadPreviewUrls.value.forEach((url) => URL.revokeObjectURL(url))
  uploadPreviewUrls.value = []
}

function openUploadModal(group: 'entrega' | 'apelacion' | 'respuestas') {
  uploadGroup.value = group
  modalFiles.value = []
  revokePreviewUrls()
  uploadModalVisible.value = true
}

function openUploadModalForOrder(order: Order, group: 'entrega' | 'apelacion' | 'respuestas') {
  selectedOrder.value = order
  loadFotosForOrder(order['Codigo integracion'])
  uploadGroup.value = group
  modalFiles.value = []
  revokePreviewUrls()
  uploadModalVisible.value = true
}

function closeUploadModal() {
  revokePreviewUrls()
  modalFiles.value = []
  const fileEl = document.getElementById('modal-file-input') as HTMLInputElement
  if (fileEl) fileEl.value = ''
  const cameraEl = document.getElementById('modal-camera-input') as HTMLInputElement
  if (cameraEl) cameraEl.value = ''
  uploadModalVisible.value = false
}

function appendModalFiles(files: File[]) {
  if (!files.length) return
  modalFiles.value = [...modalFiles.value, ...files]
  const newUrls = files.map((f) => URL.createObjectURL(f))
  uploadPreviewUrls.value = [...uploadPreviewUrls.value, ...newUrls]
}

function removeModalFile(index: number) {
  const url = uploadPreviewUrls.value[index]
  if (url) URL.revokeObjectURL(url)
  modalFiles.value = modalFiles.value.filter((_, i) => i !== index)
  uploadPreviewUrls.value = uploadPreviewUrls.value.filter((_, i) => i !== index)
}

function onModalFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const files = input.files
  if (files?.length) appendModalFiles(Array.from(files))
  input.value = ''
}

function onModalDropzoneClick() {
  document.getElementById('modal-file-input')?.click()
}

function onModalGalleryClick() {
  document.getElementById('modal-file-input')?.click()
}

function onModalCameraClick() {
  document.getElementById('modal-camera-input')?.click()
}

function onModalDragOver(e: DragEvent) {
  e.preventDefault()
  e.stopPropagation()
  modalDropzoneActive.value = true
}

function onModalDragLeave(e: DragEvent) {
  e.preventDefault()
  e.stopPropagation()
  modalDropzoneActive.value = false
}

function onModalDrop(e: DragEvent) {
  e.preventDefault()
  e.stopPropagation()
  modalDropzoneActive.value = false
  const files = e.dataTransfer?.files
  if (files?.length) appendModalFiles(Array.from(files))
}

function clearModalFiles() {
  revokePreviewUrls()
  modalFiles.value = []
  const fileEl = document.getElementById('modal-file-input') as HTMLInputElement
  if (fileEl) fileEl.value = ''
  const cameraEl = document.getElementById('modal-camera-input') as HTMLInputElement
  if (cameraEl) cameraEl.value = ''
}

async function confirmUpload() {
  if (!codigoIntegracion.value || !modalFiles.value.length) return
  uploading.value = true
  const form = new FormData()
  for (const file of modalFiles.value) {
    form.append('files', file)
  }
  const q = new URLSearchParams({ group: uploadGroup.value })
  if (uploadGroup.value === 'apelacion') {
    const canal = selectedOrder.value?.['Canal de delivery']
    if (canal) q.set('canal', canal)
  }
  try {
    const r = await fetch(
      `${API}/api/orders/${encodeURIComponent(codigoIntegracion.value)}/fotos?${q}`,
      { method: 'POST', body: form }
    )
    if (r.ok) {
      await refreshSelectedOrderAndList()
      closeUploadModal()
    }
  } finally {
    uploading.value = false
  }
}


function fullPhotoUrl(entry: string): string {
  if (entry.startsWith('http')) return entry
  const base = API ? API.replace(/\/$/, '') : (typeof window !== 'undefined' ? window.location.origin : '')
  return base + (entry.startsWith('/') ? entry : '/' + entry)
}

// ---------------------------------------------------------------------------
// Planilla diaria por sede
// ---------------------------------------------------------------------------
interface PlanillaArchivo {
  nombre: string
  tamanio: number
  fecha_subida: number
}
interface PlanillaEstado {
  subida: boolean
  archivos: PlanillaArchivo[]
}
const planilla = ref<PlanillaEstado | null>(null)
const loadingPlanilla = ref(false)
const uploadingPlanilla = ref(false)
const planillaFiles = ref<File[]>([])
const planillaModalVisible = ref(false)

async function loadPlanillaEstado() {
  if (!currentSedeId.value || !selectedDate.value) return
  loadingPlanilla.value = true
  try {
    const r = await fetch(
      `${API}/api/planilla/${encodeURIComponent(currentSedeId.value)}/${selectedDate.value}/estado`
    )
    if (r.ok) planilla.value = await r.json()
    else planilla.value = null
  } catch {
    planilla.value = null
  } finally {
    loadingPlanilla.value = false
  }
}

function onPlanillaFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.length) {
    planillaFiles.value = [...planillaFiles.value, ...Array.from(input.files)]
  }
  input.value = ''
}

function onPlanillaDropFiles(e: DragEvent) {
  e.preventDefault()
  const files = e.dataTransfer?.files
  if (files?.length) {
    planillaFiles.value = [...planillaFiles.value, ...Array.from(files)]
  }
}

function removePlanillaFile(idx: number) {
  planillaFiles.value = planillaFiles.value.filter((_, i) => i !== idx)
}

function clickPlanillaInput() {
  document.getElementById('planilla-file-input')?.click()
}

function openPlanillaModal() {
  planillaFiles.value = []
  planillaModalVisible.value = true
}

function closePlanillaModal() {
  planillaFiles.value = []
  planillaModalVisible.value = false
}

async function confirmUploadPlanilla() {
  if (!planillaFiles.value.length || !currentSedeId.value || !selectedDate.value) return
  uploadingPlanilla.value = true
  try {
    for (const file of planillaFiles.value) {
      const form = new FormData()
      form.append('file', file)
      await fetch(
        `${API}/api/planilla/${encodeURIComponent(currentSedeId.value)}/${selectedDate.value}`,
        { method: 'POST', body: form }
      )
    }
    await loadPlanillaEstado()
    closePlanillaModal()
  } finally {
    uploadingPlanilla.value = false
  }
}

const IMAGE_EXTS = new Set(['jpg', 'jpeg', 'png', 'gif', 'webp', 'heic', 'heif', 'bmp', 'svg'])

function isPlanillaImage(nombre: string): boolean {
  const ext = nombre.split('.').pop()?.toLowerCase() ?? ''
  return IMAGE_EXTS.has(ext)
}

function planillaArchivoUrl(nombre: string): string {
  return `${API}/api/planilla/${encodeURIComponent(currentSedeId.value)}/${selectedDate.value}/archivo/${encodeURIComponent(nombre)}`
}

function openPlanillaImage(nombre: string) {
  openPhotoModal(planillaArchivoUrl(nombre))
}

function confirmDeletePlanillaArchivo(nombre: string) {
  confirm.require({
    message: `¿Eliminar el archivo "${nombre}"? Esta acción no se puede deshacer.`,
    header: 'Confirmar eliminación',
    icon: 'pi pi-exclamation-triangle',
    rejectLabel: 'Cancelar',
    acceptLabel: 'Eliminar',
    acceptClass: 'p-button-danger',
    accept: () => deletePlanillaArchivo(nombre),
  })
}

async function deletePlanillaArchivo(nombre: string) {
  if (!currentSedeId.value || !selectedDate.value) return
  await fetch(
    `${API}/api/planilla/${encodeURIComponent(currentSedeId.value)}/${selectedDate.value}?nombre=${encodeURIComponent(nombre)}`,
    { method: 'DELETE' }
  )
  await loadPlanillaEstado()
}

function formatFileSize(bytes: number | null): string {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatTimestamp(ts: number | null): string {
  if (!ts) return ''
  return new Date(ts * 1000).toLocaleString('es-CO', {
    timeZone: 'America/Bogota',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

/** Parsea un valor que puede ser número o string. Acepta "72900.00" (API) o "15.000,50" (europeo). */
function parseMonto(val: string | number | null | undefined): number {
  if (val == null) return 0
  if (typeof val === 'number' && !Number.isNaN(val)) return val
  const s = String(val).trim().replace(/\s/g, '')
  if (!s) return 0
  // Si hay coma, formato europeo (15.000,50): quitar puntos de miles, coma = decimal
  if (s.includes(',')) {
    const normalized = s.replace(/\./g, '').replace(',', '.')
    const n = parseFloat(normalized)
    return Number.isNaN(n) ? 0 : n
  }
  // Si solo punto o nada: formato API/US (72900.00), el punto es decimal
  const n = parseFloat(s)
  return Number.isNaN(n) ? 0 : n
}

/** Formato pesos (COP): $ 15.000 o $ 15.000,50 */
const formatPesos = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0
}).format

function formatMonto(val: string | number | null | undefined): string {
  return formatPesos(parseMonto(val))
}

/** Logo por canal: Rappi, Didi Food, Menú Online (en public/logos). */
const CANAL_LOGOS: Record<string, string> = {
  'Rappi': '/logos/rappi.png',
  'Didi Food': '/logos/didi.png',
  'Menú Online': '/logos/menu_online.png'
}
function canalLogoUrl(canal: string | undefined): string | null {
  if (!canal?.trim()) return null
  return CANAL_LOGOS[canal.trim()] ?? null
}
</script>

<template>
  <div class="orders-view">
    <Message v-if="reportSocketConnected && reportSocketStatus" severity="info" class="report-status-message">
      <div class="flex align-items-center gap-2 flex-wrap">
        <i class="pi pi-info-circle"></i>
        <span>{{ reportSocketStatus.message }}</span>
        <span v-if="reportSocketStatus.seconds_until_next != null" class="text-secondary">
          ({{ reportSocketStatus.seconds_until_next }} s)
        </span>
        <span v-if="reportSocketStatus.last_filas != null && reportSocketStatus.last_filas > 0" class="text-secondary">
          · Última consulta: {{ reportSocketStatus.last_filas }} registros
        </span>
      </div>
    </Message>
    <Message v-else-if="!reportSocketConnected" severity="warn" class="report-status-message">
      <i class="pi pi-exclamation-triangle"></i> Desconectado del estado de la consulta automática (deliverys). Comprueba que el backend esté en marcha.
    </Message>

    <!-- Indicador extensión Didi: visible en todo momento cuando la sede tiene Didi -->
    <div v-if="didiHasDidi" class="didi-ext-indicator">
      <span class="didi-ext-dot" :class="{ 'didi-ext-dot-active': didiExtensionActive }" aria-hidden="true"></span>
      <span class="didi-ext-label">{{ didiExtensionActive ? 'Didi ext' : 'Didi ext inactiva' }}</span>
    </div>

    <!-- Modo "Hoy" (cajeros): sede y fecha fijas por link; sin buscador superior -->
    <Card v-if="uploadOnly" class="mb-3">
      <template #content>
        <div class="flex flex-wrap align-items-center gap-3">
          <span class="font-medium">Sede:</span>
          <span>{{ selectedLocal || '—' }}</span>
          <span class="px-2">|</span>
          <span class="font-medium">Fecha:</span>
          <span>{{ selectedDate || '—' }}</span>
        </div>
      </template>
    </Card>

    <!-- Modo "Reportes" (cajero): sede fija, fecha seleccionable para consultar días anteriores -->
    <Card v-else-if="reportesCajero" class="mb-3">
      <template #title>Reportes · Pedidos por fecha</template>
      <template #content>
        <div class="flex flex-wrap align-items-center gap-2 mb-2 reportes-filters">
          <span class="font-medium">Sede (fija):</span>
          <span>{{ selectedLocal || '—' }}</span>
          <span class="px-2 text-color-secondary">·</span>
          <span class="font-medium">Fecha:</span>
          <DatePicker
            v-model="selectedDateAsDate"
            :minDate="MIN_DATE"
            dateFormat="dd/mm/yy"
            showIcon
            class="date-picker-responsive"
            @update:modelValue="loadOrders"
          />
          <Button
            label="Cargar pedidos"
            icon="pi pi-refresh"
            :loading="loadingOrders"
            class="btn-touch"
            @click="loadOrders"
          />
        </div>
        <Divider />
        <div class="flex flex-wrap gap-2 align-items-end search-row">
          <InputText
            v-model="searchCodigo"
            placeholder="Buscar por código o canal"
            class="flex-grow-1 search-input"
            @keyup.enter="searchByCodigo"
          />
          <Button label="Buscar" icon="pi pi-search" :loading="loadingOrder" class="btn-touch" @click="searchByCodigo" />
        </div>
      </template>
    </Card>

    <!-- Modo "Todas las sedes" (master): selector de sede y fecha + búsqueda -->
    <Card v-else>
      <template #title>Pedidos por sede</template>
      <template #content>
        <div class="flex flex-wrap gap-3 align-items-end mb-3 consulta-filters">
          <div class="flex flex-column gap-2 filter-field">
            <label for="sede">Sede</label>
            <Select
              id="sede"
              v-model="selectedLocal"
              :options="localeOptions"
              option-label="label"
              option-value="value"
              placeholder="Seleccionar sede"
              class="select-responsive"
              filter
              filter-placeholder="Buscar sede..."
              @change="loadOrders"
            />
          </div>
          <div class="flex flex-column gap-2 filter-field">
            <label for="fecha">Fecha</label>
            <DatePicker
              id="fecha"
              v-model="selectedDateAsDate"
              :minDate="MIN_DATE"
              dateFormat="dd/mm/yy"
              showIcon
              class="date-picker-responsive"
              @update:modelValue="loadOrders"
            />
          </div>
          <Button
            label="Cargar pedidos"
            icon="pi pi-refresh"
            :loading="loadingOrders"
            class="btn-touch"
            @click="loadOrders"
          />
        </div>
        <Divider />
        <div class="flex flex-wrap gap-3 align-items-end search-row">
          <div class="flex flex-column gap-2 flex-grow-1 search-field">
            <label for="search">Buscar por código o canal</label>
            <InputText
              id="search"
              v-model="searchCodigo"
              placeholder="Ej: 5764658785054428717 o #213874"
              class="w-full search-input"
              @keyup.enter="searchByCodigo"
            />
          </div>
          <Button
            label="Buscar"
            icon="pi pi-search"
            :loading="loadingOrder"
            class="btn-touch"
            @click="searchByCodigo"
          />
        </div>
      </template>
    </Card>

    <!-- Planilla diaria (solo en modo Hoy) -->
    <Card v-if="uploadOnly" class="mb-3 planilla-card">
      <template #title>
        <div class="flex align-items-center gap-2">
          <i class="pi pi-file-excel"></i>
          Planilla del día
        </div>
      </template>
      <template #content>
        <div v-if="loadingPlanilla" class="flex align-items-center gap-2">
          <ProgressSpinner style="width:20px;height:20px" stroke-width="4" />
          <span class="text-color-secondary">Verificando...</span>
        </div>
        <div v-else-if="planilla?.subida" class="planilla-subida">
          <div class="planilla-status-row">
            <span class="planilla-badge planilla-badge-ok">
              <i class="pi pi-check-circle"></i> Planilla subida
            </span>
            <span class="text-color-secondary text-sm">
              {{ planilla.archivos.length }} archivo{{ planilla.archivos.length !== 1 ? 's' : '' }}
            </span>
          </div>
          <ul class="planilla-archivos-list">
            <li v-for="archivo in planilla.archivos" :key="archivo.nombre" class="planilla-archivo-item">
              <!-- Miniatura si es imagen -->
              <button
                v-if="isPlanillaImage(archivo.nombre)"
                type="button"
                class="planilla-img-thumb"
                :title="`Ver ${archivo.nombre}`"
                @click="openPlanillaImage(archivo.nombre)"
              >
                <img :src="planillaArchivoUrl(archivo.nombre)" :alt="archivo.nombre" />
                <span class="planilla-img-zoom"><i class="pi pi-search-plus" /></span>
              </button>

              <span class="text-sm text-color-secondary planilla-archivo-info">
                <i :class="isPlanillaImage(archivo.nombre) ? 'pi pi-image' : 'pi pi-file'" class="mr-1" />{{ archivo.nombre }}
                <span v-if="archivo.tamanio"> · {{ formatFileSize(archivo.tamanio) }}</span>
                <span v-if="archivo.fecha_subida"> · {{ formatTimestamp(archivo.fecha_subida) }}</span>
              </span>
              <div class="flex gap-1 flex-shrink-0">
                <a
                  :href="planillaArchivoUrl(archivo.nombre)"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="p-button p-button-secondary p-button-sm btn-touch planilla-archivo-btn"
                  style="text-decoration:none;display:inline-flex;align-items:center;gap:.3rem"
                >
                  <i class="pi pi-download"></i>
                </a>
                <Button
                  icon="pi pi-trash"
                  severity="danger"
                  size="small"
                  text
                  class="btn-touch planilla-archivo-btn"
                  @click="confirmDeletePlanillaArchivo(archivo.nombre)"
                />
              </div>
            </li>
          </ul>
          <Button
            label="Agregar archivos"
            icon="pi pi-upload"
            severity="secondary"
            size="small"
            class="btn-touch mt-2"
            @click="openPlanillaModal"
          />
        </div>
        <div v-else class="planilla-pendiente">
          <div class="planilla-status-row">
            <span class="planilla-badge planilla-badge-pending">
              <i class="pi pi-clock"></i> Planilla pendiente
            </span>
            <span class="text-color-secondary text-sm">No se ha subido la planilla de hoy.</span>
          </div>
          <Button
            label="Subir planilla"
            icon="pi pi-upload"
            severity="success"
            class="btn-touch mt-2"
            @click="openPlanillaModal"
          />
        </div>
      </template>
    </Card>

    <!-- Modal subir planilla -->
    <Dialog
      v-model:visible="planillaModalVisible"
      modal
      header="Subir planilla del día"
      class="planilla-dialog"
      :closable="!uploadingPlanilla"
      @hide="closePlanillaModal"
    >
      <template #default>
        <p class="text-color-secondary text-sm mt-0 mb-3">
          Sube la planilla del día para <strong>{{ selectedLocal }}</strong> — <strong>{{ selectedDate }}</strong>.<br>
          Puedes seleccionar varios archivos. Formatos: Excel (.xlsx, .xls), CSV, ODS, PDF o imagen. Máximo 50 MB por archivo.
        </p>
        <input
          id="planilla-file-input"
          type="file"
          accept=".xlsx,.xls,.csv,.ods,.pdf,.png,.jpg,.jpeg,.webp"
          multiple
          class="file-input-hidden"
          @change="onPlanillaFileChange"
        />
        <div
          class="dropzone planilla-dropzone"
          :class="{ 'dropzone-has-files': planillaFiles.length }"
          role="button"
          tabindex="0"
          @click="clickPlanillaInput"
          @keydown.enter="clickPlanillaInput"
          @dragover.prevent
          @drop="onPlanillaDropFiles"
        >
          <template v-if="!planillaFiles.length">
            <i class="pi pi-file-excel dropzone-icon"></i>
            <span class="dropzone-text">Haz clic o arrastra los archivos aquí</span>
          </template>
          <template v-else>
            <ul class="planilla-selected-list" @click.stop>
              <li v-for="(f, idx) in planillaFiles" :key="idx" class="planilla-selected-item">
                <span class="planilla-selected-name text-sm">
                  <i class="pi pi-file mr-1"></i>{{ f.name }}
                  <span class="text-color-secondary"> · {{ formatFileSize(f.size) }}</span>
                </span>
                <Button
                  icon="pi pi-times"
                  text
                  rounded
                  size="small"
                  severity="secondary"
                  class="planilla-remove-btn"
                  @click="removePlanillaFile(idx)"
                />
              </li>
            </ul>
            <span class="text-sm text-color-secondary mt-2">
              <i class="pi pi-plus mr-1"></i>Haz clic para agregar más archivos
            </span>
          </template>
        </div>
      </template>
      <template #footer>
        <Button label="Cancelar" icon="pi pi-times" severity="secondary" class="btn-touch" :disabled="uploadingPlanilla" @click="closePlanillaModal" />
        <Button label="Subir" icon="pi pi-upload" class="btn-touch" :loading="uploadingPlanilla" :disabled="!planillaFiles.length" @click="confirmUploadPlanilla" />
      </template>
    </Dialog>

    <!-- Card apelaciones (solo en Reportes) -->
    <Card v-if="reportesCajero" class="mb-3 apelaciones-report-card">
      <template #title>Apelaciones</template>
      <template #content>
        <div v-if="loadingApelaciones" class="flex align-items-center gap-2">
          <ProgressSpinner style="width: 24px; height: 24px" stroke-width="4" />
          <span>Cargando...</span>
        </div>
        <div v-else-if="apelacionesReport" class="grid apelaciones-stats">
          <div class="col-12 md:col-4">
            <div class="apelacion-stat-label">Descontado por canal</div>
            <div class="apelacion-stat-value text-orange">{{ formatMonto(apelacionesReport.total_descontado) }}</div>
          </div>
          <div class="col-12 md:col-4">
            <div class="apelacion-stat-label">Devuelto</div>
            <div class="apelacion-stat-value text-green">{{ formatMonto(apelacionesReport.total_devuelto) }}</div>
          </div>
          <div class="col-12 md:col-4">
            <div class="apelacion-stat-label">Perdido</div>
            <div class="apelacion-stat-value text-red">{{ formatMonto(apelacionesReport.total_perdido) }}</div>
          </div>
        </div>
      </template>
    </Card>

    <Message v-if="orderError" severity="error" class="mt-3">{{ orderError }}</Message>

    <div class="grid mt-3">
      <div class="col-12 md:col-6">
        <Card>
          <template #title>Pedidos del día</template>
          <template #content>
            <div class="flex flex-wrap align-items-center gap-2 mb-2 table-filter-row">
              <SelectButton
                v-model="estadoEntregaFilter"
                :options="filterOptions"
                option-label="label"
                option-value="value"
                aria-label="Ver todas, con foto o pendientes"
              >
                <template #option="slotProps">
                  <span class="filter-option-with-badge">
                    <span class="filter-option-label">{{ slotProps.option.label }}</span>
                    <Badge :value="slotProps.option.count" :severity="slotProps.option.severity" class="filter-option-badge" />
                  </span>
                </template>
              </SelectButton>
              <span class="flex-grow-1 table-filter-input">
                <InputText
                  v-model="globalFilterText"
                  placeholder="Filtrar tabla..."
                  class="w-full"
                />
              </span>
            </div>
            <DataTable
              :value="ordersFiltered"
              :loading="loadingOrders"
              data-key="Codigo integracion"
              selection-mode="single"
              v-model:selection="selectedOrder"
              :filters="tableFilters"
              :globalFilterFields="['Codigo integracion', 'Canal de delivery']"
              @row-select="(e: { data: Order }) => selectOrder(e.data)"
              class="p-datatable-sm p-datatable-striped orders-table orders-table-scroll"
              scrollable
              scroll-height="400px"
              :paginator="true"
              :rows="10"
              :rows-per-page-options="[5, 10, 25, 50]"
              paginator-template="CurrentPageReport FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown"
              current-page-report-template="Mostrando {first} a {last} de {totalRecords} registros — Página {currentPage} de {totalPages}"
            >
              <Column field="Canal de delivery" header="Canal" frozen>
                <template #body="{ data }">
                  <div class="flex align-items-center gap-2 canal-cell">
                    <div class="canal-logo-wrap">
                      <img
                        v-if="canalLogoUrl(data['Canal de delivery'])"
                        :src="canalLogoUrl(data['Canal de delivery'])!"
                        :alt="data['Canal de delivery']"
                        class="canal-logo-table"
                      />
                      <span v-if="data.has_entrega_photo" class="order-check order-check-photo" title="Foto de entrega cargada">
                        <i class="pi pi-check"></i>
                      </span>
                      <span v-else-if="data.no_entregada" class="order-check order-check-no-entrega" title="No entregada">
                        <i class="pi pi-check"></i>
                      </span>
                    </div>
                    <span>{{ data['Canal de delivery'] || '—' }}</span>
                  </div>
                </template>
              </Column>
              <Column field="Codigo integracion" header="Código integración" sortable />
              <Column v-if="isMobile" header="" class="col-upload-foto">
                <template #body="{ data }">
                  <Button
                    v-if="!data.has_entrega_photo"
                    icon="pi pi-camera"
                    severity="success"
                    size="small"
                    style="min-height: 44px;"
                    rounded
                    :text="false"
                    class="btn-touch"
                    aria-label="Subir foto de entrega"
                    @click.stop="openUploadModalForOrder(data, 'entrega')"
                  />
                  <span v-else class="order-check order-check-photo" title="Foto cargada"><i class="pi pi-check"></i></span>
                </template>
              </Column>
              <template #empty>
                <span class="text-color-secondary">Selecciona sede y fecha y pulsa Cargar pedidos.</span>
              </template>
              <template #loading>
                <ProgressSpinner style="width: 40px; height: 40px" stroke-width="4" />
              </template>
            </DataTable>
          </template>
        </Card>
      </div>
      <div class="col-12 md:col-6">
        <Card v-if="selectedOrder">
          <template #title>Orden {{ selectedOrder['Codigo integracion'] }}</template>
          <template #content>
            <div class="grid mb-3 order-detail-grid">
              <div class="col-12 sm:col-6 md:col-4 flex align-items-center gap-2">
                <strong>Canal:</strong>
                <img
                  v-if="canalLogoUrl(selectedOrder['Canal de delivery'])"
                  :src="canalLogoUrl(selectedOrder['Canal de delivery'])!"
                  :alt="selectedOrder['Canal de delivery']"
                  class="canal-logo-detail"
                />
                <span>{{ selectedOrder['Canal de delivery'] || '—' }}</span>
              </div>
              <div class="col-12 sm:col-6 md:col-4"><strong>Código integración:</strong> {{ selectedOrder['Codigo integracion'] }}</div>
              <div class="col-12 sm:col-6 md:col-4"><strong>Cliente:</strong> {{ selectedOrder['Cliente'] }}</div>
              <div class="col-12 sm:col-6 md:col-4"><strong>Celular:</strong> {{ selectedOrder.delivery_celular || '—' }}</div>
              <div class="col-12 sm:col-6 md:col-4"><strong>Valor del pedido:</strong> {{ formatMonto(selectedOrder['Monto pagado']) }}</div>
              <div class="col-12 sm:col-6 md:col-4"><strong>Fecha / Hora:</strong> {{ selectedOrder['Fecha'] }} {{ selectedOrder['Hora'] }}</div>
            </div>
            <Message v-if="selectedOrder.no_entregada" severity="warn" class="mb-3">
              <strong>Esta orden no se envió ni entregó.</strong> Marcada para seguimiento del cajero.
            </Message>
            <div v-else-if="!selectedOrder.has_entrega_photo && selectedOrder.delivery_id" class="mb-3">
              <Button
                label="Esta orden no se entregó"
                icon="pi pi-times-circle"
                severity="secondary"
                class="btn-touch"
                :loading="markingNoEntregada"
                @click="markNoEntregada"
              />
            </div>
            <Divider />

            <TabView>
              <TabPanel value="0" header="1. Fotos al entregar">
                <div class="fotos-grid mb-2">
                  <div v-for="url in fotos.entrega" :key="url" class="foto-thumb">
                    <button type="button" class="foto-link" @click="openPhotoModal(url)">
                      <img :src="fullPhotoUrl(url)" alt="Entrega" />
                    </button>
                    <Button
                      type="button"
                      icon="pi pi-trash"
                      severity="danger"
                      class="foto-delete-btn"
                      :loading="deletingPhoto"
                      aria-label="Eliminar foto"
                      @click="confirmDeletePhoto(url, $event)"
                    />
                  </div>
                </div>
                <Button label="Subir fotos entrega" icon="pi pi-upload" severity="success" :text="false" class="btn-touch btn-upload" @click="openUploadModal('entrega')" />
              </TabPanel>
              <TabPanel v-if="!uploadOnly" value="1" header="2. Fotos apelación">
                <p v-if="selectedOrder" class="text-color-secondary text-sm mt-0 mb-2">
                  Apelación al canal de esta orden: <strong>{{ selectedOrder['Canal de delivery'] }}</strong>
                </p>
                <div class="fotos-grid mb-2">
                  <div v-for="url in apelacionUrls" :key="url" class="foto-thumb">
                    <button type="button" class="foto-link" @click="openPhotoModal(url)">
                      <img :src="fullPhotoUrl(url)" alt="Apelación" />
                    </button>
                    <Button
                      type="button"
                      icon="pi pi-trash"
                      severity="danger"
                      class="foto-delete-btn"
                      :loading="deletingPhoto"
                      aria-label="Eliminar foto"
                      @click="confirmDeletePhoto(url, $event)"
                    />
                  </div>
                </div>
                <Button label="Subir fotos apelación" icon="pi pi-upload" :text="false" class="btn-touch btn-upload" @click="openUploadModal('apelacion')" />
              </TabPanel>
              <TabPanel v-if="!uploadOnly" value="2" header="3. Respuestas del canal">
                <div class="fotos-grid mb-2">
                  <div v-for="url in fotos.respuestas" :key="url" class="foto-thumb">
                    <button type="button" class="foto-link" @click="openPhotoModal(url)">
                      <img :src="fullPhotoUrl(url)" alt="Respuesta" />
                    </button>
                    <Button
                      type="button"
                      icon="pi pi-trash"
                      severity="danger"
                      class="foto-delete-btn"
                      :loading="deletingPhoto"
                      aria-label="Eliminar foto"
                      @click="confirmDeletePhoto(url, $event)"
                    />
                  </div>
                </div>
                <Button label="Subir respuestas" icon="pi pi-upload" :text="false" class="btn-touch btn-upload" @click="openUploadModal('respuestas')" />
              </TabPanel>
            </TabView>
          </template>
        </Card>
        <Card v-else>
          <template #content>
            <p class="text-color-secondary text-center p-4 m-0">
              Selecciona un pedido de la lista o busca por código de integración.
            </p>
          </template>
        </Card>
      </div>
    </div>

    <PhotoLightbox
      :src="photoModalUrl ? fullPhotoUrl(photoModalUrl) : null"
      :visible="photoModalVisible"
      @close="closePhotoModal"
    />

    <Dialog
      v-model:visible="uploadModalVisible"
      modal
      :header="`Subir fotos · ${uploadGroupLabels[uploadGroup]}`"
      class="upload-dialog"
      content-class="upload-modal-content"
      :closable="!uploading"
      @hide="closeUploadModal"
    >
      <template #default>
        <input
          id="modal-file-input"
          type="file"
          multiple
          accept="image/*,image/heic,image/heif,.heic,.heif"
          class="file-input-hidden"
          @change="onModalFileChange"
        />
        <input
          id="modal-camera-input"
          type="file"
          multiple
          accept="image/*,image/heic,image/heif,.heic,.heif"
          capture="environment"
          class="file-input-hidden"
          @change="onModalFileChange"
        />
        <div v-if="isMobile" class="upload-mobile-actions">
          <Button label="Fototeca" icon="pi pi-images" :text="false" class="btn-touch btn-upload-action" @click="onModalGalleryClick" />
          <Button label="Tomar foto" icon="pi pi-camera" severity="success" :text="false" class="btn-touch btn-upload-action" @click="onModalCameraClick" />
        </div>
        <div
          v-else
          class="dropzone"
          :class="{ 'dropzone-active': modalDropzoneActive, 'dropzone-has-files': modalFiles.length }"
          role="button"
          tabindex="0"
          @click="onModalDropzoneClick"
          @dragover="onModalDragOver"
          @dragleave="onModalDragLeave"
          @drop="onModalDrop"
          @keydown.enter="onModalDropzoneClick"
        >
          <i class="pi pi-cloud-upload dropzone-icon"></i>
          <span class="dropzone-text">{{ modalFiles.length ? `${modalFiles.length} archivo(s). Clic o arrastra para agregar más` : 'Arrastra imágenes aquí o haz clic para elegir' }}</span>
        </div>
        <div v-if="isMobile && modalFiles.length" class="mt-2">
          <span class="text-color-secondary text-sm">Para agregar más:</span>
          <div class="flex gap-2 mt-1">
            <Button label="Fototeca" icon="pi pi-images" severity="secondary" size="small" class="btn-touch" @click="onModalGalleryClick" />
            <Button label="Cámara" icon="pi pi-camera" severity="secondary" size="small" class="btn-touch" @click="onModalCameraClick" />
          </div>
        </div>
        <div v-if="modalFiles.length" class="flex flex-wrap gap-2 align-items-center mt-2 mb-2">
          <Button label="Limpiar todo" icon="pi pi-times" severity="secondary" size="small" @click="clearModalFiles" />
        </div>
        <p v-if="uploadPreviewUrls.length" class="text-color-secondary text-sm mt-2 mb-2">Previsualización (clic en × para quitar):</p>
        <div v-if="uploadPreviewUrls.length" class="upload-preview-grid">
          <div v-for="(url, i) in uploadPreviewUrls" :key="url" class="upload-preview-item">
            <img :src="url" :alt="`Vista previa ${i + 1}`" />
            <Button
              type="button"
              icon="pi pi-times"
              severity="danger"
              class="upload-preview-remove"
              aria-label="Quitar"
              @click.stop="removeModalFile(i)"
            />
          </div>
        </div>
      </template>
      <template #footer>
        <Button label="Cancelar" icon="pi pi-times" severity="secondary" class="btn-touch" :disabled="uploading" @click="closeUploadModal" />
        <Button label="Subir" icon="pi pi-upload" class="btn-touch" :loading="uploading" :disabled="!modalFiles.length" @click="confirmUpload" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.orders-view {
  max-width: 1400px;
  margin: 0 auto;
  padding: 1rem;
}
.report-status-message {
  margin-bottom: 1rem;
}

.didi-ext-indicator {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.75rem;
  margin-bottom: 1rem;
  border-radius: 9999px;
  background: var(--p-content-surface-100, #f4f4f5);
  border: 1px solid var(--p-content-border-color, #e5e7eb);
  font-size: 0.875rem;
  font-weight: 500;
}
.didi-ext-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--p-color-secondary, #6b7280);
  flex-shrink: 0;
}
.didi-ext-dot-active {
  background: var(--p-green-500, #22c55e);
  animation: didi-ext-blink 1.2s ease-in-out infinite;
}
@keyframes didi-ext-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.didi-ext-label {
  color: var(--p-text-color);
}

/* Modo oscuro: indicador Didi ext / Didi ext inactiva */
:global(.app-dark) .didi-ext-indicator {
  background: var(--p-content-surface-200, rgba(255, 255, 255, 0.06));
  border-color: var(--p-content-border-color, rgba(255, 255, 255, 0.12));
}
:global(.app-dark) .didi-ext-dot {
  background: var(--p-color-secondary-contrast, #9ca3af);
}
:global(.app-dark) .didi-ext-dot-active {
  background: var(--p-green-400, #4ade80);
}
:global(.app-dark) .didi-ext-label {
  color: var(--p-text-color);
}

.apelaciones-stats {
  gap: 1rem;
}
.apelacion-stat-label {
  font-size: 0.9rem;
  color: var(--p-text-muted-color);
  margin-bottom: 0.25rem;
}
.apelacion-stat-value {
  font-size: 1.25rem;
  font-weight: 600;
}
.apelacion-stat-value.text-orange {
  color: var(--p-orange-600, #ea580c);
}
.apelacion-stat-value.text-green {
  color: var(--p-green-600, #16a34a);
}
.apelacion-stat-value.text-red {
  color: var(--p-red-600, #dc2626);
}
.text-secondary {
  opacity: 0.9;
  font-size: 0.9rem;
}
.col-upload-foto {
  width: 1%;
  white-space: nowrap;
}
.col-upload-foto :deep(.p-button) {
  min-width: 2.5rem;
  min-height: 2.5rem;
}
.canal-logo-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
}
.canal-logo-table {
  height: 24px;
  width: auto;
  object-fit: contain;
  vertical-align: middle;
}
.order-check {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.65rem;
  color: white;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}
.order-check-photo {
  background: var(--p-green-500, #22c55e);
}
.order-check-no-entrega {
  background: var(--p-orange-500, #f97316);
}
.canal-logo-detail {
  height: 28px;
  width: auto;
  object-fit: contain;
  vertical-align: middle;
}
.fotos-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 0.5rem;
}
.foto-thumb {
  position: relative;
  aspect-ratio: 1;
  border-radius: 8px;
  overflow: hidden;
}
.foto-thumb .foto-delete-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 2rem;
  height: 2rem;
  min-width: 2rem;
  padding: 0;
  opacity: 0;
  transition: opacity 0.15s;
  z-index: 1;
}
.foto-thumb:hover .foto-delete-btn {
  opacity: 1;
}
.foto-thumb .foto-delete-btn {
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}
.foto-link {
  display: block;
  width: 100%;
  height: 100%;
  position: absolute;
  inset: 0;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--p-border-color);
  padding: 0;
  margin: 0;
  background: transparent;
  cursor: pointer;
  font: inherit;
}
.foto-thumb:hover .foto-link {
  border-color: var(--p-primary-color);
  box-shadow: 0 0 0 2px var(--p-primary-color);
}
.foto-link img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.upload-dialog :deep(.p-dialog) {
  max-width: min(420px, 95vw);
  width: 100%;
}
.upload-modal-content {
  padding: 0 0 0.5rem 0;
}
.upload-preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 0.5rem;
  max-height: 50vh;
  overflow-y: auto;
}
.upload-preview-item {
  position: relative;
  aspect-ratio: 1;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--p-content-border-color);
  background: var(--p-content-background);
}
.upload-preview-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.upload-preview-remove {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 1.75rem;
  height: 1.75rem;
  min-width: 1.75rem;
  min-height: 1.75rem;
  padding: 0;
  z-index: 1;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}
.file-input-hidden {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  overflow: hidden;
  pointer-events: none;
}
.upload-mobile-actions {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.upload-mobile-actions .btn-upload-action {
  width: 100%;
  justify-content: center;
}
.dropzone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 1.5rem;
  border: 2px dashed var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  background: var(--p-content-background);
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}
.dropzone:hover,
.dropzone-active {
  border-color: var(--p-primary-color);
  background: var(--p-highlight-background);
}
.dropzone-has-files {
  border-style: solid;
  border-color: var(--p-primary-color);
  background: var(--p-highlight-background);
}
.dropzone-icon {
  font-size: 2rem;
  color: var(--p-text-muted-color);
}
.dropzone:hover .dropzone-icon,
.dropzone-active .dropzone-icon,
.dropzone-has-files .dropzone-icon {
  color: var(--p-primary-color);
}
.dropzone-text {
  font-size: 0.9rem;
  color: var(--p-text-muted-color);
}
.dropzone:hover .dropzone-text,
.dropzone-active .dropzone-text,
.dropzone-has-files .dropzone-text {
  color: var(--p-text-color);
}
.file-chip {
  max-width: 12rem;
}
.file-chip :deep(.p-chip-text) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
:deep(.p-datatable .p-datatable-tbody > tr) {
  cursor: pointer;
}

/* --- Responsive / móvil --- */
.orders-view {
  padding-bottom: env(safe-area-inset-bottom);
}
.btn-touch {
  min-width: 44px;
}
.search-row {
  width: 100%;
}
.search-input {
  min-width: 0;
}
.filter-option-with-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}
.filter-option-badge {
  min-width: 1.5rem;
}
.table-filter-input {
  max-width: 100%;
}
.orders-table-scroll {
  --dt-scroll-height: 400px;
}
.foto-thumb .foto-delete-btn {
  min-width: 44px;

  padding: 0;
}
.dropzone {
  min-height: 120px;
  -webkit-user-select: none;
  user-select: none;
}
.upload-preview-remove {
  min-width: 44px;

}

@media (max-width: 767px) {
  .orders-view {
    padding: 0.75rem;
  }
  .search-row {
    flex-direction: column;
    align-items: stretch;
  }
  .search-row .search-input,
  .search-row .btn-touch {
    width: 100%;
  }
  .consulta-filters {
    flex-direction: column;
    align-items: stretch;
  }
  .consulta-filters .filter-field,
  .consulta-filters .select-responsive,
  .consulta-filters .date-picker-responsive {
    width: 100%;
    max-width: 100%;
  }
  .consulta-filters .btn-touch {
    width: 100%;
  }
  .reportes-filters {
    flex-direction: column;
    align-items: stretch;
  }
  .reportes-filters .date-picker-responsive {
    width: 100%;
    max-width: 100%;
  }
  .reportes-filters .btn-touch {
    width: 100%;
  }
  .table-filter-input {
    max-width: 100%;
  }
  .orders-table-scroll {
    --dt-scroll-height: min(320px, 45vh);
  }
  .order-detail-grid .col-12 {
    margin-bottom: 0.25rem;
  }
  .fotos-grid {
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 0.75rem;
  }
  .foto-thumb .foto-delete-btn {
    opacity: 1;
    top: 6px;
    right: 6px;
  }
  .btn-upload {
    width: 100%;
    justify-content: center;
    min-height: 48px;
  }
  .orders-table-scroll :deep(.p-datatable-tbody > tr > td) {
    padding: 0.6rem 0.5rem;
  }
  .orders-table-scroll :deep(.p-datatable-tbody > tr) {
    min-height: 48px;
  }
  :deep(.p-tabview-nav) {
    flex-wrap: wrap;
    gap: 0.25rem;
  }
  :deep(.p-tabview-nav-link) {
  
    padding: 0.6rem 1rem;
  }
  .dropzone {
    min-height: 160px;
    padding: 2rem 1rem;
  }
  .dropzone-icon {
    font-size: 2.5rem;
  }
  .dropzone-text {
    font-size: 1rem;
    text-align: center;
  }
  .upload-preview-grid {
    grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
    max-height: 40vh;
  }
}

/* Modales fullscreen en móvil */
@media (max-width: 767px) {
  .upload-mobile-actions .btn-upload-action {
    min-height: 48px;
    font-size: 1rem;
  }
  .upload-dialog :deep(.p-dialog) {
    width: 100vw !important;
    max-width: 100vw !important;
    height: 100%;
    max-height: 100dvh;
    margin: 0;
    border-radius: 0;
  }
  .upload-dialog :deep(.p-dialog-content) {
    flex: 1;
    overflow: auto;
    padding-bottom: env(safe-area-inset-bottom);
  }
  .upload-dialog :deep(.p-dialog-footer) {
    padding-bottom: max(1rem, env(safe-area-inset-bottom));
    gap: 0.75rem;
  }
  .upload-dialog :deep(.p-dialog-footer .p-button) {
    flex: 1;
    min-height: 48px;
  }
}

@media (min-width: 768px) {
  .date-picker-responsive {
    width: 12rem;
  }
  .select-responsive {
    width: 18rem;
  }
  .table-filter-input {
    max-width: 20rem;
  }
}

/* Planilla */
.orders-view {
  --planilla-ok-bg: #dcfce7;
  --planilla-ok-fg: #15803d;
  --planilla-pending-bg: #ffedd5;
  --planilla-pending-fg: #c2410c;
}
.app-dark .orders-view {
  --planilla-ok-bg: rgba(34, 197, 94, 0.15);
  --planilla-ok-fg: #4ade80;
  --planilla-pending-bg: rgba(249, 115, 22, 0.15);
  --planilla-pending-fg: #fb923c;
}
.planilla-status-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 1rem;
}
.planilla-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.3rem 0.75rem;
  border-radius: 9999px;
  font-weight: 600;
  font-size: 0.875rem;
}
.planilla-badge-ok {
  background: var(--planilla-ok-bg);
  color: var(--planilla-ok-fg);
}
.planilla-badge-pending {
  background: var(--planilla-pending-bg);
  color: var(--planilla-pending-fg);
}
.planilla-dropzone {
  min-height: 100px;
}
.planilla-archivos-list {
  list-style: none;
  padding: 0 0.25rem 0 0;
  margin: 0.5rem 0 0;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  max-height: 260px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--p-content-border-color) transparent;
}
.planilla-archivo-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.planilla-archivo-info {
  flex: 1;
  min-width: 0;
  word-break: break-word;
}
.planilla-archivo-btn {
  padding: 0.25rem 0.5rem !important;
  min-width: 0 !important;
}
.planilla-img-thumb {
  position: relative;
  flex-shrink: 0;
  width: 52px;
  height: 52px;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--p-content-border-color);
  cursor: pointer;
  background: var(--p-content-surface-100);
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.planilla-img-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.planilla-img-zoom {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 1.1rem;
  opacity: 0;
  transition: background 0.15s, opacity 0.15s;
}
.planilla-img-thumb:hover .planilla-img-zoom {
  background: rgba(0, 0, 0, 0.45);
  opacity: 1;
}
.planilla-selected-list {
  list-style: none;
  padding: 0;
  margin: 0;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.planilla-selected-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
  background: var(--p-content-hover-background, rgba(0,0,0,0.03));
}
.planilla-selected-name {
  flex: 1;
  min-width: 0;
  word-break: break-word;
}
.planilla-remove-btn {
  flex-shrink: 0;
  width: 1.5rem !important;
  height: 1.5rem !important;
  padding: 0 !important;
}
.planilla-dialog :deep(.p-dialog) {
  max-width: min(440px, 95vw);
  width: 100%;
}
@media (max-width: 767px) {
  .planilla-dialog :deep(.p-dialog) {
    width: 100vw !important;
    max-width: 100vw !important;
    margin: 0;
    border-radius: 0;
  }
}
</style>
