<template>
  <div class="home">
    <h1 class="home__title">Scry</h1>

    <div class="home__status">
      <span v-if="status === 'checking'" class="status status--checking">接続確認中...</span>
      <span v-else-if="status === 'connected'" class="status status--ok">✅ Backend connected</span>
      <span v-else class="status status--error">❌ Backend not connected</span>
    </div>

    <div class="home__actions">
      <button class="btn btn--primary" @click="$router.push('/import')">
        ログをインポートする
      </button>
      <button class="btn btn--secondary" @click="$router.push('/matches')">
        履歴を見る
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

const status = ref<'checking' | 'connected' | 'error'>('checking')

onMounted(async () => {
  try {
    await axios.get('http://localhost:8000/api/health')
    status.value = 'connected'
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

.home__actions {
  display: flex;
  gap: 12px;
}

.btn {
  padding: 10px 24px;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  transition: background 0.15s;
}

.btn--primary {
  background: #4a6fa5;
  color: #fff;
}
.btn--primary:hover { background: #3a5f95; }

.btn--secondary {
  background: #faf7f0;
  color: #2c2416;
  border: 1px solid #c8b89a;
}
.btn--secondary:hover { background: #f0ece0; }
</style>
