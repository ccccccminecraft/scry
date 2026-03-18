<template>
  <div class="deck-builder">
    <!-- 左ペイン: デッキ一覧 -->
    <div class="pane pane--left">
      <div class="pane__header">
        <span class="pane__title">デッキ一覧</span>
        <button class="pane__btn" @click="openNewDeck">+ 新規</button>
      </div>
      <div class="pane__filter">
        <select v-model="formatFilter" class="pane__filter-select">
          <option value="">すべて</option>
          <option v-for="f in formats" :key="f" :value="f">{{ f }}</option>
        </select>
      </div>
      <div class="pane__list">
        <div
          v-for="deck in filteredDecks"
          :key="deck.id"
          class="deck-item"
          :class="{ 'deck-item--active': selectedDeck?.id === deck.id }"
          @click="selectDeck(deck)"
        >
          <div class="deck-item__name">{{ deck.name }}</div>
          <div class="deck-item__meta">{{ deck.format ?? '未設定' }}</div>
        </div>
        <div v-if="filteredDecks.length === 0" class="pane__empty">デッキがありません</div>
      </div>
    </div>

    <!-- 中ペイン: バージョン一覧 -->
    <div class="pane pane--middle">
      <template v-if="selectedDeck">
        <div class="pane__header">
          <span class="pane__title">{{ selectedDeck.name }}</span>
          <div class="pane__header-actions">
            <button class="pane__btn" @click="openEditDeck">編集</button>
            <button class="pane__btn pane__btn--danger" @click="confirmDeleteDeck">削除</button>
            <button class="pane__btn" @click="openNewVersion">+ 追加</button>
          </div>
        </div>
        <div class="pane__list">
          <div
            v-for="v in versions"
            :key="v.id"
            class="version-item"
            :class="{ 'version-item--active': selectedVersion?.id === v.id }"
            @click="selectVersion(v)"
          >
            <div class="version-item__label">v{{ v.version_number }}</div>
            <div class="version-item__memo">{{ v.memo ?? '—' }}</div>
            <div class="version-item__count">{{ v.main_count }} / SB {{ v.side_count }}</div>
            <div class="version-item__date">{{ formatDate(v.registered_at) }}</div>
          </div>
          <div v-if="versions.length === 0" class="pane__empty">バージョンがありません</div>
        </div>
      </template>
      <div v-else class="pane__empty">デッキを選択してください</div>
    </div>

    <!-- 右ペイン: カードリスト -->
    <div class="pane pane--right">
      <template v-if="selectedVersion">
        <div class="pane__header">
          <span class="pane__title">v{{ selectedVersion.version_number }} {{ selectedVersion.memo ?? '' }}</span>
          <div class="pane__header-actions">
            <button class="pane__btn" @click="openBulkApply">一括適用</button>
            <button class="pane__btn pane__btn--danger" @click="confirmDeleteVersion">削除</button>
          </div>
        </div>
        <div class="card-list">
          <div class="card-section__title">
            メインデッキ ({{ selectedVersion.main.reduce((a, c) => a + c.quantity, 0) }})
          </div>
          <div v-for="entry in selectedVersion.main" :key="entry.card_name + '-main'" class="card-entry">
            <img
              v-if="entry.scryfall_id"
              :src="cardImageUrl(entry.scryfall_id)"
              class="card-entry__img"
              :alt="entry.card_name"
            />
            <div v-else class="card-entry__img-placeholder" />
            <span class="card-entry__qty">{{ entry.quantity }}</span>
            <span class="card-entry__name">{{ entry.card_name }}</span>
          </div>

          <div class="card-section__title card-section__title--sb">
            サイドボード ({{ selectedVersion.sideboard.reduce((a, c) => a + c.quantity, 0) }})
          </div>
          <div v-for="entry in selectedVersion.sideboard" :key="entry.card_name + '-sb'" class="card-entry">
            <img
              v-if="entry.scryfall_id"
              :src="cardImageUrl(entry.scryfall_id)"
              class="card-entry__img"
              :alt="entry.card_name"
            />
            <div v-else class="card-entry__img-placeholder" />
            <span class="card-entry__qty">{{ entry.quantity }}</span>
            <span class="card-entry__name">{{ entry.card_name }}</span>
          </div>
        </div>
      </template>
      <div v-else class="pane__empty">バージョンを選択してください</div>
    </div>

    <!-- デッキ作成・編集モーダル -->
    <div v-if="deckModalVisible" class="modal-overlay" @click.self="deckModalVisible = false">
      <div class="modal">
        <div class="modal__title">{{ editingDeck ? 'デッキを編集' : 'デッキを作成' }}</div>
        <div class="modal__field">
          <label class="modal__label">デッキ名</label>
          <input v-model="deckNameInput" type="text" class="modal__input" placeholder="UR Prowess" />
        </div>
        <div class="modal__field">
          <label class="modal__label">フォーマット</label>
          <select v-model="deckFormatInput" class="modal__select">
            <option value="">未設定</option>
            <option v-for="f in formats" :key="f" :value="f">{{ f }}</option>
          </select>
        </div>
        <div class="modal__footer">
          <button class="modal__btn" @click="deckModalVisible = false">キャンセル</button>
          <button class="modal__btn modal__btn--primary" :disabled="!deckNameInput.trim()" @click="saveDeck">保存</button>
        </div>
      </div>
    </div>

    <!-- バージョン作成・編集モーダル -->
    <div v-if="versionModalVisible" class="modal-overlay" @click.self="versionModalVisible = false">
      <div class="modal modal--wide">
        <div class="modal__title">新バージョンを作成</div>
        <div class="modal__field">
          <label class="modal__label">メモ（任意）</label>
          <input v-model="versionMemo" type="text" class="modal__input" placeholder="MH3後調整" />
        </div>
        <div class="modal__field">
          <label class="modal__label">入力方法</label>
          <div class="modal__radio-group">
            <label><input type="radio" v-model="versionSource" value="text" /> テキスト貼り付け</label>
            <label><input type="radio" v-model="versionSource" value="dek" /> .dek ファイル</label>
          </div>
        </div>
        <div class="modal__field modal__field--grow">
          <label class="modal__label">カードリスト</label>
          <textarea
            v-if="versionSource === 'text'"
            v-model="versionText"
            class="modal__textarea"
            placeholder="4 Lightning Bolt&#10;4 Dragon's Rage Channeler&#10;...&#10;&#10;Sideboard&#10;4 Veil of Summer"
          />
          <div v-else class="modal__file-row">
            <input type="file" accept=".dek" ref="dekFileInput" class="modal__file-hidden" @change="onDekFileChange" />
            <button class="modal__btn" @click="dekFileInput?.click()">ファイルを選択</button>
            <span class="modal__file-name">{{ dekFile ? dekFile.name : '未選択' }}</span>
          </div>
        </div>
        <div v-if="versionError" class="modal__error">{{ versionError }}</div>
        <div class="modal__footer">
          <button class="modal__btn" @click="versionModalVisible = false">キャンセル</button>
          <button class="modal__btn modal__btn--primary" :disabled="!canSaveVersion" @click="saveVersion">保存</button>
        </div>
      </div>
    </div>

    <!-- 一括適用モーダル -->
    <div v-if="bulkModal.visible" class="modal-overlay" @click.self="bulkModal.visible = false">
      <div class="modal">
        <div class="modal__title">「{{ bulkModal.versionLabel }}」を対戦履歴に一括適用</div>
        <div class="modal__field">
          <label class="modal__label">プレイヤー</label>
          <select v-model="bulkModal.player" class="modal__select" @change="loadBulkCount">
            <option v-for="p in bulkPlayerList" :key="p" :value="p">{{ p }}</option>
          </select>
        </div>
        <div class="modal__field">
          <label class="modal__label">フォーマット</label>
          <select v-model="bulkModal.format" class="modal__select" @change="loadBulkCount">
            <option value="">すべて</option>
            <option v-for="f in bulkFormatList" :key="f" :value="f">{{ f }}</option>
          </select>
        </div>
        <div class="modal__field">
          <label class="modal__label">デッキ名</label>
          <input v-model="bulkModal.deckName" type="text" class="modal__input" @input="loadBulkCount" />
        </div>
        <div class="modal__field">
          <label class="modal__label">対戦日（開始）</label>
          <input v-model="bulkModal.dateFrom" type="date" class="modal__input" @change="loadBulkCount" />
        </div>
        <div class="modal__field">
          <label class="modal__label">対戦日（終了）</label>
          <input v-model="bulkModal.dateTo" type="date" class="modal__input" @change="loadBulkCount" />
        </div>
        <div class="modal__field">
          <label class="modal__label">適用方法</label>
          <div class="modal__radio-group">
            <label><input type="radio" v-model="bulkModal.overwrite" :value="false" @change="loadBulkCount" /> スキップ（設定済みはそのまま）</label>
            <label><input type="radio" v-model="bulkModal.overwrite" :value="true" @change="loadBulkCount" /> 上書き（設定済みも含めて適用）</label>
          </div>
        </div>
        <div class="modal__count">
          対象: <span class="modal__count-num">{{ bulkModal.count !== null ? `${bulkModal.count} 件` : '—' }}</span>
        </div>
        <div class="modal__footer">
          <button class="modal__btn" @click="bulkModal.visible = false">キャンセル</button>
          <button
            class="modal__btn modal__btn--primary"
            :disabled="!bulkModal.player || bulkModal.count === 0 || bulkModal.applying"
            @click="applyBulk"
          >{{ bulkModal.applying ? '適用中…' : '適用する' }}</button>
        </div>
      </div>
    </div>

    <ConfirmDialog
      :visible="confirmVisible"
      :message="confirmMessage"
      confirm-label="削除"
      @confirm="onConfirm"
      @cancel="confirmVisible = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted, watch } from 'vue'
import { useToast } from '../composables/useToast'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import {
  fetchDecks,
  createDeck,
  updateDeck,
  deleteDeck,
  fetchVersions,
  fetchVersion,
  createVersionFromText,
  createVersionFromDek,
  deleteVersion,
  cardImageUrl,
  type Deck,
  type DeckVersionSummary,
  type DeckVersionDetail,
} from '../api/decklist'
import { fetchPlayers, fetchFormats } from '../api/stats'
import { fetchBulkAssignCount, bulkAssignDeckVersion } from '../api/matches'

const { showSuccess, showError } = useToast()

const formats = ['standard', 'pioneer', 'modern', 'legacy', 'vintage', 'pauper', 'commander']

// State
const decks = ref<Deck[]>([])
const formatFilter = ref('')
const filteredDecks = computed(() => {
  if (!formatFilter.value) return decks.value
  return decks.value.filter(d => d.format === formatFilter.value)
})

watch(formatFilter, () => {
  if (selectedDeck.value && !filteredDecks.value.find(d => d.id === selectedDeck.value!.id)) {
    selectedDeck.value = null
    versions.value = []
    selectedVersion.value = null
  }
})
const selectedDeck = ref<Deck | null>(null)
const versions = ref<DeckVersionSummary[]>([])
const selectedVersion = ref<DeckVersionDetail | null>(null)

// Deck modal
const deckModalVisible = ref(false)
const editingDeck = ref<Deck | null>(null)
const deckNameInput = ref('')
const deckFormatInput = ref('')

// Version modal
const versionModalVisible = ref(false)
const versionMemo = ref('')
const versionSource = ref<'text' | 'dek'>('text')
const versionText = ref('')
const dekFile = ref<File | null>(null)
const dekFileInput = ref<HTMLInputElement | null>(null)
const versionError = ref('')

// Confirm dialog
const confirmVisible = ref(false)
const confirmMessage = ref('')
const pendingAction = ref<(() => Promise<void>) | null>(null)

// Bulk apply modal
const bulkModal = reactive({
  visible: false,
  versionId: null as number | null,
  versionLabel: '',
  player: '',
  format: '',
  deckName: '',
  dateFrom: '',
  dateTo: '',
  overwrite: false,
  count: null as number | null,
  applying: false,
})
const bulkPlayerList = ref<string[]>([])
const bulkFormatList = ref<string[]>([])

const canSaveVersion = computed(() => {
  if (versionSource.value === 'text') return versionText.value.trim().length > 0
  return dekFile.value !== null
})

onMounted(async () => {
  await loadDecks()
})

async function loadDecks() {
  try {
    decks.value = await fetchDecks()
  } catch {
    showError('デッキ一覧の取得に失敗しました')
  }
}

async function selectDeck(deck: Deck) {
  selectedDeck.value = deck
  selectedVersion.value = null
  try {
    versions.value = await fetchVersions(deck.id)
  } catch {
    showError('バージョン一覧の取得に失敗しました')
  }
}

async function selectVersion(v: DeckVersionSummary) {
  if (!selectedDeck.value) return
  try {
    selectedVersion.value = await fetchVersion(selectedDeck.value.id, v.id)
  } catch {
    showError('バージョン詳細の取得に失敗しました')
  }
}

function openNewDeck() {
  editingDeck.value = null
  deckNameInput.value = ''
  deckFormatInput.value = ''
  deckModalVisible.value = true
}

function openEditDeck() {
  if (!selectedDeck.value) return
  editingDeck.value = selectedDeck.value
  deckNameInput.value = selectedDeck.value.name
  deckFormatInput.value = selectedDeck.value.format ?? ''
  deckModalVisible.value = true
}

async function saveDeck() {
  const name = deckNameInput.value.trim()
  const format = deckFormatInput.value || null
  try {
    if (editingDeck.value) {
      const updated = await updateDeck(editingDeck.value.id, name, format)
      decks.value = decks.value.map(d => d.id === updated.id ? updated : d)
      if (selectedDeck.value?.id === updated.id) selectedDeck.value = updated
      showSuccess('デッキを更新しました')
    } else {
      const created = await createDeck(name, format)
      decks.value = [created, ...decks.value]
      showSuccess('デッキを作成しました')
    }
    deckModalVisible.value = false
  } catch {
    showError('保存に失敗しました')
  }
}

function confirmDeleteDeck() {
  if (!selectedDeck.value) return
  confirmMessage.value = `「${selectedDeck.value.name}」とすべてのバージョンを削除しますか？`
  pendingAction.value = async () => {
    await deleteDeck(selectedDeck.value!.id)
    decks.value = decks.value.filter(d => d.id !== selectedDeck.value!.id)
    selectedDeck.value = null
    versions.value = []
    selectedVersion.value = null
    showSuccess('デッキを削除しました')
  }
  confirmVisible.value = true
}

function openNewVersion() {
  versionMemo.value = ''
  versionSource.value = 'text'
  versionText.value = ''
  dekFile.value = null
  versionError.value = ''
  versionModalVisible.value = true
}

function onDekFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  dekFile.value = input.files?.[0] ?? null
}

async function saveVersion() {
  if (!selectedDeck.value) return
  versionError.value = ''
  try {
    let result: DeckVersionDetail
    if (versionSource.value === 'text') {
      result = await createVersionFromText(selectedDeck.value.id, versionMemo.value, versionText.value)
    } else {
      result = await createVersionFromDek(selectedDeck.value.id, versionMemo.value, dekFile.value!)
    }
    showSuccess('バージョンを作成しました')
    versionModalVisible.value = false
    versions.value = await fetchVersions(selectedDeck.value.id)
    selectedVersion.value = result
    // デッキ一覧の latest_version も更新
    await loadDecks()
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    if (typeof detail === 'string') {
      versionError.value = detail
    } else {
      showError('保存に失敗しました')
    }
  }
}

function confirmDeleteVersion() {
  if (!selectedVersion.value || !selectedDeck.value) return
  confirmMessage.value = `v${selectedVersion.value.version_number} を削除しますか？`
  pendingAction.value = async () => {
    await deleteVersion(selectedDeck.value!.id, selectedVersion.value!.id)
    versions.value = versions.value.filter(v => v.id !== selectedVersion.value!.id)
    selectedVersion.value = null
    showSuccess('バージョンを削除しました')
    await loadDecks()
  }
  confirmVisible.value = true
}

async function onConfirm() {
  confirmVisible.value = false
  if (!pendingAction.value) return
  try {
    await pendingAction.value()
  } catch {
    showError('削除に失敗しました')
  } finally {
    pendingAction.value = null
  }
}

function formatDate(iso: string): string {
  return iso.slice(0, 10)
}

async function openBulkApply() {
  if (!selectedVersion.value || !selectedDeck.value) return
  bulkModal.versionId = selectedVersion.value.id
  bulkModal.versionLabel = `${selectedDeck.value.name} v${selectedVersion.value.version_number}`
  bulkModal.format = selectedDeck.value.format ?? ''
  bulkModal.deckName = selectedDeck.value.name
  bulkModal.dateFrom = ''
  bulkModal.dateTo = ''
  bulkModal.overwrite = false
  bulkModal.count = null
  bulkModal.applying = false
  try {
    const [players, formats] = await Promise.all([fetchPlayers(1), fetchFormats()])
    bulkPlayerList.value = players
    bulkFormatList.value = formats
    bulkModal.player = players[0] ?? ''
  } catch {
    showError('データの取得に失敗しました')
    return
  }
  bulkModal.visible = true
  await loadBulkCount()
}

async function loadBulkCount() {
  if (!bulkModal.player) { bulkModal.count = null; return }
  try {
    bulkModal.count = await fetchBulkAssignCount({
      player: bulkModal.player,
      format: bulkModal.format || undefined,
      deck_name: bulkModal.deckName || undefined,
      date_from: bulkModal.dateFrom || undefined,
      date_to: bulkModal.dateTo || undefined,
      overwrite: bulkModal.overwrite,
    })
  } catch { /* ignore */ }
}

async function applyBulk() {
  if (!bulkModal.versionId || !bulkModal.player) return
  bulkModal.applying = true
  try {
    const updated = await bulkAssignDeckVersion(bulkModal.versionId, {
      player: bulkModal.player,
      format: bulkModal.format || undefined,
      deck_name: bulkModal.deckName || undefined,
      date_from: bulkModal.dateFrom || undefined,
      date_to: bulkModal.dateTo || undefined,
      overwrite: bulkModal.overwrite,
    })
    bulkModal.visible = false
    showSuccess(`${updated} 件に適用しました`)
  } catch {
    showError('適用に失敗しました')
  } finally {
    bulkModal.applying = false
  }
}
</script>

<style scoped>
.deck-builder {
  display: flex;
  height: 100%;
  overflow: hidden;
}

/* ペイン共通 */
.pane {
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e0d8c8;
  overflow: hidden;
}

.pane--left  { width: 200px; flex-shrink: 0; }
.pane--middle { width: 220px; flex-shrink: 0; }
.pane--right { flex: 1; }

.pane__header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  border-bottom: 1px solid #e0d8c8;
  background: #faf7f0;
  flex-shrink: 0;
}

.pane__title {
  font-size: 13px;
  font-weight: bold;
  color: #2c2416;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pane__header-actions {
  display: flex;
  gap: 4px;
}

.pane__btn {
  padding: 3px 8px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  background: #faf7f0;
  font-size: 12px;
  cursor: pointer;
  color: #2c2416;
  white-space: nowrap;
}

.pane__btn:hover { background: #f0ece0; }

.pane__btn--danger {
  color: #a03030;
  border-color: #d8a0a0;
}

.pane__filter {
  padding: 6px 10px;
  border-bottom: 1px solid #e0d8c8;
  background: #faf7f0;
  flex-shrink: 0;
}

.pane__filter-select {
  width: 100%;
  padding: 4px 6px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 12px;
  background: #fff;
  color: #2c2416;
  font-family: inherit;
}

.pane__list {
  flex: 1;
  overflow-y: auto;
}

.pane__empty {
  padding: 24px 16px;
  font-size: 12px;
  color: #a09080;
  text-align: center;
}

/* デッキアイテム */
.deck-item {
  padding: 10px 12px;
  border-bottom: 1px solid #f0ece0;
  cursor: pointer;
}

.deck-item:hover { background: #f5f2ea; }

.deck-item--active {
  background: #e8f0fa;
  border-left: 3px solid #4a6fa5;
}

.deck-item__name {
  font-size: 13px;
  font-weight: bold;
  color: #2c2416;
}

.deck-item__meta {
  font-size: 11px;
  color: #7a6a55;
  margin-top: 2px;
}

/* バージョンアイテム */
.version-item {
  padding: 10px 12px;
  border-bottom: 1px solid #f0ece0;
  cursor: pointer;
}

.version-item:hover { background: #f5f2ea; }

.version-item--active {
  background: #e8f0fa;
  border-left: 3px solid #4a6fa5;
}

.version-item__label {
  font-size: 13px;
  font-weight: bold;
  color: #2c2416;
}

.version-item__memo {
  font-size: 12px;
  color: #5a4a35;
  margin-top: 2px;
}

.version-item__count {
  font-size: 11px;
  color: #7a6a55;
  margin-top: 2px;
}

.version-item__date {
  font-size: 11px;
  color: #a09080;
  margin-top: 2px;
}

/* カードリスト */
.card-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
}

.card-section__title {
  font-size: 12px;
  font-weight: bold;
  color: #7a6a55;
  padding: 8px 0 4px;
  border-bottom: 1px solid #e0d8c8;
  margin-bottom: 4px;
}

.card-section__title--sb {
  margin-top: 12px;
}

.card-entry {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 0;
}

.card-entry__img {
  width: 29px;
  height: 40px;
  border-radius: 2px;
  object-fit: cover;
  flex-shrink: 0;
}

.card-entry__img-placeholder {
  width: 29px;
  height: 40px;
  border-radius: 2px;
  background: #e0d8c8;
  flex-shrink: 0;
}

.card-entry__qty {
  font-size: 13px;
  font-weight: bold;
  color: #4a6fa5;
  width: 16px;
  text-align: right;
  flex-shrink: 0;
}

.card-entry__name {
  font-size: 13px;
  color: #2c2416;
}

/* モーダル */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}

.modal {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  width: 420px;
  max-width: 90vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.modal--wide {
  width: 560px;
}

.modal__title {
  font-size: 14px;
  font-weight: bold;
  color: #2c2416;
}

.modal__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.modal__field--grow {
  flex: 1;
  min-height: 0;
}

.modal__label {
  font-size: 12px;
  color: #7a6a55;
}

.modal__input,
.modal__select {
  padding: 6px 10px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 13px;
  background: #fff;
  color: #2c2416;
  font-family: inherit;
}

.modal__textarea {
  flex: 1;
  min-height: 240px;
  padding: 8px 10px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 13px;
  background: #fff;
  color: #2c2416;
  font-family: monospace;
  resize: none;
}

.modal__radio-group {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #2c2416;
}

.modal__file-hidden { display: none; }

.modal__file-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.modal__file-name {
  font-size: 13px;
  color: #7a6a55;
}

.modal__error {
  font-size: 12px;
  color: #a03030;
  background: #fff0f0;
  border: 1px solid #d8a0a0;
  border-radius: 4px;
  padding: 6px 10px;
}

.modal__count {
  font-size: 13px;
  color: #7a6a55;
}

.modal__count-num {
  font-weight: bold;
  color: #2c2416;
}

.modal__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.modal__btn {
  padding: 6px 16px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  background: #faf7f0;
  font-size: 13px;
  cursor: pointer;
  color: #2c2416;
  font-family: inherit;
}

.modal__btn:hover { background: #f0ece0; }

.modal__btn--primary {
  background: #4a6fa5;
  border-color: #4a6fa5;
  color: #fff;
}

.modal__btn--primary:hover:not(:disabled) { background: #3a5f95; }
.modal__btn--primary:disabled { opacity: 0.4; cursor: default; }
</style>
