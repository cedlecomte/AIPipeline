import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'
import type { PipelineDef, PipelineRun } from '../types'

export const usePipelinesStore = defineStore('pipelines', () => {
  const pipelines = ref<PipelineDef[]>([])
  const current = ref<PipelineDef | null>(null)
  const runs = ref<PipelineRun[]>([])
  const loading = ref(false)

  async function fetchAll() {
    loading.value = true
    try { pipelines.value = await api.get('/api/pipelines/definitions') }
    finally { loading.value = false }
  }

  async function fetchOne(id: string) {
    current.value = await api.get(`/api/pipelines/definitions/${id}`)
  }

  async function create(data: Partial<PipelineDef>) {
    const created = await api.post<PipelineDef>('/api/pipelines/definitions', data)
    pipelines.value.push(created)
    return created
  }

  async function update(id: string, data: Partial<PipelineDef>) {
    const updated = await api.put<PipelineDef>(`/api/pipelines/definitions/${id}`, data)
    const idx = pipelines.value.findIndex(p => p.pipeline_id === id)
    if (idx >= 0) pipelines.value[idx] = updated
    if (current.value?.pipeline_id === id) current.value = updated
    return updated
  }

  async function remove(id: string) {
    await api.del(`/api/pipelines/definitions/${id}`)
    pipelines.value = pipelines.value.filter(p => p.pipeline_id !== id)
    if (current.value?.pipeline_id === id) current.value = null
  }

  async function activate(id: string) {
    await api.post(`/api/pipelines/definitions/${id}/activate`)
    await fetchAll()
  }

  async function execute(id: string, inputData: Record<string, any> = {}) {
    return api.post<{ correlation_id: string }>(`/api/pipelines/execute/${id}`, { input_data: inputData })
  }

  async function fetchRuns() {
    runs.value = await api.get('/api/pipelines/runs')
  }

  return { pipelines, current, runs, loading, fetchAll, fetchOne, create, update, remove, activate, execute, fetchRuns }
})
