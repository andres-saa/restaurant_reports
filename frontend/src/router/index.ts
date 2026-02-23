import { createRouter, createWebHistory } from 'vue-router'
import OrdersView from '@/views/OrdersView.vue'
import MarcarApelacionView from '@/views/MarcarApelacionView.vue'
import ApelarView from '@/views/ApelarView.vue'
import MisApelacionesView from '@/views/MisApelacionesView.vue'
import ReembolsosView from '@/views/ReembolsosView.vue'
import DescuentosView from '@/views/DescuentosView.vue'
import MisDescuentosView from '@/views/MisDescuentosView.vue'
import EstadoApelacionesView from '@/views/EstadoApelacionesView.vue'
import ReporteMaestroView from '@/views/ReporteMaestroView.vue'
import InformesView from '@/views/InformesView.vue'
import CredentialsView from '@/views/CredentialsView.vue'
import LinksSedesView from '@/views/LinksSedesView.vue'
import DidiExtensionView from '@/views/DidiExtensionView.vue'
import ExtensionesView from '@/views/ExtensionesView.vue'
import PlanillasView from '@/views/PlanillasView.vue'
import NotFoundView from '@/views/NotFoundView.vue'
import { useRoleStore } from '@/stores/role'
import type { Role } from '@/stores/role'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/404', name: 'not-found', component: NotFoundView },
    { path: '/', redirect: (to) => ({ name: 'consulta', query: to.query }) },
    {
      path: '/pedidos',
      name: 'consulta',
      component: OrdersView,
      meta: { uploadOnly: false, reportesCajero: false, role: 'admin' as Role },
    },
    {
      path: '/pedidos/hoy',
      name: 'hoy',
      component: OrdersView,
      meta: { uploadOnly: true, reportesCajero: false, role: 'user' as Role },
    },
    {
      path: '/pedidos/reportes',
      name: 'reportes',
      component: OrdersView,
      meta: { uploadOnly: false, reportesCajero: true, role: 'user' as Role },
    },
    {
      path: '/pedidos/extensiones',
      name: 'extensiones',
      component: ExtensionesView,
      meta: { role: 'user' as Role },
    },
    {
      path: '/pedidos/apelar',
      name: 'apelar',
      component: ApelarView,
      meta: { role: 'user' as Role },
    },
    {
      path: '/pedidos/mis-apelaciones',
      name: 'mis-apelaciones',
      component: MisApelacionesView,
      meta: { role: 'user' as Role },
    },
    {
      path: '/pedidos/reembolsos',
      name: 'reembolsos',
      component: ReembolsosView,
      meta: { role: 'admin' as Role },
    },
    {
      path: '/pedidos/mis-descuentos',
      name: 'mis-descuentos',
      component: MisDescuentosView,
      meta: { role: 'user' as Role },
    },
    {
      path: '/pedidos/marcar-apelacion',
      name: 'marcar-apelacion',
      component: MarcarApelacionView,
      meta: { role: 'admin' as Role },
    },
    {
      path: '/pedidos/descuentos',
      name: 'descuentos',
      component: DescuentosView,
      meta: { role: 'admin' as Role },
    },
    {
      path: '/pedidos/estado-apelaciones',
      name: 'estado-apelaciones',
      component: EstadoApelacionesView,
      meta: { role: 'admin' as Role },
    },
    {
      path: '/pedidos/reporte-maestro',
      name: 'reporte-maestro',
      component: ReporteMaestroView,
      meta: { role: 'admin' as Role },
    },
    {
      path: '/pedidos/informes',
      name: 'informes',
      component: InformesView,
      meta: { role: 'admin' as Role },
    },
    { path: '/pedidos/subir', redirect: (to) => ({ name: 'hoy', query: to.query }) },
    {
      path: '/pedidos/links-sedes',
      name: 'links-sedes',
      component: LinksSedesView,
      meta: { role: 'admin' as Role },
    },
    {
      path: '/pedidos/extension-didi',
      name: 'extension-didi',
      component: DidiExtensionView,
      meta: { role: 'admin' as Role },
    },
    {
      path: '/pedidos/planillas',
      name: 'planillas',
      component: PlanillasView,
      meta: { role: 'admin' as Role },
    },
    {
      path: '/credenciales',
      name: 'credenciales',
      component: CredentialsView,
      meta: { role: 'admin' as Role },
    },
    { path: '/:pathMatch(.*)', redirect: '/404' },
  ],
})

router.beforeEach((to, _from, next) => {
  if (to.name === 'not-found') {
    next()
    return
  }

  const roleStore = useRoleStore()

  const q = to.query
  if ('user' in q) {
    roleStore.setRole('user')
  }
  if ('admin' in q) {
    roleStore.setRole('admin')
  }

  if (!roleStore.hasRole()) {
    next({ path: '/404', query: { from: to.fullPath } })
    return
  }

  const requiredRole = to.meta.role as Role | Role[] | undefined
  const role = roleStore.role
  if (requiredRole && role) {
    const allowed = Array.isArray(requiredRole) ? requiredRole.includes(role) : role === requiredRole
    if (!allowed) {
      const query = { ...to.query, [role]: '' }
      if (role === 'user') next({ name: 'hoy', query })
      else next({ name: 'consulta', query })
      return
    }
  }

  next()
})

export default router
