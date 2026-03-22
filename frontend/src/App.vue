<template>
  <div class="app">
    <GlobalNav />
    <main class="app__content">
      <router-view v-slot="{ Component }">
        <keep-alive :include="['MatchListView', 'StatsView', 'AnalysisView', 'DeckBuilderView']">
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </main>
    <AppToast />
    <OnboardingWizard
      v-if="showOnboarding"
      @complete="showOnboarding = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, provide, onMounted } from 'vue'
import GlobalNav from './components/GlobalNav.vue'
import AppToast from './components/AppToast.vue'
import OnboardingWizard from './components/OnboardingWizard.vue'
import { fetchSettings } from './api/settings'
import { getMtgaSyncStatus, syncMtgaCards } from './api/admin'
import { useToast } from './composables/useToast'

const showOnboarding = ref(false)
const { showSuccess } = useToast()

provide('showOnboarding', showOnboarding)

async function checkAndAutoSyncMtgaCards(): Promise<void> {
  try {
    const status = await getMtgaSyncStatus()
    if (!status.folder) return

    const mtime = await window.electronAPI?.getMtgaCardsMtime(status.folder)
    if (mtime == null) return

    // ファイルの更新日時が最終同期日時より新しければ自動同期
    const lastSynced = status.last_synced_at ? new Date(status.last_synced_at).getTime() : 0
    if (mtime <= lastSynced) return

    showSuccess('MTGAカードデータが更新されています。自動同期中...')
    const result = await syncMtgaCards(status.folder)
    showSuccess(`MTGAカードデータを自動同期しました（${result.synced.toLocaleString()} 件）`)
  } catch { /* 自動同期の失敗は無視 */ }
}

onMounted(async () => {
  try {
    const settings = await fetchSettings()
    if (!settings.onboarding_completed) {
      showOnboarding.value = true
      return
    }
  } catch { /* バックエンド未起動時は無視 */ }

  // onboarding 完了済みの場合のみ自動同期チェック
  checkAndAutoSyncMtgaCards()
})
</script>

<style>
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  background-color: #f0ece0;
  color: #2c2416;
  font-family: 'Noto Sans JP', 'Noto Sans CJK JP', 'Yu Gothic UI', 'Segoe UI', sans-serif;
  font-size: 14px;
  -webkit-font-smoothing: antialiased;
}

button {
  cursor: pointer;
  font-size: 14px;
  font-family: inherit;
}
</style>

<style scoped>
.app {
  display: flex;
  min-height: 100vh;
}

.app__content {
  flex: 1;
  overflow: auto;
}
</style>
