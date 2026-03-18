<template>
  <div class="filter-bar">
    <div v-if="showPlayer" class="filter-bar__group">
      <label class="filter-bar__label">プレイヤー</label>
      <select v-model="playerModel" class="filter-bar__select">
        <option value="">すべて</option>
        <option v-for="p in playerList" :key="p" :value="p">{{ p }}</option>
      </select>
    </div>
    <div class="filter-bar__group">
      <label class="filter-bar__label">フォーマット</label>
      <select v-model="formatModel" class="filter-bar__select">
        <option value="">すべて</option>
        <option v-for="f in formatList" :key="f" :value="f">{{ f }}</option>
      </select>
    </div>
    <div class="filter-bar__group">
      <label class="filter-bar__label">対戦相手</label>
      <select v-model="opponentModel" class="filter-bar__select">
        <option value="">すべて</option>
        <option v-for="o in opponentList" :key="o" :value="o">{{ o }}</option>
      </select>
    </div>
    <div class="filter-bar__group">
      <label class="filter-bar__label">使用デッキ</label>
      <div class="filter-bar__deck-row">
        <select v-if="useDeckManager" v-model="deckId" class="filter-bar__select">
          <option :value="null">すべて</option>
          <option v-for="d in deckList" :key="d.id" :value="d.id">{{ d.name }}</option>
        </select>
        <select v-else v-model="deck" class="filter-bar__select">
          <option value="">すべて</option>
          <option v-for="d in deckNameList" :key="d" :value="d">{{ d }}</option>
        </select>
        <label class="filter-bar__check-label">
          <input type="checkbox" v-model="useDeckManager" />
          デッキ管理
        </label>
      </div>
    </div>
    <div class="filter-bar__group">
      <label class="filter-bar__label">相手デッキ</label>
      <select v-model="opponentDeck" class="filter-bar__select">
        <option value="">すべて</option>
        <option v-for="d in opponentDeckList" :key="d" :value="d">{{ d }}</option>
      </select>
    </div>
    <div class="filter-bar__group">
      <label class="filter-bar__label">対戦日（開始）</label>
      <input v-model="dateFrom" type="date" class="filter-bar__select" />
    </div>
    <div class="filter-bar__group">
      <label class="filter-bar__label">対戦日（終了）</label>
      <input v-model="dateTo" type="date" class="filter-bar__select" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useFilterState } from '../composables/useFilterState'

withDefaults(defineProps<{ showPlayer?: boolean }>(), { showPlayer: true })

const {
  playerModel, opponentModel, formatModel,
  useDeckManager, deckId, deck, opponentDeck, dateFrom, dateTo,
  playerList, opponentList, deckList, deckNameList, opponentDeckList, formatList,
} = useFilterState()
</script>

<style scoped>
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 10px;
}

.filter-bar__group {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.filter-bar__label {
  font-size: 10px;
  color: #7a6a55;
}

.filter-bar__select {
  padding: 3px 6px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 11px;
  background: #fff;
  color: #2c2416;
  font-family: inherit;
}

.filter-bar__deck-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.filter-bar__check-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #7a6a55;
  cursor: pointer;
  white-space: nowrap;
}
</style>
