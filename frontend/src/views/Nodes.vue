<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-bold">Nodes ({{ filtered.length }})</h2>
      <div class="flex gap-3">
        <input v-model="search" placeholder="Search nodes..." class="input w-64" />
        <select v-model="typeFilter" class="input">
          <option value="">All Types</option>
          <option v-for="t in types" :key="t" :value="t">{{ t }}</option>
        </select>
      </div>
    </div>

    <div class="overflow-auto">
      <table class="w-full text-sm">
        <thead class="text-gray-400 border-b border-gray-700">
          <tr>
            <th class="text-left py-2 px-3">Enabled</th>
            <th class="text-left py-2 px-3">Name</th>
            <th class="text-left py-2 px-3">Type</th>
            <th class="text-left py-2 px-3">Server</th>
            <th class="text-left py-2 px-3">Local Port</th>
            <th class="text-left py-2 px-3">Proxy Address</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="n in filtered" :key="n.id" class="border-b border-gray-800 hover:bg-gray-800/50">
            <td class="py-2 px-3">
              <input type="checkbox" :checked="n.enabled" @change="toggle(n)" class="accent-indigo-500" />
            </td>
            <td class="py-2 px-3">{{ n.name }}</td>
            <td class="py-2 px-3">
              <span class="px-2 py-0.5 rounded text-xs font-mono"
                :class="typeColor(n.type)">{{ n.type }}</span>
            </td>
            <td class="py-2 px-3 text-gray-400 font-mono text-xs">{{ n.server }}:{{ n.port }}</td>
            <td class="py-2 px-3 font-mono text-indigo-400">{{ n.listener_port || '-' }}</td>
            <td class="py-2 px-3 font-mono text-xs text-gray-400">
              <span v-if="n.listener_port" class="select-all">127.0.0.1:{{ n.listener_port }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'

const nodes = ref([])
const search = ref('')
const typeFilter = ref('')

const types = computed(() => [...new Set(nodes.value.map(n => n.type))])

const filtered = computed(() => {
  return nodes.value.filter(n => {
    if (typeFilter.value && n.type !== typeFilter.value) return false
    if (search.value && !n.name.toLowerCase().includes(search.value.toLowerCase())) return false
    return true
  })
})

const typeColor = (t) => ({
  'vmess': 'bg-blue-900 text-blue-300',
  'vless': 'bg-purple-900 text-purple-300',
  'trojan': 'bg-red-900 text-red-300',
  'ss': 'bg-green-900 text-green-300',
  'hysteria2': 'bg-yellow-900 text-yellow-300',
}[t] || 'bg-gray-700 text-gray-300')

async function toggle(node) {
  await api.toggleNode(node.id, !node.enabled)
  node.enabled = !node.enabled
}

onMounted(async () => {
  nodes.value = (await api.getNodes()).data
})
</script>

<style>
.card { @apply bg-gray-900 rounded-lg border border-gray-800 p-4; }
.btn { @apply px-4 py-1.5 rounded text-sm font-medium text-white transition-colors disabled:opacity-50; }
.input { @apply bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-indigo-500; }
</style>
