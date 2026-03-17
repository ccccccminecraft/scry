<template>
  <div class="match-list">
    <div class="match-list__header">
      <h1 class="match-list__title">対戦履歴</h1>
    </div>

    <!-- フィルターバー -->
    <div class="match-list__filters">
      <div class="filter-group">
        <label class="filter-label">プレイヤー</label>
        <select v-model="playerModel" class="filter-select">
          <option value="">すべて</option>
          <option v-for="p in playerList" :key="p" :value="p">{{ p }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">対戦相手</label>
        <select v-model="opponentModel" class="filter-select">
          <option value="">すべて</option>
          <option v-for="o in opponentList" :key="o" :value="o">{{ o }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">デッキ</label>
        <select v-model="deck" class="filter-select">
          <option value="">すべて</option>
          <option v-for="d in deckList" :key="d" :value="d">{{ d }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">相手デッキ</label>
        <select v-model="opponentDeck" class="filter-select" :disabled="!player">
          <option value="">すべて</option>
          <option v-for="d in opponentDeckList" :key="d" :value="d">{{ d }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">フォーマット</label>
        <select v-model="formatModel" class="filter-select">
          <option value="">すべて</option>
          <option v-for="f in formatList" :key="f" :value="f">{{ f }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">対戦日時（開始）</label>
        <input type="date" v-model="dateFrom" class="filter-date" />
      </div>
      <div class="filter-group">
        <label class="filter-label">対戦日時（終了）</label>
        <input type="date" v-model="dateTo" class="filter-date" />
      </div>
    </div>

    <div v-if="loading" class="match-list__loading">読み込み中...</div>

    <template v-else>
      <div v-if="matches.length > 0" class="table-wrap">
        <table class="table">
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
      </div>

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
import { useToast } from '../composables/useToast'
import { useFilterState } from '../composables/useFilterState'

const { showError } = useToast()
const {
  playerModel, opponentModel, formatModel,
  deck, opponentDeck, dateFrom, dateTo,
  player, opponent, format,
  playerList, opponentList, deckList, opponentDeckList, formatList,
  init,
} = useFilterState()

const matches = ref<MatchSummary[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)

const totalPages = computed(() => Math.ceil(total.value / 10))

async function load() {
  loading.value = true
  try {
    const res = await fetchMatches(10, (page.value - 1) * 10, {
      player: player.value || undefined,
      opponent: opponent.value || undefined,
      deck: deck.value || undefined,
      opponent_deck: opponentDeck.value || undefined,
      format: format.value || undefined,
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined,
    })
    matches.value = res.matches
    total.value = res.total
  } catch (e) {
    showError(e instanceof Error ? e.message : '対戦履歴の取得に失敗しました')
  } finally {
    loading.value = false
  }
}

watch(
  [player, opponent, deck, opponentDeck, format, dateFrom, dateTo],
  () => { page.value = 1; load() },
)

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

async function activate() {
  const playerSet = await init()
  if (!playerSet) load()
}

onMounted(activate)
onActivated(activate)
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

.table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.table {
  width: 100%;
  min-width: 480px;
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
