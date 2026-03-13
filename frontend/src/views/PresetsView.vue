<template>
  <div class="presets">
    <h1 class="presets__title">プリセット管理</h1>

    <div v-if="loading" class="loading">読み込み中...</div>

    <template v-else>
      <!-- プロンプトテンプレート -->
      <section class="section">
        <div class="section__header">
          <h2 class="section__title">プロンプトテンプレート</h2>
          <button class="btn btn--primary" @click="$router.push('/presets/templates/new')">
            + 新規作成
          </button>
        </div>

        <table class="table">
          <thead>
            <tr>
              <th class="col-default">既定</th>
              <th>名前</th>
              <th class="col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in templates" :key="t.id">
              <td class="col-default">
                <span :class="t.is_default ? 'badge badge--default' : 'badge'">
                  {{ t.is_default ? '●' : '○' }}
                </span>
              </td>
              <td>{{ t.name }}</td>
              <td class="col-actions">
                <button
                  v-if="!t.is_default"
                  class="btn-sm"
                  @click="$router.push(`/presets/templates/${t.id}/edit?setDefault=true`)"
                >
                  既定にする
                </button>
                <button
                  class="btn-sm"
                  @click="$router.push(`/presets/templates/${t.id}/edit`)"
                >
                  編集
                </button>
                <button
                  class="btn-sm btn-sm--danger"
                  :disabled="t.is_default"
                  @click="removeTemplate(t)"
                >
                  {{ t.is_default ? '—' : '削除' }}
                </button>
              </td>
            </tr>
            <tr v-if="templates.length === 0">
              <td colspan="3" class="empty">テンプレートがありません</td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- 質問セット -->
      <section class="section">
        <div class="section__header">
          <h2 class="section__title">質問セット</h2>
          <button class="btn btn--primary" @click="$router.push('/presets/question-sets/new')">
            + 新規作成
          </button>
        </div>

        <table class="table">
          <thead>
            <tr>
              <th class="col-default">既定</th>
              <th>名前</th>
              <th>質問数</th>
              <th class="col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="q in questionSets" :key="q.id">
              <td class="col-default">
                <span :class="q.is_default ? 'badge badge--default' : 'badge'">
                  {{ q.is_default ? '●' : '○' }}
                </span>
              </td>
              <td>{{ q.name }}</td>
              <td>{{ q.items.length }} 件</td>
              <td class="col-actions">
                <button
                  v-if="!q.is_default"
                  class="btn-sm"
                  @click="$router.push(`/presets/question-sets/${q.id}/edit?setDefault=true`)"
                >
                  既定にする
                </button>
                <button
                  class="btn-sm"
                  @click="$router.push(`/presets/question-sets/${q.id}/edit`)"
                >
                  編集
                </button>
                <button
                  class="btn-sm btn-sm--danger"
                  :disabled="q.is_default"
                  @click="removeQuestionSet(q)"
                >
                  {{ q.is_default ? '—' : '削除' }}
                </button>
              </td>
            </tr>
            <tr v-if="questionSets.length === 0">
              <td colspan="4" class="empty">質問セットがありません</td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchPromptTemplates, fetchQuestionSets } from '../api/analysis'
import { deletePromptTemplate, deleteQuestionSet } from '../api/presets'
import { useToast } from '../composables/useToast'
import type { PromptTemplate, QuestionSet } from '../api/analysis'

const { showError, showSuccess } = useToast()

const templates = ref<PromptTemplate[]>([])
const questionSets = ref<QuestionSet[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    const [tmpl, qsets] = await Promise.all([fetchPromptTemplates(), fetchQuestionSets()])
    templates.value = tmpl
    questionSets.value = qsets
  } catch (e) {
    showError(e instanceof Error ? e.message : '読み込みに失敗しました')
  } finally {
    loading.value = false
  }
})

async function removeTemplate(t: PromptTemplate) {
  if (!confirm(`「${t.name}」を削除しますか？`)) return
  try {
    await deletePromptTemplate(t.id)
    templates.value = templates.value.filter(x => x.id !== t.id)
    showSuccess('削除しました')
  } catch (e) {
    showError(e instanceof Error ? e.message : '削除に失敗しました')
  }
}

async function removeQuestionSet(q: QuestionSet) {
  if (!confirm(`「${q.name}」を削除しますか？`)) return
  try {
    await deleteQuestionSet(q.id)
    questionSets.value = questionSets.value.filter(x => x.id !== q.id)
    showSuccess('削除しました')
  } catch (e) {
    showError(e instanceof Error ? e.message : '削除に失敗しました')
  }
}
</script>

<style scoped>
.presets {
  padding: 24px;
}

.presets__title {
  font-size: 1.2rem;
  margin-bottom: 24px;
}

.loading {
  color: #7a6a55;
  padding: 32px;
  text-align: center;
}

.section {
  margin-bottom: 32px;
}

.section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.section__title {
  font-size: 1rem;
  color: #2c2416;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.table th {
  text-align: left;
  padding: 8px 12px;
  background: #e8e0d0;
  border-bottom: 2px solid #c8b89a;
  white-space: nowrap;
}

.table td {
  padding: 8px 12px;
  border-bottom: 1px solid #e0d8c8;
  vertical-align: middle;
}

.col-default {
  width: 48px;
  text-align: center;
}

.col-actions {
  width: 200px;
  text-align: right;
}

.badge {
  color: #b0a090;
  font-size: 14px;
}

.badge--default {
  color: #4a6fa5;
  font-weight: bold;
}

.empty {
  color: #9a8a76;
  text-align: center;
  padding: 24px;
}

.btn {
  padding: 7px 16px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  background: #faf7f0;
  color: #2c2416;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
}

.btn:hover {
  background: #f0ece0;
}

.btn--primary {
  background: #4a6fa5;
  border-color: #4a6fa5;
  color: #fff;
}

.btn--primary:hover {
  background: #3a5f95;
}

.btn-sm {
  padding: 4px 10px;
  border: 1px solid #c8b89a;
  border-radius: 3px;
  background: #faf7f0;
  color: #2c2416;
  font-size: 12px;
  cursor: pointer;
  font-family: inherit;
  margin-left: 4px;
}

.btn-sm:hover:not(:disabled) {
  background: #f0ece0;
}

.btn-sm--danger:not(:disabled) {
  border-color: #c08080;
  color: #a03030;
}

.btn-sm--danger:not(:disabled):hover {
  background: #fff0f0;
}

.btn-sm:disabled {
  opacity: 0.35;
  cursor: default;
}
</style>
