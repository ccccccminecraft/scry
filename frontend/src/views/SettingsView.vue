<template>
  <div class="settings">
    <h1 class="settings__title">設定</h1>

    <div class="settings__section">
      <div class="settings__section-title">アプリケーション</div>
      <div class="settings__row">
        <button class="settings__btn settings__btn--primary" @click="reload">再読み込み</button>
      </div>
      <p class="settings__note">画面の表示がおかしい場合や設定を反映させたい場合にご利用ください。</p>
    </div>

    <div class="settings__section">
      <div class="settings__section-title">デフォルトプレイヤー</div>
      <div class="settings__row">
        <select v-model="defaultPlayerInput" class="settings__select">
          <option value="">未設定</option>
          <option v-for="p in playerList" :key="p" :value="p">{{ p }}</option>
        </select>
        <button class="settings__btn settings__btn--primary" @click="saveDefaultPlayer">保存</button>
      </div>
      <p class="settings__note">統計・AI分析・エクスポート画面を開いたときに自動で選択されるプレイヤーです。</p>
    </div>

    <div class="settings__section">
      <div class="settings__section-title">絞り込みの最低試合数</div>
      <div class="settings__row">
        <label class="settings__inline-label">プレイヤー</label>
        <input v-model.number="minPlayerMatchesInput" type="number" min="0" class="settings__number-input" />
      </div>
      <div class="settings__row">
        <label class="settings__inline-label">デッキ</label>
        <input v-model.number="minDeckMatchesInput" type="number" min="0" class="settings__number-input" />
        <button class="settings__btn settings__btn--primary" @click="saveMinMatches">保存</button>
      </div>
      <p class="settings__note">プルダウンの候補に表示するプレイヤーおよびデッキの最低試合数を設定します。0 で全件表示します。</p>
    </div>

    <div class="settings__section">
      <div class="settings__section-title">Anthropic API キー</div>
      <div class="settings__row">
        <span v-if="configured" class="settings__configured">設定済み ✓</span>
        <span v-else class="settings__not-configured">未設定</span>
      </div>
      <div class="settings__row">
        <input
          v-model="apiKeyInput"
          type="password"
          class="settings__input"
          placeholder="sk-ant-..."
          autocomplete="off"
        />
        <button class="settings__btn settings__btn--primary" @click="saveApiKey" :disabled="!apiKeyInput.trim()">
          保存
        </button>
        <button v-if="configured" class="settings__btn settings__btn--danger" @click="removeApiKey">
          削除
        </button>
      </div>
      <p class="settings__note">
        APIキーは <a href="https://console.anthropic.com/" target="_blank">Anthropic Console</a> で取得できます。
        入力したキーはローカルの SQLite データベースに保存されます。
      </p>
    </div>
    <div class="settings__section">
      <div class="settings__section-title">カード名データベース（MTGA）</div>

      <div class="settings__subsection-title">MTGA 公式カードデータ同期</div>
      <div class="settings__row">
        <input
          v-model="mtgaFolderInput"
          type="text"
          class="settings__input"
          placeholder="フォルダパスを入力または右のボタンで選択"
        />
        <button class="settings__btn" @click="handleSelectMtgaFolder">参照...</button>
        <button class="settings__btn settings__btn--primary" :disabled="!mtgaFolderInput.trim()" @click="handleSaveMtgaFolder">保存</button>
      </div>
      <div class="settings__row">
        <button
          class="settings__btn settings__btn--primary"
          :disabled="mtgaSyncing || !mtgaFolderSaved"
          @click="handleSyncMtgaCards"
        >
          {{ mtgaSyncing ? '同期中...' : 'MTGAデータを同期' }}
        </button>
        <span v-if="mtgaLastSyncedAt" class="settings__note" style="margin-top: 0;">
          最終同期: {{ mtgaLastSyncedAt }}
        </span>
      </div>
      <p class="settings__note">
        MTGA インストールフォルダ内の Raw_CardDatabase ファイルを読み込み、カード名キャッシュを更新します。
      </p>
    </div>

    <div class="settings__section">
      <div class="settings__section-title">自動インポート</div>
      <div class="settings__row">
        <label class="settings__toggle-label">
          <input type="checkbox" v-model="autoImportEnabled" @change="saveAutoImport" />
          自動インポートを有効にする
        </label>
      </div>
      <div class="settings__row">
        <label class="settings__inline-label">スキャン間隔</label>
        <input
          v-model.number="autoImportIntervalInput"
          type="number"
          min="10"
          class="settings__number-input"
          :disabled="!autoImportEnabled"
        />
        <span style="font-size: 13px; color: #7a6a55;">秒</span>
        <button
          class="settings__btn settings__btn--primary"
          :disabled="!autoImportEnabled"
          @click="saveAutoImport"
        >保存</button>
      </div>
      <div v-if="autoImportStatus" class="settings__row" style="flex-direction: column; align-items: flex-start; gap: 4px;">
        <span class="settings__note" style="margin-top: 0;">
          最終実行: {{ autoImportStatus.last_run_at ? new Date(autoImportStatus.last_run_at).toLocaleString('ja-JP') : 'なし' }}
        </span>
        <span v-if="autoImportStatus.last_result" class="settings__note" style="margin-top: 0;">
          MTGO: {{ autoImportStatus.last_result.mtgo.imported }} 件追加 / {{ autoImportStatus.last_result.mtgo.skipped }} 件スキップ / {{ autoImportStatus.last_result.mtgo.errors }} 件エラー
          &nbsp;|&nbsp;
          MTGA: {{ autoImportStatus.last_result.mtga.imported }} 件追加 / {{ autoImportStatus.last_result.mtga.skipped }} 件スキップ / {{ autoImportStatus.last_result.mtga.errors }} 件エラー
        </span>
      </div>
      <p class="settings__note">
        MTGO クイックインポートフォルダおよび Surveil 監視フォルダを定期的にスキャンし、新しい試合を自動で取り込みます。
        フォルダは各インポート画面で設定してください。
      </p>
    </div>

    <div class="settings__section">
      <div class="settings__section-title">データベース</div>
      <div class="settings__row">
        <button class="settings__btn settings__btn--primary" @click="handleDownloadBackup">バックアップをダウンロード</button>
      </div>
      <div class="settings__row">
        <input type="file" accept=".db" ref="restoreFileInput" @change="onRestoreFileChange" class="settings__file-hidden" />
        <button class="settings__btn" @click="restoreFileInput?.click()">ファイルを選択</button>
        <span class="settings__file-name">{{ restoreFile ? restoreFile.name : '未選択' }}</span>
        <button class="settings__btn settings__btn--danger" :disabled="!restoreFile" @click="handleRestore">リストア</button>
      </div>
      <p class="settings__note">リストアを実行すると現在のデータが置き換えられます。リストア前に自動バックアップが作成されます。</p>
    </div>

    <div class="settings__section">
      <div class="settings__section-title">データ削除</div>
      <div class="settings__row">
        <button class="settings__btn settings__btn--danger" @click="handleDeleteAllMatches">全試合データを削除</button>
      </div>
      <div class="settings__row">
        <label class="settings__inline-label">開始日</label>
        <input v-model="deleteFrom" type="date" class="settings__date-input" />
        <label class="settings__inline-label" style="width: auto; margin-left: 4px;">終了日</label>
        <input v-model="deleteTo" type="date" class="settings__date-input" />
        <button class="settings__btn settings__btn--danger" :disabled="!deleteFrom && !deleteTo" @click="handleDeleteRange">期間指定で削除</button>
      </div>
      <div class="settings__divider" />
      <div class="settings__row">
        <button class="settings__btn settings__btn--danger" @click="resetDialogVisible = true">完全リセット</button>
      </div>
      <p class="settings__note">完全リセットはすべてのデータ（試合・設定・デッキ定義）を削除します。</p>
    </div>

    <ConfirmDialog
      :visible="confirmVisible"
      :message="confirmMessage"
      confirm-label="削除"
      @confirm="onConfirmAction"
      @cancel="confirmVisible = false"
    />

    <ConfirmDialog
      :visible="restoreConfirmVisible"
      message="データベースをリストアしますか？現在のデータはすべて置き換えられます。"
      @confirm="onConfirmRestore"
      @cancel="restoreConfirmVisible = false"
    />

    <TypeToConfirmDialog
      :visible="resetDialogVisible"
      message="すべてのデータ（試合・設定・デッキ定義）が完全に削除されます。この操作は取り消せません。"
      confirm-text="削除する"
      @confirm="onConfirmReset"
      @cancel="resetDialogVisible = false"
    />

    <div v-if="appVersion" class="settings__version">v{{ appVersion }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { useToast } from '../composables/useToast'
import { fetchSettings, updateSettings, deleteApiKey, fetchAutoImportStatus, type AutoImportStatus } from '../api/settings'
import { fetchPlayers } from '../api/stats'
import { downloadBackup, restoreBackup } from '../api/backup'
import { deleteAllMatches, deleteMatchesByRange, resetDatabase } from '../api/deletion'
import { getMtgaSyncStatus, setMtgaFolder, syncMtgaCards } from '../api/admin'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import TypeToConfirmDialog from '../components/TypeToConfirmDialog.vue'

const { showSuccess, showError } = useToast()

const configured = ref(false)
const restoreFileInput = ref<HTMLInputElement | null>(null)
const restoreFile = ref<File | null>(null)
const restoreConfirmVisible = ref(false)
const confirmVisible = ref(false)
const confirmMessage = ref('')
const pendingAction = ref<(() => Promise<void>) | null>(null)
const deleteFrom = ref('')
const deleteTo = ref('')
const resetDialogVisible = ref(false)
const apiKeyInput = ref('')
const playerList = ref<string[]>([])
const defaultPlayerInput = ref('')
const appVersion = ref('')
const minPlayerMatchesInput = ref(1)
const minDeckMatchesInput = ref(1)
const mtgaFolderInput = ref('')
const mtgaFolderSaved = ref(false)
const mtgaSyncing = ref(false)
const mtgaLastSyncedAt = ref<string | null>(null)
const autoImportEnabled = ref(false)
const autoImportIntervalInput = ref(30)
const autoImportStatus = ref<AutoImportStatus | null>(null)

onMounted(async () => {
  try {
    const [s, players, health, mtgaStatus, aiStatus] = await Promise.all([
      fetchSettings(),
      fetchPlayers(),
      axios.get('http://localhost:18432/api/health').catch(() => null),
      getMtgaSyncStatus().catch(() => null),
      fetchAutoImportStatus().catch(() => null),
    ])
    configured.value = s.api_key_configured
    playerList.value = players
    defaultPlayerInput.value = s.default_player ?? ''
    appVersion.value = health?.data?.version ?? ''
    minPlayerMatchesInput.value = s.min_player_matches ?? 1
    minDeckMatchesInput.value = s.min_deck_matches ?? 1
    autoImportEnabled.value = s.auto_import_enabled ?? false
    autoImportIntervalInput.value = s.auto_import_interval_sec ?? 30
    autoImportStatus.value = aiStatus
    if (mtgaStatus?.folder) {
      mtgaFolderInput.value = mtgaStatus.folder
      mtgaFolderSaved.value = true
    }
    if (mtgaStatus?.last_synced_at) {
      mtgaLastSyncedAt.value = new Date(mtgaStatus.last_synced_at).toLocaleString('ja-JP')
    }
  } catch {
    showError('設定の取得に失敗しました')
  }
})

async function saveDefaultPlayer() {
  try {
    await updateSettings({ default_player: defaultPlayerInput.value || null })
    showSuccess('デフォルトプレイヤーを保存しました')
  } catch {
    showError('保存に失敗しました')
  }
}

async function saveMinMatches() {
  try {
    await updateSettings({
      min_player_matches: Math.max(0, minPlayerMatchesInput.value),
      min_deck_matches: Math.max(0, minDeckMatchesInput.value),
    })
    showSuccess('最低試合数を保存しました')
  } catch {
    showError('保存に失敗しました')
  }
}

async function saveApiKey() {
  if (!apiKeyInput.value.trim()) return
  try {
    await updateSettings({ api_key: apiKeyInput.value.trim() })
    configured.value = true
    apiKeyInput.value = ''
    showSuccess('APIキーを保存しました')
  } catch {
    showError('保存に失敗しました')
  }
}

function reload() {
  window.location.reload()
}

async function handleDownloadBackup() {
  try {
    await downloadBackup()
  } catch {
    showError('バックアップのダウンロードに失敗しました')
  }
}

function onRestoreFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  restoreFile.value = input.files?.[0] ?? null
}

function handleRestore() {
  if (!restoreFile.value) return
  restoreConfirmVisible.value = true
}

async function onConfirmRestore() {
  restoreConfirmVisible.value = false
  if (!restoreFile.value) return
  try {
    await restoreBackup(restoreFile.value)
    showSuccess('リストアが完了しました。再読み込みします...')
    setTimeout(() => window.location.reload(), 1000)
  } catch {
    showError('リストアに失敗しました')
  }
}

function handleDeleteAllMatches() {
  confirmMessage.value = '全試合データを削除しますか？設定・デッキ定義は保持されます。'
  pendingAction.value = async () => {
    const count = await deleteAllMatches()
    if (count === 0) {
      showSuccess('削除対象のデータがありませんでした')
    } else {
      showSuccess(`${count} 件の試合を削除しました`)
    }
  }
  confirmVisible.value = true
}

function handleDeleteRange() {
  confirmMessage.value = `期間を指定して試合を削除しますか？`
  pendingAction.value = async () => {
    const count = await deleteMatchesByRange(deleteFrom.value || undefined, deleteTo.value || undefined)
    if (count === 0) {
      showSuccess('削除対象のデータがありませんでした')
    } else {
      showSuccess(`${count} 件の試合を削除しました`)
    }
  }
  confirmVisible.value = true
}

async function onConfirmAction() {
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

async function onConfirmReset() {
  resetDialogVisible.value = false
  try {
    await resetDatabase()
    showSuccess('完全リセットが完了しました。再読み込みします...')
    setTimeout(() => window.location.reload(), 1000)
  } catch {
    showError('リセットに失敗しました')
  }
}

async function handleSelectMtgaFolder() {
  const folder = await window.electronAPI?.selectFolder()
  if (folder) mtgaFolderInput.value = folder
}

async function handleSaveMtgaFolder() {
  const folder = mtgaFolderInput.value.trim()
  if (!folder) return
  try {
    await setMtgaFolder(folder)
    mtgaFolderSaved.value = true
    showSuccess('フォルダパスを保存しました')
  } catch {
    showError('保存に失敗しました')
  }
}

async function handleSyncMtgaCards() {
  mtgaSyncing.value = true
  try {
    const result = await syncMtgaCards()
    mtgaLastSyncedAt.value = new Date().toLocaleString('ja-JP')
    showSuccess(`MTGAカード名データを同期しました（${result.synced.toLocaleString()} 件）`)
  } catch (e: any) {
    showError(e?.response?.data?.detail || '同期に失敗しました')
  } finally {
    mtgaSyncing.value = false
  }
}


async function saveAutoImport() {
  try {
    await updateSettings({
      auto_import_enabled: autoImportEnabled.value,
      auto_import_interval_sec: Math.max(10, autoImportIntervalInput.value),
    })
    autoImportStatus.value = await fetchAutoImportStatus().catch(() => null)
    showSuccess('自動インポート設定を保存しました')
  } catch {
    showError('保存に失敗しました')
  }
}

async function removeApiKey() {
  if (!confirm('APIキーを削除しますか？')) return
  try {
    await deleteApiKey()
    configured.value = false
    showSuccess('APIキーを削除しました')
  } catch {
    showError('削除に失敗しました')
  }
}
</script>

<style scoped>
.settings {
  padding: 24px;
}

.settings__title {
  font-size: 1.2rem;
  font-weight: bold;
  margin-bottom: 20px;
}

.settings__section {
  background: #fff;
  border: 1px solid #e0d8c8;
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 20px;
}

.settings__section-title {
  font-size: 13px;
  font-weight: bold;
  color: #7a6a55;
  margin-bottom: 12px;
}

.settings__row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.settings__configured {
  font-size: 13px;
  color: #5a7a4a;
}

.settings__not-configured {
  font-size: 13px;
  color: #a03030;
}

.settings__input {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 13px;
  font-family: monospace;
  background: #fff;
  color: #2c2416;
}

.settings__btn {
  padding: 6px 14px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  background: #faf7f0;
  font-size: 13px;
  cursor: pointer;
  color: #2c2416;
  white-space: nowrap;
}

.settings__btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.settings__btn--primary {
  background: #4a6fa5;
  border-color: #4a6fa5;
  color: #fff;
}

.settings__btn--primary:hover:not(:disabled) {
  background: #3a5f95;
}

.settings__btn--danger {
  color: #a03030;
  border-color: #d8a0a0;
}

.settings__select {
  padding: 6px 10px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 13px;
  background: #fff;
  color: #2c2416;
  font-family: inherit;
  min-width: 160px;
}

.settings__note {
  font-size: 11px;
  color: #7a6a55;
  margin-top: 8px;
}

.settings__note a {
  color: #4a6fa5;
}

.settings__inline-label {
  font-size: 13px;
  color: #2c2416;
  white-space: nowrap;
  width: 80px;
  display: inline-block;
}

.settings__number-input {
  width: 72px;
  padding: 6px 10px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 13px;
  background: #fff;
  color: #2c2416;
  font-family: inherit;
}

.settings__version {
  font-size: 11px;
  color: #a09080;
  text-align: right;
}

.settings__file-hidden {
  display: none;
}

.settings__file-name {
  font-size: 13px;
  color: #7a6a55;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.settings__date-input {
  padding: 6px 10px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 13px;
  background: #fff;
  color: #2c2416;
  font-family: inherit;
}

.settings__divider {
  border-top: 1px solid #e0d8c8;
  margin: 8px 0;
}

.settings__subsection-title {
  font-size: 12px;
  font-weight: bold;
  color: #9a8a75;
  margin-bottom: 8px;
  margin-top: 4px;
}

.settings__folder-path {
  font-size: 12px;
  color: #5a5040;
  font-family: monospace;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.settings__toggle-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #2c2416;
  cursor: pointer;
}
</style>
