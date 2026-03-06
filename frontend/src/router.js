import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from './views/Dashboard.vue'
import Subscriptions from './views/Subscriptions.vue'
import Nodes from './views/Nodes.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Dashboard },
    { path: '/subscriptions', component: Subscriptions },
    { path: '/nodes', component: Nodes },
  ]
})
