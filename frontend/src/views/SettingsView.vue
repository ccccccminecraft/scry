<template>
  <div class="settings">
    <h1 class="settings__title">設定</h1>

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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToast } from '../composables/useToast'
import { fetchSettings, updateSettings, deleteApiKey } from '../api/settings'

const { showSuccess, showError } = useToast()

const configured = ref(false)
const apiKeyInput = ref('')

onMounted(async () => {
  try {
    const s = await fetchSettings()
    configured.value = s.api_key_configured
  } catch {
    showError('設定の取得に失敗しました')
  }
})

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
  max-width: 560px;
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

.settings__note {
  font-size: 11px;
  color: #7a6a55;
  margin-top: 8px;
}

.settings__note a {
  color: #4a6fa5;
}
</style>
