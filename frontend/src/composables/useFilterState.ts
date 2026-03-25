import { ref, computed, watch } from 'vue'
import {
  fetchPlayers, fetchOpponents, fetchPlayerDecks, fetchOpponentDecks, fetchFormats,
} from '../api/stats'
import { fetchDecks, fetchVersions, type Deck, type DeckVersionSummary } from '../api/decklist'
import { fetchSettings } from '../api/settings'

// ── localStorage 永続化 ───────────────────────────────────────────────────────
const STORAGE_KEY = 'scry_filter_state'

function _loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    return JSON.parse(raw) as Record<string, unknown>
  } catch { return {} }
}

function _saveToStorage() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      format: format.value,
      opponent: opponent.value,
      deckIds: deckIds.value,
      decks: decks.value,
      opponentDecks: opponentDecks.value,
    }))
  } catch { /* ignore */ }
}

// ── module-level shared state (全ビューで共有) ────────────────────────────────
const _saved = _loadFromStorage()

const player = ref('')
const opponent = ref(typeof _saved.opponent === 'string' ? _saved.opponent : '')
const deckIds = ref<number[]>(Array.isArray(_saved.deckIds) ? (_saved.deckIds as number[]).filter(v => typeof v === 'number') : [])
const decks = ref<string[]>(Array.isArray(_saved.decks) ? (_saved.decks as string[]).filter(v => typeof v === 'string') : [])
const opponentDecks = ref<string[]>(Array.isArray(_saved.opponentDecks) ? (_saved.opponentDecks as string[]).filter(v => typeof v === 'string') : [])
const format = ref(typeof _saved.format === 'string' ? _saved.format : '')
const dateFrom = ref('')
const dateTo = ref('')

const playerList = ref<string[]>([])
const opponentList = ref<string[]>([])
const deckList = ref<Deck[]>([])           // デッキ管理リスト
const deckNameList = ref<string[]>([])     // デッキ定義リスト
const versionList = ref<DeckVersionSummary[]>([])  // 選択中デッキのバージョン一覧
const opponentDeckList = ref<string[]>([])
const formatList = ref<string[]>([])

const versionId = ref<number | null>(null)

// フィルター変更時に localStorage へ保存
watch([format, opponent, deckIds, decks, opponentDecks], _saveToStorage, { deep: true })

// デッキ選択変更時にバージョン一覧を再取得（単一選択時のみ）
watch(deckIds, async (newIds) => {
  versionId.value = null
  if (newIds.length !== 1) { versionList.value = []; return }
  try {
    versionList.value = await fetchVersions(newIds[0])
  } catch { versionList.value = [] }
}, { deep: true })

// フォーマットの表示順
const FORMAT_ORDER = ['standard', 'pioneer', 'modern', 'pauper', 'legacy', 'vintage', 'unknown']

function _sortFormats(formats: string[]): string[] {
  return [...formats].sort((a, b) => {
    const ai = FORMAT_ORDER.indexOf(a)
    const bi = FORMAT_ORDER.indexOf(b)
    const aRank = ai === -1 ? FORMAT_ORDER.length : ai
    const bRank = bi === -1 ? FORMAT_ORDER.length : bi
    return aRank - bRank
  })
}

// settings から取得した最低試合数
const minPlayerMatches = ref(1)
const minDeckMatches = ref(1)

function calcDefaultDateFrom(filter: string, customFrom: string | null): string {
  const today = new Date()
  if (filter === 'this_month') {
    return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-01`
  }
  if (filter === 'last_30_days') {
    const d = new Date(today)
    d.setDate(d.getDate() - 30)
    return d.toISOString().slice(0, 10)
  }
  if (filter === 'custom' && customFrom) {
    return customFrom
  }
  return ''
}

// ── private loaders ───────────────────────────────────────────────────────────

async function _loadAllLists() {
  if (!player.value) {
    opponentList.value = []
    deckList.value = []
    deckNameList.value = []
    opponentDeckList.value = []
    return
  }
  try {
    const [opps, decks, deckNames, oppDecks] = await Promise.all([
      fetchOpponents(player.value),
      fetchDecks(false, format.value || undefined),
      fetchPlayerDecks(player.value, format.value || undefined, minDeckMatches.value),
      fetchOpponentDecks(player.value, opponent.value || undefined, format.value || undefined, minDeckMatches.value),
    ])
    opponentList.value = opps
    deckList.value = decks
    deckNameList.value = deckNames
    opponentDeckList.value = oppDecks
  } catch { /* ignore */ }
}

async function _loadOpponentDeckList() {
  if (!player.value) { opponentDeckList.value = []; return }
  try {
    opponentDeckList.value = await fetchOpponentDecks(
      player.value, opponent.value || undefined, format.value || undefined, minDeckMatches.value,
    )
  } catch { /* ignore */ }
}

async function _loadDeckAndOpponentDeckList() {
  if (!player.value) { deckList.value = []; deckNameList.value = []; opponentDeckList.value = []; return }
  try {
    const [decks, deckNames, oppDecks] = await Promise.all([
      fetchDecks(false, format.value || undefined),
      fetchPlayerDecks(player.value, format.value || undefined, minDeckMatches.value),
      fetchOpponentDecks(player.value, opponent.value || undefined, format.value || undefined, minDeckMatches.value),
    ])
    deckList.value = decks
    deckNameList.value = deckNames
    opponentDeckList.value = oppDecks
  } catch { /* ignore */ }
}

// ── composable ────────────────────────────────────────────────────────────────

export function useFilterState() {
  // v-model 用 computed（setter でリスト再取得・依存フィルターリセットを行う）
  const playerModel = computed({
    get: () => player.value,
    set: (p: string) => {
      player.value = p
      opponent.value = ''
      deckIds.value = []
      decks.value = []
      opponentDecks.value = []
      _loadAllLists()
    },
  })

  const opponentModel = computed({
    get: () => opponent.value,
    set: (o: string) => {
      opponent.value = o
      opponentDecks.value = []
      _loadOpponentDeckList()
    },
  })

  const formatModel = computed({
    get: () => format.value,
    set: (f: string) => {
      format.value = f
      deckIds.value = []
      decks.value = []
      opponentDecks.value = []
      _loadDeckAndOpponentDeckList()
    },
  })

  /**
   * 初期化。playerList / formatList を取得し、未設定なら default_player をセット。
   * @returns player を新たにセットした場合 true（watch が発火するので呼び出し元は追加ロード不要）
   */
  async function init(): Promise<boolean> {
    try {
      const [formats, settings] = await Promise.all([
        fetchFormats(), fetchSettings(),
      ])
      minPlayerMatches.value = settings.min_player_matches ?? 1
      minDeckMatches.value = settings.min_deck_matches ?? 1
      const players = await fetchPlayers(minPlayerMatches.value)
      playerList.value = players
      formatList.value = _sortFormats(formats)
      if (!dateFrom.value) {
        dateFrom.value = calcDefaultDateFrom(
          settings.default_date_filter ?? 'none',
          settings.default_date_filter_from ?? null,
        )
      }
      // 保存済み deckIds のうちリストに存在しないものを除外
      deckIds.value = deckIds.value.filter(id => deckList.value.some(d => d.id === id))

      if (!player.value && players.length > 0) {
        const preferred = settings.default_player
        playerModel.value = (preferred && players.includes(preferred)) ? preferred : players[0]
        return true
      }
    } catch { /* ignore */ }
    return false
  }

  function resetFilters() {
    opponent.value = ''
    deckIds.value = []
    decks.value = []
    versionId.value = null
    opponentDecks.value = []
    format.value = ''
    dateFrom.value = ''
    dateTo.value = ''
    try { localStorage.removeItem(STORAGE_KEY) } catch { /* ignore */ }
    _loadAllLists()
  }

  return {
    // v-model 用 computed
    playerModel,
    opponentModel,
    formatModel,
    // 直接 v-model 可能な ref
    deckIds,
    decks,
    versionId,
    opponentDecks,
    dateFrom,
    dateTo,
    // API 呼び出し用の読み取り ref
    player,
    opponent,
    format,
    // 選択肢リスト
    playerList,
    opponentList,
    deckList,
    deckNameList,
    versionList,
    opponentDeckList,
    formatList,
    // 最低試合数
    minDeckMatches,
    // アクション
    init,
    resetFilters,
    refreshLists: _loadAllLists,
  }
}
