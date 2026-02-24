<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import { useRoleStore } from '@/stores/role'
import { useNotifications, ADMIN_NOTIF_LOCAL, type Notificacion } from '@/composables/useNotifications'

const props = defineProps<{ sede: string }>()

const router = useRouter()
const roleStore = useRoleStore()
const panelOpen = ref(false)

const { notifications, unreadCount, markRead, markAllRead, deleteNotification, onNewNotification, sedeResolved } =
  useNotifications(() => props.sede)

const SOUND_URL = (import.meta.env.VITE_API_URL
  ? `${(import.meta.env.VITE_API_URL as string).replace(/\/$/, '')}/tono.mp3`
  : '/tono.mp3')

let audioCtx: AudioContext | null = null
function playSound() {
  try {
    const audio = new Audio(SOUND_URL)
    audio.volume = 0.6
    audio.play().catch(() => {
      // Si el navegador bloquea autoplay, intentar con AudioContext
      if (!audioCtx) audioCtx = new AudioContext()
      fetch(SOUND_URL)
        .then((r) => r.arrayBuffer())
        .then((buf) => audioCtx!.decodeAudioData(buf))
        .then((decoded) => {
          const src = audioCtx!.createBufferSource()
          src.buffer = decoded
          src.connect(audioCtx!.destination)
          src.start()
        })
        .catch(() => {})
    })
  } catch {}
}

onNewNotification(() => playSound())

// Filtrar por el nombre resuelto (sedeResolved puede diferir del ?sede= numérico de la URL)
const sedeKey = computed(() => sedeResolved.value || props.sede)
const sedeNotifs = computed(() =>
  notifications.value.filter((n) => n.local === sedeKey.value).slice(0, 50)
)

const TIPO_ICONS: Record<string, string> = {
  orden_por_apelar: 'pi pi-flag',
  reembolso_canal: 'pi pi-wallet',
  descuento_programado: 'pi pi-calendar',
  descuento_ejecutado: 'pi pi-check-circle',
  apelacion_sede: 'pi pi-send',
  planilla_subida: 'pi pi-file-arrow-up',
}
const TIPO_COLORS: Record<string, string> = {
  orden_por_apelar: '#eab308',
  reembolso_canal: '#16a34a',
  descuento_programado: '#3b82f6',
  descuento_ejecutado: '#22c55e',
  apelacion_sede: '#8b5cf6',
  planilla_subida: '#0ea5e9',
}

function iconFor(tipo: string) { return TIPO_ICONS[tipo] ?? 'pi pi-bell' }
function colorFor(tipo: string) { return TIPO_COLORS[tipo] ?? '#6366f1' }

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return 'Ahora'
    if (diffMin < 60) return `Hace ${diffMin} min`
    const diffH = Math.floor(diffMin / 60)
    if (diffH < 24) return `Hace ${diffH} h`
    const diffD = Math.floor(diffH / 24)
    if (diffD < 7) return `Hace ${diffD} d`
    return d.toLocaleDateString('es-CO', { day: '2-digit', month: '2-digit' })
  } catch { return '' }
}

async function handleClick(n: Notificacion) {
  await markRead(n.id)
  panelOpen.value = false
  // Notificaciones de admin (local=ADMIN) no llevan ?sede=
  if (props.sede === ADMIN_NOTIF_LOCAL || roleStore.isAdmin()) {
    router.push({ name: n.route_name, query: { admin: '' } })
  } else {
    router.push({ name: n.route_name, query: { sede: props.sede, user: '' } })
  }
}

function togglePanel() { panelOpen.value = !panelOpen.value }
function closePanel() { panelOpen.value = false }
</script>

<template>
  <div class="notif-bell" v-if="sede">
    <!-- Campanita -->
    <button
      class="notif-trigger"
      :class="{ 'notif-trigger-active': panelOpen }"
      aria-label="Notificaciones"
      @click.stop="togglePanel"
    >
      <i class="pi pi-bell"></i>
      <span v-if="unreadCount > 0" class="notif-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
    </button>

    <!-- Overlay para cerrar al hacer clic fuera -->
    <div v-if="panelOpen" class="notif-backdrop" @click="closePanel" />

    <!-- Panel de notificaciones -->
    <div v-if="panelOpen" class="notif-panel" @click.stop>
      <!-- Header -->
      <div class="notif-header">
        <span class="notif-header-title">
          <i class="pi pi-bell mr-2"></i>Notificaciones
          <span v-if="unreadCount > 0" class="notif-header-count">{{ unreadCount }}</span>
        </span>
        <Button
          v-if="unreadCount > 0"
          label="Leer todas"
          size="small"
          text
          class="notif-read-all"
          @click="markAllRead"
        />
      </div>

      <!-- Lista -->
      <div class="notif-list">
        <div v-if="sedeNotifs.length === 0" class="notif-empty">
          <i class="pi pi-check-circle notif-empty-icon"></i>
          <p>Sin notificaciones</p>
        </div>

        <div
          v-for="n in sedeNotifs"
          :key="n.id"
          class="notif-item"
          :class="{ 'notif-item-unread': !n.leida }"
          @click="handleClick(n)"
        >
          <span class="notif-dot" :style="{ background: colorFor(n.tipo) }">
            <i :class="iconFor(n.tipo)"></i>
          </span>
          <div class="notif-body">
            <div class="notif-titulo">{{ n.titulo }}</div>
            <div class="notif-mensaje">{{ n.mensaje }}</div>
            <div class="notif-time">{{ formatTime(n.fecha) }}</div>
          </div>
          <button
            class="notif-delete"
            title="Eliminar"
            @click.stop="deleteNotification(n.id)"
          >
            <i class="pi pi-times"></i>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.notif-bell {
  position: relative;
}

/* Trigger */
.notif-trigger {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--p-text-color);
  cursor: pointer;
  font-size: 1.1rem;
  transition: background 0.15s;
}
.notif-trigger:hover,
.notif-trigger-active {
  background: var(--p-content-hover-background);
  color: var(--p-primary-color);
}

/* Badge */
.notif-badge {
  position: absolute;
  top: 2px;
  right: 2px;
  min-width: 1rem;
  height: 1rem;
  padding: 0 3px;
  border-radius: 999px;
  background: #ef4444;
  color: #fff;
  font-size: 0.6rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

/* Backdrop */
.notif-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1090;
}

/* Panel */
.notif-panel {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 1091;
  width: min(360px, 94vw);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 480px;
}

/* Header del panel */
.notif-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--p-content-border-color);
  flex-shrink: 0;
}
.notif-header-title {
  font-weight: 600;
  font-size: 0.95rem;
  display: flex;
  align-items: center;
}
.notif-header-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-left: 0.4rem;
  min-width: 1.2rem;
  height: 1.2rem;
  padding: 0 4px;
  background: #ef4444;
  color: #fff;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 700;
}
.notif-read-all {
  font-size: 0.78rem !important;
  padding: 0.2rem 0.5rem !important;
}

/* Lista */
.notif-list {
  overflow-y: auto;
  flex: 1;
}
.notif-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem 1rem;
  color: var(--p-text-muted-color, #94a3b8);
  gap: 0.5rem;
}
.notif-empty-icon { font-size: 2rem; }
.notif-empty p { margin: 0; font-size: 0.875rem; }

/* Item */
.notif-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  cursor: pointer;
  border-bottom: 1px solid var(--p-content-border-color);
  transition: background 0.12s;
  position: relative;
}
.notif-item:last-child { border-bottom: none; }
.notif-item:hover { background: var(--p-content-hover-background); }
.notif-item-unread { background: var(--p-highlight-background); }
.notif-item-unread:hover { background: var(--p-highlight-background); filter: brightness(0.97); }

/* Dot/Icon */
.notif-dot {
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 0.8rem;
  flex-shrink: 0;
  margin-top: 2px;
}

/* Body */
.notif-body { flex: 1; min-width: 0; }
.notif-titulo { font-weight: 600; font-size: 0.85rem; line-height: 1.3; }
.notif-mensaje {
  font-size: 0.78rem;
  color: var(--p-text-muted-color, #64748b);
  line-height: 1.4;
  margin-top: 2px;
  white-space: normal;
  word-break: break-word;
}
.notif-time {
  font-size: 0.7rem;
  color: var(--p-text-muted-color, #94a3b8);
  margin-top: 3px;
}

/* Delete btn */
.notif-delete {
  display: none;
  align-items: center;
  justify-content: center;
  width: 1.4rem;
  height: 1.4rem;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--p-text-muted-color);
  cursor: pointer;
  font-size: 0.65rem;
  flex-shrink: 0;
  padding: 0;
}
.notif-delete:hover { background: var(--p-content-hover-background); color: #ef4444; }
.notif-item:hover .notif-delete { display: flex; }
</style>
