<template>
  <div class="ai-export">
    <h1 class="ai-export__title">AI用エクスポート</h1>

    <!-- フィルター -->
    <div class="ai-export__section">
      <div class="ai-export__section-label">フィルター</div>
      <FilterBar />
    </div>

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
  </div>

  <ConfirmDialog
    :visible="confirmVisible"
    :message="confirmMessage"
    confirmLabel="エクスポート"
    @confirm="onConfirmExport"
    @cancel="confirmVisible = false"
  />
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { fetchExportCount, fetchExportMarkdown } from '../api/matches'
import { useToast } from '../composables/useToast'
import { useFilterState } from '../composables/useFilterState'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import FilterBar from '../components/FilterBar.vue'

const { showError } = useToast()
const {
  deckIds, decks, versionId, opponentDecks, dateFrom, dateTo,
  player, opponent, format,
  init,
} = useFilterState()

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
const downloading = ref(false)
const matchCount = ref<number | null>(null)

const nothingSelected = computed(() =>
  !inclSummary.value && !inclDeckStats.value && !inclCardStats.value &&
  !inclDeckList.value && !inclMatches.value
)

// 対戦一覧がオフになったらアクション詳細もオフ
watch(inclMatches, (v) => { if (!v) inclActions.value = false })

// 出力内容の変更を保存
watch([inclSummary, inclDeckStats, inclCardStats, inclDeckList, inclMatches, inclActions], _saveExportSettings)

async function loadCount() {
  if (!player.value) { matchCount.value = null; return }
  try {
    matchCount.value = await fetchExportCount(currentFilters())
  } catch { /* ignore */ }
}

watch([player, opponent, deckIds, decks, versionId, opponentDecks, format, dateFrom, dateTo], loadCount, { deep: true })

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

async function onConfirmExport() {
  confirmVisible.value = false
  downloading.value = true
  await doDownload()
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
    a.download = `scry_export_${player.value}_${dateStr}.md`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    showError(e instanceof Error ? e.message : 'ダウンロードに失敗しました')
  } finally {
    downloading.value = false
  }
}

onMounted(async () => {
  const playerSet = await init()
  if (!playerSet) loadCount()
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
</style>
