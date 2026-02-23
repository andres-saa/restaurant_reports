<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import Card from 'primevue/card'
import Message from 'primevue/message'
import Tag from 'primevue/tag'

const API = import.meta.env.VITE_API_URL ?? ''

interface SedeItem {
  shopId: string
  shopName: string
  lastSeen: number
  connected: boolean
  neverInstalled?: boolean
  restaurant_id?: string
}

const sedes = ref<SedeItem[]>([])
const wsConnected = ref(false)
let ws: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
const WS_RECONNECT_MS = 3000

function getDidiSedesWsUrl(): string {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  if (API && API.trim()) {
    try {
      const u = new URL(API)
      const wsProtocol = u.protocol === 'https:' ? 'wss:' : 'ws:'
      const path = (u.pathname || '/').replace(/\/+$/, '')
      const base = path && path !== '/' ? path : ''
      return `${wsProtocol}//${u.host}${base}/didi/sedes/ws`
    } catch {
      return `${protocol}//${location.hostname}:8000/didi/sedes/ws`
    }
  }
  return `${protocol}//${location.hostname}:8000/didi/sedes/ws`
}

function connectWs() {
  if (ws?.readyState === WebSocket.OPEN) return
  const wsUrl = getDidiSedesWsUrl()
  ws = new WebSocket(wsUrl)
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (Array.isArray(data.sedes)) {
        sedes.value = data.sedes
      }
    } catch {
      sedes.value = []
    }
  }
  ws.onopen = () => { wsConnected.value = true }
  ws.onclose = () => {
    wsConnected.value = false
    ws = null
    if (typeof window !== 'undefined') {
      reconnectTimer = window.setTimeout(connectWs, WS_RECONNECT_MS)
    }
  }
  ws.onerror = () => { wsConnected.value = false }
}

function disconnectWs() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (ws) {
    ws.close()
    ws = null
  }
  wsConnected.value = false
}

function formatLastSeen(ts: number): string {
  const sec = Math.floor(Date.now() / 1000 - ts)
  if (sec < 60) return `hace ${sec} s`
  if (sec < 3600) return `hace ${Math.floor(sec / 60)} min`
  return `hace ${Math.floor(sec / 3600)} h`
}

const connectedCount = computed(() => sedes.value.filter((s) => s.connected).length)
const disconnectedCount = computed(() => sedes.value.filter((s) => !s.connected).length)

const CHROME_STORE_EXTENSION_URL = 'https://chromewebstore.google.com/detail/jbfjmccnfmpciehmmiigokdklpaohfom'

onMounted(connectWs)
onUnmounted(disconnectWs)
</script>

<template>
  <div class="didi-extension">
    <Card class="didi-extension-card">
      <template #title>
        <span class="didi-card-title">
          <img src="/logos/didi.svg" alt="" class="didi-card-logo" />
          Extensiones
        </span>
      </template>
      <template #subtitle>
        Didi Food Capture: instala la extensión en Chrome para que cada sede envíe el estado y las órdenes al servidor.
      </template>
      <template #content>
        <div class="didi-extension-download">
          <a
            :href="CHROME_STORE_EXTENSION_URL"
            target="_blank"
            rel="noopener noreferrer"
            class="didi-extension-link"
          >
            <i class="pi pi-download"></i>
            Descargar Didi Food Capture en la Chrome Web Store
          </a>
        </div>
      </template>
    </Card>

    <Card class="didi-extension-card mt-3">
      <template #title>Estado por sede</template>
      <template #subtitle>
        Sedes que envían heartbeat cada ~30 s. Si no llega en 36 s se marca como extensión desconectada.
      </template>
      <template #content>
        <div class="didi-extension-body">
          <Message v-if="!wsConnected" severity="warn" class="mb-3">
            Conectando al servidor… Si no se conecta, comprueba la URL del API y que el backend esté en marcha.
          </Message>
          <div v-else class="didi-extension-status mb-3">
            <Tag severity="success" value="WebSocket conectado" />
            <span class="ml-2 text-color-secondary">
              {{ connectedCount }} con extensión activa, {{ disconnectedCount }} desconectadas
            </span>
          </div>

          <p v-if="sedes.length === 0" class="text-color-secondary">
            Aún no ha enviado heartbeat ninguna sede. Abre la extensión Didi en cada tienda para que aparezcan aquí.
          </p>
          <ul v-else class="didi-extension-list">
            <li
              v-for="(sede, index) in sedes"
              :key="sede.shopId || index"
              class="didi-extension-item"
              :class="{ 'didi-extension-item-disconnected': !sede.connected }"
            >
              <span class="didi-extension-name">{{ sede.shopName }}</span>
              <span class="didi-extension-id text-color-secondary">{{ sede.shopId }}</span>
              <Tag
                v-if="sede.neverInstalled"
                severity="warn"
                value="Nunca instalada"
              />
              <Tag
                v-else
                :severity="sede.connected ? 'success' : 'danger'"
                :value="sede.connected ? 'Extensión conectada' : 'Desconectada'"
              />
              <span v-if="!sede.neverInstalled" class="didi-extension-time text-color-secondary">{{ formatLastSeen(sede.lastSeen) }}</span>
              <span v-else class="didi-extension-time text-color-secondary">—</span>
            </li>
          </ul>
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.didi-extension {
  max-width: 48rem;
  margin: 0 auto;
}
.didi-card-title {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}
.didi-card-logo {
  width: 1.75rem;
  height: 1.75rem;
  object-fit: contain;
}
.didi-extension-download {
  margin-bottom: 0;
}
.didi-extension-link {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--p-primary-color);
  font-weight: 500;
  text-decoration: none;
}
.didi-extension-link:hover {
  text-decoration: underline;
}
.didi-extension-body {
  min-height: 2rem;
  margin-top: 0;
  padding: 0;
}
.mt-3 { margin-top: 0.75rem; }
.didi-extension-status {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.25rem;
}
.didi-extension-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.didi-extension-item {
  display: flex;
  align-items: center;
  gap: 0.5rem 1rem;
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--p-content-border-color);
  flex-wrap: wrap;
}
.didi-extension-item:last-child {
  border-bottom: none;
}
.didi-extension-item-disconnected {
  color: var(--p-danger-color, #dc3545);
}
.didi-extension-item-disconnected .didi-extension-name {
  color: inherit;
}
.didi-extension-name {
  font-weight: 500;
  min-width: 12rem;
}
.didi-extension-id {
  font-size: 0.8rem;
  max-width: 12rem;
  overflow: hidden;
  text-overflow: ellipsis;
}
.didi-extension-time {
  font-size: 0.875rem;
  margin-left: auto;
}
.mb-3 { margin-bottom: 0.75rem; }
.ml-2 { margin-left: 0.5rem; }
</style>
