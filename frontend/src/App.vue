<template>
  <div class="min-h-screen bg-gray-950 text-gray-100">
    <nav class="bg-gray-900 border-b border-gray-800">
      <div class="max-w-7xl mx-auto px-4 py-3 flex items-center gap-8">
        <h1 class="text-xl font-bold text-indigo-400">MProxy</h1>
        <router-link to="/" class="nav-link">Dashboard</router-link>
        <router-link to="/subscriptions" class="nav-link">Subscriptions</router-link>
        <router-link to="/nodes" class="nav-link">Nodes</router-link>
      </div>
    </nav>
    <main class="max-w-7xl mx-auto px-4 py-6">
      <router-view />
    </main>
  </div>
</template>

<style>
@reference "tailwindcss";
.nav-link {
  @apply text-sm text-gray-400 hover:text-gray-100 transition-colors;
}
.router-link-active {
  @apply text-indigo-400;
}
</style>
