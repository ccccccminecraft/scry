<template>
  <div class="settings">
    <h1 class="settings__title">設定</h1>

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
      <div class="settings__section-title">アプリケーション</div>
      <div class="settings__row">
        <button class="settings__btn settings__btn--primary" @click="reload">再読み込み</button>
      </div>
      <p class="settings__note">画面の表示がおかしい場合や設定を反映させたい場合にご利用ください。</p>
    </div>

    <div v-if="appVersion" class="settings__version">v{{ appVersion }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { useToast } from '../composables/useToast'
import { fetchSettings, updateSettings, deleteApiKey } from '../api/settings'
import { fetchPlayers } from '../api/stats'

const { showSuccess, showError } = useToast()

const configured = ref(false)
const apiKeyInput = ref('')
const playerList = ref<string[]>([])
const defaultPlayerInput = ref('')
const appVersion = ref('')
const minPlayerMatchesInput = ref(1)
const minDeckMatchesInput = ref(1)

onMounted(async () => {
  try {
    const [s, players, health] = await Promise.all([
      fetchSettings(),
      fetchPlayers(),
      axios.get('http://localhost:18432/api/health').catch(() => null),
    ])
    configured.value = s.api_key_configured
    playerList.value = players
    defaultPlayerInput.value = s.default_player ?? ''
    appVersion.value = health?.data?.version ?? ''
    minPlayerMatchesInput.value = s.min_player_matches ?? 1
    minDeckMatchesInput.value = s.min_deck_matches ?? 1
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
</style>
