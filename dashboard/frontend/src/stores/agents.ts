import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'
import type { AgentDef } from '../types'

export const useAgentsStore = defineStore('agents', () => {
  const agents = ref<AgentDef[]>([])
  const current = ref<AgentDef | null>(null)
  const loading = ref(false)

  async function fetchAll() {
    loading.value = true
    try { agents.value = await api.get('/api/agents') }
    finally { loading.value = false }
  }

  async function fetchOne(id: string) {
    current.value = await api.get(`/api/agents/${id}`)
  }

  async function create(data: Partial<AgentDef>) {
    const created = await api.post<AgentDef>('/api/agents', data)
    agents.value.push(created)
    return created
  }

  async function update(id: string, data: Partial<AgentDef>) {
    const updated = await api.put<AgentDef>(`/api/agents/${id}`, data)
    const idx = agents.value.findIndex(a => a.agent_id === id)
    if (idx >= 0) agents.value[idx] = updated
    if (current.value?.agent_id === id) current.value = updated
    return updated
  }

  async function remove(id: string) {
    await api.del(`/api/agents/${id}`)
    agents.value = agents.value.filter(a => a.agent_id !== id)
    if (current.value?.agent_id === id) current.value = null
  }

  async function seedBuiltins() {
    return api.post('/api/agents/seed-builtins')
  }

  return { agents, current, loading, fetchAll, fetchOne, create, update, remove, seedBuiltins }
})
