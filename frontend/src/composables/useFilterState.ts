import { ref, computed } from 'vue'
import {
  fetchPlayers, fetchOpponents, fetchPlayerDecks, fetchOpponentDecks, fetchFormats,
} from '../api/stats'
import { fetchSettings } from '../api/settings'

// ── module-level shared state (全ビューで共有) ────────────────────────────────
const player = ref('')
const opponent = ref('')
const deck = ref('')
const opponentDeck = ref('')
const format = ref('')
const dateFrom = ref('')
const dateTo = ref('')

const playerList = ref<string[]>([])
const opponentList = ref<string[]>([])
const deckList = ref<string[]>([])
const opponentDeckList = ref<string[]>([])
const formatList = ref<string[]>([])

// ── private loaders ───────────────────────────────────────────────────────────

async function _loadAllLists() {
  if (!player.value) {
    opponentList.value = []
    deckList.value = []
    opponentDeckList.value = []
    return
  }
  try {
    const [opps, decks, oppDecks] = await Promise.all([
      fetchOpponents(player.value),
      fetchPlayerDecks(player.value, format.value || undefined),
      fetchOpponentDecks(player.value, opponent.value || undefined, format.value || undefined),
    ])
    opponentList.value = opps
    deckList.value = decks
    opponentDeckList.value = oppDecks
  } catch { /* ignore */ }
}

async function _loadOpponentDeckList() {
  if (!player.value) { opponentDeckList.value = []; return }
  try {
    opponentDeckList.value = await fetchOpponentDecks(
      player.value, opponent.value || undefined, format.value || undefined,
    )
  } catch { /* ignore */ }
}

async function _loadDeckAndOpponentDeckList() {
  if (!player.value) { deckList.value = []; opponentDeckList.value = []; return }
  try {
    const [decks, oppDecks] = await Promise.all([
      fetchPlayerDecks(player.value, format.value || undefined),
      fetchOpponentDecks(player.value, opponent.value || undefined, format.value || undefined),
    ])
    deckList.value = decks
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
      const [players, formats, settings] = await Promise.all([
        fetchPlayers(), fetchFormats(), fetchSettings(),
      ])
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
    opponentDeckList,
    formatList,
    // アクション
    init,
    resetFilters,
  }
}
