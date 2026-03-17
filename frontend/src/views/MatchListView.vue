<template>
  <div class="match-list">
    <div class="match-list__header">
      <h1 class="match-list__title">対戦履歴</h1>
    </div>

    <!-- フィルターバー -->
    <div class="match-list__filters">
      <div class="filter-group">
        <label class="filter-label">プレイヤー</label>
        <select v-model="filterPlayer" class="filter-select">
          <option value="">すべて</option>
          <option v-for="p in playerList" :key="p" :value="p">{{ p }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">対戦相手</label>
        <select v-model="filterOpponent" class="filter-select">
          <option value="">すべて</option>
          <option v-for="o in opponentList" :key="o" :value="o">{{ o }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">デッキ</label>
        <select v-model="filterDeck" class="filter-select">
          <option value="">すべて</option>
          <option v-for="d in deckList" :key="d" :value="d">{{ d }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">相手デッキ</label>
        <select v-model="filterOpponentDeck" class="filter-select" :disabled="!filterPlayer">
          <option value="">すべて</option>
          <option v-for="d in opponentDeckList" :key="d" :value="d">{{ d }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">フォーマット</label>
        <select v-model="filterFormat" class="filter-select">
          <option value="">すべて</option>
          <option v-for="f in formatList" :key="f" :value="f">{{ f }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">対戦日時（開始）</label>
        <input type="date" v-model="filterDateFrom" class="filter-date" />
      </div>
      <div class="filter-group">
        <label class="filter-label">対戦日時（終了）</label>
        <input type="date" v-model="filterDateTo" class="filter-date" />
      </div>
    </div>

    <div v-if="loading" class="match-list__loading">読み込み中...</div>

    <template v-else>
      <table v-if="matches.length > 0" class="table">
        <thead>
          <tr>
            <th>日時</th>
            <th>対戦</th>
            <th>勝者</th>
            <th>ゲーム数</th>
            <th>フォーマット</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="m in matches"
            :key="m.match_id"
            class="table__row"
            @click="$router.push(`/matches/${m.match_id}`)"
          >
            <td>{{ formatDate(m.date) }}</td>
            <td>
              <span class="match-list__player">{{ m.players[0] }}</span>
              <span v-if="m.decks[0]" class="match-list__deck">{{ m.decks[0] }}</span>
              <span class="match-list__vs">vs</span>
              <span class="match-list__player">{{ m.players[1] }}</span>
              <span v-if="m.decks[1]" class="match-list__deck">{{ m.decks[1] }}</span>
            </td>
            <td>{{ m.match_winner }}</td>
            <td>{{ m.game_count }}</td>
            <td>{{ m.format ?? '—' }}</td>
          </tr>
        </tbody>
      </table>

      <p v-else class="match-list__empty">対戦ログがありません</p>

      <div v-if="totalPages > 1" class="pagination">
        <button :disabled="page <= 1" @click="page--">← 前へ</button>
        <span>{{ page }} / {{ totalPages }}</span>
        <button :disabled="page >= totalPages" @click="page++">次へ →</button>
      </div>
    </template>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onActivated } from 'vue'

defineOptions({ name: 'MatchListView' })
import { fetchMatches, type MatchSummary } from '../api/matches'
import { fetchPlayers, fetchOpponents, fetchOpponentDecks, fetchFormats } from '../api/stats'
import { useToast } from '../composables/useToast'

const { showError } = useToast()

const matches = ref<MatchSummary[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)

const playerList = ref<string[]>([])
const opponentList = ref<string[]>([])
const opponentDeckList = ref<string[]>([])
const formatList = ref<string[]>([])

const filterPlayer = ref('')
const filterOpponent = ref('')
const filterDeck = ref('')
const filterOpponentDeck = ref('')
const filterFormat = ref('')
const filterDateFrom = ref('')
const filterDateTo = ref('')

const totalPages = computed(() => Math.ceil(total.value / 10))

const deckList = computed(() => {
  if (!filterPlayer.value) return []
  const decks = new Set<string>()
  matches.value.forEach(m => {
    const idx = m.players.indexOf(filterPlayer.value)
    if (idx >= 0 && m.decks[idx]) decks.add(m.decks[idx]!)
  })
  return [...decks].sort()
})

async function load() {
  loading.value = true
  try {
    const res = await fetchMatches(10, (page.value - 1) * 10, {
      player: filterPlayer.value || undefined,
      opponent: filterOpponent.value || undefined,
      deck: filterDeck.value || undefined,
      opponent_deck: filterOpponentDeck.value || undefined,
      format: filterFormat.value || undefined,
      date_from: filterDateFrom.value || undefined,
      date_to: filterDateTo.value || undefined,
    })
    matches.value = res.matches
    total.value = res.total
  } catch (e) {
    showError(e instanceof Error ? e.message : '対戦履歴の取得に失敗しました')
  } finally {
    loading.value = false
  }
}

async function loadOpponents() {
  if (!filterPlayer.value) {
    opponentList.value = []
    return
  }
  try {
    opponentList.value = await fetchOpponents(filterPlayer.value)
  } catch {
    // 失敗しても無視
  }
}

async function loadOpponentDecks() {
  if (!filterPlayer.value) {
    opponentDeckList.value = []
    return
  }
  try {
    opponentDeckList.value = await fetchOpponentDecks(
      filterPlayer.value,
      filterOpponent.value || undefined,
    )
  } catch {
    // 失敗しても無視
  }
}

watch(filterPlayer, () => {
  filterOpponent.value = ''
  filterDeck.value = ''
  filterOpponentDeck.value = ''
  page.value = 1
  loadOpponents()
  loadOpponentDecks()
  load()
})

watch(filterOpponent, () => {
  filterOpponentDeck.value = ''
  loadOpponentDecks()
  page.value = 1
  load()
})

watch([filterDeck, filterOpponentDeck, filterFormat, filterDateFrom, filterDateTo], () => {
  page.value = 1
  load()
})

watch(page, load)


function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('ja-JP', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function initData() {
  try {
    const [players, formats] = await Promise.all([fetchPlayers(), fetchFormats()])
    playerList.value = players
    formatList.value = formats
  } catch {
    showError('フィルター情報の取得に失敗しました')
  }
  load()
}

onMounted(initData)
onActivated(initData)
</script>

<style scoped>
.match-list {
  padding: 24px;
}

.match-list__header {
  margin-bottom: 16px;
}

.match-list__title {
  font-size: 1.2rem;
  margin-bottom: 0;
}


.match-list__filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
  padding: 10px 16px;
  background: #fff;
  border: 1px solid #e0d8c8;
  border-radius: 6px;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.filter-label {
  font-size: 10px;
  color: #7a6a55;
}

.filter-select,
.filter-date {
  padding: 3px 6px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  background: #fff;
  color: #2c2416;
  font-size: 11px;
  font-family: inherit;
}

.match-list__loading,
.match-list__empty {
  color: #7a6a55;
  padding: 32px 0;
  text-align: center;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.table th {
  text-align: left;
  padding: 8px 12px;
  background: #e8e0d0;
  border-bottom: 2px solid #c8b89a;
  white-space: nowrap;
}

.table td {
  padding: 8px 12px;
  border-bottom: 1px solid #e0d8c8;
}

.table__row {
  cursor: pointer;
}

.match-list__vs {
  margin: 0 6px;
  color: #b0a090;
  font-size: 12px;
}

.match-list__deck {
  margin-left: 4px;
  font-size: 11px;
  color: #7a6a55;
  background: #f0ece0;
  border: 1px solid #d8d0c0;
  border-radius: 3px;
  padding: 0 5px;
}

.table__row:hover td {
  background: #f5f0e8;
}

.pagination {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  justify-content: center;
}

.pagination button {
  padding: 6px 14px;
  background: #faf7f0;
  border: 1px solid #c8b89a;
  border-radius: 4px;
}

.pagination button:disabled {
  opacity: 0.4;
  cursor: default;
}

.pagination button:not(:disabled):hover {
  background: #f0ece0;
}
</style>
