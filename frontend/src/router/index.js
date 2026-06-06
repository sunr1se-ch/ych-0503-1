import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'FiringList',
    component: () => import('../views/FiringList.vue')
  },
  {
    path: '/firing/:id',
    name: 'FiringDetail',
    component: () => import('../views/FiringDetail.vue')
  },
  {
    path: '/orders',
    name: 'Orders',
    component: () => import('../views/Orders.vue')
  },
  {
    path: '/loading',
    name: 'Loading',
    component: () => import('../views/Loading.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
