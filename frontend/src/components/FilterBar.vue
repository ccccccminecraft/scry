<template>
  <div class="filter-bar">
    <!-- プレイヤー -->
    <div v-if="showPlayer" class="filter-bar__item">
      <div class="filter-bar__label">プレイヤー</div>
      <button
        class="filter-bar__btn"
        :class="{ 'filter-bar__btn--active': !!player }"
        @click="open('player')"
      >{{ player || 'すべて' }} ▾</button>
    </div>

    <!-- フォーマット -->
    <div class="filter-bar__item">
      <div class="filter-bar__label">フォーマット</div>
      <button
        class="filter-bar__btn"
        :class="{ 'filter-bar__btn--active': !!format }"
        @click="open('format')"
      >{{ format || 'すべて' }} ▾</button>
    </div>

    <!-- 対戦相手 -->
    <div class="filter-bar__item">
      <div class="filter-bar__label">対戦相手</div>
      <button
        class="filter-bar__btn"
        :class="{ 'filter-bar__btn--active': !!opponent }"
        @click="open('opponent')"
      >{{ opponent || 'すべて' }} ▾</button>
    </div>

    <!-- 使用デッキ -->
    <div class="filter-bar__item">
      <div class="filter-bar__label">使用デッキ</div>
      <button
        class="filter-bar__btn"
        :class="{ 'filter-bar__btn--active': !!(deckId || deck) }"
        @click="open('deck')"
      >{{ deckLabel }} ▾</button>
    </div>

    <!-- バージョン -->
    <div class="filter-bar__item">
      <div class="filter-bar__label">バージョン</div>
      <button
        class="filter-bar__btn"
        :class="{ 'filter-bar__btn--active': !!versionId, 'filter-bar__btn--disabled': !deckId }"
        :disabled="!deckId"
        @click="open('version')"
      >{{ versionLabel }} ▾</button>
    </div>

    <!-- 相手デッキ -->
    <div class="filter-bar__item">
      <div class="filter-bar__label">相手デッキ</div>
      <button
        class="filter-bar__btn"
        :class="{ 'filter-bar__btn--active': !!opponentDeck }"
        @click="open('opponentDeck')"
      >{{ opponentDeck || 'すべて' }} ▾</button>
    </div>

    <!-- 対戦期間 -->
    <div class="filter-bar__item">
      <div class="filter-bar__label">対戦期間</div>
      <button
        class="filter-bar__btn"
        :class="{ 'filter-bar__btn--active': !!(dateFrom || dateTo) }"
        @click="open('date')"
      >{{ dateLabel }} ▾</button>
    </div>

    <!-- リセット -->
    <div class="filter-bar__item filter-bar__item--reset">
      <button class="filter-bar__reset" @click="resetFilters">リセット</button>
    </div>
  </div>

  <!-- 汎用モーダル -->
  <FilterSelectModal
    v-if="activeFilter === 'player'"
    title="プレイヤーを選択"
    :items="playerList.map(p => ({ value: p, label: p }))"
    :model-value="player"
    @update:model-value="v => { playerModel = String(v ?? '') }"
    @close="activeFilter = null"
  />
  <FilterSelectModal
    v-if="activeFilter === 'format'"
    title="フォーマットを選択"
    :items="formatList.map(f => ({ value: f, label: f }))"
    :model-value="format"
    @update:model-value="v => { formatModel = String(v ?? '') }"
    @close="activeFilter = null"
  />
  <FilterSelectModal
    v-if="activeFilter === 'opponent'"
    title="対戦相手を選択"
    :items="opponentList.map(o => ({ value: o, label: o }))"
    :model-value="opponent"
    @update:model-value="v => { opponentModel = String(v ?? '') }"
    @close="activeFilter = null"
  />
  <FilterSelectModal
    v-if="activeFilter === 'version'"
    title="バージョンを選択"
    :items="versionList.map(v => ({ value: v.id, label: `v${v.version_number}${v.memo ? ' ' + v.memo : ''}` }))"
    :model-value="versionId"
    @update:model-value="v => { versionId = (v as number | null) }"
    @close="activeFilter = null"
  />
  <FilterSelectModal
    v-if="activeFilter === 'opponentDeck'"
    title="相手デッキを選択"
    :items="opponentDeckList.map(d => ({ value: d, label: d }))"
    :model-value="opponentDeck"
    @update:model-value="v => { opponentDeck = String(v ?? '') }"
    @close="activeFilter = null"
  />

  <!-- デッキ専用モーダル -->
  <DeckSelectModal
    v-if="activeFilter === 'deck'"
    :deck-list="deckList"
    :deck-name-list="deckNameList"
    :deck-id="deckId"
    :deck="deck"
    @select-deck-id="id => { deckId = id }"
    @select-deck="name => { deck = name }"
    @close="activeFilter = null"
  />

  <!-- 日付範囲モーダル -->
  <DateRangeModal
    v-if="activeFilter === 'date'"
    :date-from="dateFrom"
    :date-to="dateTo"
    @update:date-from="v => { dateFrom = v }"
    @update:date-to="v => { dateTo = v }"
    @close="activeFilter = null"
  />
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useFilterState } from '../composables/useFilterState'
import FilterSelectModal from './FilterSelectModal.vue'
import DeckSelectModal from './DeckSelectModal.vue'
import DateRangeModal from './DateRangeModal.vue'

withDefaults(defineProps<{ showPlayer?: boolean }>(), { showPlayer: true })

const {
  playerModel, opponentModel, formatModel,
  deckId, deck, versionId, opponentDeck, dateFrom, dateTo,
  player, opponent, format,
  playerList, opponentList, deckList, deckNameList, versionList, opponentDeckList, formatList,
  resetFilters,
} = useFilterState()

type ActiveFilter = 'player' | 'format' | 'opponent' | 'deck' | 'version' | 'opponentDeck' | 'date' | null
const activeFilter = ref<ActiveFilter>(null)

function open(f: ActiveFilter) {
  activeFilter.value = f
}

const deckLabel = computed(() => {
  if (deckId.value) {
    return deckList.value.find(d => d.id === deckId.value)?.name ?? 'すべて'
  }
  return deck.value || 'すべて'
})

const versionLabel = computed(() => {
  if (!versionId.value) return 'すべて'
  const v = versionList.value.find(v => v.id === versionId.value)
  return v ? `v${v.version_number}${v.memo ? ' ' + v.memo : ''}` : 'すべて'
})

const dateLabel = computed(() => {
  if (!dateFrom.value && !dateTo.value) return 'すべての期間'
  if (dateFrom.value && !dateTo.value) return `${dateFrom.value} 〜`
  if (!dateFrom.value && dateTo.value) return `〜 ${dateTo.value}`
  return `${dateFrom.value} 〜 ${dateTo.value}`
})
</script>

<style scoped>
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 8px;
}

.filter-bar__item {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.filter-bar__item--reset {
  justify-content: flex-end;
}

.filter-bar__label {
  font-size: 10px;
  color: #7a6a55;
}

.filter-bar__btn {
  padding: 4px 10px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  background: #fff;
  color: #2c2416;
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
  text-align: left;
  white-space: nowrap;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.filter-bar__btn:hover { background: #faf7f0; }

.filter-bar__btn--active {
  border-color: #4a6fa5;
  color: #4a6fa5;
  font-weight: bold;
}

.filter-bar__btn--disabled {
  opacity: 0.4;
  cursor: default;
}

.filter-bar__reset {
  padding: 4px 10px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  background: #faf7f0;
  color: #7a6a55;
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
}
.filter-bar__reset:hover { background: #f0ece0; }
</style>
