<template>
  <div class="accordion">
    <button class="accordion__header" @click="toggle">
      <span class="accordion__title">
        ゲーム {{ game.game_number }}
        <span class="accordion__meta">先手: {{ game.first_player }} / {{ game.turns }} ターン / 勝者: {{ game.winner }}</span>
      </span>
      <span class="accordion__icon">{{ open ? '▲' : '▼' }}</span>
    </button>

    <div class="accordion__sub">
      <span v-for="(count, player) in game.mulligans" :key="player" class="accordion__mulligan">
        {{ player }}: マリガン {{ count }} 回
      </span>
    </div>

    <div v-if="open" class="accordion__body">
      <div v-if="loading" class="accordion__loading">読み込み中...</div>
      <ActionLog v-else-if="actions" :actions="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import ActionLog from './ActionLog.vue'
import { fetchActionLog, type ActionEntry, type GameSummary } from '../api/matches'
import { useToast } from '../composables/useToast'

const props = defineProps<{ game: GameSummary; matchId: string }>()

const { showError } = useToast()
const open = ref(false)
const actions = ref<ActionEntry[] | null>(null)
const loading = ref(false)

async function toggle() {
  open.value = !open.value
  if (open.value && actions.value === null) {
    loading.value = true
    try {
      const res = await fetchActionLog(props.matchId, props.game.game_id)
      actions.value = res.actions
    } catch (e) {
      showError(e instanceof Error ? e.message : 'アクションログの取得に失敗しました')
      open.value = false
    } finally {
      loading.value = false
    }
  }
}
</script>

<style scoped>
.accordion {
  border: 1px solid #d8cfc0;
  border-radius: 4px;
  margin-bottom: 8px;
  overflow: hidden;
}

.accordion__header {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: #faf7f0;
  border: none;
  text-align: left;
  cursor: pointer;
  font-size: 14px;
}

.accordion__header:hover {
  background: #f0ece0;
}

.accordion__title {
  font-weight: bold;
  color: #2c2416;
}

.accordion__meta {
  font-weight: normal;
  font-size: 13px;
  color: #7a6a55;
  margin-left: 12px;
}

.accordion__icon {
  color: #7a6a55;
  font-size: 11px;
}

.accordion__sub {
  display: flex;
  gap: 16px;
  padding: 4px 14px 6px;
  background: #f5f0e8;
  font-size: 12px;
  color: #7a6a55;
  border-top: 1px solid #e8e0d0;
}

.accordion__loading {
  padding: 12px 14px;
  color: #7a6a55;
  font-size: 13px;
}

.accordion__body {
  border-top: 1px solid #e8e0d0;
}
</style>
