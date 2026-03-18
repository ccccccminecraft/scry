<template>
  <div v-if="visible" class="overlay" @click.self="$emit('cancel')">
    <div class="modal">
      <div class="modal__warning">⚠️ この操作は取り消せません</div>
      <p class="modal__message">{{ message }}</p>
      <label class="modal__label">確認のため「{{ confirmText }}」と入力してください</label>
      <input
        v-model="input"
        type="text"
        class="modal__input"
        :placeholder="confirmText"
        @keydown.enter="input === confirmText && $emit('confirm')"
      />
      <div class="modal__footer">
        <button class="modal__btn" @click="$emit('cancel')">キャンセル</button>
        <button
          class="modal__btn modal__btn--danger"
          :disabled="input !== confirmText"
          @click="$emit('confirm')"
        >実行</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  visible: boolean
  message: string
  confirmText: string
}>()

defineEmits<{
  confirm: []
  cancel: []
}>()

const input = ref('')

watch(() => props.visible, (v) => {
  if (!v) input.value = ''
})
</script>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}

.modal {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  width: 440px;
  max-width: 90vw;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.modal__warning {
  font-size: 13px;
  font-weight: bold;
  color: #a03030;
}

.modal__message {
  font-size: 13px;
  color: #2c2416;
  line-height: 1.6;
  margin: 0;
}

.modal__label {
  font-size: 12px;
  color: #7a6a55;
}

.modal__input {
  padding: 6px 10px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 13px;
  background: #fff;
  color: #2c2416;
  font-family: inherit;
}

.modal__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.modal__btn {
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

.modal__btn:hover {
  background: #f0ece0;
}

.modal__btn--danger {
  background: #a03030;
  border-color: #a03030;
  color: #fff;
}

.modal__btn--danger:hover:not(:disabled) {
  background: #8a2020;
}

.modal__btn--danger:disabled {
  opacity: 0.4;
  cursor: default;
}
</style>
