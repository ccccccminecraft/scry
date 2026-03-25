<template>
  <div class="dsm-overlay" @click.self="$emit('close')">
    <div class="dsm">
      <div class="dsm__header">
        <span class="dsm__title">デッキを選択</span>
        <button class="dsm__close" @click="$emit('close')">✕</button>
      </div>
      <div class="dsm__search-wrap">
        <input
          ref="searchInput"
          v-model="query"
          class="dsm__search"
          placeholder="絞り込み..."
          autocomplete="off"
          @keydown.esc="$emit('close')"
        />
      </div>
      <div class="dsm__list">
        <!-- すべて -->
        <button
          class="dsm__item"
          :class="{ 'dsm__item--selected': !deckId && !deck }"
          @click="selectAll"
        >
          <span class="dsm__check">{{ (!deckId && !deck) ? '✓' : '' }}</span>
          すべて
        </button>

        <!-- デッキリストセクション -->
        <template v-if="filteredDeckList.length > 0">
          <div class="dsm__section">デッキリスト</div>
          <button
            v-for="d in filteredDeckList"
            :key="d.id"
            class="dsm__item"
            :class="{ 'dsm__item--selected': deckId === d.id }"
            @click="selectDeckId(d.id)"
          >
            <span class="dsm__check">{{ deckId === d.id ? '✓' : '' }}</span>
            {{ d.name }}
          </button>
        </template>

        <!-- アーキタイプセクション -->
        <template v-if="filteredDeckNameList.length > 0">
          <div class="dsm__section">アーキタイプ</div>
          <button
            v-for="name in filteredDeckNameList"
            :key="name"
            class="dsm__item"
            :class="{ 'dsm__item--selected': deck === name }"
            @click="selectDeckName(name)"
          >
            <span class="dsm__check">{{ deck === name ? '✓' : '' }}</span>
            {{ name }}
          </button>
        </template>

        <div v-if="filteredDeckList.length === 0 && filteredDeckNameList.length === 0" class="dsm__empty">
          該当なし
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { Deck } from '../api/decklist'

const props = defineProps<{
  deckList: Deck[]
  deckNameList: string[]
  deckId: number | null
  deck: string
}>()

const emit = defineEmits<{
  'selectDeckId': [id: number | null]
  'selectDeck': [name: string]
  'close': []
}>()

const query = ref('')
const searchInput = ref<HTMLInputElement | null>(null)

const filteredDeckList = computed(() => {
  if (!query.value) return props.deckList
  const q = query.value.toLowerCase()
  return props.deckList.filter(d => d.name.toLowerCase().includes(q))
})

const filteredDeckNameList = computed(() => {
  if (!query.value) return props.deckNameList
  const q = query.value.toLowerCase()
  return props.deckNameList.filter(n => n.toLowerCase().includes(q))
})

function selectAll() {
  emit('selectDeckId', null)
  emit('selectDeck', '')
  emit('close')
}

function selectDeckId(id: number) {
  emit('selectDeckId', id)
  emit('selectDeck', '')
  emit('close')
}

function selectDeckName(name: string) {
  emit('selectDeck', name)
  emit('selectDeckId', null)
  emit('close')
}

onMounted(() => {
  searchInput.value?.focus()
})
</script>

<style scoped>
.dsm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 300;
}

.dsm {
  background: #fff;
  border-radius: 8px;
  width: 360px;
  max-width: 90vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
}

.dsm__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 10px;
  border-bottom: 1px solid #e0d8c8;
  flex-shrink: 0;
}

.dsm__title {
  font-size: 13px;
  font-weight: bold;
  color: #2c2416;
}

.dsm__close {
  background: none;
  border: none;
  font-size: 14px;
  color: #7a6a55;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}
.dsm__close:hover { color: #2c2416; }

.dsm__search-wrap {
  padding: 10px 12px 8px;
  flex-shrink: 0;
}

.dsm__search {
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
.dsm__search:focus { border-color: #4a6fa5; background: #fff; }

.dsm__list {
  overflow-y: auto;
  padding: 4px 0 8px;
}

.dsm__section {
  font-size: 10px;
  color: #9a8a75;
  font-weight: bold;
  padding: 8px 16px 4px;
  border-top: 1px solid #f0ece0;
  margin-top: 4px;
  letter-spacing: 0.05em;
}

.dsm__item {
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
.dsm__item:hover { background: #faf7f0; }
.dsm__item--selected { color: #4a6fa5; font-weight: bold; }

.dsm__check {
  width: 14px;
  flex-shrink: 0;
  color: #4a6fa5;
  font-size: 12px;
}

.dsm__empty {
  padding: 16px;
  text-align: center;
  font-size: 12px;
  color: #b0a090;
}
</style>
