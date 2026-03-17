<template>
  <div v-if="visible" class="confirm-overlay" @click.self="$emit('cancel')">
    <div class="confirm-modal">
      <p class="confirm-message">{{ message }}</p>
      <div class="confirm-footer">
        <button class="confirm-btn" @click="$emit('cancel')">{{ cancelLabel }}</button>
        <button class="confirm-btn confirm-btn--primary" @click="$emit('confirm')">{{ confirmLabel }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  visible: boolean
  message: string
  confirmLabel?: string
  cancelLabel?: string
}>(), {
  confirmLabel: 'OK',
  cancelLabel: 'キャンセル',
})

defineEmits<{
  confirm: []
  cancel: []
}>()
</script>

<style scoped>
.confirm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}

.confirm-modal {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  width: 400px;
  max-width: 90vw;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.confirm-message {
  font-size: 13px;
  color: #2c2416;
  line-height: 1.6;
  margin: 0;
}

.confirm-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.confirm-btn {
  padding: 6px 16px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  background: #faf7f0;
  font-size: 13px;
  cursor: pointer;
  color: #2c2416;
  font-family: inherit;
  white-space: nowrap;
}

.confirm-btn:hover {
  background: #f0ece0;
}

.confirm-btn--primary {
  background: #4a6fa5;
  border-color: #4a6fa5;
  color: #fff;
}

.confirm-btn--primary:hover {
  background: #3a5f95;
}
</style>
