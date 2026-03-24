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

    <!-- タブ -->
    <div v-if="state === 'idle'" class="tabs">
      <button
        class="tab"
        :class="{ 'tab--active': activeTab === 'mtgo' }"
        @click="activeTab = 'mtgo'"
      >MTGO</button>
      <button
        class="tab"
        :class="{ 'tab--active': activeTab === 'mtga' }"
        @click="activeTab = 'mtga'"
      >MTGA (Surveil)</button>
    </div>

    <!-- ── MTGA タブ ── -->
    <template v-if="state === 'idle' && activeTab === 'mtga'">
      <div class="quick">
        <div class="quick__label">登録フォルダ</div>

        <!-- フォルダ登録済み -->
        <template v-if="surveilFolder">
          <p class="quick__path">📁 {{ surveilFolder }}</p>
          <p v-if="surveilPending !== null" class="quick__since">
            未取り込み:
            <span v-if="surveilPending > 0" style="color: #4a6fa5; font-weight: bold;">{{ surveilPending }} 件</span>
            <span v-else>なし</span>
          </p>
          <div class="quick__actions">
            <button
              class="btn btn--primary"
              :disabled="surveilRunning || surveilPending === 0"
              @click="runSurveilScan"
            >
              {{ surveilRunning ? '取り込み中...' : '全て取り込む' }}
            </button>
            <button class="btn" @click="loadSurveilPending" :disabled="surveilRunning">更新</button>
            <button class="btn" @click="changeSurveilFolder">フォルダを変更</button>
            <button class="btn btn--danger" @click="clearSurveilFolderSetting" :disabled="surveilRunning">解除</button>
          </div>

          <!-- pending ファイル一覧 -->
          <div v-if="surveilPendingFiles.length > 0" class="scan-list" style="margin-top: 8px;">
            <div
              v-for="f in surveilPendingFiles"
              :key="f.match_id"
              class="scan-item"
              style="cursor: default;"
            >
              <span class="scan-item__name">{{ f.filename }}</span>
              <span style="margin-left: auto; font-size: 11px; color: #b0a090;">
                {{ new Date(f.mtime * 1000).toLocaleString('ja-JP') }}
              </span>
            </div>
          </div>
        </template>

        <!-- フォルダ未登録 -->
        <template v-else>
          <p class="quick__desc">
            Surveil の出力フォルダ（matches/）を登録してください
          </p>
          <button class="btn btn--primary" style="align-self: flex-start;" @click="registerSurveilFolder">フォルダを登録する</button>
        </template>
      </div>

      <div class="divider">── または ──</div>

      <div
        class="dropzone"
        :class="{ 'dropzone--over': dragOver }"
        @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false"
        @drop.prevent="handleSurveilDrop"
      >
        <p class="dropzone__label">JSON ファイルをドラッグ＆ドロップ</p>
        <p class="dropzone__sub">または</p>
        <button class="btn btn--primary" @click="selectSurveilFile">ファイルを選択</button>
      </div>

      <div class="divider">── または ──</div>

      <div class="folder-area">
        <button class="btn btn--folder" @click="scanSurveilFolderBulk">
          📁 フォルダから一括で取り込む
        </button>
      </div>
    </template>

    <!-- Idle -->
    <template v-if="state === 'idle' && activeTab === 'mtgo'">

      <!-- 登録フォルダ -->
      <div class="quick">
        <div class="quick__label">登録フォルダ</div>

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
              {{ quickRunning ? 'スキャン中...' : '⚡ 新着を取り込む' }}
            </button>
            <button class="btn" @click="changeFolder">フォルダを変更</button>
            <button class="btn btn--danger" @click="clearQuickFolder" :disabled="quickRunning">解除</button>
          </div>
        </template>

        <!-- フォルダ未登録 -->
        <template v-else>
          <p class="quick__desc">
            フォルダを登録するとワンクリックで新規ログをインポートできます
          </p>
          <button class="btn btn--primary" style="align-self: flex-start;" @click="registerFolder">フォルダを登録する</button>
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
          📁 フォルダから一括で取り込む
        </button>
        <p class="hint">ヒント: C:\Users\[ユーザー名]\AppData\Local\Apps\2.0</p>
      </div>

      <!-- インポートオプション -->
      <div class="import-options">
        <label class="import-options__item">
          <input type="checkbox" v-model="skipFormatInference" />
          <span>Scryfall でのフォーマット自動推定をスキップする</span>
        </label>
        <p v-if="skipFormatInference" class="import-options__note">
          ⚡ Scryfall API を呼ばないため大量インポートが高速になります。フォーマットは「不明」として保存されます。
        </p>
        <p v-else class="import-options__note import-options__note--muted">
          未キャッシュのカードは Scryfall API から取得するため、初回の大量インポートは時間がかかります。
        </p>
      </div>
    </template>  <!-- /mtgo idle -->

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
      <button
        class="btn btn--cancel"
        :disabled="cancelling"
        @click="handleCancel"
      >
        {{ cancelling ? '中断中...' : '中断する' }}
      </button>
      <div v-if="importLog.length > 0" class="import-log" ref="importLogEl">
        <div v-for="(line, i) in importLog" :key="i" class="import-log__line">{{ line }}</div>
      </div>
    </div>

    <!-- Batch result -->
    <template v-else-if="state === 'batch_result'">
      <div class="result">
        <p v-if="cancelRequested" class="result__title result__title--cancelled">⚠️ インポートを中断しました</p>
        <p v-else class="result__title">✅ インポート完了</p>

        <table class="result__table">
          <tr>
            <td class="result__label">インポート済み</td>
            <td class="result__count result__count--imported">{{ batchResult!.imported }} 件</td>
          </tr>
          <tr>
            <td class="result__label">スキップ（重複）</td>
            <td class="result__count">{{ batchResult!.skipped }} 件</td>
          </tr>
          <tr v-if="batchResult!.cancelled > 0">
            <td class="result__label">中断スキップ</td>
            <td class="result__count">{{ batchResult!.cancelled }} 件</td>
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
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import {
  importSingleFile,
  importSurveilFile,
  getSurveilFolder,
  setSurveilFolder,
  clearSurveilFolder,
  getSurveilImportedIds,
  getImportStatus,
  cancelImport,
  type ImportResult,
} from '../api/import'
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
const activeTab = ref<'mtgo' | 'mtga'>('mtgo')

// クイックインポート (MTGO)
const quickFolder = ref<string | null>(null)
const latestDate = ref<string | null>(null)
const quickRunning = ref(false)

// Surveil (MTGA)
interface SurveilPendingItem {
  filename: string
  match_id: string
  mtime: number  // seconds (表示用)
  size: number
  path: string   // ローカルパス (Electron 読み込み用)
}
const surveilFolder = ref<string | null>(null)
const surveilPending = ref<number | null>(null)
const surveilPendingFiles = ref<SurveilPendingItem[]>([])
const surveilRunning = ref(false)

// scan result
const folderPath = ref('')
const scanMode = ref<'mtgo' | 'mtga'>('mtgo')
interface ScanFile { path: string; name: string; checked: boolean }
const scanFiles = ref<ScanFile[]>([])

// import progress
const importDone = ref(0)
const importTotal = ref(0)
const progressPct = computed(() =>
  importTotal.value > 0 ? Math.round((importDone.value / importTotal.value) * 100) : 0,
)
const importLog = ref<string[]>([])
const importLogEl = ref<HTMLElement | null>(null)
const cancelRequested = ref(false)
const cancelling = ref(false)

watch(importLog, async () => {
  await nextTick()
  if (importLogEl.value) {
    importLogEl.value.scrollTop = importLogEl.value.scrollHeight
  }
}, { deep: true })

// batch result
interface BatchResult {
  imported: number
  skipped: number
  cancelled: number
  errors: number
  results: Array<{ name: string; status: string; match_id?: string; reason?: string }>
}
const batchResult = ref<BatchResult | null>(null)
const errorResults = computed(() =>
  batchResult.value?.results.filter(r => r.status === 'error') ?? [],
)

const skipFormatInference = ref(false)

const checkedCount = computed(() => scanFiles.value.filter(f => f.checked).length)
const allChecked = computed(() => scanFiles.value.length > 0 && checkedCount.value === scanFiles.value.length)

onMounted(async () => {
  try {
    const [settings, latest, surveilFolderRes] = await Promise.all([
      fetchSettings(),
      fetchLatestMatchDate('mtgo'),
      getSurveilFolder(),
    ])
    quickFolder.value = settings.quick_import_folder
    latestDate.value = latest
    surveilFolder.value = surveilFolderRes.folder
    if (surveilFolderRes.folder) {
      loadSurveilPending()
    }
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
  importLog.value = []
  cancelRequested.value = false
  cancelling.value = false
  batchResult.value = null
  // 最終インポート日時を再取得
  fetchLatestMatchDate('mtgo').then(d => { latestDate.value = d }).catch(() => {})
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

async function clearQuickFolder() {
  try {
    await updateSettings({ quick_import_folder: null })
    quickFolder.value = null
  } catch {
    showError('フォルダの解除に失敗しました')
  }
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
    '登録フォルダから新着ファイルを取り込みます。前回インポート以降の新しいファイルをすべて対象にします。よろしいですか？',
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

// ── Surveil (MTGA) ──────────────────────────────────────────────────────

async function registerSurveilFolder() {
  const result = await window.electronAPI.scanFolder()
  if (!result) return
  await saveSurveilFolder(result.folderPath)
}

async function changeSurveilFolder() {
  const result = await window.electronAPI.scanFolder()
  if (!result) return
  await saveSurveilFolder(result.folderPath)
}

async function clearSurveilFolderSetting() {
  try {
    await clearSurveilFolder()
    surveilFolder.value = null
    surveilPending.value = null
    surveilPendingFiles.value = []
  } catch {
    showError('フォルダの解除に失敗しました')
  }
}

async function saveSurveilFolder(path: string) {
  try {
    await setSurveilFolder(path)
    surveilFolder.value = path
    await loadSurveilPending()
  } catch (e) {
    showError(e instanceof Error ? e.message : 'フォルダの保存に失敗しました')
  }
}

async function loadSurveilPending() {
  if (!surveilFolder.value) return
  try {
    const [files, importedIds] = await Promise.all([
      window.electronAPI.scanSurveilFolder(surveilFolder.value),
      getSurveilImportedIds(),
    ])
    const importedSet = new Set(importedIds)
    const pending = files
      .filter(f => !importedSet.has(f.name.replace(/\.json$/i, '')))
      .sort((a, b) => b.mtime - a.mtime)
      .map(f => ({
        filename: f.name,
        match_id: f.name.replace(/\.json$/i, ''),
        mtime: f.mtime / 1000,
        size: f.size,
        path: f.path,
      }))
    surveilPendingFiles.value = pending
    surveilPending.value = pending.length
  } catch {
    surveilPending.value = null
  }
}

async function runSurveilScan() {
  if (surveilRunning.value) return
  surveilRunning.value = true
  try {
    const targets = surveilPendingFiles.value.map(f => ({ path: f.path, name: f.filename }))
    if (targets.length === 0) {
      showSuccess('取り込むファイルがありません')
      return
    }
    await runSurveilImport(targets)
  } catch (e) {
    showError(e instanceof Error ? e.message : '取り込みに失敗しました')
  } finally {
    surveilRunning.value = false
    surveilPendingFiles.value = []
    surveilPending.value = 0
  }
}

async function handleSurveilDrop(e: DragEvent) {
  dragOver.value = false
  const files = e.dataTransfer?.files
  if (!files || files.length === 0) return

  const items: Array<{ path: string; name: string }> = []
  for (let i = 0; i < files.length; i++) {
    const f = files[i] as File & { path?: string }
    if (!f.name.endsWith('.json')) continue
    items.push({ path: f.path ?? f.name, name: f.name })
  }
  if (items.length === 0) {
    showError('.json ファイルをドロップしてください')
    return
  }
  await runSurveilImport(items)
}

async function selectSurveilFile() {
  const path = await window.electronAPI.selectJsonFile()
  if (!path) return
  const name = path.split(/[\\/]/).pop() ?? path
  await runSurveilImport([{ path, name }])
}

async function runSurveilImport(targets: Array<{ path: string; name: string }>) {
  state.value = 'importing'
  importDone.value = 0
  importTotal.value = targets.length
  importLog.value = []
  cancelRequested.value = false
  cancelling.value = false

  let imported = 0
  let skipped = 0
  let cancelled = 0
  let errors = 0
  const results: BatchResult['results'] = []

  const pollInterval = setInterval(async () => {
    try {
      const status = await getImportStatus()
      importLog.value = status.log
    } catch { /* ignore */ }
  }, 500)

  try {
    for (const target of targets) {
      if (cancelRequested.value) {
        results.push({ name: target.name, status: 'skipped', reason: 'cancelled' })
        cancelled++
        importDone.value++
        continue
      }
      try {
        const buf: Buffer = await window.electronAPI.readDatFile(target.path)
        const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer
        const result: ImportResult = await importSurveilFile(target.name, ab)

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
  } finally {
    clearInterval(pollInterval)
    try {
      const status = await getImportStatus()
      importLog.value = status.log
    } catch { /* ignore */ }
  }

  batchResult.value = { imported, skipped, cancelled, errors, results }
  state.value = 'batch_result'
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
    scanMode.value = 'mtgo'
    state.value = 'scan_result'
  } catch (e) {
    showError(e instanceof Error ? e.message : 'フォルダのスキャンに失敗しました')
    state.value = 'idle'
  }
}

async function scanSurveilFolderBulk() {
  state.value = 'scanning'
  try {
    const result = await window.electronAPI.scanFolder()
    if (!result) {
      state.value = 'idle'
      return
    }
    const files = await window.electronAPI.scanSurveilFolder(result.folderPath)
    if (files.length === 0) {
      showError('.json ファイルが見つかりませんでした')
      state.value = 'idle'
      return
    }
    folderPath.value = result.folderPath
    scanFiles.value = files.map(f => ({
      path: f.path,
      name: f.name,
      checked: true,
    }))
    scanMode.value = 'mtga'
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
  if (scanMode.value === 'mtga') {
    await runSurveilImport(targets)
  } else {
    await runImport(targets)
  }
}

async function handleCancel() {
  if (cancelling.value) return
  cancelling.value = true
  cancelRequested.value = true
  try {
    await cancelImport()
  } catch { /* ignore */ }
}

async function runImport(targets: Array<{ path: string; name: string }>) {
  state.value = 'importing'
  importDone.value = 0
  importTotal.value = targets.length
  importLog.value = []
  cancelRequested.value = false
  cancelling.value = false

  let imported = 0
  let skipped = 0
  let cancelled = 0
  let errors = 0
  const results: BatchResult['results'] = []

  const pollInterval = setInterval(async () => {
    try {
      const status = await getImportStatus()
      importLog.value = status.log
    } catch { /* ignore */ }
  }, 500)

  try {
    for (const target of targets) {
      if (cancelRequested.value) {
        results.push({ name: target.name, status: 'skipped', reason: 'cancelled' })
        cancelled++
        importDone.value++
        continue
      }
      try {
        const buf: Buffer = await window.electronAPI.readDatFile(target.path)
        const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer
        const result: ImportResult = await importSingleFile(target.name, ab, skipFormatInference.value)

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
  } finally {
    clearInterval(pollInterval)
    try {
      const status = await getImportStatus()
      importLog.value = status.log
    } catch { /* ignore */ }
  }

  batchResult.value = { imported, skipped, cancelled, errors, results }
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

/* ── タブ ── */
.tabs {
  display: flex;
  border-bottom: 2px solid #e0d8c8;
  margin-bottom: 20px;
  gap: 4px;
}

.tab {
  padding: 8px 20px;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  background: none;
  color: #7a6a55;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  border-radius: 4px 4px 0 0;
}

.tab:hover {
  color: #2c2416;
  background: #f5f0e8;
}

.tab--active {
  color: #2c2416;
  font-weight: bold;
  border-bottom-color: #4a6fa5;
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

.btn--danger {
  color: #a03030;
  border-color: #d8a0a0;
}

.btn--danger:hover:not(:disabled) {
  background: #fff0f0;
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

.import-options {
  margin-top: 24px;
  padding: 14px 16px;
  background: #f5f0e8;
  border: 1px solid #d8cfc0;
  border-radius: 6px;
}

.import-options__item {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
  color: #2c2416;
}

.import-options__item input[type="checkbox"] {
  width: 15px;
  height: 15px;
  cursor: pointer;
  flex-shrink: 0;
}

.import-options__note {
  margin: 8px 0 0 23px;
  font-size: 12px;
  color: #7a5c30;
  line-height: 1.5;
}

.import-options__note--muted {
  color: #a09080;
}

.btn--cancel {
  margin-top: 16px;
  padding: 6px 20px;
  background: none;
  border: 1px solid #a07060;
  color: #a07060;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.btn--cancel:hover:not(:disabled) {
  background: #a07060;
  color: #fff;
}

.btn--cancel:disabled {
  opacity: 0.5;
  cursor: default;
}

.result__title--cancelled {
  color: #c08030;
}

.import-log {
  margin: 16px auto 0;
  max-width: 640px;
  max-height: 280px;
  overflow-y: auto;
  background: #1e1a14;
  border: 1px solid #3a3020;
  border-radius: 4px;
  padding: 10px 14px;
  text-align: left;
}

.import-log__line {
  font-family: monospace;
  font-size: 12px;
  line-height: 1.6;
  color: #c8bfa8;
  white-space: pre;
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
