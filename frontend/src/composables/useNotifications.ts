import { ref, computed, onUnmounted } from 'vue'

const API = import.meta.env.VITE_API_URL ?? ''

export interface Notificacion {
  id: string
  local: string
  tipo: 'orden_por_apelar' | 'reembolso_canal' | 'descuento_programado' | 'descuento_ejecutado' | 'apelacion_sede' | 'planilla_subida'
  titulo: string
  mensaje: string
  leida: boolean
  fecha: string
  route_name: string
  data: Record<string, unknown>
}

export const ADMIN_NOTIF_LOCAL = 'ADMIN'

type NewNotifCallback = (n: Notificacion) => void

// Estado global compartido entre todas las instancias del composable
const notifications = ref<Notificacion[]>([])
const connected = ref(false)
// Nombre real del local resuelto (puede diferir del ?sede= numérico de la URL)
const sedeResolved = ref('')
let ws: WebSocket | null = null
let wsSedeActual = ''
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null
let instanceCount = 0
const newNotifCallbacks: NewNotifCallback[] = []

const POLL_INTERVAL_MS = 20_000 // polling cada 20s como respaldo

function wsUrl(s: string): string {
  if (API) {
    const base = API.replace(/^http/, 'ws').replace(/\/$/, '')
    return `${base}/ws/notificaciones?sede=${encodeURIComponent(s)}`
  }
  // Sin VITE_API_URL: usar el host actual (Vite proxy maneja /ws)
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/ws/notificaciones?sede=${encodeURIComponent(s)}`
}

function apiUrl(path: string): string {
  return API ? `${API.replace(/\/$/, '')}${path}` : path
}

function _emitNew(n: Notificacion) {
  for (const cb of newNotifCallbacks) {
    try { cb(n) } catch {}
  }
}

async function fetchAndMerge(s: string) {
  if (!s) return
  try {
    const r = await fetch(apiUrl(`/api/notificaciones?sede=${encodeURIComponent(s)}`))
    if (!r.ok) return
    const data = await r.json()
    const fresh: Notificacion[] = data.items ?? []
    // Merge: agregar nuevas y actualizar estado leida de las existentes
    const existingIds = new Set(notifications.value.map((n) => n.id))
    const brandNew = fresh.filter((n) => !existingIds.has(n.id))
    // Actualizar leida de las existentes (por si se marcó en otra pestaña)
    for (const n of notifications.value) {
      const updated = fresh.find((f) => f.id === n.id)
      if (updated) n.leida = updated.leida
    }
    if (brandNew.length > 0) {
      notifications.value.unshift(...brandNew)
      brandNew.forEach(_emitNew)
    }
  } catch {}
}

async function fetchInitial(s: string) {
  if (!s) return
  try {
    const r = await fetch(apiUrl(`/api/notificaciones?sede=${encodeURIComponent(s)}`))
    if (!r.ok) return
    const data = await r.json()
    notifications.value = data.items ?? []
    // El backend resuelve IDs numéricos al nombre real; guardarlo para filtrar correctamente
    sedeResolved.value = data.resolved_sede ?? s
  } catch {}
}

function startPolling(s: string) {
  stopPolling()
  pollTimer = setInterval(() => fetchAndMerge(s), POLL_INTERVAL_MS)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

function connect(s: string) {
  if (!s) return
  if (ws && wsSedeActual === s && ws.readyState <= 1) return

  disconnect()
  wsSedeActual = s

  try {
    ws = new WebSocket(wsUrl(s))

    ws.onopen = () => { connected.value = true }

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data)
        if (msg.type === 'initial') {
          const ids = new Set(notifications.value.map((n) => n.id))
          for (const n of (msg.items ?? [])) {
            if (!ids.has(n.id)) notifications.value.unshift(n)
          }
        } else if (msg.type === 'notificacion' && msg.data) {
          const exists = notifications.value.some((n) => n.id === msg.data.id)
          if (!exists) {
            notifications.value.unshift(msg.data)
            _emitNew(msg.data)
          }
        }
        // ping: ignorar
      } catch {}
    }

    ws.onclose = () => {
      connected.value = false
      reconnectTimer = setTimeout(() => connect(wsSedeActual), 4000)
    }

    ws.onerror = () => {
      ws?.close()
    }
  } catch {}
}

function disconnect() {
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
  if (ws) { ws.onclose = null; ws.close(); ws = null }
  connected.value = false
  stopPolling()
}

export function useNotifications(sede: () => string) {
  instanceCount++

  const unreadCount = computed(() => {
    const key = sedeResolved.value || sede()
    return notifications.value.filter((n) => !n.leida && n.local === key).length
  })

  async function markRead(id: string) {
    const n = notifications.value.find((x) => x.id === id)
    if (n) n.leida = true
    try {
      await fetch(apiUrl(`/api/notificaciones/${id}/leer`), { method: 'POST' })
    } catch {}
  }

  async function markAllRead() {
    const s = sedeResolved.value || sede()
    if (!s) return
    notifications.value.forEach((n) => { if (n.local === s) n.leida = true })
    try {
      await fetch(apiUrl(`/api/notificaciones/leer-todas?sede=${encodeURIComponent(s)}`), { method: 'POST' })
    } catch {}
  }

  async function deleteNotification(id: string) {
    notifications.value = notifications.value.filter((n) => n.id !== id)
    try {
      await fetch(apiUrl(`/api/notificaciones/${id}`), { method: 'DELETE' })
    } catch {}
  }

  function init(s: string) {
    if (!s) return
    fetchInitial(s).then(() => {
      connect(s)
      startPolling(s)
    })
  }

  function onNewNotification(cb: NewNotifCallback) {
    newNotifCallbacks.push(cb)
    onUnmounted(() => {
      const i = newNotifCallbacks.indexOf(cb)
      if (i !== -1) newNotifCallbacks.splice(i, 1)
    })
  }

  onUnmounted(() => {
    instanceCount--
    if (instanceCount <= 0) {
      instanceCount = 0
      disconnect() // también llama stopPolling()
      notifications.value = []
    }
  })

  return {
    notifications,
    unreadCount,
    connected,
    sedeResolved,
    init,
    connect,
    disconnect,
    markRead,
    markAllRead,
    deleteNotification,
    onNewNotification,
  }
}
