import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // Public
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { guest: true },
    },
    {
      path: '/q/:slug',
      name: 'public-queue',
      component: () => import('@/views/PublicQueueView.vue'),
      meta: { public: true },
    },
    // Dashboard layout
    {
      path: '/',
      component: () => import('@/views/layouts/DashboardLayout.vue'),
      meta: { requiresAuth: true },
      redirect: '/queue',
      children: [
        {
          path: 'queue',
          name: 'queue',
          component: () => import('@/views/QueueView.vue'),
        },
        {
          path: 'customers',
          name: 'customers',
          component: () => import('@/views/CustomersView.vue'),
        },
        {
          path: 'customers/:id',
          name: 'customer-detail',
          component: () => import('@/views/CustomerDetailView.vue'),
        },
        {
          path: 'services',
          name: 'services',
          component: () => import('@/views/ServicesView.vue'),
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/SettingsView.vue'),
        },
      ],
    },
    // Catch all
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

// Navigation guard
router.beforeEach(async (to) => {
  const auth = useAuthStore()

  // Public routes — always allow
  if (to.meta.public) return true

  // Guest-only routes (login page) — redirect if already authenticated
  if (to.meta.guest) {
    if (auth.isAuthenticated) return '/'
    return true
  }

  // Protected routes
  if (to.meta.requiresAuth) {
    if (!auth.isAuthenticated) return '/login'
    // Load user profile if not loaded yet
    if (!auth.user) {
      try {
        await auth.fetchMe()
      } catch {
        auth.logout()
        return '/login'
      }
    }
    return true
  }

  return true
})

export default router
