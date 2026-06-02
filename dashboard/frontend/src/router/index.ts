import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/pipelines' },
    { path: '/pipelines', name: 'pipelines', component: () => import('../views/PipelineEditor.vue') },
    { path: '/agents', name: 'agents', component: () => import('../views/AgentBuilder.vue') },
    { path: '/skills', name: 'skills', component: () => import('../views/SkillsEditor.vue') },
    { path: '/monitor', name: 'monitor', component: () => import('../views/MonitorView.vue') },
  ],
})

export default router
