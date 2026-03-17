<template>
  <div class="home">
    <h1 class="home__title">Scry</h1>

    <div class="home__status">
      <span v-if="status === 'checking'" class="status status--checking">接続確認中...</span>
      <span v-else-if="status === 'connected'" class="status status--ok">✅ Backend connected</span>
      <span v-else class="status status--error">❌ Backend not connected</span>
    </div>
    <div v-if="version" class="home__version">v{{ version }}</div>

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

const status = ref<'checking' | 'connected' | 'error'>('checking')
const version = ref('')

onMounted(async () => {
  try {
    const res = await axios.get('http://localhost:18432/api/health')
    status.value = 'connected'
    version.value = res.data.version ?? ''
  } catch {
    status.value = 'error'
  }
})
</script>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  gap: 28px;
}

.home__title {
  font-size: 2.4rem;
  font-weight: 700;
  color: #2c2416;
  letter-spacing: 0.05em;
}

.home__status {
  font-size: 1.05rem;
}

.status--checking { color: #7a6a55; }
.status--ok       { color: #5a7a4a; }
.status--error    { color: #a03030; }

.home__version {
  font-size: 0.85rem;
  color: #a09080;
}
</style>
