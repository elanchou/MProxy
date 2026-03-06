<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-bold">Dashboard</h2>
      <div class="flex items-center gap-3">
        <span :class="status.running ? 'text-green-400' : 'text-red-400'" class="text-sm font-medium">
          {{ status.running ? 'Running' : 'Stopped' }}
          <span v-if="status.pid" class="text-gray-500 ml-1">PID: {{ status.pid }}</span>
        </span>
        <button v-if="!status.running" @click="start" :disabled="loading"
          class="btn bg-green-600 hover:bg-green-700">Start</button>
        <button v-else @click="restart" :disabled="loading"
          class="btn bg-yellow-600 hover:bg-yellow-700">Restart</button>
        <button v-if="status.running" @click="stop" :disabled="loading"
          class="btn bg-red-600 hover:bg-red-700">Stop</button>
      </div>
    </div>

    <div class="grid grid-cols-3 gap-4">
      <div class="card">
        <div class="text-3xl font-bold text-indigo-400">{{ stats.subscriptions }}</div>
        <div class="text-sm text-gray-400 mt-1">Subscriptions</div>
      </div>
      <div class="card">
        <div class="text-3xl font-bold text-green-400">{{ stats.nodes }}</div>
        <div class="text-sm text-gray-400 mt-1">Total Nodes</div>
      </div>
      <div class="card">
        <div class="text-3xl font-bold text-yellow-400">{{ stats.enabledNodes }}</div>
        <div class="text-sm text-gray-400 mt-1">Active Nodes</div>
      </div>
    </div>

    <div class="card" v-if="nodes.length">
      <h3 class="text-lg font-semibold mb-3">Node Port Mapping</h3>
      <div class="overflow-auto max-h-96">
        <table class="w-full text-sm">
          <thead class="text-gray-400 border-b border-gray-700">
            <tr>
              <th class="text-left py-2 px-3">Name</th>
              <th class="text-left py-2 px-3">Type</th>
              <th class="text-left py-2 px-3">Server</th>
              <th class="text-left py-2 px-3">Local Port</th>
              <th class="text-left py-2 px-3">Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="n in nodes" :key="n.id" class="border-b border-gray-800 hover:bg-gray-800/50">
              <td class="py-2 px-3">{{ n.name }}</td>
              <td class="py-2 px-3">
                <span class="px-2 py-0.5 rounded text-xs font-mono"
                  :class="typeColor(n.type)">{{ n.type }}</span>
              </td>
              <td class="py-2 px-3 text-gray-400 font-mono text-xs">{{ n.server }}:{{ n.port }}</td>
              <td class="py-2 px-3 font-mono text-indigo-400">{{ n.listener_port || '-' }}</td>
              <td class="py-2 px-3">
                <span :class="n.enabled ? 'text-green-400' : 'text-gray-500'" class="text-xs">
                  {{ n.enabled ? 'Enabled' : 'Disabled' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const status = ref({ running: false, pid: null })
const stats = ref({ subscriptions: 0, nodes: 0, enabledNodes: 0 })
const nodes = ref([])
const loading = ref(false)

const typeColor = (t) => ({
  'vmess': 'bg-blue-900 text-blue-300',
  'vless': 'bg-purple-900 text-purple-300',
  'trojan': 'bg-red-900 text-red-300',
  'ss': 'bg-green-900 text-green-300',
  'hysteria2': 'bg-yellow-900 text-yellow-300',
}[t] || 'bg-gray-700 text-gray-300')

async function load() {
  const [s, n, st] = await Promise.all([
    api.getSubs(), api.getNodes(), api.proxyStatus()
  ])
  stats.value.subscriptions = s.data.length
  stats.value.nodes = n.data.length
  stats.value.enabledNodes = n.data.filter(x => x.enabled).length
  nodes.value = n.data
  status.value = st.data
}

async function start() { loading.value = true; await api.proxyStart(); await load(); loading.value = false }
async function stop() { loading.value = true; await api.proxyStop(); await load(); loading.value = false }
async function restart() { loading.value = true; await api.proxyRestart(); await load(); loading.value = false }

onMounted(load)
</script>

<style>
@reference "tailwindcss";
.card { @apply bg-gray-900 rounded-lg border border-gray-800 p-4; }
.btn { @apply px-4 py-1.5 rounded text-sm font-medium text-white transition-colors disabled:opacity-50; }
</style>
