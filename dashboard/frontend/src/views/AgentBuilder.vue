<template>
  <div class="flex h-full">
    <!-- Agent list -->
    <div class="w-72 border-r border-surface-lighter flex flex-col">
      <div class="p-4 border-b border-surface-lighter flex items-center justify-between">
        <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wide">Agents</h2>
        <div class="flex gap-2">
          <button @click="seedBuiltins" class="px-2 py-1 bg-surface-lighter text-gray-400 text-xs rounded hover:text-gray-200" title="Seed builtin agents">
            Seed
          </button>
          <button @click="createNew" class="px-3 py-1 bg-primary text-white text-sm rounded hover:bg-primary-dark">
            + New
          </button>
        </div>
      </div>
      <div class="flex-1 overflow-auto p-2 space-y-1">
        <div
          v-for="agent in store.agents"
          :key="agent.agent_id"
          @click="selectAgent(agent.agent_id)"
          class="p-3 rounded-lg cursor-pointer transition-colors"
          :class="store.current?.agent_id === agent.agent_id ? 'bg-primary/20 border border-primary/40' : 'hover:bg-surface-lighter'"
        >
          <div class="flex items-center gap-2">
            <span class="text-sm font-medium text-gray-200">{{ agent.name }}</span>
            <span v-if="agent.is_builtin" class="px-1.5 py-0.5 bg-blue-600/20 text-blue-400 text-xs rounded">builtin</span>
          </div>
          <div class="text-xs text-gray-500 mt-1">{{ agent.model }}</div>
        </div>
      </div>
    </div>

    <!-- Editor form -->
    <div class="flex-1 overflow-auto">
      <template v-if="store.current">
        <div class="p-6 max-w-4xl space-y-6">
          <div class="flex items-center justify-between">
            <h2 class="text-xl font-semibold text-gray-200">{{ store.current.is_builtin ? '(Builtin) ' : '' }}{{ editForm.name }}</h2>
            <div class="flex gap-2">
              <button @click="save" :disabled="store.current.is_builtin" class="px-4 py-2 bg-primary text-white text-sm rounded hover:bg-primary-dark disabled:opacity-40 disabled:cursor-not-allowed">
                Save
              </button>
              <button @click="previewPrompt" class="px-3 py-2 bg-surface-lighter text-gray-400 text-sm rounded hover:text-gray-200">
                Preview Prompt
              </button>
              <button @click="remove" v-if="!store.current.is_builtin" class="px-3 py-2 bg-red-600/20 text-red-400 text-sm rounded hover:bg-red-600/40">
                Delete
              </button>
            </div>
          </div>

          <!-- Prompt preview panel -->
          <div v-if="promptPreview" class="bg-surface rounded-lg border border-surface-lighter p-4">
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-3">
                <h3 class="text-xs font-semibold text-gray-400 uppercase">Full Prompt Preview</h3>
                <span class="text-xs text-gray-500">{{ promptPreview.prompt_length }} chars</span>
                <span v-if="promptPreview.skills_count" class="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded">
                  {{ promptPreview.skills_count }} skill{{ promptPreview.skills_count > 1 ? 's' : '' }} loaded
                </span>
                <span v-else class="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs rounded">
                  no skills
                </span>
              </div>
              <button @click="promptPreview = null" class="text-gray-500 hover:text-gray-300 text-sm">Close</button>
            </div>
            <div v-if="promptPreview.skills_loaded?.length" class="flex gap-2 mb-2 flex-wrap">
              <span v-for="s in promptPreview.skills_loaded" :key="s.skill_id" class="px-2 py-0.5 bg-primary/10 text-primary text-xs rounded">
                {{ s.name }} ({{ s.chars }} chars)
              </span>
            </div>
            <pre class="text-xs text-gray-300 bg-surface-lighter rounded p-3 max-h-80 overflow-auto whitespace-pre-wrap">{{ promptPreview.full_prompt }}</pre>
          </div>

          <!-- Name & Description -->
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-xs text-gray-400 mb-1">Name</label>
              <input v-model="editForm.name" class="w-full bg-surface-lighter border border-surface-lighter rounded px-3 py-2 text-sm text-gray-200 focus:border-primary focus:outline-none" />
            </div>
            <div>
              <label class="block text-xs text-gray-400 mb-1">Description</label>
              <input v-model="editForm.description" class="w-full bg-surface-lighter border border-surface-lighter rounded px-3 py-2 text-sm text-gray-200 focus:border-primary focus:outline-none" />
            </div>
          </div>

          <!-- Model & Config -->
          <div class="grid grid-cols-3 gap-4">
            <div>
              <label class="block text-xs text-gray-400 mb-1">Model (Vertex AI)</label>
              <select v-model="editForm.model" class="w-full bg-surface-lighter border border-surface-lighter rounded px-3 py-2 text-sm text-gray-200 focus:border-primary focus:outline-none">
                <option value="claude-sonnet-4-5@20250929">Sonnet 4.5</option>
                <option value="claude-sonnet-4-6">Sonnet 4.6</option>
                <option value="claude-opus-4-5@20251101">Opus 4.5</option>
                <option value="claude-opus-4-6">Opus 4.6</option>
                <option value="claude-opus-4-7">Opus 4.7</option>
                <option value="claude-haiku-4-5@20251001">Haiku 4.5</option>
              </select>
            </div>
            <div>
              <label class="block text-xs text-gray-400 mb-1">Max Tokens</label>
              <input v-model.number="editForm.max_tokens" type="number" class="w-full bg-surface-lighter border border-surface-lighter rounded px-3 py-2 text-sm text-gray-200 focus:border-primary focus:outline-none" />
            </div>
            <div>
              <label class="block text-xs text-gray-400 mb-1">Thinking</label>
              <select v-model="editForm.effort" class="w-full bg-surface-lighter border border-surface-lighter rounded px-3 py-2 text-sm text-gray-200 focus:border-primary focus:outline-none">
                <option value="enabled">Enabled</option>
                <option value="disabled">Disabled</option>
              </select>
            </div>
          </div>

          <!-- System Prompt -->
          <div>
            <label class="block text-xs text-gray-400 mb-1">System Prompt</label>
            <textarea v-model="editForm.system_prompt" rows="12" class="w-full bg-surface-lighter border border-surface-lighter rounded px-3 py-2 text-sm text-gray-200 font-mono focus:border-primary focus:outline-none resize-y" />
          </div>

          <!-- Skills -->
          <div>
            <label class="block text-xs text-gray-400 mb-1">Attached Skills</label>
            <div class="flex flex-wrap gap-2 mt-1">
              <div v-for="skill in availableSkills" :key="skill.skill_id"
                @click="toggleSkill(skill.skill_id)"
                class="px-3 py-1.5 rounded-lg cursor-pointer text-sm transition-colors"
                :class="editForm.skill_ids.includes(skill.skill_id) ? 'bg-primary/30 text-primary border border-primary/50' : 'bg-surface-lighter text-gray-400 hover:text-gray-200'"
              >
                {{ skill.name }}
              </div>
              <div v-if="!availableSkills.length" class="text-sm text-gray-500">No skills available. Create some in the Skills tab.</div>
            </div>
          </div>

          <!-- Plugins -->
          <div>
            <div class="flex items-center justify-between mb-2">
              <label class="text-xs text-gray-400">Plugins (Environment Variables)</label>
              <button @click="addPlugin" class="px-2 py-1 text-xs bg-surface-lighter text-gray-400 rounded hover:text-gray-200">+ Add Plugin</button>
            </div>
            <div v-for="(plugin, i) in editForm.plugins" :key="i" class="bg-surface-lighter rounded-lg p-4 mb-3">
              <div class="flex items-center gap-3 mb-3">
                <input v-model="plugin.plugin_name" placeholder="Plugin name (e.g. jira)" class="flex-1 bg-surface border border-surface-lighter rounded px-3 py-1.5 text-sm text-gray-200 focus:border-primary focus:outline-none" />
                <label class="flex items-center gap-2 text-sm text-gray-400">
                  <input type="checkbox" v-model="plugin.enabled" class="rounded" />
                  Enabled
                </label>
                <button @click="editForm.plugins.splice(i, 1)" class="text-red-400 text-sm hover:text-red-300">Remove</button>
              </div>
              <div v-for="(val, key) in plugin.env_vars" :key="key" class="flex items-center gap-2 mb-1">
                <input :value="key" @change="renameEnvVar(plugin, key as string, ($event.target as HTMLInputElement).value)" class="w-48 bg-surface border border-surface-lighter rounded px-2 py-1 text-xs text-gray-300 font-mono focus:border-primary focus:outline-none" />
                <input v-model="plugin.env_vars[key as string]" type="password" class="flex-1 bg-surface border border-surface-lighter rounded px-2 py-1 text-xs text-gray-300 font-mono focus:border-primary focus:outline-none" />
                <button @click="delete plugin.env_vars[key as string]" class="text-red-400 text-xs">x</button>
              </div>
              <button @click="addEnvVar(plugin)" class="text-xs text-gray-500 hover:text-gray-300 mt-1">+ Add variable</button>
            </div>
          </div>
        </div>
      </template>
      <div v-else class="flex-1 flex items-center justify-center h-full text-gray-500">
        Select an agent or create a new one
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, onMounted } from 'vue'
import { useAgentsStore } from '../stores/agents'
import { useSkillsStore } from '../stores/skills'
import type { PluginConfig } from '../types'

const store = useAgentsStore()
const skillsStore = useSkillsStore()
const availableSkills = ref<{ skill_id: string; name: string }[]>([])
const promptPreview = ref<any>(null)

const editForm = reactive({
  name: '',
  description: '',
  system_prompt: '',
  model: 'claude-opus-4-7',
  max_tokens: 64000,
  effort: 'high',
  skill_ids: [] as string[],
  plugins: [] as PluginConfig[],
})

onMounted(async () => {
  await Promise.all([store.fetchAll(), skillsStore.fetchAll()])
  availableSkills.value = skillsStore.skills.map(s => ({ skill_id: s.skill_id, name: s.name }))
})

watch(() => store.current, (agent) => {
  if (agent) {
    editForm.name = agent.name
    editForm.description = agent.description
    editForm.system_prompt = agent.system_prompt || ''
    editForm.model = agent.model
    editForm.max_tokens = agent.max_tokens
    editForm.effort = agent.effort
    editForm.skill_ids = [...(agent.skill_ids || [])]
    editForm.plugins = JSON.parse(JSON.stringify(agent.plugins || []))
  }
})

async function selectAgent(id: string) {
  promptPreview.value = null
  await store.fetchOne(id)
}

async function createNew() {
  const agent = await store.create({ name: 'New Agent', description: '', system_prompt: '' })
  await store.fetchOne(agent.agent_id)
}

async function save() {
  if (!store.current) return
  await store.update(store.current.agent_id, { ...editForm })
  promptPreview.value = null
}

async function previewPrompt() {
  if (!store.current) return
  try {
    const res = await fetch(`/api/agents/${store.current.agent_id}/prompt-preview`)
    if (res.ok) promptPreview.value = await res.json()
  } catch (e: any) {
    alert('Error: ' + e.message)
  }
}

async function remove() {
  if (!store.current || !confirm('Delete this agent?')) return
  await store.remove(store.current.agent_id)
}

async function seedBuiltins() {
  await store.seedBuiltins()
  await store.fetchAll()
}

function toggleSkill(id: string) {
  const idx = editForm.skill_ids.indexOf(id)
  if (idx >= 0) editForm.skill_ids.splice(idx, 1)
  else editForm.skill_ids.push(id)
}

function addPlugin() {
  editForm.plugins.push({ plugin_name: '', env_vars: {}, enabled: true })
}

function addEnvVar(plugin: PluginConfig) {
  plugin.env_vars['NEW_VAR'] = ''
}

function renameEnvVar(plugin: PluginConfig, oldKey: string, newKey: string) {
  if (oldKey === newKey) return
  plugin.env_vars[newKey] = plugin.env_vars[oldKey]
  delete plugin.env_vars[oldKey]
}
</script>
