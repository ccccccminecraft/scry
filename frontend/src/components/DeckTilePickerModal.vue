<template>
  <div v-if="visible" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal">
      <div class="modal__title">代表カードを選択</div>
      <div class="card-grid">
        <div
          v-for="card in uniqueCards"
          :key="card.scryfall_id!"
          class="card-thumb"
          :class="{ 'card-thumb--selected': card.scryfall_id === selectedId }"
          @click="selectedId = card.scryfall_id"
        >
          <img :src="imageUrl(card.scryfall_id!)" :alt="card.card_name" />
          <div class="card-thumb__name">{{ card.card_name }}</div>
        </div>
      </div>
      <div class="modal__footer">
        <button class="modal__btn" @click="$emit('close')">キャンセル</button>
        <button
          class="modal__btn modal__btn--primary"
          :disabled="!selectedId"
          @click="confirm"
        >選択</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { cardImageUrl, type DeckVersionDetail } from '../api/decklist'

const props = defineProps<{
  visible: boolean
  version: DeckVersionDetail | null
  currentTile: string | null
}>()

const emit = defineEmits<{
  close: []
  select: [scryfallId: string]
}>()

const selectedId = ref<string | null>(null)

watch(() => props.visible, (v) => {
  if (v) selectedId.value = props.currentTile
})

const uniqueCards = computed(() => {
  if (!props.version) return []
  const all = [...props.version.main, ...props.version.sideboard]
  const seen = new Set<string>()
  return all.filter(c => {
    if (!c.scryfall_id || seen.has(c.scryfall_id)) return false
    seen.add(c.scryfall_id)
    return true
  })
})

function imageUrl(scryfallId: string) {
  return cardImageUrl(scryfallId, 'normal')
}

function confirm() {
  if (selectedId.value) emit('select', selectedId.value)
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 300;
}

.modal {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  width: 680px;
  max-width: 95vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.modal__title {
  font-size: 16px;
  font-weight: bold;
  color: #2c2416;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 8px;
  overflow-y: auto;
  flex: 1;
  padding: 4px;
}

.card-thumb {
  border-radius: 6px;
  overflow: hidden;
  cursor: pointer;
  border: 2px solid transparent;
  transition: border-color 0.15s;
}

.card-thumb:hover {
  border-color: #4a6fa5;
}

.card-thumb--selected {
  border-color: #4a6fa5;
  box-shadow: 0 0 0 2px #4a6fa5;
}

.card-thumb img {
  width: 100%;
  aspect-ratio: 63 / 88;
  object-fit: cover;
  display: block;
}

.card-thumb__name {
  font-size: 9px;
  color: #5a4a35;
  text-align: center;
  padding: 2px 4px;
  background: #faf7f0;
  line-height: 1.3;
  word-break: break-word;
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
}

.modal__btn:hover { background: #f0ece0; }

.modal__btn--primary {
  background: #4a6fa5;
  color: #fff;
  border-color: #4a6fa5;
}

.modal__btn--primary:hover { background: #3a5f95; }

.modal__btn:disabled {
  opacity: 0.5;
  cursor: default;
}
</style>
