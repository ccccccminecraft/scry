<template>
  <div class="fsm-overlay" @click.self="$emit('close')">
    <div class="fsm">
      <div class="fsm__header">
        <span class="fsm__title">{{ title }}</span>
        <button class="fsm__close" @click="$emit('close')">✕</button>
      </div>
      <div class="fsm__search-wrap">
        <input
          ref="searchInput"
          v-model="query"
          class="fsm__search"
          placeholder="絞り込み..."
          autocomplete="off"
          @keydown.esc="$emit('close')"
        />
      </div>
      <div class="fsm__list">
        <button
          class="fsm__item"
          :class="{ 'fsm__item--selected': modelValue === null || modelValue === '' }"
          @click="select(null)"
        >
          <span class="fsm__check">{{ (modelValue === null || modelValue === '') ? '✓' : '' }}</span>
          すべて
        </button>
        <button
          v-for="item in filtered"
          :key="item.value ?? ''"
          class="fsm__item"
          :class="{ 'fsm__item--selected': item.value === modelValue }"
          @click="select(item.value)"
        >
          <span class="fsm__check">{{ item.value === modelValue ? '✓' : '' }}</span>
          {{ item.label }}
        </button>
        <div v-if="filtered.length === 0" class="fsm__empty">該当なし</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

interface Item {
  value: string | number | null
  label: string
}

const props = defineProps<{
  title: string
  items: Item[]
  modelValue: string | number | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string | number | null]
  'close': []
}>()

const query = ref('')
const searchInput = ref<HTMLInputElement | null>(null)

const filtered = computed(() => {
  if (!query.value) return props.items
  const q = query.value.toLowerCase()
  return props.items.filter(i => i.label.toLowerCase().includes(q))
})

function select(value: string | number | null) {
  emit('update:modelValue', value)
  emit('close')
}

onMounted(() => {
  searchInput.value?.focus()
})
</script>

<style scoped>
.fsm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 300;
}

.fsm {
  background: #fff;
  border-radius: 8px;
  width: 360px;
  max-width: 90vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
}

.fsm__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 10px;
  border-bottom: 1px solid #e0d8c8;
  flex-shrink: 0;
}

.fsm__title {
  font-size: 13px;
  font-weight: bold;
  color: #2c2416;
}

.fsm__close {
  background: none;
  border: none;
  font-size: 14px;
  color: #7a6a55;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}
.fsm__close:hover { color: #2c2416; }

.fsm__search-wrap {
  padding: 10px 12px 8px;
  flex-shrink: 0;
}

.fsm__search {
  width: 100%;
  box-sizing: border-box;
  padding: 6px 10px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 13px;
  font-family: inherit;
  color: #2c2416;
  background: #faf7f0;
  outline: none;
}
.fsm__search:focus { border-color: #4a6fa5; background: #fff; }

.fsm__list {
  overflow-y: auto;
  padding: 4px 0 8px;
}

.fsm__item {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 8px 16px;
  background: none;
  border: none;
  text-align: left;
  font-size: 13px;
  font-family: inherit;
  color: #2c2416;
  cursor: pointer;
  gap: 8px;
}
.fsm__item:hover { background: #faf7f0; }
.fsm__item--selected { color: #4a6fa5; font-weight: bold; }

.fsm__check {
  width: 14px;
  flex-shrink: 0;
  color: #4a6fa5;
  font-size: 12px;
}

.fsm__empty {
  padding: 16px;
  text-align: center;
  font-size: 12px;
  color: #b0a090;
}
</style>
