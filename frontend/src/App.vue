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

const showOnboarding = ref(false)

provide('showOnboarding', showOnboarding)

onMounted(async () => {
  try {
    const settings = await fetchSettings()
    if (!settings.onboarding_completed) {
      showOnboarding.value = true
    }
  } catch { /* バックエンド未起動時は無視 */ }
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
