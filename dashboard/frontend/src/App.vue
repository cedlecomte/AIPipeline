<template>
  <div class="flex h-screen">
    <!-- Sidebar -->
    <aside class="w-56 bg-surface-light border-r border-surface-lighter flex flex-col">
      <div class="p-4 border-b border-surface-lighter">
        <h1 class="text-lg font-bold text-primary">Agent Pipeline</h1>
      </div>
      <nav class="flex-1 p-2 space-y-1">
        <router-link
          v-for="item in nav"
          :key="item.to"
          :to="item.to"
          class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors"
          :class="$route.path === item.to ? 'bg-primary/20 text-primary' : 'text-gray-400 hover:text-gray-200 hover:bg-surface-lighter'"
        >
          <span class="text-lg">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>
      <div class="p-4 border-t border-surface-lighter text-xs text-gray-500">
        v0.2.0
      </div>
    </aside>

    <!-- Main content -->
    <main class="flex-1 overflow-auto">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
const nav = [
  { to: '/pipelines', icon: '🔗', label: 'Pipelines' },
  { to: '/agents', icon: '🤖', label: 'Agents' },
  { to: '/skills', icon: '📝', label: 'Skills' },
  { to: '/monitor', icon: '📊', label: 'Monitor' },
]
</script>
