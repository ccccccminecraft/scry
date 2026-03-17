<template>
  <div class="deck-def">
    <h1 class="deck-def__title">デッキ定義管理</h1>

    <!-- 一括上書きパネル -->
    <div class="deck-def__section">
      <div class="deck-def__section-title">デッキ名一括上書き</div>
      <div class="deck-def__bulk-form">
        <div class="deck-def__field">
          <label class="deck-def__label">プレイヤー</label>
          <select v-model="bulk.player_name" class="deck-def__select">
            <option value="">選択してください</option>
            <option v-for="p in playerList" :key="p" :value="p">{{ p }}</option>
          </select>
        </div>
        <div class="deck-def__field">
          <label class="deck-def__label">デッキ名</label>
          <input v-model="bulk.deck_name" class="deck-def__input" placeholder="デッキ名" />
        </div>
        <div class="deck-def__field">
          <label class="deck-def__label">直近N件</label>
          <input v-model.number="bulk.last_n" type="number" min="1" class="deck-def__input deck-def__input--short" placeholder="例: 10" />
        </div>
        <div class="deck-def__field">
          <label class="deck-def__label">開始日</label>
          <input v-model="bulk.date_from" type="date" class="deck-def__input" />
        </div>
        <div class="deck-def__field">
          <label class="deck-def__label">終了日</label>
          <input v-model="bulk.date_to" type="date" class="deck-def__input" />
        </div>
        <button class="deck-def__btn deck-def__btn--primary" @click="runBulk" :disabled="!bulk.player_name || !bulk.deck_name">
          上書き実行
        </button>
      </div>
    </div>

    <!-- JSON Import / Export -->
    <div class="deck-def__section">
      <div class="deck-def__section-title">JSON インポート / エクスポート</div>
      <div class="deck-def__bulk-form">
        <div class="deck-def__field">
          <label class="deck-def__label">インポート先プレイヤー（空欄 = 共通定義）</label>
          <select v-model="importPlayerName" class="deck-def__select">
            <option value="">（共通）</option>
            <option v-for="p in playerList" :key="p" :value="p">{{ p }}</option>
          </select>
        </div>
        <div class="deck-def__field">
          <label class="deck-def__label">同名定義が存在する場合</label>
          <select v-model="importOnConflict" class="deck-def__select">
            <option value="skip">スキップ</option>
            <option value="overwrite">上書き</option>
          </select>
        </div>
        <div class="deck-def__field">
          <label class="deck-def__label">JSONファイル</label>
          <div class="deck-def__file-row">
            <button class="deck-def__btn" @click="fileInputRef?.click()">ファイルを選択</button>
            <span class="deck-def__file-name">{{ importFile ? importFile.name : '未選択' }}</span>
            <input ref="fileInputRef" type="file" accept=".json" class="deck-def__file-hidden" @change="onFileChange" />
          </div>
        </div>
        <button class="deck-def__btn deck-def__btn--primary" @click="runImport" :disabled="!importFile || importing">
          {{ importing ? 'インポート中...' : 'インポート' }}
        </button>
        <button class="deck-def__btn" @click="runExport">エクスポート</button>
      </div>
    </div>

    <!-- 既存試合への適用 -->
    <div class="deck-def__section">
      <div class="deck-def__section-title">既存試合へのデッキ定義適用</div>
      <div class="deck-def__bulk-form">
        <div class="deck-def__apply-btns">
          <button
            class="deck-def__btn deck-def__btn--primary"
            :disabled="applying"
            @click="runApply(false)"
          >{{ applying ? '適用中...' : 'デッキ名未設定の試合に適用' }}</button>
          <button
            class="deck-def__btn"
            :disabled="applying"
            @click="runApply(true)"
          >{{ applying ? '適用中...' : 'すべての試合に適用（上書き）' }}</button>
        </div>
        <p class="deck-def__apply-note">「デッキ名未設定」は deck_name が空の試合のみを対象にします。「すべての試合」は既存のデッキ名も上書きします。</p>
      </div>
    </div>

    <!-- Claude 生成 -->
    <div class="deck-def__section">
      <div class="deck-def__section-title">Claude で生成</div>
      <div class="deck-def__bulk-form">
        <div class="deck-def__field">
          <label class="deck-def__label">フォーマット（空欄 = 問わず）</label>
          <select v-model="genFormat" class="deck-def__select">
            <option value="">（問わず）</option>
            <option v-for="f in ALL_FORMATS" :key="f" :value="f">{{ f }}</option>
          </select>
        </div>
        <div class="deck-def__field deck-def__field--grow">
          <label class="deck-def__label">追加指示（任意）</label>
          <input v-model="genNotes" class="deck-def__input" placeholder="例: focus on top 10 decks from recent tournaments" />
        </div>
        <button class="deck-def__btn deck-def__btn--claude" @click="runGenerate" :disabled="generating">
          {{ generating ? '生成中...' : '✦ Claude で生成' }}
        </button>
      </div>
    </div>

    <!-- デッキ定義一覧 -->
    <div class="deck-def__section">
      <div class="deck-def__section-header">
        <div class="deck-def__section-title">デッキ定義一覧</div>
        <div class="deck-def__list-controls">
          <select v-model="filterDefFormat" class="deck-def__select deck-def__select--sm">
            <option value="">フォーマット: すべて</option>
            <option v-for="f in ALL_FORMATS" :key="f" :value="f">{{ f }}</option>
          </select>
          <button class="deck-def__btn deck-def__btn--primary" @click="openNew">＋ 新規作成</button>
        </div>
      </div>

      <div v-if="definitions.length === 0" class="deck-def__empty">デッキ定義がありません</div>
      <div v-else-if="filteredDefinitions.length === 0" class="deck-def__empty">該当するデッキ定義がありません</div>

      <table v-else class="deck-def__table">
        <thead>
          <tr>
            <th>プレイヤー</th>
            <th>デッキ名</th>
            <th>フォーマット</th>
            <th class="deck-def__th-num">しきい値</th>
            <th>シグネチャカード</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in filteredDefinitions" :key="d.id">
            <td>{{ d.player_name ?? '（共通）' }}</td>
            <td>{{ d.deck_name }}</td>
            <td>{{ d.format ?? '—' }}</td>
            <td class="deck-def__td-num">{{ d.threshold }}</td>
            <td class="deck-def__td-cards">{{ d.cards.join(', ') }}</td>
            <td class="deck-def__td-actions">
              <button class="deck-def__btn deck-def__btn--sm" @click="openEdit(d)">編集</button>
              <button class="deck-def__btn deck-def__btn--sm deck-def__btn--danger" @click="remove(d)">削除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 生成プレビューモーダル -->
    <div v-if="genPreview" class="deck-def__overlay" @click.self="genPreview = null">
      <div class="deck-def__modal deck-def__modal--wide">
        <h2 class="deck-def__modal-title">生成されたデッキ定義（{{ genPreview.definitions.length }}件）</h2>
        <p class="deck-def__gen-meta">
          フォーマット: {{ genPreview.format ?? '問わず' }} &nbsp;／&nbsp;
          生成日時: {{ new Date(genPreview.generated_at).toLocaleString('ja-JP') }}
        </p>

        <div class="deck-def__gen-list">
          <div v-for="d in genPreview.definitions" :key="d.deck_name" class="deck-def__gen-item">
            <div class="deck-def__gen-header">
              <span class="deck-def__gen-name">{{ d.deck_name }}</span>
              <span class="deck-def__gen-threshold">しきい値 {{ d.threshold }}</span>
            </div>
            <div class="deck-def__gen-cards">{{ d.cards.join(', ') }}</div>
          </div>
        </div>

        <div class="deck-def__modal-footer">
          <button class="deck-def__btn" @click="genPreview = null">キャンセル</button>
          <div class="deck-def__gen-import-opts">
            <select v-model="genImportPlayer" class="deck-def__select">
              <option value="">（共通定義）</option>
              <option v-for="p in playerList" :key="p" :value="p">{{ p }}</option>
            </select>
            <select v-model="genImportConflict" class="deck-def__select">
              <option value="skip">重複スキップ</option>
              <option value="overwrite">重複上書き</option>
            </select>
            <button class="deck-def__btn deck-def__btn--primary" @click="importGenerated" :disabled="importing">
              {{ importing ? '登録中...' : 'このまま登録' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 編集モーダル -->
    <div v-if="editing" class="deck-def__overlay" @click.self="editing = null">
      <div class="deck-def__modal">
        <h2 class="deck-def__modal-title">{{ editingId ? 'デッキ定義を編集' : 'デッキ定義を作成' }}</h2>

        <div class="deck-def__form">
          <div class="deck-def__field">
            <label class="deck-def__label">プレイヤー（空欄 = 共通定義）</label>
            <select v-model="editing.player_name" class="deck-def__select">
              <option :value="null">（共通）</option>
              <option v-for="p in playerList" :key="p" :value="p">{{ p }}</option>
            </select>
          </div>
          <div class="deck-def__field">
            <label class="deck-def__label">デッキ名 *</label>
            <input v-model="editing.deck_name" class="deck-def__input" placeholder="例: Spirits" />
          </div>
          <div class="deck-def__field">
            <label class="deck-def__label">フォーマット（空欄 = 問わず）</label>
            <select v-model="editing.format" class="deck-def__select">
              <option :value="null">（問わず）</option>
              <option v-for="f in formatList" :key="f" :value="f">{{ f }}</option>
            </select>
          </div>
          <div class="deck-def__field">
            <label class="deck-def__label">しきい値（最低マッチ枚数）</label>
            <input v-model.number="editing.threshold" type="number" min="1" class="deck-def__input deck-def__input--short" />
          </div>
          <div class="deck-def__field deck-def__field--full">
            <label class="deck-def__label">シグネチャカード（1行1枚）</label>
            <textarea v-model="cardText" class="deck-def__textarea" rows="8" placeholder="Supreme Phantom&#10;Mausoleum Wanderer&#10;Spectral Sailor" />
          </div>
        </div>

        <div class="deck-def__modal-footer">
          <button class="deck-def__btn" @click="editing = null">キャンセル</button>
          <button class="deck-def__btn deck-def__btn--primary" @click="save">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useToast } from '../composables/useToast'
import {
  fetchDeckDefinitions, createDeckDefinition, updateDeckDefinition,
  deleteDeckDefinition, deckBulkUpdate, importDeckDefinitions, exportDeckDefinitions,
  generateDeckDefinitions, applyDeckDefinitions,
  type DeckDefinition, type DeckDefinitionInput, type GeneratedDeckPayload,
} from '../api/decks'
import { fetchPlayers, fetchFormats } from '../api/stats'

const { showError, showSuccess } = useToast()

const ALL_FORMATS = ['standard', 'pioneer', 'modern', 'pauper', 'legacy', 'vintage']

const definitions = ref<DeckDefinition[]>([])
const playerList = ref<string[]>([])
const formatList = ref<string[]>([])

const filterDefFormat = ref('')
const filteredDefinitions = computed(() => {
  if (!filterDefFormat.value) return definitions.value
  return definitions.value.filter(d => d.format === filterDefFormat.value)
})

// 編集フォーム
const editingId = ref<number | null>(null)
const editing = ref<DeckDefinitionInput | null>(null)
const cardText = ref('')

// apply definitions
const applying = ref(false)

async function runApply(overwrite: boolean) {
  const msg = overwrite
    ? 'すべての試合にデッキ定義を適用します。既存のデッキ名も上書きされます。よろしいですか？'
    : 'デッキ名が未設定の試合にデッキ定義を適用します。よろしいですか？'
  if (!confirm(msg)) return
  applying.value = true
  try {
    const res = await applyDeckDefinitions(overwrite)
    showSuccess(`${res.updated} 件更新しました（スキップ: ${res.skipped} 件）`)
  } catch (e) {
    showError(e instanceof Error ? e.message : '適用に失敗しました')
  } finally {
    applying.value = false
  }
}

// JSON import/export
const importPlayerName = ref('')
const importOnConflict = ref<'skip' | 'overwrite'>('skip')
const importFile = ref<File | null>(null)
const importing = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

// Claude 生成
const genFormat = ref('')
const genNotes = ref('')
const generating = ref(false)
const genPreview = ref<GeneratedDeckPayload | null>(null)
const genImportPlayer = ref('')
const genImportConflict = ref<'skip' | 'overwrite'>('skip')

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  importFile.value = input.files?.[0] ?? null
}

async function runImport() {
  if (!importFile.value) return
  importing.value = true
  try {
    const res = await importDeckDefinitions(
      importFile.value,
      importPlayerName.value || null,
      importOnConflict.value,
    )
    definitions.value = await fetchDeckDefinitions()
    showSuccess(`インポート完了: ${res.imported}件追加、${res.skipped}件スキップ、${res.errors}件エラー`)
    importFile.value = null
    if (fileInputRef.value) fileInputRef.value.value = ''
  } catch {
    showError('インポートに失敗しました')
  } finally {
    importing.value = false
  }
}

async function runExport() {
  try {
    const blob = await exportDeckDefinitions()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'deck_definitions.json'
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    showError('エクスポートに失敗しました')
  }
}

async function runGenerate() {
  generating.value = true
  try {
    const result = await generateDeckDefinitions(genFormat.value || null, genNotes.value || null)
    genPreview.value = result
    genImportPlayer.value = ''
    genImportConflict.value = 'skip'
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    const status = e?.response?.status
    const msg = detail
      ? `エラー (${status}): ${detail}`
      : `Claude API呼び出しに失敗しました (${e?.message ?? '不明'})`
    showError(msg)
    console.error('[generate] error:', e?.response ?? e)
  } finally {
    generating.value = false
  }
}

async function importGenerated() {
  if (!genPreview.value) return
  importing.value = true
  try {
    const blob = new Blob([JSON.stringify(genPreview.value)], { type: 'application/json' })
    const file = new File([blob], 'generated.json', { type: 'application/json' })
    const res = await importDeckDefinitions(
      file,
      genImportPlayer.value || null,
      genImportConflict.value,
    )
    definitions.value = await fetchDeckDefinitions()
    genPreview.value = null
    showSuccess(`登録完了: ${res.imported}件追加、${res.skipped}件スキップ、${res.errors}件エラー`)
  } catch {
    showError('登録に失敗しました')
  } finally {
    importing.value = false
  }
}

// 一括上書きフォーム
const bulk = ref({
  player_name: '',
  deck_name: '',
  last_n: undefined as number | undefined,
  date_from: '',
  date_to: '',
})

function openNew() {
  editingId.value = null
  editing.value = { player_name: null, deck_name: '', format: null, threshold: 2, cards: [] }
  cardText.value = ''
}

function openEdit(d: DeckDefinition) {
  editingId.value = d.id
  editing.value = {
    player_name: d.player_name,
    deck_name: d.deck_name,
    format: d.format,
    threshold: d.threshold,
    cards: [...d.cards],
  }
  cardText.value = d.cards.join('\n')
}

async function save() {
  if (!editing.value) return
  if (!editing.value.deck_name.trim()) {
    showError('デッキ名を入力してください')
    return
  }
  const cards = cardText.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (cards.length === 0) {
    showError('シグネチャカードを1枚以上入力してください')
    return
  }
  const body: DeckDefinitionInput = { ...editing.value, cards }
  try {
    if (editingId.value) {
      await updateDeckDefinition(editingId.value, body)
    } else {
      await createDeckDefinition(body)
    }
    definitions.value = await fetchDeckDefinitions()
    editing.value = null
    showSuccess('保存しました')
  } catch {
    showError('保存に失敗しました')
  }
}

async function remove(d: DeckDefinition) {
  if (!confirm(`「${d.deck_name}」を削除しますか？`)) return
  try {
    await deleteDeckDefinition(d.id)
    definitions.value = definitions.value.filter(x => x.id !== d.id)
    showSuccess('削除しました')
  } catch {
    showError('削除に失敗しました')
  }
}

async function runBulk() {
  if (!bulk.value.player_name || !bulk.value.deck_name) return
  try {
    const res = await deckBulkUpdate({
      player_name: bulk.value.player_name,
      deck_name: bulk.value.deck_name,
      last_n: bulk.value.last_n || undefined,
      date_from: bulk.value.date_from || undefined,
      date_to: bulk.value.date_to || undefined,
    })
    showSuccess(`${res.updated}件のマッチに「${bulk.value.deck_name}」を設定しました`)
  } catch {
    showError('一括上書きに失敗しました')
  }
}

onMounted(async () => {
  try {
    const [defs, players, formats] = await Promise.all([
      fetchDeckDefinitions(),
      fetchPlayers(),
      fetchFormats(),
    ])
    definitions.value = defs
    playerList.value = players
    formatList.value = formats
  } catch {
    showError('データの取得に失敗しました')
  }
})
</script>

<style scoped>
.deck-def {
  padding: 24px;
  max-width: 960px;
}

.deck-def__title {
  font-size: 1.2rem;
  font-weight: bold;
  margin-bottom: 20px;
}

.deck-def__section {
  background: #fff;
  border: 1px solid #e0d8c8;
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 20px;
}

.deck-def__section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.deck-def__section-title {
  font-size: 13px;
  font-weight: bold;
  color: #7a6a55;
  margin-bottom: 12px;
}

.deck-def__section-header .deck-def__section-title {
  margin-bottom: 0;
}

.deck-def__list-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.deck-def__select--sm {
  font-size: 11px;
  padding: 3px 6px;
}

.deck-def__apply-btns {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.deck-def__apply-note {
  font-size: 11px;
  color: #7a6a55;
  margin: 0;
  width: 100%;
}

.deck-def__bulk-form {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: flex-end;
}

.deck-def__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.deck-def__field--full {
  width: 100%;
}

.deck-def__label {
  font-size: 11px;
  color: #7a6a55;
}

.deck-def__input {
  padding: 5px 8px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 13px;
  font-family: inherit;
  background: #fff;
  color: #2c2416;
}

.deck-def__input--short {
  width: 80px;
}

.deck-def__select {
  padding: 5px 8px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 13px;
  background: #fff;
  color: #2c2416;
}

.deck-def__textarea {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 13px;
  font-family: inherit;
  resize: vertical;
}

.deck-def__btn {
  padding: 5px 14px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  background: #faf7f0;
  font-size: 13px;
  cursor: pointer;
  color: #2c2416;
  white-space: nowrap;
}

.deck-def__btn:hover:not(:disabled) {
  background: #f0ece0;
}

.deck-def__btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.deck-def__btn--primary {
  background: #4a6fa5;
  border-color: #4a6fa5;
  color: #fff;
}

.deck-def__btn--primary:hover:not(:disabled) {
  background: #3a5f95;
}

.deck-def__btn--danger {
  color: #a03030;
  border-color: #d8a0a0;
}

.deck-def__btn--sm {
  padding: 3px 10px;
  font-size: 12px;
}

.deck-def__empty {
  color: #b0a090;
  font-size: 13px;
  padding: 16px 0;
  text-align: center;
}

.deck-def__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.deck-def__table th {
  text-align: left;
  padding: 6px 8px;
  border-bottom: 2px solid #e0d8c8;
  color: #7a6a55;
  font-size: 11px;
  font-weight: normal;
  white-space: nowrap;
}

.deck-def__th-num {
  text-align: right;
}

.deck-def__table td {
  padding: 6px 8px;
  border-bottom: 1px solid #f0ece0;
  vertical-align: top;
}

.deck-def__td-num {
  text-align: right;
}

.deck-def__td-cards {
  color: #7a6a55;
  font-size: 12px;
  max-width: 300px;
}

.deck-def__td-actions {
  white-space: nowrap;
  display: flex;
  gap: 6px;
}

.deck-def__file-hidden {
  display: none;
}

.deck-def__file-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.deck-def__file-name {
  font-size: 12px;
  color: #7a6a55;
}

.deck-def__field--grow {
  flex: 1;
  min-width: 200px;
}

.deck-def__btn--claude {
  background: #7c4a9e;
  border-color: #7c4a9e;
  color: #fff;
}

.deck-def__btn--claude:hover:not(:disabled) {
  background: #6a3a8c;
}

/* 生成プレビューモーダル */
.deck-def__modal--wide {
  width: min(1100px, 92vw);
}

.deck-def__modal--wide .deck-def__modal-footer {
  flex-wrap: wrap;
}

.deck-def__gen-meta {
  font-size: 12px;
  color: #7a6a55;
  margin-bottom: 12px;
}

.deck-def__gen-list {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #e0d8c8;
  border-radius: 4px;
  margin-bottom: 16px;
}

.deck-def__gen-item {
  padding: 8px 12px;
  border-bottom: 1px solid #f0ece0;
}

.deck-def__gen-item:last-child {
  border-bottom: none;
}

.deck-def__gen-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}

.deck-def__gen-name {
  font-weight: bold;
  font-size: 13px;
}

.deck-def__gen-threshold {
  font-size: 11px;
  color: #7a6a55;
  background: #f0ece0;
  padding: 1px 6px;
  border-radius: 10px;
}

.deck-def__gen-cards {
  font-size: 12px;
  color: #7a6a55;
}

.deck-def__gen-import-opts {
  display: flex;
  gap: 8px;
  align-items: center;
}

/* モーダル */
.deck-def__overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.deck-def__modal {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  width: 480px;
  max-width: 90vw;
  max-height: 90vh;
  overflow-y: auto;
}

.deck-def__modal-title {
  font-size: 1rem;
  font-weight: bold;
  margin-bottom: 16px;
}

.deck-def__form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

.deck-def__modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
