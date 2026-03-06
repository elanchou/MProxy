<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-bold">Subscriptions</h2>
      <button @click="showAdd = true" class="btn bg-indigo-600 hover:bg-indigo-700">+ Add</button>
    </div>

    <div v-if="showAdd" class="card">
      <h3 class="font-semibold mb-3">{{ editing ? 'Edit' : 'Add' }} Subscription</h3>
      <div class="space-y-3">
        <input v-model="form.name" placeholder="Name" class="input w-full" />
        <input v-model="form.url" placeholder="Subscription URL" class="input w-full" />
        <div class="flex gap-2">
          <button @click="save" class="btn bg-indigo-600 hover:bg-indigo-700">Save</button>
          <button @click="cancel" class="btn bg-gray-700 hover:bg-gray-600">Cancel</button>
        </div>
      </div>
    </div>

    <div v-for="sub in subs" :key="sub.id" class="card flex items-center justify-between">
      <div>
        <div class="font-medium">{{ sub.name }}</div>
        <div class="text-xs text-gray-500 mt-1 font-mono truncate max-w-lg">{{ sub.url }}</div>
        <div class="text-xs text-gray-400 mt-1">{{ sub.node_count }} nodes</div>
      </div>
      <div class="flex items-center gap-2">
        <button @click="refresh(sub.id)" :disabled="refreshing === sub.id"
          class="btn bg-green-600 hover:bg-green-700 text-xs">
          {{ refreshing === sub.id ? 'Fetching...' : 'Refresh' }}
        </button>
        <button @click="edit(sub)" class="btn bg-gray-700 hover:bg-gray-600 text-xs">Edit</button>
        <button @click="remove(sub.id)" class="btn bg-red-600 hover:bg-red-700 text-xs">Delete</button>
      </div>
    </div>

    <div v-if="!subs.length" class="text-gray-500 text-center py-12">
      No subscriptions yet. Click "+ Add" to get started.
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const subs = ref([])
const showAdd = ref(false)
const editing = ref(null)
const refreshing = ref(null)
const form = ref({ name: '', url: '' })

async function load() {
  subs.value = (await api.getSubs()).data
}

async function save() {
  if (editing.value) {
    await api.updateSub(editing.value, form.value)
  } else {
    await api.createSub(form.value)
  }
  cancel()
  await load()
}

function edit(sub) {
  editing.value = sub.id
  form.value = { name: sub.name, url: sub.url }
  showAdd.value = true
}

function cancel() {
  showAdd.value = false
  editing.value = null
  form.value = { name: '', url: '' }
}

async function refresh(id) {
  refreshing.value = id
  await api.refreshSub(id)
  await load()
  refreshing.value = null
}

async function remove(id) {
  await api.deleteSub(id)
  await load()
}

onMounted(load)
</script>

<style>
.card { @apply bg-gray-900 rounded-lg border border-gray-800 p-4; }
.btn { @apply px-4 py-1.5 rounded text-sm font-medium text-white transition-colors disabled:opacity-50; }
.input { @apply bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-indigo-500; }
</style>
