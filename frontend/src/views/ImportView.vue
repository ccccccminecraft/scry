<template>
  <div class="import">
    <ConfirmDialog
      :visible="confirmVisible"
      :message="confirmMessage"
      confirm-label="実行"
      @confirm="onConfirm"
      @cancel="confirmVisible = false"
    />

    <div class="import__header">
      <h1 class="import__title">ログのインポート</h1>
      <button v-if="state !== 'idle'" class="btn-back" @click="reset">← 戻る</button>
    </div>

    <!-- Idle -->
    <template v-if="state === 'idle'">

      <!-- クイックインポート -->
      <div class="quick">
        <div class="quick__label">クイックインポート</div>

        <!-- フォルダ登録済み -->
        <template v-if="quickFolder">
          <p class="quick__path">📁 {{ quickFolder }}</p>
          <p class="quick__since">
            最終インポート:
            <span v-if="latestDate">{{ formatDate(latestDate) }}</span>
            <span v-else class="quick__since--none">なし（全件対象）</span>
          </p>
          <div class="quick__actions">
            <button
              class="btn btn--primary"
              :disabled="quickRunning"
              @click="confirmQuickImport"
            >
              {{ quickRunning ? 'スキャン中...' : '⚡ クイックインポート' }}
            </button>
            <button class="btn" @click="changeFolder">フォルダを変更</button>
          </div>
        </template>

        <!-- フォルダ未登録 -->
        <template v-else>
          <p class="quick__desc">
            フォルダを登録するとワンクリックで新規ログをインポートできます
          </p>
          <button class="btn btn--primary" @click="registerFolder">フォルダを登録する</button>
        </template>
      </div>

      <div class="divider">── または ──</div>

      <!-- 手動インポート -->
      <div
        class="dropzone"
        :class="{ 'dropzone--over': dragOver }"
        @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false"
        @drop.prevent="handleDrop"
      >
        <p class="dropzone__label">ファイルをドラッグ＆ドロップ</p>
        <p class="dropzone__sub">または</p>
        <button class="btn btn--primary" @click="selectFile">ファイルを選択</button>
      </div>

      <div class="divider">── または ──</div>

      <div class="folder-area">
        <button class="btn btn--folder" @click="scanFolder">
          📁 フォルダから一括取り込む
        </button>
        <p class="hint">ヒント: C:\Users\[ユーザー名]\AppData\Local\Apps\2.0</p>
      </div>
    </template>

    <!-- Scanning -->
    <div v-else-if="state === 'scanning'" class="status-msg">
      フォルダをスキャン中...
    </div>

    <!-- Scan result -->
    <template v-else-if="state === 'scan_result'">
      <p class="scan-info">📁 {{ folderPath }}</p>
      <p class="scan-count">{{ scanFiles.length }} 件のログファイルが見つかりました</p>

      <div class="scan-actions">
        <button class="btn-link" @click="toggleAll">
          {{ allChecked ? 'すべて解除' : 'すべて選択' }}
        </button>
        <span class="scan-actions__selected">{{ checkedCount }} 件選択中</span>
      </div>

      <div class="scan-list">
        <label
          v-for="f in scanFiles"
          :key="f.path"
          class="scan-item"
        >
          <input type="checkbox" v-model="f.checked" class="scan-item__check" />
          <span class="scan-item__name">{{ f.name }}</span>
        </label>
      </div>

      <div class="scan-footer">
        <button
          class="btn btn--primary"
          :disabled="checkedCount === 0"
          @click="confirmStartImport"
        >
          選択した {{ checkedCount }} 件をインポート
        </button>
      </div>
    </template>

    <!-- Importing -->
    <div v-else-if="state === 'importing'" class="importing">
      <p class="importing__label">インポート中... {{ importDone }} / {{ importTotal }} 件</p>
      <div class="progress-bar">
        <div class="progress-bar__fill" :style="{ width: progressPct + '%' }"></div>
      </div>
    </div>

    <!-- Batch result -->
    <template v-else-if="state === 'batch_result'">
      <div class="result">
        <p class="result__title">✅ インポート完了</p>

        <table class="result__table">
          <tr>
            <td class="result__label">インポート済み</td>
            <td class="result__count result__count--imported">{{ batchResult!.imported }} 件</td>
          </tr>
          <tr>
            <td class="result__label">スキップ（重複）</td>
            <td class="result__count">{{ batchResult!.skipped }} 件</td>
          </tr>
          <tr>
            <td class="result__label">エラー</td>
            <td class="result__count" :class="{ 'result__count--error': batchResult!.errors > 0 }">
              {{ batchResult!.errors }} 件
            </td>
          </tr>
        </table>

        <div v-if="batchResult!.errors > 0" class="result__errors">
          <p class="result__errors-title">エラー詳細</p>
          <ul class="result__errors-list">
            <li v-for="r in errorResults" :key="r.name">
              {{ r.name }}: {{ r.reason }}
            </li>
          </ul>
        </div>

        <div class="result__actions">
          <button class="btn" @click="reset">続けて取り込む</button>
          <button class="btn btn--primary" @click="$router.push('/matches')">対戦履歴を見る</button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { importSingleFile, type ImportResult } from '../api/import'
import { fetchSettings, updateSettings } from '../api/settings'
import { fetchLatestMatchDate } from '../api/matches'
import { useToast } from '../composables/useToast'
import ConfirmDialog from '../components/ConfirmDialog.vue'

const { showError, showSuccess } = useToast()

// 確認ダイアログ
const confirmVisible = ref(false)
const confirmMessage = ref('')
const pendingAction = ref<(() => void) | null>(null)

function showConfirm(message: string, action: () => void) {
  confirmMessage.value = message
  pendingAction.value = action
  confirmVisible.value = true
}

function onConfirm() {
  confirmVisible.value = false
  pendingAction.value?.()
  pendingAction.value = null
}

type State = 'idle' | 'scanning' | 'scan_result' | 'importing' | 'batch_result'

const state = ref<State>('idle')
const dragOver = ref(false)

// クイックインポート
const quickFolder = ref<string | null>(null)
const latestDate = ref<string | null>(null)
const quickRunning = ref(false)

// scan result
const folderPath = ref('')
interface ScanFile { path: string; name: string; checked: boolean }
const scanFiles = ref<ScanFile[]>([])

// import progress
const importDone = ref(0)
const importTotal = ref(0)
const progressPct = computed(() =>
  importTotal.value > 0 ? Math.round((importDone.value / importTotal.value) * 100) : 0,
)

// batch result
interface BatchResult {
  imported: number
  skipped: number
  errors: number
  results: Array<{ name: string; status: string; match_id?: string; reason?: string }>
}
const batchResult = ref<BatchResult | null>(null)
const errorResults = computed(() =>
  batchResult.value?.results.filter(r => r.status === 'error') ?? [],
)

const checkedCount = computed(() => scanFiles.value.filter(f => f.checked).length)
const allChecked = computed(() => scanFiles.value.length > 0 && checkedCount.value === scanFiles.value.length)

onMounted(async () => {
  try {
    const [settings, latest] = await Promise.all([
      fetchSettings(),
      fetchLatestMatchDate(),
    ])
    quickFolder.value = settings.quick_import_folder
    latestDate.value = latest
  } catch {
    // 失敗しても無視
  }
})

function reset() {
  state.value = 'idle'
  dragOver.value = false
  folderPath.value = ''
  scanFiles.value = []
  importDone.value = 0
  importTotal.value = 0
  batchResult.value = null
  // 最終インポート日時を再取得
  fetchLatestMatchDate().then(d => { latestDate.value = d }).catch(() => {})
}

function toggleAll() {
  const next = !allChecked.value
  scanFiles.value.forEach(f => { f.checked = next })
}

// ── クイックインポート ────────────────────────────────────────────────────

async function registerFolder() {
  const result = await window.electronAPI.scanFolder()
  if (!result) return
  await saveQuickFolder(result.folderPath)
}

async function changeFolder() {
  const result = await window.electronAPI.scanFolder()
  if (!result) return
  await saveQuickFolder(result.folderPath)
}

async function saveQuickFolder(path: string) {
  try {
    await updateSettings({ quick_import_folder: path })
    quickFolder.value = path
  } catch (e) {
    showError(e instanceof Error ? e.message : 'フォルダの保存に失敗しました')
  }
}

function confirmQuickImport() {
  showConfirm(
    'クイックインポートを実行します。前回インポート以降の新しいファイルをすべて取り込みます。よろしいですか？',
    runQuickImport,
  )
}

async function runQuickImport() {
  if (!quickFolder.value || quickRunning.value) return
  quickRunning.value = true
  try {
    const files = await window.electronAPI.scanFolderQuick(quickFolder.value)

    // mtime > latest_date のファイルのみ抽出
    const sinceMs = latestDate.value ? new Date(latestDate.value).getTime() : 0
    const targets = files
      .filter(f => f.mtime > sinceMs)
      .map(f => ({ path: f.path, name: f.path.split(/[\\/]/).pop() ?? f.path }))

    if (targets.length === 0) {
      showSuccess('新しいログはありません')
      return
    }

    await runImport(targets)
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'スキャンに失敗しました'
    // フォルダが存在しない場合は登録を解除
    if (msg.includes('ENOENT') || msg.includes('no such file')) {
      showError('登録フォルダが見つかりません。フォルダを再登録してください')
      await updateSettings({ quick_import_folder: null }).catch(() => {})
      quickFolder.value = null
    } else {
      showError(msg)
    }
  } finally {
    quickRunning.value = false
  }
}

// ── 手動インポート ───────────────────────────────────────────────────────

async function selectFile() {
  const path = await window.electronAPI.selectDatFile()
  if (!path) return
  const name = path.split(/[\\/]/).pop() ?? path
  await runImport([{ path, name }])
}

async function handleDrop(e: DragEvent) {
  dragOver.value = false
  const files = e.dataTransfer?.files
  if (!files || files.length === 0) return

  const items: Array<{ path: string; name: string }> = []
  for (let i = 0; i < files.length; i++) {
    const f = files[i] as File & { path?: string }
    if (!f.name.endsWith('.dat')) continue
    const filePath = f.path ?? f.name
    items.push({ path: filePath, name: f.name })
  }
  if (items.length === 0) {
    showError('.dat ファイルをドロップしてください')
    return
  }
  await runImport(items)
}

async function scanFolder() {
  state.value = 'scanning'
  try {
    const result = await window.electronAPI.scanFolder()
    if (!result) {
      state.value = 'idle'
      return
    }
    if (result.files.length === 0) {
      showError('対象の .dat ファイルが見つかりませんでした')
      state.value = 'idle'
      return
    }
    folderPath.value = result.folderPath
    scanFiles.value = result.files.map(p => ({
      path: p,
      name: p.split(/[\\/]/).pop() ?? p,
      checked: true,
    }))
    state.value = 'scan_result'
  } catch (e) {
    showError(e instanceof Error ? e.message : 'フォルダのスキャンに失敗しました')
    state.value = 'idle'
  }
}

function confirmStartImport() {
  const count = checkedCount.value
  if (count === 0) return
  showConfirm(
    `選択した ${count} 件をインポートします。よろしいですか？`,
    startImport,
  )
}

async function startImport() {
  const targets = scanFiles.value.filter(f => f.checked)
  if (targets.length === 0) return
  await runImport(targets)
}

async function runImport(targets: Array<{ path: string; name: string }>) {
  state.value = 'importing'
  importDone.value = 0
  importTotal.value = targets.length

  let imported = 0
  let skipped = 0
  let errors = 0
  const results: BatchResult['results'] = []

  for (const target of targets) {
    try {
      const buf: Buffer = await window.electronAPI.readDatFile(target.path)
      const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer
      const result: ImportResult = await importSingleFile(target.name, ab)

      results.push({ name: target.name, status: result.status, match_id: result.match_id, reason: result.reason ?? undefined })
      if (result.status === 'imported') imported++
      else if (result.status === 'skipped') skipped++
      else errors++
    } catch (e) {
      const reason = e instanceof Error ? e.message : '不明なエラー'
      results.push({ name: target.name, status: 'error', reason })
      errors++
    }
    importDone.value++
  }

  batchResult.value = { imported, skipped, errors, results }
  state.value = 'batch_result'
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('ja-JP', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}
</script>

<style scoped>
.import {
  padding: 32px 40px;
  max-width: 960px;
}

.import__header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 28px;
}

.import__title {
  font-size: 1.2rem;
  margin: 0;
}

.btn-back {
  background: none;
  border: none;
  color: #7a6a55;
  font-size: 13px;
  cursor: pointer;
  padding: 0;
}

.btn-back:hover {
  color: #2c2416;
}

/* ── クイックインポート ── */
.quick {
  background: #fff;
  border: 1px solid #e0d8c8;
  border-radius: 8px;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.quick__label {
  font-size: 11px;
  font-weight: bold;
  color: #7a6a55;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.quick__path {
  font-size: 13px;
  color: #2c2416;
  word-break: break-all;
  margin: 0;
}

.quick__since {
  font-size: 12px;
  color: #9a8a76;
  margin: 0;
}

.quick__since--none {
  color: #b0a090;
  font-style: italic;
}

.quick__actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.quick__desc {
  font-size: 13px;
  color: #7a6a55;
  margin: 0;
}

/* ── Dropzone ── */
.dropzone {
  border: 2px dashed #c8b89a;
  border-radius: 8px;
  padding: 40px 32px;
  text-align: center;
  background: #faf7f0;
  transition: background 0.15s, border-color 0.15s;
}

.dropzone--over {
  background: #f0ece0;
  border-color: #4a6fa5;
}

.dropzone__label {
  font-size: 15px;
  color: #2c2416;
  margin-bottom: 8px;
}

.dropzone__sub {
  font-size: 12px;
  color: #b0a090;
  margin-bottom: 16px;
}

.divider {
  text-align: center;
  color: #b0a090;
  font-size: 13px;
  margin: 20px 0;
}

.folder-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.hint {
  font-size: 12px;
  color: #9a8a76;
}

/* ── Buttons ── */
.btn {
  padding: 8px 20px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  background: #faf7f0;
  color: #2c2416;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
}

.btn:hover:not(:disabled) {
  background: #f0ece0;
}

.btn--primary {
  background: #4a6fa5;
  border-color: #4a6fa5;
  color: #fff;
}

.btn--primary:hover:not(:disabled) {
  background: #3a5f95;
}

.btn--folder {
  padding: 10px 24px;
  font-size: 14px;
}

.btn:disabled {
  opacity: 0.4;
  cursor: default;
}

/* ── Scan result ── */
.scan-info {
  font-size: 13px;
  color: #7a6a55;
  margin-bottom: 4px;
  word-break: break-all;
}

.scan-count {
  font-size: 14px;
  color: #2c2416;
  margin-bottom: 12px;
}

.scan-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 8px;
}

.btn-link {
  background: none;
  border: none;
  color: #4a6fa5;
  font-size: 13px;
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
  font-family: inherit;
}

.scan-actions__selected {
  font-size: 12px;
  color: #9a8a76;
}

.scan-list {
  border: 1px solid #e0d8c8;
  border-radius: 6px;
  max-height: 360px;
  overflow-y: auto;
  background: #fff;
}

.scan-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 12px;
  border-bottom: 1px solid #f0ece0;
  cursor: pointer;
}

.scan-item:last-child {
  border-bottom: none;
}

.scan-item:hover {
  background: #faf7f0;
}

.scan-item__check {
  flex-shrink: 0;
  cursor: pointer;
}

.scan-item__name {
  font-size: 13px;
  color: #2c2416;
  word-break: break-all;
}

.scan-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

/* ── Importing ── */
.status-msg {
  color: #7a6a55;
  padding: 48px 0;
  text-align: center;
  font-size: 14px;
}

.importing {
  padding: 48px 0;
  text-align: center;
}

.importing__label {
  font-size: 14px;
  color: #2c2416;
  margin-bottom: 16px;
}

.progress-bar {
  height: 8px;
  background: #e0d8c8;
  border-radius: 4px;
  overflow: hidden;
  max-width: 360px;
  margin: 0 auto;
}

.progress-bar__fill {
  height: 100%;
  background: #4a6fa5;
  border-radius: 4px;
  transition: width 0.2s;
}

/* ── Result ── */
.result {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result__title {
  font-size: 16px;
  font-weight: bold;
  color: #2c2416;
}

.result__table {
  border-collapse: collapse;
  font-size: 14px;
}

.result__table td {
  padding: 6px 16px 6px 0;
}

.result__label {
  color: #7a6a55;
  min-width: 160px;
}

.result__count {
  font-weight: bold;
  color: #2c2416;
}

.result__count--imported {
  color: #3a7a3a;
}

.result__count--error {
  color: #a03030;
}

.result__errors {
  background: #fff0f0;
  border: 1px solid #e0b0b0;
  border-radius: 6px;
  padding: 12px 16px;
}

.result__errors-title {
  font-size: 13px;
  font-weight: bold;
  color: #a03030;
  margin-bottom: 6px;
}

.result__errors-list {
  margin: 0;
  padding-left: 20px;
  font-size: 12px;
  color: #7a3030;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.result__actions {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}
</style>
