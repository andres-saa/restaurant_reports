<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SelectButton from 'primevue/selectbutton'
import Button from 'primevue/button'
import Menu from 'primevue/menu'
import ConfirmDialog from 'primevue/confirmdialog'
import { useRoleStore } from '@/stores/role'

const route = useRoute()
const router = useRouter()
const roleStore = useRoleStore()

type QueryKey = 'default' | 'hoy' | 'consulta' | 'role'
interface NavItem {
  name: string
  label: string
  icon: string
  queryKey: QueryKey
  /** Logo opcional (ruta a imagen) para mostrar en lugar del icono PrimeIcons. */
  logoUrl?: string
}

const NAV_ITEMS_USER: NavItem[] = [
  { name: 'hoy', label: 'Hoy', icon: 'pi-calendar', queryKey: 'hoy' },
  { name: 'apelar', label: 'Apelar', icon: 'pi-send', queryKey: 'default' },
  { name: 'mis-apelaciones', label: 'Estado de mis apelaciones', icon: 'pi-list-check', queryKey: 'default' },
  { name: 'mis-descuentos', label: 'Mis descuentos', icon: 'pi-tag', queryKey: 'default' },
  { name: 'extensiones', label: 'Extensiones', icon: 'pi-plug', queryKey: 'default' },
  { name: 'reportes', label: 'Reportes', icon: 'pi-chart-bar', queryKey: 'default' },
]

const NAV_ITEMS_ADMIN: NavItem[] = [
  { name: 'consulta', label: 'Todas las sedes', icon: 'pi-th-large', queryKey: 'consulta' },
  { name: 'marcar-apelacion', label: 'Marcar para apelación', icon: 'pi-flag', queryKey: 'default' },
  { name: 'estado-apelaciones', label: 'Estado apelaciones', icon: 'pi-list', queryKey: 'default' },
  { name: 'reembolsos', label: 'Reembolsos', icon: 'pi-wallet', queryKey: 'default' },
  { name: 'descuentos', label: 'Descuentos', icon: 'pi-tag', queryKey: 'default' },
  { name: 'reporte-maestro', label: 'Master', icon: 'pi-chart-line', queryKey: 'default' },
  { name: 'informes', label: 'Reportes', icon: 'pi-file', queryKey: 'default' },
  { name: 'planillas', label: 'Planillas', icon: 'pi-file-excel', queryKey: 'default' },
  { name: 'links-sedes', label: 'Links sedes', icon: 'pi-link', queryKey: 'default' },
  { name: 'extension-didi', label: 'Ext. Didi', icon: 'pi-wifi', queryKey: 'default', logoUrl: '/logos/didi.svg' },
  { name: 'credenciales', label: 'Credenciales', icon: 'pi-key', queryKey: 'role' },
]

const MAX_TOPBAR_ITEMS = 6
const moreMenuRef = ref<InstanceType<typeof Menu> | null>(null)

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

/** Query base con el rol activo (?user o ?admin) para que la URL siempre lo lleve. */
const roleQuery = computed(() => {
  const r = roleStore.role
  if (!r) return {}
  return { [r]: '' }
})

/** Query actual; en "Hoy" y "Todas las sedes" la fecha va siempre a hoy. */
const navQuery = computed(() => ({ ...route.query, ...roleQuery.value }))
const navQueryHoy = computed(() => ({ ...route.query, ...roleQuery.value, fecha: todayStr() }))
const navQueryConsulta = computed(() => ({ ...route.query, ...roleQuery.value, fecha: todayStr() }))

const isHoy = computed(() => route.name === 'hoy')
const isReportes = computed(() => route.name === 'reportes')
const isExtensiones = computed(() => route.name === 'extensiones')
const isApelar = computed(() => route.name === 'apelar')
const isMisApelaciones = computed(() => route.name === 'mis-apelaciones')
const isReembolsos = computed(() => route.name === 'reembolsos')
const isMisDescuentos = computed(() => route.name === 'mis-descuentos')
const isTodasSedes = computed(() => route.name === 'consulta')
const isMarcarApelacion = computed(() => route.name === 'marcar-apelacion')
const isDescuentos = computed(() => route.name === 'descuentos')
const isEstadoApelaciones = computed(() => route.name === 'estado-apelaciones')
const isReporteMaestro = computed(() => route.name === 'reporte-maestro')
const isInformes = computed(() => route.name === 'informes')
const isPlanillas = computed(() => route.name === 'planillas')
const isLinksSedes = computed(() => route.name === 'links-sedes')
const isExtensionDidi = computed(() => route.name === 'extension-didi')
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

const navItems = computed<NavItem[]>(() => {
  if (roleStore.isUser()) return NAV_ITEMS_USER
  if (roleStore.isAdmin()) return NAV_ITEMS_ADMIN
  return []
})

const visibleNavItems = computed(() => navItems.value.slice(0, MAX_TOPBAR_ITEMS))
const overflowNavItems = computed(() => navItems.value.slice(MAX_TOPBAR_ITEMS))

function getQueryFor(item: NavItem) {
  if (item.queryKey === 'hoy') return navQueryHoy.value
  if (item.queryKey === 'consulta') return navQueryConsulta.value
  if (item.queryKey === 'role') return roleQuery.value
  return navQuery.value
}

const overflowMenuModel = computed(() =>
  overflowNavItems.value.map((item) => ({
    label: item.label,
    icon: 'pi ' + item.icon,
    command: () => {
      router.push({ name: item.name, query: getQueryFor(item) })
      moreMenuRef.value?.hide()
    },
  }))
)

function isActiveNav(name: string) {
  return route.name === name
}

function openMoreMenu(e: Event) {
  moreMenuRef.value?.toggle(e as MouseEvent)
}
</script>

<template>
  <div class="app-layout">
    <header class="app-topbar">
      <RouterLink
        :to="roleStore.isUser() ? { name: 'hoy', query: navQueryHoy } : { name: 'consulta', query: navQueryConsulta }"
        class="app-title"
      >
        <img src="/logos/salchimonster.png" alt="Salchimonster" class="app-title-logo app-title-logo-brand" />
        Evidencias y pedidos
      </RouterLink>
      <nav v-if="roleStore.hasRole()" class="app-nav">
        <RouterLink
          v-for="item in visibleNavItems"
          :key="item.name"
          :to="{ name: item.name, query: getQueryFor(item) }"
          class="app-nav-link"
          :class="{ 'app-nav-link-active': isActiveNav(item.name) }"
        >
          <img v-if="item.logoUrl" :src="item.logoUrl" :alt="item.label" class="app-nav-logo" />
          <i v-else :class="'pi ' + item.icon"></i>
          <span>{{ item.label }}</span>
        </RouterLink>
        <Button
          v-if="overflowNavItems.length > 0"
          class="app-nav-link app-nav-more"
          icon="pi pi-plus"
          label="Más"
          text
          rounded
          aria-label="Más secciones"
          @click="openMoreMenu"
        />
        <Menu ref="moreMenuRef" :model="overflowMenuModel" :popup="true" />
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
    <div v-if="roleStore.hasRole()" class="app-sidebar-trigger-wrap">
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
      v-if="roleStore.hasRole()"
      class="app-sidebar"
      :class="{ 'app-sidebar-open': sidebarOpen }"
      aria-label="Menú de navegación"
    >
      <div class="app-sidebar-inner">
        <RouterLink
          :to="roleStore.isUser() ? { name: 'hoy', query: navQueryHoy } : { name: 'consulta', query: navQueryConsulta }"
          class="app-sidebar-title"
          @click="closeSidebar"
        >
          <img src="/logos/menu_online.png" alt="Pedidos Menu Online" class="app-sidebar-logo" />
          Evidencias y pedidos
        </RouterLink>
        <nav v-if="roleStore.hasRole()" class="app-sidebar-nav">
          <template v-if="roleStore.isUser()">
            <RouterLink
              :to="{ name: 'hoy', query: navQueryHoy }"
              class="app-sidebar-link"
              :class="{ 'app-sidebar-link-active': isHoy }"
              @click="closeSidebar"
            >
              <i class="pi pi-calendar"></i>
              <span>Hoy</span>
            </RouterLink>
            <RouterLink
              :to="{ name: 'apelar', query: navQuery }"
              class="app-sidebar-link"
              :class="{ 'app-sidebar-link-active': isApelar }"
              @click="closeSidebar"
            >
              <i class="pi pi-send"></i>
              <span>Apelar</span>
            </RouterLink>
            <RouterLink
              :to="{ name: 'mis-apelaciones', query: navQuery }"
              class="app-sidebar-link"
              :class="{ 'app-sidebar-link-active': isMisApelaciones }"
              @click="closeSidebar"
            >
              <i class="pi pi-list-check"></i>
              <span>Estado de mis apelaciones</span>
            </RouterLink>
            <RouterLink
              :to="{ name: 'mis-descuentos', query: navQuery }"
              class="app-sidebar-link"
              :class="{ 'app-sidebar-link-active': isMisDescuentos }"
              @click="closeSidebar"
            >
              <i class="pi pi-tag"></i>
              <span>Mis descuentos</span>
            </RouterLink>
            <RouterLink
              :to="{ name: 'extensiones', query: navQuery }"
              class="app-sidebar-link"
              :class="{ 'app-sidebar-link-active': isExtensiones }"
              @click="closeSidebar"
            >
              <i class="pi pi-plug"></i>
              <span>Extensiones</span>
            </RouterLink>
            <RouterLink
              :to="{ name: 'reportes', query: navQuery }"
              class="app-sidebar-link"
              :class="{ 'app-sidebar-link-active': isReportes }"
              @click="closeSidebar"
            >
              <i class="pi pi-chart-bar"></i>
              <span>Reportes</span>
            </RouterLink>
          </template>
          <template v-else-if="roleStore.isAdmin()">
            <RouterLink
              :to="{ name: 'consulta', query: navQueryConsulta }"
              class="app-sidebar-link"
              :class="{ 'app-sidebar-link-active': isTodasSedes }"
              @click="closeSidebar"
            >
              <i class="pi pi-th-large"></i>
              <span>Todas las sedes</span>
            </RouterLink>
            <RouterLink
              :to="{ name: 'marcar-apelacion', query: navQuery }"
              class="app-sidebar-link"
              :class="{ 'app-sidebar-link-active': isMarcarApelacion }"
              @click="closeSidebar"
            >
              <i class="pi pi-flag"></i>
              <span>Marcar para apelación</span>
            </RouterLink>
            <RouterLink
              :to="{ name: 'estado-apelaciones', query: navQuery }"
              class="app-sidebar-link"
              :class="{ 'app-sidebar-link-active': isEstadoApelaciones }"
              @click="closeSidebar"
            >
              <i class="pi pi-list"></i>
              <span>Estado apelaciones</span>
            </RouterLink>
            <RouterLink
              :to="{ name: 'reembolsos', query: navQuery }"
              class="app-sidebar-link"
              :class="{ 'app-sidebar-link-active': isReembolsos }"
              @click="closeSidebar"
            >
              <i class="pi pi-wallet"></i>
              <span>Reembolsos</span>
            </RouterLink>
            <RouterLink
              :to="{ name: 'descuentos', query: navQuery }"
              class="app-sidebar-link"
              :class="{ 'app-sidebar-link-active': isDescuentos }"
              @click="closeSidebar"
            >
              <i class="pi pi-tag"></i>
              <span>Descuentos</span>
            </RouterLink>
            <RouterLink
              :to="{ name: 'informes', query: navQuery }"
              class="app-sidebar-link"
              :class="{ 'app-sidebar-link-active': isInformes }"
              @click="closeSidebar"
            >
              <i class="pi pi-file"></i>
              <span>Reportes</span>
            </RouterLink>
            <RouterLink
              :to="{ name: 'reporte-maestro', query: navQuery }"
              class="app-sidebar-link"
              :class="{ 'app-sidebar-link-active': isReporteMaestro }"
              @click="closeSidebar"
            >
              <i class="pi pi-chart-line"></i>
              <span>Reporte maestro</span>
            </RouterLink>
            <RouterLink
              :to="{ name: 'planillas', query: navQuery }"
              class="app-sidebar-link"
              :class="{ 'app-sidebar-link-active': isPlanillas }"
              @click="closeSidebar"
            >
              <i class="pi pi-file-excel"></i>
              <span>Planillas</span>
            </RouterLink>
            <RouterLink
              :to="{ name: 'links-sedes', query: navQuery }"
              class="app-sidebar-link"
              :class="{ 'app-sidebar-link-active': isLinksSedes }"
              @click="closeSidebar"
            >
              <i class="pi pi-link"></i>
              <span>Links sedes</span>
            </RouterLink>
            <RouterLink
              :to="{ name: 'extension-didi', query: navQuery }"
              class="app-sidebar-link"
              :class="{ 'app-sidebar-link-active': isExtensionDidi }"
              @click="closeSidebar"
            >
              <img src="/logos/didi.svg" alt="Ext. Didi" class="app-sidebar-logo" />
              <span>Ext. Didi</span>
            </RouterLink>
            <RouterLink
              :to="{ name: 'credenciales', query: roleQuery }"
              class="app-sidebar-link"
              :class="{ 'app-sidebar-link-active': isCredenciales }"
              @click="closeSidebar"
            >
              <i class="pi pi-key"></i>
              <span>Credenciales</span>
            </RouterLink>
          </template>
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
  /* Fondos gris frío más oscuro en modo oscuro */
  --p-content-background: #0c0c0e;
  --p-content-surface-0: #0c0c0e;
  --p-content-surface-50: #18181b;
  --p-content-surface-100: #27272a;
  --p-content-surface-200: #3f3f46;
  --p-surface-0: #0c0c0e;
  --p-surface-50: #18181b;
  --p-surface-100: #27272a;
  --p-surface-200: #3f3f46;
}
.app-dark body,
.app-dark #app,
.app-dark .app-layout,
.app-dark .app-main {
  background: #0c0c0e !important;
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
.app-title-logo-brand {
  height: 2rem;
  border-radius: 6px;
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
  gap: 0.4rem;
  border-radius: 8px;
  color: var(--p-text-color);
  text-decoration: none;
  font-weight: 500;
  font-size: 0.95rem;
}
.app-nav-link .pi {
  font-size: 1rem;
}
.app-nav-logo {
  width: 1.25rem;
  height: 1.25rem;
  object-fit: contain;
  flex-shrink: 0;
}
.app-nav-more {
  min-width: 44px;
  min-height: 44px;
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
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .app-sidebar-link .pi {
    font-size: 1.05rem;
  }
  .app-sidebar-logo {
    width: 1.25rem;
    height: 1.25rem;
    object-fit: contain;
    flex-shrink: 0;
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
