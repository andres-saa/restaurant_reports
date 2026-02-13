<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import SelectButton from 'primevue/selectbutton'
import Button from 'primevue/button'
import ConfirmDialog from 'primevue/confirmdialog'

const route = useRoute()

const THEME_KEY = 'app-theme'
type Theme = 'light' | 'dark'
const themeOptions: { label: string; value: Theme }[] = [
  { label: 'Claro', value: 'light' },
  { label: 'Oscuro', value: 'dark' }
]

const theme = ref<Theme>('light')
const sidebarOpen = ref(false)

/** Fecha de hoy en Colombia (YYYY-MM-DD). */
function todayStr() {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'America/Bogota' })
}

/** Query actual; en "Hoy" y "Todas las sedes" la fecha va siempre a hoy. */
const navQuery = computed(() => ({ ...route.query }))
const navQueryHoy = computed(() => ({ ...route.query, fecha: todayStr() }))
const navQueryConsulta = computed(() => ({ ...route.query, fecha: todayStr() }))

const isHoy = computed(() => route.name === 'hoy')
const isReportes = computed(() => route.name === 'reportes')
const isTodasSedes = computed(() => route.name === 'consulta')
const isCredenciales = computed(() => route.name === 'credenciales')

function applyTheme(isDark: boolean) {
  if (isDark) {
    document.documentElement.classList.add('app-dark')
  } else {
    document.documentElement.classList.remove('app-dark')
  }
}

function initTheme() {
  const stored = localStorage.getItem(THEME_KEY) as Theme | null
  if (stored === 'light' || stored === 'dark') {
    theme.value = stored
  } else if (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    theme.value = 'dark'
  } else {
    theme.value = 'light'
  }
  applyTheme(theme.value === 'dark')
}

function closeSidebar() {
  sidebarOpen.value = false
}

onMounted(initTheme)

watch(theme, (val) => {
  applyTheme(val === 'dark')
  localStorage.setItem(THEME_KEY, val)
})
watch(() => route.fullPath, closeSidebar)
</script>

<template>
  <div class="app-layout">
    <header class="app-topbar">
      <RouterLink to="/" class="app-title">
        <img src="/logos/menu_online.png" alt="Pedidos Menu Online" class="app-title-logo" />
        Evidencias y pedidos
      </RouterLink>
      <nav class="app-nav">
        <RouterLink
          :to="{ name: 'hoy', query: navQueryHoy }"
          class="app-nav-link"
          :class="{ 'app-nav-link-active': isHoy }"
        >
          Hoy
        </RouterLink>
        <RouterLink
          :to="{ name: 'reportes', query: navQuery }"
          class="app-nav-link"
          :class="{ 'app-nav-link-active': isReportes }"
        >
          Reportes
        </RouterLink>
        <RouterLink
          :to="{ name: 'consulta', query: navQueryConsulta }"
          class="app-nav-link"
          :class="{ 'app-nav-link-active': isTodasSedes }"
        >
          Todas las sedes
        </RouterLink>
        <RouterLink to="/credenciales" class="app-nav-link" :class="{ 'app-nav-link-active': isCredenciales }">
          Credenciales
        </RouterLink>
      </nav>
      <SelectButton
        v-model="theme"
        :options="themeOptions"
        option-label="label"
        option-value="value"
        aria-label="Tema claro u oscuro"
      />
    </header>

    <!-- Móvil: botón fijo en el borde izquierdo, centrado vertical (viewport) -->
    <div class="app-sidebar-trigger-wrap">
      <Button
        class="app-sidebar-trigger"
        icon="pi pi-bars" style="border-radius: 0 .5rem .5rem 0;"
        aria-label="Abrir menú"
        @click="sidebarOpen = true"
      />
    </div>

    <!-- Móvil: overlay y sidebar -->
    <div
      class="app-sidebar-backdrop"
      :class="{ 'app-sidebar-backdrop-visible': sidebarOpen }"
      aria-hidden="true"
      @click="closeSidebar"
    />
    <aside
      class="app-sidebar"
      :class="{ 'app-sidebar-open': sidebarOpen }"
      aria-label="Menú de navegación"
    >
      <div class="app-sidebar-inner">
        <RouterLink to="/" class="app-sidebar-title" @click="closeSidebar">
          <img src="/logos/menu_online.png" alt="Pedidos Menu Online" class="app-sidebar-logo" />
          Evidencias y pedidos
        </RouterLink>
        <nav class="app-sidebar-nav">
          <RouterLink
            :to="{ name: 'hoy', query: navQueryHoy }"
            class="app-sidebar-link"
            :class="{ 'app-sidebar-link-active': isHoy }"
            @click="closeSidebar"
          >
            Hoy
          </RouterLink>
          <RouterLink
            :to="{ name: 'reportes', query: navQuery }"
            class="app-sidebar-link"
            :class="{ 'app-sidebar-link-active': isReportes }"
            @click="closeSidebar"
          >
            Reportes
          </RouterLink>
          <RouterLink
            :to="{ name: 'consulta', query: navQueryConsulta }"
            class="app-sidebar-link"
            :class="{ 'app-sidebar-link-active': isTodasSedes }"
            @click="closeSidebar"
          >
            Todas las sedes
          </RouterLink>
          <RouterLink to="/credenciales" class="app-sidebar-link" :class="{ 'app-sidebar-link-active': isCredenciales }" @click="closeSidebar">
            Credenciales
          </RouterLink>
        </nav>
        <div class="app-sidebar-theme">
          <span class="app-sidebar-theme-label">Tema</span>
          <SelectButton
            v-model="theme"
            :options="themeOptions"
            option-label="label"
            option-value="value"
            aria-label="Tema claro u oscuro"
          />
        </div>

      </div>
    </aside>

    <main class="app-main">
      <RouterView />
    </main>
    <ConfirmDialog />
  </div>
</template>

<style>
/* Color principal de marca: rgb(255, 98, 0) */
:root {
  --p-primary-color: rgb(255, 98, 0);
  --p-primary-contrast-color: #ffffff;
  --p-highlight-background: rgba(255, 98, 0, 0.16);
  --p-highlight-border-color: rgb(255, 98, 0);
  --p-highlight-text-color: rgb(255, 98, 0);
}
.app-dark {
  --p-primary-color: rgb(255, 98, 0);
  --p-primary-contrast-color: #ffffff;
  --p-highlight-background: rgba(255, 98, 0, 0.24);
  --p-highlight-border-color: rgb(255, 98, 0);
  --p-highlight-text-color: rgb(255, 98, 0);
}
body {
  margin: 0;
  font-family: 'Roboto', 'Source Sans 3', -apple-system, BlinkMacSystemFont, sans-serif;
  -webkit-tap-highlight-color: transparent;
}
.app-layout {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
}
.app-topbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  padding-top: max(0.5rem, env(safe-area-inset-top));
  background: var(--p-content-background);
  border-bottom: 1px solid var(--p-content-border-color);
  flex-wrap: wrap;
}
.app-title {
  font-weight: 600;
  font-size: 1rem;
  color: var(--p-text-color);
  text-decoration: none;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}
.app-title:hover {
  color: var(--p-primary-color);
}
.app-title-logo {
  height: 1.75rem;
  width: auto;
  object-fit: contain;
  vertical-align: middle;
}
.app-nav {
  display: flex;
  align-items: center;
  gap: 0.2rem;
  flex-wrap: wrap;
  justify-content: center;
}
.app-nav-link {
  padding: 0.5rem 0.65rem;
  min-height: 44px;
  min-width: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: var(--p-text-color);
  text-decoration: none;
  font-weight: 500;
  font-size: 0.95rem;
}
.app-nav-link:hover {
  background: var(--p-content-hover-background);
  color: var(--p-primary-color);
}
.app-nav-link-active {
  background: var(--p-highlight-background);
  color: var(--p-primary-color);
}
.app-main {
  flex: 1;
  padding-top: 3.5rem;
  padding-top: calc(3.5rem + env(safe-area-inset-top));
  padding-left: env(safe-area-inset-left);
  padding-right: env(safe-area-inset-right);
}

/* Móvil: ocultar topbar, mostrar botón y sidebar */
.app-sidebar-trigger-wrap {
  display: none;
}
.app-sidebar-trigger {
  display: none;
}
.app-sidebar-backdrop,
.app-sidebar {
  display: none;
}
@media (max-width: 767px) {
  .app-topbar {
    display: none;
  }
  .app-main {
    padding-top: 0.5rem;
    padding-top: calc(0.5rem + env(safe-area-inset-top));
  }
  .app-sidebar-trigger-wrap {
    display: block;
    position: fixed;
    left: 0;
    top: 50%;
    transform: translateY(-50%);
    z-index: 1001;
  }
  .app-sidebar-trigger {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2.5rem;
    height: 3rem;
    min-width: 2.5rem;
    min-height: 3rem;
    padding: 0;
    border: none;
    border-radius: 0 1rem 1rem 0;
    box-shadow: 2px 0 8px rgba(0, 0, 0, 0.15);
    background: var(--p-primary-color);
    color: #fff;
  }
  .app-sidebar-trigger :deep(.pi) {
    color: #fff;
  }
  .app-sidebar-trigger:hover,
  .app-sidebar-trigger:focus {
    background: var(--p-primary-color);
    opacity: 0.92;
    color: #fff;
  }
  .app-sidebar-trigger:hover :deep(.pi),
  .app-sidebar-trigger:focus :deep(.pi) {
    color: #fff;
  }
  .app-sidebar-backdrop {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 1002;
    background: rgba(0, 0, 0, 0.4);
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.2s, visibility 0.2s;
  }
  .app-sidebar-backdrop-visible {
    opacity: 1;
    visibility: visible;
  }
  .app-sidebar {
    display: block;
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    z-index: 1003;
    width: min(280px, 85vw);
    max-width: 280px;
    background: var(--p-content-background);
    border-right: 1px solid var(--p-content-border-color);
    box-shadow: 4px 0 12px rgba(0, 0, 0, 0.15);
    transform: translateX(-100%);
    transition: transform 0.25s ease-out;
    padding: 1rem;
    padding-left: max(1rem, env(safe-area-inset-left));
    overflow-y: auto;
  }
  .app-sidebar-open {
    transform: translateX(0);
  }
  .app-sidebar-inner {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    position: relative;
  }
  .app-sidebar-title {
    font-weight: 600;
    font-size: 1.1rem;
    color: var(--p-text-color);
    text-decoration: none;
    padding: 0.25rem 0;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
  }
  .app-sidebar-title:hover {
    color: var(--p-primary-color);
  }
  .app-sidebar-logo {
    height: 1.75rem;
    width: auto;
    object-fit: contain;
  }
  .app-sidebar-nav {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .app-sidebar-link {
    padding: 0.65rem 0.75rem;
    border-radius: 8px;
    color: var(--p-text-color);
    text-decoration: none;
    font-weight: 500;
  }
  .app-sidebar-link:hover {
    background: var(--p-content-hover-background);
    color: var(--p-primary-color);
  }
  .app-sidebar-link-active {
    background: var(--p-highlight-background);
    color: var(--p-primary-color);
  }
  .app-sidebar-theme {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .app-sidebar-theme-label {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--p-text-muted-color);
  }
  .app-sidebar-close {
    position: absolute;
    top: -0.25rem;
    right: -0.25rem;
    align-self: flex-end;
  }
}

@media (min-width: 768px) {
  .app-topbar { padding: 0.6rem 1rem; }
  .app-title { font-size: 1.1rem; }
  .app-nav-link { padding: 0.4rem 0.75rem; min-height: 0; min-width: 0; }
}
</style>
