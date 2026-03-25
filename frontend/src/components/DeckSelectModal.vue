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
          :class="{ 'dsm__item--selected': localDeckIds.length === 0 && localDecks.length === 0 }"
          @click="selectAll"
        >
          <span class="dsm__check">{{ (localDeckIds.length === 0 && localDecks.length === 0) ? '✓' : '' }}</span>
          すべて
        </button>

        <!-- デッキリストセクション -->
        <template v-if="filteredDeckList.length > 0">
          <div class="dsm__section">デッキリスト</div>
          <button
            v-for="d in filteredDeckList"
            :key="d.id"
            class="dsm__item"
            :class="{ 'dsm__item--selected': localDeckIds.includes(d.id) }"
            @click="toggleDeckId(d.id)"
          >
            <span class="dsm__check">{{ localDeckIds.includes(d.id) ? '✓' : '' }}</span>
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
            :class="{ 'dsm__item--selected': localDecks.includes(name) }"
            @click="toggleDeckName(name)"
          >
            <span class="dsm__check">{{ localDecks.includes(name) ? '✓' : '' }}</span>
            {{ name }}
          </button>
        </template>

        <div v-if="filteredDeckList.length === 0 && filteredDeckNameList.length === 0" class="dsm__empty">
          該当なし
        </div>
      </div>
      <div class="dsm__footer">
        <button class="dsm__footer-btn dsm__footer-btn--clear" @click="clearAll">クリア</button>
        <button class="dsm__footer-btn dsm__footer-btn--confirm" @click="confirm">確定</button>
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
  deckIds: number[]
  decks: string[]
}>()

const emit = defineEmits<{
  'update:deckIds': [ids: number[]]
  'update:decks': [names: string[]]
  'close': []
}>()

const query = ref('')
const searchInput = ref<HTMLInputElement | null>(null)

const localDeckIds = ref<number[]>([...props.deckIds])
const localDecks = ref<string[]>([...props.decks])

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
  emit('update:deckIds', [])
  emit('update:decks', [])
  emit('close')
}

function toggleDeckId(id: number) {
  // デッキリスト選択時はアーキタイプをクリア
  localDecks.value = []
  const idx = localDeckIds.value.indexOf(id)
  if (idx === -1) {
    localDeckIds.value = [...localDeckIds.value, id]
  } else {
    localDeckIds.value = localDeckIds.value.filter(v => v !== id)
  }
}

function toggleDeckName(name: string) {
  // アーキタイプ選択時はデッキリストをクリア
  localDeckIds.value = []
  const idx = localDecks.value.indexOf(name)
  if (idx === -1) {
    localDecks.value = [...localDecks.value, name]
  } else {
    localDecks.value = localDecks.value.filter(v => v !== name)
  }
}

function clearAll() {
  localDeckIds.value = []
  localDecks.value = []
}

function confirm() {
  emit('update:deckIds', localDeckIds.value)
  emit('update:decks', localDecks.value)
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
  padding: 4px 0 4px;
  flex: 1;
  min-height: 0;
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

.dsm__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 10px 16px;
  border-top: 1px solid #e0d8c8;
  flex-shrink: 0;
}

.dsm__footer-btn {
  padding: 5px 14px;
  border-radius: 4px;
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
}

.dsm__footer-btn--clear {
  border: 1px solid #c8b89a;
  background: #faf7f0;
  color: #7a6a55;
}
.dsm__footer-btn--clear:hover { background: #f0ece0; }

.dsm__footer-btn--confirm {
  border: 1px solid #4a6fa5;
  background: #4a6fa5;
  color: #fff;
}
.dsm__footer-btn--confirm:hover { background: #3a5f95; }
</style>
