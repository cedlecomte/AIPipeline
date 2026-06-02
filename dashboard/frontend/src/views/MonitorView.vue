<template>
  <div class="flex h-full">
    <!-- Runs list -->
    <div class="w-80 border-r border-surface-lighter flex flex-col">
      <div class="p-4 border-b border-surface-lighter">
        <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wide">Pipeline Runs</h2>
      </div>
      <div class="flex-1 overflow-auto p-2 space-y-2">
        <div
          v-for="run in runs"
          :key="run.correlation_id"
          @click="selectRun(run.correlation_id)"
          class="p-3 rounded-lg cursor-pointer transition-colors"
          :class="selectedRunId === run.correlation_id ? 'bg-primary/20 border border-primary/40' : 'bg-surface-light hover:bg-surface-lighter border border-transparent'"
        >
          <div class="flex items-center justify-between mb-1">
            <span class="text-xs font-mono text-gray-400">{{ run.correlation_id.slice(0, 8) }}</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-semibold uppercase"
              :class="{
                'bg-yellow-500/20 text-yellow-400': run.status === 'pending',
                'bg-blue-500/20 text-blue-400': run.status === 'in_progress',
                'bg-green-500/20 text-green-400': run.status === 'completed',
                'bg-red-500/20 text-red-400': run.status === 'failed',
              }"
            >
              {{ run.status }}
            </span>
          </div>
          <div class="text-xs text-gray-500">{{ run.current_stage }}</div>
          <div class="flex gap-1 mt-1.5 flex-wrap">
            <span v-for="stage in run.stages_completed" :key="stage" class="px-1.5 py-0.5 bg-green-600/10 text-green-400 text-[10px] rounded">
              {{ stage }}
            </span>
          </div>
          <div class="text-[10px] text-gray-600 mt-1">{{ new Date(run.started_at).toLocaleString() }}</div>
        </div>
        <div v-if="!runs.length" class="text-sm text-gray-500 p-4 text-center">
          No pipeline runs yet
        </div>
      </div>
    </div>

    <!-- Log detail -->
    <div class="flex-1 flex flex-col">
      <template v-if="selectedRunId">
        <div class="p-4 border-b border-surface-lighter flex items-center justify-between">
          <div>
            <h2 class="text-sm font-semibold text-gray-200">Run {{ selectedRunId.slice(0, 8) }}</h2>
            <span class="text-xs text-gray-500">{{ selectedRun?.status }} &mdash; {{ selectedRun?.stages_completed?.length || 0 }} stages</span>
          </div>
          <button @click="fetchLogs" class="px-3 py-1 bg-surface-lighter text-gray-400 text-xs rounded hover:text-gray-200">
            Refresh
          </button>
        </div>
        <div class="flex-1 overflow-auto p-4 font-mono text-xs space-y-1">
          <div v-for="(log, i) in logs" :key="i"
            class="flex gap-3 py-1.5 px-3 rounded"
            :class="{
              'bg-red-500/5': log.level === 'error',
              'bg-yellow-500/5': log.level === 'warning',
            }"
          >
            <span class="text-gray-600 whitespace-nowrap w-20 shrink-0">{{ formatTime(log.timestamp) }}</span>
            <span class="w-14 shrink-0 uppercase font-semibold"
              :class="{
                'text-blue-400': log.level === 'info',
                'text-yellow-400': log.level === 'warning',
                'text-red-400': log.level === 'error',
              }"
            >{{ log.level }}</span>
            <span class="text-primary w-28 shrink-0 truncate" :title="log.stage">{{ log.stage }}</span>
            <span class="text-gray-300 flex-1">{{ log.message }}</span>
            <button v-if="log.data" @click="toggleData(i)" class="text-gray-500 hover:text-gray-300 shrink-0">
              {{ expandedLogs.has(i) ? '[-]' : '[+]' }}
            </button>
          </div>
          <!-- Expanded data -->
          <template v-for="(log, i) in logs" :key="'d'+i">
            <div v-if="expandedLogs.has(i) && log.data" class="ml-[11.5rem] bg-surface rounded p-3 text-gray-400 whitespace-pre-wrap break-all">{{ JSON.stringify(log.data, null, 2) }}</div>
          </template>

          <div v-if="!logs.length && !logsLoading" class="text-gray-500 p-4 text-center text-sm">
            No logs for this run
          </div>
          <div v-if="logsLoading" class="text-gray-500 p-4 text-center text-sm">
            Loading...
          </div>
        </div>
      </template>
      <div v-else class="flex-1 flex items-center justify-center text-gray-500 text-sm">
        Select a pipeline run to view its logs
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import type { PipelineRun } from '../types'

interface LogEntry {
  timestamp: string
  level: string
  stage: string
  message: string
  data?: any
}

const runs = ref<PipelineRun[]>([])
const selectedRunId = ref<string | null>(null)
const logs = ref<LogEntry[]>([])
const logsLoading = ref(false)
const expandedLogs = ref<Set<number>>(new Set())

let pollInterval: ReturnType<typeof setInterval> | null = null

const selectedRun = computed(() => runs.value.find(r => r.correlation_id === selectedRunId.value))

onMounted(() => {
  fetchRuns()
  pollInterval = setInterval(() => {
    fetchRuns()
    if (selectedRunId.value) fetchLogs()
  }, 5000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})

async function fetchRuns() {
  try {
    const res = await fetch('/api/pipelines/runs')
    if (res.ok) runs.value = await res.json()
  } catch {}
}

async function selectRun(id: string) {
  selectedRunId.value = id
  expandedLogs.value = new Set()
  await fetchLogs()
}

async function fetchLogs() {
  if (!selectedRunId.value) return
  logsLoading.value = true
  try {
    const res = await fetch(`/api/pipelines/runs/${selectedRunId.value}/logs`)
    if (res.ok) logs.value = await res.json()
  } catch {}
  logsLoading.value = false
}

function toggleData(index: number) {
  if (expandedLogs.value.has(index)) {
    expandedLogs.value.delete(index)
  } else {
    expandedLogs.value.add(index)
  }
  expandedLogs.value = new Set(expandedLogs.value)
}

function formatTime(ts: string) {
  try {
    return new Date(ts).toLocaleTimeString()
  } catch {
    return ts
  }
}
</script>
