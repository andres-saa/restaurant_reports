import { createRouter, createWebHistory } from 'vue-router'
import OrdersView from '@/views/OrdersView.vue'
import CredentialsView from '@/views/CredentialsView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: { name: 'consulta' } },
    {
      path: '/pedidos',
      name: 'consulta',
      component: OrdersView,
      meta: { uploadOnly: false, reportesCajero: false },
    },
    {
      path: '/pedidos/hoy',
      name: 'hoy',
      component: OrdersView,
      meta: { uploadOnly: true, reportesCajero: false },
    },
    {
      path: '/pedidos/reportes',
      name: 'reportes',
      component: OrdersView,
      meta: { uploadOnly: false, reportesCajero: true },
    },
    { path: '/pedidos/subir', redirect: (to) => ({ name: 'hoy', query: to.query }) },
    {
      path: '/credenciales',
      name: 'credenciales',
      component: CredentialsView,
    },
  ],
})

export default router
