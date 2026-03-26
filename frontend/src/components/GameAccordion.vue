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
      <template v-else>
        <div v-if="hasSideboard" class="accordion__sideboard">
          <div v-if="sideboardIn.length" class="accordion__sideboard-row">
            <span class="accordion__sideboard-label accordion__sideboard-label--in">サイドイン</span>
            <span class="accordion__sideboard-cards">{{ sideboardIn.join(', ') }}</span>
          </div>
          <div v-if="sideboardOut.length" class="accordion__sideboard-row">
            <span class="accordion__sideboard-label accordion__sideboard-label--out">サイドアウト</span>
            <span class="accordion__sideboard-cards">{{ sideboardOut.join(', ') }}</span>
          </div>
        </div>
        <ActionLog v-if="actions" :actions="actions" />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import ActionLog from './ActionLog.vue'
import { fetchActionLog, type ActionEntry, type GameSummary } from '../api/matches'
import { useToast } from '../composables/useToast'

const props = defineProps<{ game: GameSummary; matchId: string }>()

const { showError } = useToast()
const open = ref(false)
const actions = ref<ActionEntry[] | null>(null)
const loading = ref(false)

function formatSideboard(record: Record<string, number>): string[] {
  return Object.entries(record).sort().map(([name, cnt]) => `${name} x${cnt}`)
}

const hasSideboard = computed(() =>
  (props.game.sideboard_in && Object.keys(props.game.sideboard_in).length > 0) ||
  (props.game.sideboard_out && Object.keys(props.game.sideboard_out).length > 0)
)
const sideboardIn = computed(() =>
  props.game.sideboard_in ? formatSideboard(props.game.sideboard_in) : []
)
const sideboardOut = computed(() =>
  props.game.sideboard_out ? formatSideboard(props.game.sideboard_out) : []
)

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

.accordion__sideboard {
  padding: 8px 14px;
  background: #f5f0e8;
  border-bottom: 1px solid #e8e0d0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.accordion__sideboard-row {
  display: flex;
  gap: 8px;
  font-size: 12px;
  align-items: baseline;
}

.accordion__sideboard-label {
  font-weight: 600;
  white-space: nowrap;
  min-width: 70px;
}

.accordion__sideboard-label--in {
  color: #2a6b2a;
}

.accordion__sideboard-label--out {
  color: #8b2a2a;
}

.accordion__sideboard-cards {
  color: #2c2416;
  line-height: 1.4;
}
</style>
