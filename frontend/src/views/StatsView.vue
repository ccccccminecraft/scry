<template>
  <div class="stats">
    <div class="stats__header">
      <h1 class="stats__title">統計</h1>
    </div>
    <div class="stats__filters">
      <FilterBar />
    </div>

    <div v-if="playerList.length === 0" class="stats__empty">
      対戦ログがありません
    </div>

    <template v-else-if="stats">
      <!-- サマリーカード -->
      <div class="stats__summary">
        <div class="stats__card">
          <div class="stats__card-label">総試合数</div>
          <div class="stats__card-value">{{ stats.total_matches }}</div>
        </div>
        <div class="stats__card">
          <div class="stats__card-label">勝率</div>
          <div class="stats__card-value">{{ pct(stats.win_rate) }}</div>
        </div>
        <div class="stats__card">
          <div class="stats__card-label">平均ターン数</div>
          <div class="stats__card-value">{{ stats.avg_turns.toFixed(1) }}</div>
        </div>
        <div class="stats__card">
          <div class="stats__card-label">マリガン率</div>
          <div class="stats__card-value">{{ pct(stats.mulligan_rate) }}</div>
        </div>
      </div>

      <!-- グラフ行 -->
      <div class="stats__charts">
        <!-- 勝率推移 -->
        <div class="stats__chart-box stats__chart-box--wide">
          <div class="stats__chart-title-row">
            <div class="stats__chart-title">
              勝率推移（{{ historyMode === 0 ? '全' : '直近' }}{{ stats.win_rate_history.length }}試合）
            </div>
            <select v-model="historyMode" class="stats__history-select" @change="loadStats">
              <option :value="20">直近20試合</option>
              <option :value="0">全試合</option>
            </select>
          </div>
          <WinRateHistoryChart
            v-if="stats.win_rate_history.length > 0"
            :data="stats.win_rate_history"
          />
          <div v-else class="stats__no-data">データなし</div>
        </div>

        <!-- 先手/後手 -->
        <div class="stats__chart-box">
          <div class="stats__chart-title">先手 / 後手 勝率</div>
          <FirstSecondChart
            :firstRate="stats.first_play_win_rate"
            :secondRate="stats.second_play_win_rate"
          />
        </div>

        <!-- デッキ別 -->
        <div v-if="stats.deck_stats.length > 0" class="stats__chart-box">
          <div class="stats__chart-title">デッキ別勝率</div>
          <DeckStatsChart :data="stats.deck_stats" />
        </div>
      </div>

      <!-- カード統計テーブル -->
      <div class="stats__section">
        <div class="stats__section-title stats__section-title--toggle" @click="cardStatsOpen = !cardStatsOpen">
          <span class="stats__section-caret">{{ cardStatsOpen ? '▼' : '▶' }}</span>
          カード統計
        </div>
        <template v-if="cardStatsOpen">
          <div class="stats__card-tabs">
            <button
              class="stats__card-tab"
              :class="{ 'stats__card-tab--active': cardStatsPerspective === 'self' }"
              @click="cardStatsPerspective = 'self'"
            >選択プレイヤー（Top {{ cardStats.length }}）</button>
            <button
              class="stats__card-tab"
              :class="{ 'stats__card-tab--active': cardStatsPerspective === 'opponent' }"
              @click="cardStatsPerspective = 'opponent'"
            >対戦相手（Top {{ opponentCardStats.length }}）</button>
          </div>
          <div v-if="activeCardStats.length > 0" class="stats__table-wrap">
            <table class="stats__table">
              <thead>
                <tr>
                  <th>カード名</th>
                  <th class="stats__th-num stats__th-sort" @click="toggleSort('play_count')">
                    使用回数 <span class="stats__sort-icon">{{ sortIcon('play_count') }}</span>
                  </th>
                  <th class="stats__th-num stats__th-sort" @click="toggleSort('game_count')">
                    登場ゲーム <span class="stats__sort-icon">{{ sortIcon('game_count') }}</span>
                  </th>
                  <th class="stats__th-num stats__th-sort" @click="toggleSort('win_rate')">
                    {{ cardStatsPerspective === 'self' ? '勝率' : '選択プレイヤー勝率' }}
                    <span class="stats__sort-icon">{{ sortIcon('win_rate') }}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="c in sortedActiveCardStats" :key="c.card_name">
                  <td>{{ c.card_name }}</td>
                  <td class="stats__td-num">{{ c.play_count }}</td>
                  <td class="stats__td-num">{{ c.game_count }}</td>
                  <td class="stats__td-num">{{ pct(c.win_rate) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="stats__no-data">データなし</div>
        </template>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onActivated } from 'vue'

defineOptions({ name: 'StatsView' })
import { useToast } from '../composables/useToast'
import { fetchStats, fetchCardStats, type StatsResponse, type CardStat } from '../api/stats'
import { useFilterState } from '../composables/useFilterState'
import WinRateHistoryChart from '../components/charts/WinRateHistoryChart.vue'
import FirstSecondChart from '../components/charts/FirstSecondChart.vue'
import DeckStatsChart from '../components/charts/DeckStatsChart.vue'
import FilterBar from '../components/FilterBar.vue'

const { showError } = useToast()
const {
  useDeckManager, deckId, deck, versionId, opponentDeck, dateFrom, dateTo,
  player, opponent, format,
  playerList,
  minDeckMatches,
  init,
} = useFilterState()

const stats = ref<StatsResponse | null>(null)
const historyMode = ref<number>(20)
const cardStats = ref<CardStat[]>([])
const opponentCardStats = ref<CardStat[]>([])

type SortKey = 'play_count' | 'game_count' | 'win_rate'
const sortKey = ref<SortKey>('play_count')
const sortAsc = ref(false)
const cardStatsOpen = ref(false)
const cardStatsPerspective = ref<'self' | 'opponent'>('self')

function toggleSort(key: SortKey) {
  if (sortKey.value === key) {
    sortAsc.value = !sortAsc.value
  } else {
    sortKey.value = key
    sortAsc.value = false
  }
}

function sortIcon(key: SortKey) {
  if (sortKey.value !== key) return '↕'
  return sortAsc.value ? '↑' : '↓'
}

const activeCardStats = computed(() =>
  cardStatsPerspective.value === 'self' ? cardStats.value : opponentCardStats.value
)

const sortedActiveCardStats = computed(() => {
  const key = sortKey.value
  const dir = sortAsc.value ? 1 : -1
  return [...activeCardStats.value].sort((a, b) => (a[key] - b[key]) * dir)
})


const pct = (v: number) => `${(v * 100).toFixed(1)}%`

async function loadAll() {
  await Promise.all([loadStats(), loadCardStats(), loadOpponentCardStats()])
}

async function loadStats() {
  if (!player.value) return
  try {
    stats.value = await fetchStats({
      player: player.value,
      opponent: opponent.value || undefined,
      deck_id: useDeckManager.value && !versionId.value ? (deckId.value ?? undefined) : undefined,
      deck: useDeckManager.value ? undefined : (deck.value || undefined),
      version_id: useDeckManager.value ? (versionId.value ?? undefined) : undefined,
      opponent_deck: opponentDeck.value || undefined,
      format: format.value || undefined,
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined,
      history_size: historyMode.value,
      min_deck_matches: minDeckMatches.value,
    })
  } catch {
    showError('統計の取得に失敗しました')
  }
}

function _deckFilters() {
  if (!useDeckManager.value) return { deck: deck.value || undefined }
  if (versionId.value) return { version_id: versionId.value }
  return { deck_id: deckId.value ?? undefined }
}

async function loadCardStats() {
  if (!player.value) return
  const filters = {
    player: player.value,
    opponent: opponent.value || undefined,
    ..._deckFilters(),
    opponent_deck: opponentDeck.value || undefined,
    format: format.value || undefined,
    date_from: dateFrom.value || undefined,
    date_to: dateTo.value || undefined,
  }
  try {
    cardStats.value = await fetchCardStats(filters, 20, 'self')
  } catch {
    showError('カード統計の取得に失敗しました')
  }
}

async function loadOpponentCardStats() {
  if (!player.value) return
  const filters = {
    player: player.value,
    opponent: opponent.value || undefined,
    ..._deckFilters(),
    opponent_deck: opponentDeck.value || undefined,
    format: format.value || undefined,
    date_from: dateFrom.value || undefined,
    date_to: dateTo.value || undefined,
  }
  try {
    opponentCardStats.value = await fetchCardStats(filters, 20, 'opponent')
  } catch {
    showError('相手カード統計の取得に失敗しました')
  }
}

watch(
  [player, opponent, useDeckManager, deckId, deck, versionId, opponentDeck, format, dateFrom, dateTo],
  loadAll,
)

async function activate() {
  const playerSet = await init()
  if (!playerSet) loadAll()
}

onMounted(activate)
onActivated(activate)
</script>

<style scoped>
.stats {
  padding: 24px;

}

.stats__header {
  margin-bottom: 12px;
}

.stats__title {
  font-size: 1.2rem;
  font-weight: bold;
  color: #2c2416;
  margin-right: 8px;
}

.stats__filters {
  margin-bottom: 16px;
  padding: 10px 16px;
  background: #fff;
  border: 1px solid #e0d8c8;
  border-radius: 6px;
}

.stats__empty {
  color: #7a6a55;
  padding: 40px 0;
  text-align: center;
}

.stats__summary {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.stats__card {
  background: #fff;
  border: 1px solid #e0d8c8;
  border-radius: 6px;
  padding: 12px 20px;
  min-width: 120px;
}

.stats__card-label {
  font-size: 11px;
  color: #7a6a55;
  margin-bottom: 4px;
}

.stats__card-value {
  font-size: 1.5rem;
  font-weight: bold;
  color: #2c2416;
}

.stats__charts {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 24px;
}

.stats__chart-box {
  background: #fff;
  border: 1px solid #e0d8c8;
  border-radius: 6px;
  padding: 12px 16px;
  flex: 1;
  min-width: 220px;
}

.stats__chart-box--wide {
  flex: 2;
  min-width: 340px;
}

.stats__chart-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.stats__chart-title {
  font-size: 12px;
  color: #7a6a55;
  font-weight: bold;
}

.stats__history-select {
  padding: 2px 6px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  background: #fff;
  color: #2c2416;
  font-size: 11px;
  font-family: inherit;
}

.stats__no-data {
  color: #b0a090;
  font-size: 12px;
  padding: 16px 0;
  text-align: center;
}

.stats__section {
  background: #fff;
  border: 1px solid #e0d8c8;
  border-radius: 6px;
  padding: 12px 16px;
}

.stats__section-title {
  font-size: 12px;
  color: #7a6a55;
  font-weight: bold;
  margin-bottom: 10px;
}

.stats__section-title--toggle {
  cursor: pointer;
  user-select: none;
}

.stats__section-title--toggle:hover {
  color: #4a6fa5;
}

.stats__section-caret {
  font-size: 10px;
  margin-right: 4px;
}

.stats__card-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 10px;
}

.stats__card-tab {
  padding: 3px 12px;
  border: 1px solid #c8b89a;
  border-radius: 3px;
  background: #faf7f0;
  color: #7a6a55;
  font-size: 11px;
  cursor: pointer;
}

.stats__card-tab:hover {
  background: #f0ece0;
}

.stats__card-tab--active {
  background: #4a6fa5;
  border-color: #4a6fa5;
  color: #fff;
}

.stats__table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.stats__table {
  width: 100%;
  min-width: 360px;
  border-collapse: collapse;
  font-size: 13px;
}

.stats__table th {
  text-align: left;
  padding: 6px 8px;
  border-bottom: 2px solid #e0d8c8;
  color: #7a6a55;
  font-size: 11px;
  font-weight: normal;
}

.stats__th-num,
.stats__td-num {
  text-align: right;
}

.stats__th-sort {
  cursor: pointer;
  user-select: none;
}

.stats__th-sort:hover {
  color: #4a6fa5;
}

.stats__sort-icon {
  color: #b0a090;
  font-size: 10px;
}

.stats__table td {
  padding: 5px 8px;
  border-bottom: 1px solid #f0ece0;
}

.stats__table tbody tr:hover {
  background: #faf7f0;
}
</style>
