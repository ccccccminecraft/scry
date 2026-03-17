<template>
  <div class="stats">
    <div class="stats__header">
      <h1 class="stats__title">統計</h1>
    </div>
    <div class="stats__filters">
      <div class="stats__filter-group">
        <label class="stats__label">プレイヤー</label>
        <select v-model="selectedPlayer" class="stats__select">
          <option v-for="p in playerList" :key="p" :value="p">{{ p }}</option>
        </select>
      </div>
      <div class="stats__filter-group">
        <label class="stats__label">対戦相手</label>
        <select v-model="selectedOpponent" class="stats__select">
          <option value="">すべて</option>
          <option v-for="o in opponentList" :key="o" :value="o">{{ o }}</option>
        </select>
      </div>
      <div class="stats__filter-group">
        <label class="stats__label">デッキ</label>
        <select v-model="selectedDeck" class="stats__select">
          <option value="">すべて</option>
          <option v-for="d in deckList" :key="d" :value="d">{{ d }}</option>
        </select>
      </div>
      <div class="stats__filter-group">
        <label class="stats__label">相手デッキ</label>
        <select v-model="selectedOpponentDeck" class="stats__select">
          <option value="">すべて</option>
          <option v-for="d in opponentDeckList" :key="d" :value="d">{{ d }}</option>
        </select>
      </div>
      <div class="stats__filter-group">
        <label class="stats__label">フォーマット</label>
        <select v-model="selectedFormat" class="stats__select">
          <option value="">すべて</option>
          <option v-for="f in formatList" :key="f" :value="f">{{ f }}</option>
        </select>
      </div>
      <div class="stats__filter-group">
        <label class="stats__label">対戦日時（開始）</label>
        <input type="date" v-model="dateFrom" class="stats__input-date" />
      </div>
      <div class="stats__filter-group">
        <label class="stats__label">対戦日時（終了）</label>
        <input type="date" v-model="dateTo" class="stats__input-date" />
      </div>
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
          <div class="stats__chart-title">勝率推移（直近{{ stats.win_rate_history.length }}試合）</div>
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
          <table class="stats__table" v-if="activeCardStats.length > 0">
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
import {
  fetchStats, fetchCardStats, fetchPlayers, fetchOpponents, fetchOpponentDecks, fetchFormats,
  type StatsResponse, type CardStat,
} from '../api/stats'
import WinRateHistoryChart from '../components/charts/WinRateHistoryChart.vue'
import FirstSecondChart from '../components/charts/FirstSecondChart.vue'
import DeckStatsChart from '../components/charts/DeckStatsChart.vue'

const { showError } = useToast()

const playerList = ref<string[]>([])
const opponentList = ref<string[]>([])
const opponentDeckList = ref<string[]>([])
const formatList = ref<string[]>([])
const selectedPlayer = ref('')
const selectedOpponent = ref('')
const selectedDeck = ref('')
const selectedOpponentDeck = ref('')
const selectedFormat = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const stats = ref<StatsResponse | null>(null)
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

const deckList = computed(() =>
  stats.value?.deck_stats.map(d => d.deck_name) ?? []
)

const pct = (v: number) => `${(v * 100).toFixed(1)}%`

async function loadAll() {
  await Promise.all([loadStats(), loadCardStats(), loadOpponentCardStats()])
}

async function loadStats() {
  if (!selectedPlayer.value) return
  try {
    stats.value = await fetchStats({
      player: selectedPlayer.value,
      opponent: selectedOpponent.value || undefined,
      deck: selectedDeck.value || undefined,
      opponent_deck: selectedOpponentDeck.value || undefined,
      format: selectedFormat.value || undefined,
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined,
      history_size: 20,
    })
  } catch {
    showError('統計の取得に失敗しました')
  }
}

async function loadCardStats() {
  if (!selectedPlayer.value) return
  const filters = {
    player: selectedPlayer.value,
    opponent: selectedOpponent.value || undefined,
    deck: selectedDeck.value || undefined,
    opponent_deck: selectedOpponentDeck.value || undefined,
    format: selectedFormat.value || undefined,
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
  if (!selectedPlayer.value) return
  const filters = {
    player: selectedPlayer.value,
    opponent: selectedOpponent.value || undefined,
    deck: selectedDeck.value || undefined,
    opponent_deck: selectedOpponentDeck.value || undefined,
    format: selectedFormat.value || undefined,
    date_from: dateFrom.value || undefined,
    date_to: dateTo.value || undefined,
  }
  try {
    opponentCardStats.value = await fetchCardStats(filters, 20, 'opponent')
  } catch {
    showError('相手カード統計の取得に失敗しました')
  }
}

async function loadOpponents() {
  if (!selectedPlayer.value) return
  try {
    opponentList.value = await fetchOpponents(selectedPlayer.value)
  } catch {
    showError('対戦相手の取得に失敗しました')
  }
}

async function loadOpponentDecks() {
  if (!selectedPlayer.value) {
    opponentDeckList.value = []
    return
  }
  try {
    opponentDeckList.value = await fetchOpponentDecks(
      selectedPlayer.value,
      selectedOpponent.value || undefined,
    )
  } catch {
    // 失敗しても無視
  }
}

watch(selectedPlayer, () => {
  selectedOpponent.value = ''
  selectedDeck.value = ''
  selectedOpponentDeck.value = ''
  loadOpponents()
  loadOpponentDecks()
  loadAll()
})

watch(selectedOpponent, () => {
  selectedOpponentDeck.value = ''
  loadOpponentDecks()
  loadAll()
})

watch([selectedDeck, selectedOpponentDeck, selectedFormat, dateFrom, dateTo], () => {
  loadAll()
})

async function initLists() {
  try {
    const [players, formats] = await Promise.all([fetchPlayers(), fetchFormats()])
    playerList.value = players
    formatList.value = formats
    if (!selectedPlayer.value && playerList.value.length > 0) {
      selectedPlayer.value = playerList.value[0]
      // watch が発火するので loadAll/loadOpponents は不要
    } else if (selectedPlayer.value) {
      loadAll()
    }
  } catch {
    showError('初期データの取得に失敗しました')
  }
}

onMounted(initLists)
onActivated(initLists)
</script>

<style scoped>
.stats {
  padding: 24px;
  max-width: 960px;
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
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
  padding: 10px 16px;
  background: #fff;
  border: 1px solid #e0d8c8;
  border-radius: 6px;
}

.stats__filter-group {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.stats__label {
  font-size: 10px;
  color: #7a6a55;
}

.stats__select {
  padding: 3px 6px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  background: #fff;
  color: #2c2416;
  font-size: 11px;
}

.stats__input-date {
  padding: 3px 6px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  background: #fff;
  color: #2c2416;
  font-size: 11px;
  font-family: inherit;
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

.stats__chart-title {
  font-size: 12px;
  color: #7a6a55;
  margin-bottom: 8px;
  font-weight: bold;
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

.stats__table {
  width: 100%;
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
