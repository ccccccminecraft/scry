<template>
  <div class="action-log">
    <template v-for="group in groupedByTurnPlayer" :key="`${group.turn}:${group.activePlayer}`">
      <div class="action-log__turn-header">
        ターン {{ group.turn }}
        <span class="action-log__turn-player">{{ group.activePlayer }}</span>
      </div>
      <div v-for="a in group.actions" :key="a.sequence" class="action-log__row">
        <span class="action-log__player">{{ a.player }}</span>
        <span class="action-log__type">{{ ACTION_LABELS[a.action_type] ?? a.action_type }}</span>
        <span v-if="a.card_name" class="action-log__card">{{ a.card_name }}</span>
        <span v-if="a.target_name" class="action-log__target">→ {{ a.target_name }}</span>
        <span v-if="a.phase" class="action-log__phase">{{ PHASE_LABELS[a.phase] ?? a.phase }}</span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ActionEntry } from '../api/matches'

const props = defineProps<{ actions: ActionEntry[] }>()

const ACTION_LABELS: Record<string, string> = {
  play:           '土地プレイ',
  cast:           '唱える',
  activate:       '能力起動',
  trigger:        '誘発',
  attack:         '攻撃',
  block:          'ブロック',
  draw:           'ドロー',
  discard:        '捨てる',
  mill:           'ミル',
  damage:         'ダメージ',
  reveal:         '公開',
  counter_gained: 'カウンター追加',
  counter_lost:   'カウンター除去',
  add_counter:    'カウンター追加',
  remove_counter: 'カウンター除去',
  mulligan:       'マリガン',
}

const PHASE_LABELS: Record<string, string> = {
  beginning:         'アンタップ',
  upkeep:            'アップキープ',
  draw_step:         'ドロー',
  main1:             'メイン1',
  begin_combat:      '戦闘開始',
  declare_attackers: '攻撃宣言',
  declare_blockers:  'ブロック宣言',
  combat_damage:     '戦闘ダメージ',
  end_combat:        '戦闘終了',
  main2:             'メイン2',
  ending:            'エンド',
}

const groupedByTurnPlayer = computed(() => {
  const groups: { turn: number; activePlayer: string; actions: ActionEntry[] }[] = []
  for (const a of props.actions) {
    const last = groups.at(-1)
    if (last && last.turn === a.turn && last.activePlayer === a.active_player) {
      last.actions.push(a)
    } else {
      groups.push({ turn: a.turn, activePlayer: a.active_player, actions: [a] })
    }
  }
  return groups
})
</script>

<style scoped>
.action-log {
  font-size: 13px;
  padding: 8px 0;
}

.action-log__turn-header {
  font-weight: bold;
  background: #e8e0d0;
  padding: 3px 12px;
  margin-top: 4px;
  color: #5a4a35;
  font-size: 12px;
}

.action-log__turn-player {
  font-weight: normal;
  color: #4a6fa5;
  margin-left: 8px;
}

.action-log__row {
  display: flex;
  gap: 8px;
  padding: 3px 12px;
  border-bottom: 1px solid #f0ece0;
}

.action-log__row:hover {
  background: #faf7f0;
}

.action-log__player {
  min-width: 100px;
  color: #4a6fa5;
  font-weight: 500;
}

.action-log__type {
  min-width: 90px;
  color: #7a6a55;
}

.action-log__card {
  color: #2c2416;
}

.action-log__target {
  color: #8b4a2a;
}

.action-log__phase {
  margin-left: auto;
  font-size: 11px;
  color: #b0a090;
  white-space: nowrap;
}
</style>
