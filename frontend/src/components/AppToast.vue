<template>
  <div class="toast-container">
    <div
      v-for="toast in toasts"
      :key="toast.id"
      class="toast"
      :class="`toast--${toast.type}`"
      @click="remove(toast.id)"
    >
      {{ toast.message }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { useToast } from '../composables/useToast'

const { toasts, remove } = useToast()
</script>

<style scoped>
.toast-container {
  position: fixed;
  bottom: 16px;
  right: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 9999;
}

.toast {
  padding: 10px 16px;
  border-radius: 4px;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  max-width: 320px;
  word-break: break-word;
}

.toast--error   { background: #a03030; }
.toast--success { background: #5a7a4a; }
</style>
