<template>
  <div class="match-list">
    <div class="match-list__header">
      <h1 class="match-list__title">対戦履歴</h1>
      <button class="match-list__export-btn" @click="openExportModal">AI用エクスポート</button>
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

    <!-- エクスポートモーダル -->
    <div v-if="exportOpen" class="exp-overlay" @click.self="exportOpen = false">
      <div class="exp-modal">
        <div class="exp-modal__title">AI用データエクスポート</div>

        <div class="exp-section-label">フィルター</div>
        <div class="exp-filters">
          <div class="exp-group">
            <label class="exp-label">プレイヤー</label>
            <select v-model="expPlayer" class="exp-select">
              <option v-for="p in playerList" :key="p" :value="p">{{ p }}</option>
            </select>
          </div>
          <div class="exp-group">
            <label class="exp-label">対戦相手</label>
            <select v-model="expOpponent" class="exp-select">
              <option value="">すべて</option>
              <option v-for="o in expOpponentList" :key="o" :value="o">{{ o }}</option>
            </select>
          </div>
          <div class="exp-group">
            <label class="exp-label">使用デッキ</label>
            <select v-model="expDeck" class="exp-select">
              <option value="">すべて</option>
              <option v-for="d in expDeckList" :key="d" :value="d">{{ d }}</option>
            </select>
          </div>
          <div class="exp-group">
            <label class="exp-label">相手デッキ</label>
            <select v-model="expOpponentDeck" class="exp-select">
              <option value="">すべて</option>
              <option v-for="d in expOpponentDeckList" :key="d" :value="d">{{ d }}</option>
            </select>
          </div>
          <div class="exp-group">
            <label class="exp-label">フォーマット</label>
            <select v-model="expFormat" class="exp-select">
              <option value="">すべて</option>
              <option v-for="f in formatList" :key="f" :value="f">{{ f }}</option>
            </select>
          </div>
          <div class="exp-group">
            <label class="exp-label">対戦日（開始）</label>
            <input v-model="expDateFrom" type="date" class="exp-select" />
          </div>
          <div class="exp-group">
            <label class="exp-label">対戦日（終了）</label>
            <input v-model="expDateTo" type="date" class="exp-select" />
          </div>
        </div>

        <div class="exp-section-label">出力内容</div>
        <div class="exp-radios">
          <label class="exp-radio">
            <input type="radio" v-model="expDetailLevel" value="summary" />
            サマリーのみ（統計サマリー＋デッキ別勝率）
          </label>
          <label class="exp-radio">
            <input type="radio" v-model="expDetailLevel" value="matches" />
            マッチ一覧あり（＋各マッチの基本情報・ゲーム結果）
          </label>
          <label class="exp-radio">
            <input type="radio" v-model="expDetailLevel" value="actions" />
            アクション詳細あり（＋各ゲームのターン別アクション）
          </label>
        </div>

        <div class="exp-section-label">件数上限</div>
        <div class="exp-limit-row">
          <span class="exp-label">直近</span>
          <input v-model.number="expLimit" type="number" min="1" max="1000" class="exp-limit-input" />
          <span class="exp-label">件</span>
        </div>

        <div v-if="expConfirmMsg" class="exp-confirm">
          <p class="exp-confirm__msg">⚠ {{ expConfirmMsg }}</p>
          <div class="exp-confirm__btns">
            <button class="exp-btn" @click="expConfirmMsg = ''">キャンセル</button>
            <button class="exp-btn exp-btn--primary" @click="confirmExport" :disabled="expDownloading">続ける</button>
          </div>
        </div>

        <div class="exp-modal__footer">
          <button class="exp-btn" @click="exportOpen = false">閉じる</button>
          <button
            v-if="!expConfirmMsg"
            class="exp-btn exp-btn--primary"
            :disabled="!expPlayer || expDownloading"
            @click="runExport"
          >{{ expDownloading ? '処理中…' : 'ダウンロード' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onActivated } from 'vue'

defineOptions({ name: 'MatchListView' })
import { fetchMatches, fetchExportCount, fetchExportMarkdown, type MatchSummary, type ExportDetailLevel } from '../api/matches'
import { fetchPlayers, fetchOpponents, fetchPlayerDecks, fetchOpponentDecks, fetchFormats } from '../api/stats'
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

const totalPages = computed(() => Math.ceil(total.value / 50))

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

// ── エクスポートモーダル ───────────────────────────────────────────────────
const exportOpen = ref(false)
const expPlayer = ref('')
const expOpponent = ref('')
const expDeck = ref('')
const expOpponentDeck = ref('')
const expFormat = ref('')
const expDateFrom = ref('')
const expDateTo = ref('')
const expDetailLevel = ref<ExportDetailLevel>('matches')
const expLimit = ref(200)
const expOpponentList = ref<string[]>([])
const expDeckList = ref<string[]>([])
const expOpponentDeckList = ref<string[]>([])
const expDownloading = ref(false)
const expConfirmMsg = ref('')

async function openExportModal() {
  expPlayer.value = filterPlayer.value || (playerList.value[0] ?? '')
  expOpponent.value = ''
  expDeck.value = ''
  expOpponentDeck.value = ''
  expFormat.value = filterFormat.value
  expDateFrom.value = filterDateFrom.value
  expDateTo.value = filterDateTo.value
  expDetailLevel.value = 'matches'
  expLimit.value = 200
  expConfirmMsg.value = ''
  await loadExpOpponents()
  exportOpen.value = true
}

async function loadExpOpponents() {
  if (!expPlayer.value) { expOpponentList.value = []; return }
  try {
    const [opps, decks] = await Promise.all([
      fetchOpponents(expPlayer.value),
      fetchPlayerDecks(expPlayer.value),
    ])
    expOpponentList.value = opps
    expDeckList.value = decks
  } catch { /* ignore */ }
}

async function loadExpOpponentDecks() {
  if (!expPlayer.value) { expOpponentDeckList.value = []; return }
  try {
    expOpponentDeckList.value = await fetchOpponentDecks(
      expPlayer.value,
      expOpponent.value || undefined,
    )
  } catch { /* ignore */ }
}

watch(expPlayer, () => {
  expOpponent.value = ''
  expDeck.value = ''
  expOpponentDeck.value = ''
  loadExpOpponents()
})

watch(expOpponent, () => {
  expOpponentDeck.value = ''
  loadExpOpponentDecks()
})

async function runExport() {
  if (!expPlayer.value) return
  expDownloading.value = true
  expConfirmMsg.value = ''
  try {
    const filters = {
      player: expPlayer.value,
      opponent: expOpponent.value || undefined,
      deck: expDeck.value || undefined,
      opponent_deck: expOpponentDeck.value || undefined,
      format: expFormat.value || undefined,
      date_from: expDateFrom.value || undefined,
      date_to: expDateTo.value || undefined,
    }
    const count = await fetchExportCount(filters)

    const warnings: string[] = []
    if (count > expLimit.value) {
      warnings.push(`${count} 件中直近 ${expLimit.value} 件をエクスポートします。`)
    }
    if (expDetailLevel.value === 'actions' && Math.min(count, expLimit.value) > 50) {
      warnings.push('アクション詳細を含むためファイルサイズが大きくなる可能性があります。')
    }

    if (warnings.length > 0) {
      expConfirmMsg.value = warnings.join(' ') + ' 続けますか？'
      expDownloading.value = false
      return
    }

    await doDownload(filters)
  } catch (e) {
    showError(e instanceof Error ? e.message : 'エクスポートに失敗しました')
    expDownloading.value = false
  }
}

async function confirmExport() {
  if (!expPlayer.value) return
  expConfirmMsg.value = ''
  expDownloading.value = true
  const filters = {
    player: expPlayer.value,
    opponent: expOpponent.value || undefined,
    deck: expDeck.value || undefined,
    opponent_deck: expOpponentDeck.value || undefined,
    format: expFormat.value || undefined,
    date_from: expDateFrom.value || undefined,
    date_to: expDateTo.value || undefined,
  }
  await doDownload(filters)
}

async function doDownload(filters: Record<string, string | undefined>) {
  try {
    const markdown = await fetchExportMarkdown({
      ...filters,
      detail_level: expDetailLevel.value,
      limit: expLimit.value,
    } as any)
    const blob = new Blob([markdown], { type: 'text/plain; charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const now = new Date()
    const dateStr = now.getFullYear().toString()
      + String(now.getMonth() + 1).padStart(2, '0')
      + String(now.getDate()).padStart(2, '0')
      + String(now.getHours()).padStart(2, '0')
      + String(now.getMinutes()).padStart(2, '0')
      + String(now.getSeconds()).padStart(2, '0')
    a.href = url
    a.download = `scry_export_${expPlayer.value}_${dateStr}.md`
    a.click()
    URL.revokeObjectURL(url)
    exportOpen.value = false
  } catch (e) {
    showError(e instanceof Error ? e.message : 'ダウンロードに失敗しました')
  } finally {
    expDownloading.value = false
  }
}

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
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.match-list__title {
  font-size: 1.2rem;
  margin-bottom: 0;
}

.match-list__export-btn {
  padding: 6px 14px;
  background: #4a6fa5;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
}

.match-list__export-btn:hover {
  background: #3a5f95;
}

/* エクスポートモーダル */
.exp-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}

.exp-modal {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  width: min(640px, 92vw);
  max-height: 85vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.exp-modal__title {
  font-size: 15px;
  font-weight: bold;
  color: #2c2416;
}

.exp-section-label {
  font-size: 11px;
  font-weight: bold;
  color: #7a6a55;
  border-bottom: 1px solid #e0d8c8;
  padding-bottom: 4px;
  margin-top: 4px;
}

.exp-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.exp-group {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.exp-label {
  font-size: 11px;
  color: #7a6a55;
}

.exp-select {
  padding: 4px 8px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 13px;
  background: #fff;
  color: #2c2416;
  font-family: inherit;
}

.exp-radios {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.exp-radio {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #2c2416;
  cursor: pointer;
}

.exp-limit-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.exp-limit-input {
  width: 72px;
  padding: 4px 8px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 13px;
  text-align: right;
}

.exp-confirm {
  background: #fff8e8;
  border: 1px solid #e0c870;
  border-radius: 6px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.exp-confirm__msg {
  font-size: 13px;
  color: #7a5a00;
}

.exp-confirm__btns {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.exp-modal__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 4px;
}

.exp-btn {
  padding: 7px 16px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  background: #faf7f0;
  font-size: 13px;
  cursor: pointer;
  color: #2c2416;
}

.exp-btn--primary {
  background: #4a6fa5;
  border-color: #4a6fa5;
  color: #fff;
}

.exp-btn--primary:hover:not(:disabled) {
  background: #3a5f95;
}

.exp-btn:disabled {
  opacity: 0.4;
  cursor: default;
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
