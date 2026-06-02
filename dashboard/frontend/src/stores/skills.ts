import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'
import type { Skill } from '../types'

export const useSkillsStore = defineStore('skills', () => {
  const skills = ref<Skill[]>([])
  const current = ref<Skill | null>(null)
  const loading = ref(false)

  async function fetchAll() {
    loading.value = true
    try { skills.value = await api.get('/api/skills') }
    finally { loading.value = false }
  }

  async function fetchOne(id: string) {
    current.value = await api.get(`/api/skills/${id}`)
  }

  async function create(data: Partial<Skill>) {
    const created = await api.post<Skill>('/api/skills', data)
    skills.value.push(created)
    return created
  }

  async function update(id: string, data: Partial<Skill>) {
    const updated = await api.put<Skill>(`/api/skills/${id}`, data)
    const idx = skills.value.findIndex(s => s.skill_id === id)
    if (idx >= 0) skills.value[idx] = updated
    if (current.value?.skill_id === id) current.value = updated
    return updated
  }

  async function remove(id: string) {
    await api.del(`/api/skills/${id}`)
    skills.value = skills.value.filter(s => s.skill_id !== id)
    if (current.value?.skill_id === id) current.value = null
  }

  return { skills, current, loading, fetchAll, fetchOne, create, update, remove }
})
