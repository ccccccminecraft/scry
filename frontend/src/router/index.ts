import { createRouter, createWebHashHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import ImportView from '../views/ImportView.vue'
import MatchListView from '../views/MatchListView.vue'
import MatchDetailView from '../views/MatchDetailView.vue'
import StatsView from '../views/StatsView.vue'
import DeckDefinitionsView from '../views/DeckDefinitionsView.vue'
import AnalysisView from '../views/AnalysisView.vue'
import AIExportView from '../views/AIExportView.vue'
import SettingsView from '../views/SettingsView.vue'
import PresetsView from '../views/PresetsView.vue'
import PromptTemplateEditView from '../views/PromptTemplateEditView.vue'
import QuestionSetEditView from '../views/QuestionSetEditView.vue'

const router = createRouter({
  // Electron の本番環境（file://）では WebHashHistory を使用する
  history: createWebHashHistory(),
  routes: [
    { path: '/',                                        component: HomeView },
    { path: '/import',                                  component: ImportView },
    { path: '/matches',                                 component: MatchListView },
    { path: '/matches/:match_id',                       component: MatchDetailView },
    { path: '/stats',                                   component: StatsView },
    { path: '/decks',                                   component: DeckDefinitionsView },
    { path: '/analysis',                                component: AnalysisView },
    { path: '/export',                                  component: AIExportView },
    { path: '/settings',                                component: SettingsView },
    { path: '/presets',                                 component: PresetsView },
    { path: '/presets/templates/new',                   component: PromptTemplateEditView },
    { path: '/presets/templates/:id/edit',              component: PromptTemplateEditView },
    { path: '/presets/question-sets/new',               component: QuestionSetEditView },
    { path: '/presets/question-sets/:id/edit',          component: QuestionSetEditView },
  ],
})

export default router
