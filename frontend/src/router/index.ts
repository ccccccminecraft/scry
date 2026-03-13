import { createRouter, createWebHashHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import ImportView from '../views/ImportView.vue'
import MatchListView from '../views/MatchListView.vue'
import MatchDetailView from '../views/MatchDetailView.vue'
import StatsView from '../views/StatsView.vue'
import DeckDefinitionsView from '../views/DeckDefinitionsView.vue'
import AnalysisView from '../views/AnalysisView.vue'
import SettingsView from '../views/SettingsView.vue'

const router = createRouter({
  // Electron の本番環境（file://）では WebHashHistory を使用する
  history: createWebHashHistory(),
  routes: [
    { path: '/',                       component: HomeView },
    { path: '/import',                 component: ImportView },
    { path: '/matches',                component: MatchListView },
    { path: '/matches/:match_id',      component: MatchDetailView },
    { path: '/stats',                  component: StatsView },
    { path: '/decks',                  component: DeckDefinitionsView },
    { path: '/analysis',               component: AnalysisView },
    { path: '/settings',               component: SettingsView },
  ],
})

export default router
