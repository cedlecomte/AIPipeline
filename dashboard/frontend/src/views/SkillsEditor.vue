<template>
  <div class="flex h-full">
    <!-- Skill list -->
    <div class="w-72 border-r border-surface-lighter flex flex-col">
      <div class="p-4 border-b border-surface-lighter flex items-center justify-between">
        <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wide">Skills</h2>
        <button @click="createNew" class="px-3 py-1 bg-primary text-white text-sm rounded hover:bg-primary-dark">
          + New
        </button>
      </div>
      <div class="flex-1 overflow-auto p-2 space-y-1">
        <div
          v-for="skill in store.skills"
          :key="skill.skill_id"
          @click="selectSkill(skill.skill_id)"
          class="p-3 rounded-lg cursor-pointer transition-colors"
          :class="store.current?.skill_id === skill.skill_id ? 'bg-primary/20 border border-primary/40' : 'hover:bg-surface-lighter'"
        >
          <div class="text-sm font-medium text-gray-200">{{ skill.name }}</div>
          <div class="text-xs text-gray-500 mt-1">{{ skill.description || 'No description' }}</div>
          <div class="flex gap-1 mt-2 flex-wrap">
            <span v-for="tag in (skill.tags || [])" :key="tag" class="px-1.5 py-0.5 bg-surface-lighter rounded text-xs text-gray-400">
              {{ tag }}
            </span>
          </div>
        </div>
        <div v-if="!store.skills.length" class="p-4 text-center text-gray-500 text-sm">
          No skills yet. Create one to get started.
        </div>
      </div>
    </div>

    <!-- Editor -->
    <div class="flex-1 flex flex-col">
      <template v-if="store.current">
        <div class="p-4 border-b border-surface-lighter flex items-center gap-4">
          <input
            v-model="editName"
            class="bg-transparent text-lg font-semibold text-gray-200 border-b border-transparent hover:border-gray-600 focus:border-primary focus:outline-none px-1 py-0.5 flex-1"
            placeholder="Skill name"
          />
          <input
            v-model="editDescription"
            class="bg-transparent text-sm text-gray-400 border-b border-transparent hover:border-gray-600 focus:border-primary focus:outline-none px-1 py-0.5 flex-1"
            placeholder="Description"
          />
          <button @click="save" class="px-4 py-1.5 bg-primary text-white text-sm rounded hover:bg-primary-dark">
            Save
          </button>
          <button @click="remove" class="px-3 py-1.5 bg-red-600/20 text-red-400 text-sm rounded hover:bg-red-600/40">
            Delete
          </button>
        </div>
        <div class="flex-1 overflow-auto">
          <MdEditor
            v-model="editContent"
            :theme="'dark'"
            language="en-US"
            class="h-full"
            :toolbarsExclude="['github']"
          />
        </div>
      </template>
      <div v-else class="flex-1 flex items-center justify-center text-gray-500">
        Select a skill or create a new one
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { MdEditor } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import { useSkillsStore } from '../stores/skills'

const store = useSkillsStore()
const editName = ref('')
const editDescription = ref('')
const editContent = ref('')

onMounted(() => store.fetchAll())

watch(() => store.current, (skill) => {
  if (skill) {
    editName.value = skill.name
    editDescription.value = skill.description
    editContent.value = skill.content
  }
})

async function selectSkill(id: string) {
  await store.fetchOne(id)
}

async function createNew() {
  const skill = await store.create({ name: 'New Skill', description: '', content: '# New Skill\n\nDescribe this skill...' })
  await store.fetchOne(skill.skill_id)
}

async function save() {
  if (!store.current) return
  await store.update(store.current.skill_id, {
    name: editName.value,
    description: editDescription.value,
    content: editContent.value,
  })
}

async function remove() {
  if (!store.current || !confirm('Delete this skill?')) return
  await store.remove(store.current.skill_id)
}
</script>
