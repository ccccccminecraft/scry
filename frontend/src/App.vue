<template>
  <div class="app">
    <GlobalNav />
    <main class="app__content">
      <router-view />
    </main>
    <AppToast />
  </div>
</template>

<script setup lang="ts">
import GlobalNav from './components/GlobalNav.vue'
import AppToast from './components/AppToast.vue'
</script>

<style>
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  background-color: #f0ece0;
  color: #2c2416;
  font-family: 'Noto Sans JP', 'Noto Sans CJK JP', 'Yu Gothic UI', 'Segoe UI', sans-serif;
  font-size: 14px;
  -webkit-font-smoothing: antialiased;
}

button {
  cursor: pointer;
  font-size: 14px;
  font-family: inherit;
}
</style>

<style scoped>
.app {
  display: flex;
  min-height: 100vh;
}

.app__content {
  flex: 1;
  overflow: auto;
}
</style>
