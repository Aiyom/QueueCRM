import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      component: () => import('@/views/AdminLoginView.vue'),
      meta: { guest: true },
    },
    {
      path: '/',
      component: () => import('@/views/AdminLayout.vue'),
      meta: { requiresAuth: true },
      redirect: '/tenants',
      children: [
        { path: 'tenants', component: () => import('@/views/TenantsView.vue') },
        { path: 'tenants/:id', component: () => import('@/views/TenantDetailView.vue') },
        { path: 'plans', component: () => import('@/views/PlansView.vue') },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('admin_access_token')
  if (to.meta.requiresAuth && !token) return '/login'
  if (to.meta.guest && token) return '/'
  return true
})

export default router
