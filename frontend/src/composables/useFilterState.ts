import { ref, computed, watch } from 'vue'
import {
  fetchPlayers, fetchOpponents, fetchPlayerDecks, fetchOpponentDecks, fetchFormats,
} from '../api/stats'
import { fetchDecks, type Deck } from '../api/decklist'
import { fetchSettings } from '../api/settings'

// ── module-level shared state (全ビューで共有) ────────────────────────────────
const player = ref('')
const opponent = ref('')
const useDeckManager = ref(false)
const deckId = ref<number | null>(null)   // デッキ管理モード用
const deck = ref('')                       // デッキ定義モード用
const opponentDeck = ref('')
const format = ref('')
const dateFrom = ref('')
const dateTo = ref('')

const playerList = ref<string[]>([])
const opponentList = ref<string[]>([])
const deckList = ref<Deck[]>([])           // デッキ管理リスト
const deckNameList = ref<string[]>([])     // デッキ定義リスト
const opponentDeckList = ref<string[]>([])
const formatList = ref<string[]>([])

// モード切替時にデッキ選択をリセット
watch(useDeckManager, () => {
  deckId.value = null
  deck.value = ''
})

// settings から取得した最低試合数
const minPlayerMatches = ref(1)
const minDeckMatches = ref(1)

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
      fetchDecks(),
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
      fetchDecks(),
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
      deckId.value = null
      deck.value = ''
      opponentDeck.value = ''
      _loadAllLists()
    },
  })

  const opponentModel = computed({
    get: () => opponent.value,
    set: (o: string) => {
      opponent.value = o
      opponentDeck.value = ''
      _loadOpponentDeckList()
    },
  })

  const formatModel = computed({
    get: () => format.value,
    set: (f: string) => {
      format.value = f
      deckId.value = null
      deck.value = ''
      opponentDeck.value = ''
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
      formatList.value = formats
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
    deckId.value = null
    deck.value = ''
    opponentDeck.value = ''
    format.value = ''
    dateFrom.value = ''
    dateTo.value = ''
  }

  return {
    // v-model 用 computed
    playerModel,
    opponentModel,
    formatModel,
    // 直接 v-model 可能な ref
    useDeckManager,
    deckId,
    deck,
    opponentDeck,
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
    opponentDeckList,
    formatList,
    // 最低試合数
    minDeckMatches,
    // アクション
    init,
    resetFilters,
  }
}
