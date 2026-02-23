<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps<{ src: string | null; visible: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const zoom = ref(1)
const tx = ref(0)
const ty = ref(0)
const dragging = ref(false)
let _sx = 0, _sy = 0, _stx = 0, _sty = 0

const imgStyle = computed(() => ({
  transform: `translate(${tx.value}px, ${ty.value}px) scale(${zoom.value})`,
  cursor: zoom.value > 1 ? (dragging.value ? 'grabbing' : 'grab') : 'default',
  transition: dragging.value ? 'none' : 'transform 0.15s ease',
  userSelect: 'none' as const,
}))

function reset() {
  zoom.value = 1; tx.value = 0; ty.value = 0
}

function zoomIn() { zoom.value = Math.min(6, parseFloat((zoom.value + 0.5).toFixed(2))) }
function zoomOut() {
  zoom.value = Math.max(1, parseFloat((zoom.value - 0.5).toFixed(2)))
  if (zoom.value === 1) { tx.value = 0; ty.value = 0 }
}

function onWheel(e: WheelEvent) {
  e.preventDefault()
  const delta = e.deltaY > 0 ? -0.3 : 0.3
  zoom.value = Math.max(1, Math.min(6, parseFloat((zoom.value + delta).toFixed(2))))
  if (zoom.value === 1) { tx.value = 0; ty.value = 0 }
}

function onDragStart(e: MouseEvent) {
  if (zoom.value <= 1) return
  e.preventDefault()
  dragging.value = true
  _sx = e.clientX; _sy = e.clientY; _stx = tx.value; _sty = ty.value
}

function onDragMove(e: MouseEvent) {
  if (!dragging.value) return
  tx.value = _stx + (e.clientX - _sx)
  ty.value = _sty + (e.clientY - _sy)
}

function onDragEnd() { dragging.value = false }

// Touch pinch-to-zoom
let _lastDist = 0
function getTouchDist(e: TouchEvent) {
  const [a, b] = [e.touches[0], e.touches[1]]
  return Math.hypot(b.clientX - a.clientX, b.clientY - a.clientY)
}
function onTouchStart(e: TouchEvent) {
  if (e.touches.length === 2) { e.preventDefault(); _lastDist = getTouchDist(e) }
  else if (e.touches.length === 1 && zoom.value > 1) {
    dragging.value = true
    _sx = e.touches[0].clientX; _sy = e.touches[0].clientY
    _stx = tx.value; _sty = ty.value
  }
}
function onTouchMove(e: TouchEvent) {
  if (e.touches.length === 2) {
    e.preventDefault()
    const dist = getTouchDist(e)
    if (_lastDist) {
      const delta = (dist - _lastDist) * 0.02
      zoom.value = Math.max(1, Math.min(6, parseFloat((zoom.value + delta).toFixed(2))))
      if (zoom.value === 1) { tx.value = 0; ty.value = 0 }
    }
    _lastDist = dist
  } else if (e.touches.length === 1 && dragging.value) {
    tx.value = _stx + (e.touches[0].clientX - _sx)
    ty.value = _sty + (e.touches[0].clientY - _sy)
  }
}
function onTouchEnd() { dragging.value = false; _lastDist = 0 }

function close() { emit('close') }

function onKeydown(e: KeyboardEvent) {
  if (!props.visible) return
  if (e.key === 'Escape') close()
  if (e.key === '+' || e.key === '=') zoomIn()
  if (e.key === '-') zoomOut()
  if (e.key === '0') reset()
}

watch(() => props.visible, (v) => {
  if (v) {
    reset()
    document.body.style.overflow = 'hidden'
  } else {
    document.body.style.overflow = ''
  }
})

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="lb">
      <div v-if="visible && src" class="lb-overlay" @click.self="close">
        <!-- Botón cerrar -->
        <button class="lb-close" aria-label="Cerrar" @click="close">
          <i class="pi pi-times" />
        </button>

        <!-- Imagen -->
        <div
          class="lb-stage"
          @wheel.prevent="onWheel"
          @mousedown="onDragStart"
          @mousemove="onDragMove"
          @mouseup="onDragEnd"
          @mouseleave="onDragEnd"
          @touchstart.passive="onTouchStart"
          @touchmove.prevent="onTouchMove"
          @touchend="onTouchEnd"
          @click.self="close"
        >
          <img
            :src="src"
            alt="Foto"
            class="lb-img"
            :style="imgStyle"
            draggable="false"
            @click.stop
          />
        </div>

        <!-- Controles de zoom -->
        <div class="lb-controls" @click.stop>
          <button class="lb-btn" :disabled="zoom <= 1" aria-label="Reducir zoom" @click="zoomOut">
            <i class="pi pi-search-minus" />
          </button>
          <span class="lb-zoom-pct">{{ Math.round(zoom * 100) }}%</span>
          <button class="lb-btn" :disabled="zoom >= 6" aria-label="Aumentar zoom" @click="zoomIn">
            <i class="pi pi-search-plus" />
          </button>
          <button class="lb-btn" :disabled="zoom === 1" aria-label="Restablecer" @click="reset">
            <i class="pi pi-refresh" />
          </button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.lb-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.82);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

/* Stage ocupa todo el espacio central */
.lb-stage {
  flex: 1;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 3.5rem 1rem 0;
}

.lb-img {
  max-width: 92vw;
  max-height: 80vh;
  width: auto;
  height: auto;
  object-fit: contain;
  transform-origin: center center;
  will-change: transform;
  border-radius: 6px;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.6);
}

/* Botón cerrar (esquina superior derecha) */
.lb-close {
  position: absolute;
  top: 0.85rem;
  right: 0.85rem;
  z-index: 1;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 50%;
  border: none;
  background: #e53935;
  color: #fff;
  font-size: 1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, transform 0.1s;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
}
.lb-close:hover {
  background: #c62828;
  transform: scale(1.1);
}

/* Barra de controles inferior */
.lb-controls {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.6rem 0.75rem;
  margin: 0.75rem auto 1rem;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 999px;
  backdrop-filter: blur(6px);
}

.lb-btn {
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: #fff;
  font-size: 1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}
.lb-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.18);
}
.lb-btn:disabled {
  opacity: 0.3;
  cursor: default;
}

.lb-zoom-pct {
  font-size: 0.8125rem;
  font-variant-numeric: tabular-nums;
  color: rgba(255, 255, 255, 0.75);
  min-width: 3.25rem;
  text-align: center;
  font-weight: 500;
}

/* Transición entrada/salida */
.lb-enter-active,
.lb-leave-active {
  transition: opacity 0.2s ease;
}
.lb-enter-from,
.lb-leave-to {
  opacity: 0;
}

@media (max-width: 767px) {
  .lb-img {
    max-width: 98vw;
    max-height: 75vh;
  }
  .lb-stage {
    padding-top: 3rem;
  }
}
</style>
