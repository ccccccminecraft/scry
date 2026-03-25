<template>
  <div class="ai-export">
    <h1 class="ai-export__title">AI用エクスポート</h1>

    <!-- フィルター（タブ共有） -->
    <div class="ai-export__section">
      <div class="ai-export__section-label">フィルター</div>
      <FilterBar />
    </div>

    <!-- タブ切り替え -->
    <div class="ai-export__tabs">
      <button
        class="ai-export__tab"
        :class="{ 'ai-export__tab--active': activeTab === 'matches' }"
        @click="activeTab = 'matches'"
      >対戦ログ</button>
      <button
        class="ai-export__tab"
        :class="{ 'ai-export__tab--active': activeTab === 'cards' }"
        @click="activeTab = 'cards'"
      >カード辞書</button>
    </div>

    <!-- 対戦ログタブ -->
    <template v-if="activeTab === 'matches'">
      <!-- 対象件数 -->
      <div class="ai-export__section ai-export__count-section">
        対象: <span class="ai-export__count-num">{{ matchCount !== null ? `${matchCount} 件` : '—' }}</span>
      </div>

      <!-- 出力内容 -->
      <div class="ai-export__section">
        <div class="ai-export__section-label">出力内容</div>
        <div class="ai-export__checks">
          <label class="ai-export__checkbox-label">
            <input type="checkbox" v-model="inclSummary" class="ai-export__checkbox" />
            サマリー
          </label>
          <label class="ai-export__checkbox-label">
            <input type="checkbox" v-model="inclDeckStats" class="ai-export__checkbox" />
            デッキ別勝率
          </label>
          <label class="ai-export__checkbox-label">
            <input type="checkbox" v-model="inclCardStats" class="ai-export__checkbox" />
            カード統計
          </label>
          <label class="ai-export__checkbox-label">
            <input type="checkbox" v-model="inclDeckList" class="ai-export__checkbox" />
            デッキリスト
          </label>
          <label class="ai-export__checkbox-label">
            <input type="checkbox" v-model="inclMatches" class="ai-export__checkbox" />
            対戦一覧
          </label>
          <label class="ai-export__checkbox-label" :class="{ 'ai-export__checkbox-label--disabled': !inclMatches }">
            <input type="checkbox" v-model="inclActions" class="ai-export__checkbox" :disabled="!inclMatches" />
            アクション詳細
          </label>
        </div>
      </div>

      <!-- 件数上限 -->
      <div class="ai-export__section" :class="{ 'ai-export__section--disabled': !inclMatches }">
        <div class="ai-export__section-label">件数上限（対戦一覧）</div>
        <div class="ai-export__limit-row">
          <label class="ai-export__checkbox-label">
            <input type="checkbox" v-model="noLimit" class="ai-export__checkbox" :disabled="!inclMatches" />
            制限なし（全件）
          </label>
        </div>
        <div v-if="!noLimit" class="ai-export__limit-row">
          <span class="ai-export__label">直近</span>
          <input v-model.number="expLimit" type="number" min="1" max="1000" class="ai-export__limit-input" :disabled="!inclMatches" />
          <span class="ai-export__label">件</span>
        </div>
      </div>

      <!-- ダウンロードボタン -->
      <div class="ai-export__footer">
        <button
          class="ai-export__btn ai-export__btn--primary"
          :disabled="!player || downloading || nothingSelected"
          @click="runExport"
        >{{ downloading ? '処理中…' : 'エクスポート' }}</button>
      </div>
    </template>

    <!-- カード辞書タブ -->
    <template v-else>
      <!-- 対象カード件数 -->
      <div class="ai-export__section ai-export__count-section">
        対象:
        <span class="ai-export__count-num">
          {{ cardCount !== null ? `${cardCount.total} 種類` : '—' }}
        </span>
        <span v-if="cardCount && (cardCount.fetchable + cardCount.miss) > 0" class="ai-export__count-missing">
          （うちデータ未取得: {{ cardCount.fetchable + cardCount.miss }} 種類）
        </span>
        <span v-if="cardCount && cardCount.miss > 0" class="ai-export__count-miss-detail">
          （取得可能: {{ cardCount.fetchable }} 種類 / 既知の失敗: {{ cardCount.miss }} 種類）
        </span>
      </div>

      <!-- fetch / reset ボタン行 -->
      <div v-if="cardCount && (cardCount.fetchable > 0 || cardCount.miss > 0)" class="ai-export__section">
        <div class="ai-export__action-row">
          <button
            v-if="cardCount.fetchable > 0"
            class="ai-export__btn ai-export__btn--primary"
            :disabled="!player || fetching || resettingMiss"
            @click="runFetchMissing"
          >{{ fetching ? '取得中…' : `未取得カードを取得 (${cardCount.fetchable}件)` }}</button>
          <button
            v-if="cardCount.miss > 0"
            class="ai-export__btn"
            :disabled="!player || fetching || resettingMiss"
            @click="runResetMiss"
          >{{ resettingMiss ? 'リセット中…' : `失敗リストをリセット (${cardCount.miss}件)` }}</button>
        </div>
        <div v-if="fetching && fetchProgress.total > 0" class="ai-export__progress">
          <div class="ai-export__progress-bar">
            <div
              class="ai-export__progress-fill"
              :style="{ width: `${Math.round((fetchProgress.done / fetchProgress.total) * 100)}%` }"
            ></div>
          </div>
          <span class="ai-export__progress-text">{{ fetchProgress.done }} / {{ fetchProgress.total }}件</span>
        </div>
      </div>

      <!-- ダウンロードボタン -->
      <div class="ai-export__footer">
        <button
          class="ai-export__btn ai-export__btn--primary"
          :disabled="!player || cardDownloading"
          @click="runCardExport"
        >{{ cardDownloading ? '処理中…' : 'カード辞書をエクスポート' }}</button>
      </div>
    </template>
  </div>

  <ConfirmDialog
    :visible="confirmVisible"
    :message="confirmMessage"
    :confirmLabel="confirmLabel"
    @confirm="onConfirm"
    @cancel="confirmVisible = false"
  />
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import {
  fetchExportCount, fetchExportMarkdown,
  fetchCardDictionaryCount, fetchCardDictionary,
  streamFetchMissingCardData, resetCardCacheMiss,
  type CardDictionaryCount,
} from '../api/matches'
import { useToast } from '../composables/useToast'
import { useFilterState } from '../composables/useFilterState'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import FilterBar from '../components/FilterBar.vue'

const { showError, showSuccess } = useToast()
const {
  deckIds, decks, versionId, opponentDecks, dateFrom, dateTo,
  player, opponent, format,
  init,
} = useFilterState()

// ── タブ ──────────────────────────────────────────────────────────────────
const activeTab = ref<'matches' | 'cards'>('matches')

// ── 対戦ログタブ: 設定の永続化 ───────────────────────────────────────────
const EXPORT_SETTINGS_KEY = 'scry_export_settings'

function _loadExportSettings() {
  try {
    const raw = localStorage.getItem(EXPORT_SETTINGS_KEY)
    if (!raw) return {}
    return JSON.parse(raw) as Record<string, unknown>
  } catch { return {} }
}

function _saveExportSettings() {
  try {
    localStorage.setItem(EXPORT_SETTINGS_KEY, JSON.stringify({
      inclSummary: inclSummary.value,
      inclDeckStats: inclDeckStats.value,
      inclCardStats: inclCardStats.value,
      inclDeckList: inclDeckList.value,
      inclMatches: inclMatches.value,
      inclActions: inclActions.value,
    }))
  } catch { /* ignore */ }
}

const _s = _loadExportSettings()
const _bool = (key: string, def: boolean) =>
  typeof _s[key] === 'boolean' ? (_s[key] as boolean) : def

const inclSummary = ref(_bool('inclSummary', true))
const inclDeckStats = ref(_bool('inclDeckStats', true))
const inclCardStats = ref(_bool('inclCardStats', true))
const inclDeckList = ref(_bool('inclDeckList', true))
const inclMatches = ref(_bool('inclMatches', true))
const inclActions = ref(_bool('inclActions', false))
const expLimit = ref(200)
const noLimit = ref(false)
const confirmVisible = ref(false)
const confirmMessage = ref('')
const confirmLabel = ref('OK')
const confirmAction = ref<(() => void) | null>(null)
const downloading = ref(false)
const matchCount = ref<number | null>(null)

const nothingSelected = computed(() =>
  !inclSummary.value && !inclDeckStats.value && !inclCardStats.value &&
  !inclDeckList.value && !inclMatches.value
)

watch(inclMatches, (v) => { if (!v) inclActions.value = false })
watch([inclSummary, inclDeckStats, inclCardStats, inclDeckList, inclMatches, inclActions], _saveExportSettings)

// ── カード辞書タブ ────────────────────────────────────────────────────────
const cardCount = ref<CardDictionaryCount | null>(null)
const cardDownloading = ref(false)
const fetching = ref(false)
const resettingMiss = ref(false)
const fetchProgress = ref({ done: 0, total: 0 })

// ── 共通: フィルター ──────────────────────────────────────────────────────
function currentFilters() {
  const hasSingleDeck = deckIds.value.length === 1 && decks.value.length === 0
  return {
    player: player.value,
    opponent: opponent.value || undefined,
    ...(hasSingleDeck && versionId.value
      ? { version_id: versionId.value }
      : deckIds.value.length > 0
        ? { deck_ids: deckIds.value }
        : decks.value.length > 0
          ? { decks: decks.value }
          : {}),
    opponent_decks: opponentDecks.value.length > 0 ? opponentDecks.value : undefined,
    format: format.value || undefined,
    date_from: dateFrom.value || undefined,
    date_to: dateTo.value || undefined,
  }
}

async function loadCount() {
  if (!player.value) { matchCount.value = null; return }
  try {
    matchCount.value = await fetchExportCount(currentFilters())
  } catch { /* ignore */ }
}

async function loadCardCount() {
  if (!player.value) { cardCount.value = null; return }
  try {
    cardCount.value = await fetchCardDictionaryCount(currentFilters())
  } catch { /* ignore */ }
}

const filterWatchSources = [player, opponent, deckIds, decks, versionId, opponentDecks, format, dateFrom, dateTo]
watch(filterWatchSources, () => { loadCount(); loadCardCount() }, { deep: true })

// ── 対戦ログエクスポート ──────────────────────────────────────────────────
async function runExport() {
  if (!player.value) return
  downloading.value = true
  try {
    const count = await fetchExportCount(currentFilters())
    const outputCount = noLimit.value ? count : Math.min(count, expLimit.value)
    const warnings: string[] = []
    if (inclMatches.value) {
      if (noLimit.value) {
        warnings.push(`${count} 件全件をエクスポートします。`)
      } else if (count > expLimit.value) {
        warnings.push(`${count} 件中直近 ${expLimit.value} 件をエクスポートします。`)
      }
      if (inclActions.value && outputCount > 50) {
        warnings.push('アクション詳細を含むためファイルサイズが大きくなる可能性があります。')
      }
    }
    if (warnings.length > 0) {
      confirmMessage.value = warnings.join(' ') + ' 続けますか？'
      confirmLabel.value = 'エクスポート'
      confirmAction.value = async () => {
        downloading.value = true
        await doDownload()
      }
      confirmVisible.value = true
      downloading.value = false
      return
    }
    await doDownload()
  } catch (e) {
    showError(e instanceof Error ? e.message : 'エクスポートに失敗しました')
    downloading.value = false
  }
}

async function onConfirm() {
  confirmVisible.value = false
  await confirmAction.value?.()
}

async function doDownload() {
  try {
    const markdown = await fetchExportMarkdown({
      ...currentFilters(),
      include_summary: inclSummary.value,
      include_deck_stats: inclDeckStats.value,
      include_card_stats: inclCardStats.value,
      include_deck_list: inclDeckList.value,
      include_matches: inclMatches.value,
      include_actions: inclActions.value,
      limit: expLimit.value,
      no_limit: noLimit.value || undefined,
    })
    _triggerDownload(markdown, `scry_export_${player.value}_${_dateStr()}.md`)
  } catch (e) {
    showError(e instanceof Error ? e.message : 'ダウンロードに失敗しました')
  } finally {
    downloading.value = false
  }
}

// ── カード辞書: 未取得補完 ────────────────────────────────────────────────
function runFetchMissing() {
  if (!player.value || fetching.value) return
  const count = cardCount.value?.fetchable ?? 0
  confirmMessage.value = `Scryfall から ${count} 件のカードデータを取得します。続けますか？`
  confirmLabel.value = '取得'
  confirmAction.value = doFetchMissing
  confirmVisible.value = true
}

async function doFetchMissing() {
  fetching.value = true
  fetchProgress.value = { done: 0, total: cardCount.value?.fetchable ?? 0 }
  try {
    const result = await streamFetchMissingCardData(
      currentFilters(),
      (done, total) => { fetchProgress.value = { done, total } },
    )
    const msg = result.failed > 0
      ? `${result.fetched}件取得しました（失敗: ${result.failed}件 → 失敗リストに追加）`
      : `${result.fetched}件取得しました`
    showSuccess(msg)
    await loadCardCount()
  } catch (e) {
    showError(e instanceof Error ? e.message : 'カードデータの取得に失敗しました')
  } finally {
    fetching.value = false
  }
}

async function runResetMiss() {
  if (!player.value || resettingMiss.value) return
  resettingMiss.value = true
  try {
    const result = await resetCardCacheMiss(currentFilters())
    showSuccess(`失敗リストを${result.deleted}件リセットしました`)
    await loadCardCount()
  } catch (e) {
    showError(e instanceof Error ? e.message : '失敗リストのリセットに失敗しました')
  } finally {
    resettingMiss.value = false
  }
}

// ── カード辞書エクスポート ────────────────────────────────────────────────
async function runCardExport() {
  if (!player.value) return
  cardDownloading.value = true
  try {
    const text = await fetchCardDictionary(currentFilters())
    _triggerDownload(text, `scry_cards_${player.value}_${_dateStr()}.md`)
  } catch (e) {
    showError(e instanceof Error ? e.message : 'カード辞書のダウンロードに失敗しました')
  } finally {
    cardDownloading.value = false
  }
}

// ── ユーティリティ ────────────────────────────────────────────────────────
function _dateStr() {
  const now = new Date()
  return now.getFullYear().toString()
    + String(now.getMonth() + 1).padStart(2, '0')
    + String(now.getDate()).padStart(2, '0')
    + String(now.getHours()).padStart(2, '0')
    + String(now.getMinutes()).padStart(2, '0')
    + String(now.getSeconds()).padStart(2, '0')
}

function _triggerDownload(content: string, filename: string) {
  const blob = new Blob([content], { type: 'text/plain; charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(async () => {
  const playerSet = await init()
  if (!playerSet) {
    loadCount()
    loadCardCount()
  }
})
</script>

<style scoped>
.ai-export {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ai-export__title {
  font-size: 1.2rem;
  font-weight: bold;
  color: #2c2416;
}

.ai-export__tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid #c8b89a;
}

.ai-export__tab {
  padding: 7px 20px;
  border: 1px solid #c8b89a;
  border-bottom: none;
  border-radius: 4px 4px 0 0;
  background: #f0ece0;
  font-size: 13px;
  cursor: pointer;
  color: #7a6a55;
  margin-bottom: -2px;
}

.ai-export__tab--active {
  background: #fff;
  color: #2c2416;
  font-weight: bold;
  border-bottom: 2px solid #fff;
}

.ai-export__section {
  background: #fff;
  border: 1px solid #e0d8c8;
  border-radius: 6px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ai-export__section--disabled {
  opacity: 0.45;
  pointer-events: none;
}

.ai-export__count-section {
  font-size: 13px;
  color: #7a6a55;
}

.ai-export__count-num {
  font-weight: bold;
  color: #2c2416;
}

.ai-export__count-missing {
  margin-left: 6px;
  font-size: 12px;
  color: #a07040;
}

.ai-export__count-miss-detail {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  color: #a07040;
}

.ai-export__action-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.ai-export__section-label {
  font-size: 11px;
  font-weight: bold;
  color: #7a6a55;
  border-bottom: 1px solid #e0d8c8;
  padding-bottom: 4px;
}

.ai-export__checks {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ai-export__limit-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ai-export__limit-input {
  width: 72px;
  padding: 4px 8px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 13px;
  text-align: right;
  font-family: inherit;
}

.ai-export__checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #2c2416;
  cursor: pointer;
  user-select: none;
}

.ai-export__checkbox-label--disabled {
  opacity: 0.45;
  cursor: default;
}

.ai-export__checkbox {
  width: 14px;
  height: 14px;
  accent-color: #4a6fa5;
  cursor: pointer;
}

.ai-export__label {
  font-size: 13px;
  color: #2c2416;
}

.ai-export__footer {
  display: flex;
  justify-content: center;
}

.ai-export__btn {
  padding: 7px 20px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  background: #faf7f0;
  font-size: 13px;
  cursor: pointer;
  color: #2c2416;
}

.ai-export__btn--primary {
  background: #4a6fa5;
  border-color: #4a6fa5;
  color: #fff;
}

.ai-export__btn--primary:hover:not(:disabled) {
  background: #3a5f95;
}

.ai-export__btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.ai-export__progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}

.ai-export__progress-bar {
  flex: 1;
  height: 8px;
  background: #e8e0d0;
  border-radius: 4px;
  overflow: hidden;
}

.ai-export__progress-fill {
  height: 100%;
  background: #4a6fa5;
  border-radius: 4px;
  transition: width 0.2s ease;
}

.ai-export__progress-text {
  font-size: 12px;
  color: #6b5e4e;
  white-space: nowrap;
}
</style>
