<template>
  <div class="edit">
    <div class="edit__header">
      <button class="btn-back" @click="$router.push('/presets')">← 戻る</button>
      <h1 class="edit__title">{{ isNew ? 'テンプレート新規作成' : 'テンプレート編集' }}</h1>
    </div>

    <div v-if="loading" class="loading">読み込み中...</div>

    <form v-else class="form" @submit.prevent="save">
      <div class="form__group">
        <label class="form__label">テンプレート名 <span class="required">*</span></label>
        <input
          v-model="name"
          type="text"
          class="form__input"
          placeholder="例: 総合分析テンプレート"
          maxlength="100"
        />
      </div>

      <div class="form__group">
        <label class="form__label">プロンプト本文 <span class="required">*</span></label>
        <p class="form__hint">
          <code>{player_name}</code> でプレイヤー名、<code>{stats_text}</code> で対戦データが挿入されます。
        </p>
        <textarea
          v-model="content"
          class="form__textarea"
          placeholder="例: 以下は {player_name} の対戦データです。&#10;{stats_text}&#10;&#10;勝率と改善点を分析してください。"
          rows="12"
        />
      </div>

      <div class="form__group form__group--row">
        <label class="form__checkbox">
          <input type="checkbox" v-model="isDefault" />
          このテンプレートを既定にする
        </label>
      </div>

      <div class="form__footer">
        <button type="button" class="btn" @click="$router.push('/presets')">キャンセル</button>
        <button type="submit" class="btn btn--primary" :disabled="saving">
          {{ saving ? '保存中...' : '保存' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchPromptTemplates } from '../api/analysis'
import { createPromptTemplate, updatePromptTemplate } from '../api/presets'
import { useToast } from '../composables/useToast'

const route = useRoute()
const router = useRouter()
const { showError } = useToast()

const templateId = computed(() => {
  const id = route.params.id
  return id ? Number(id) : null
})
const isNew = computed(() => templateId.value === null)
const setDefault = computed(() => route.query.setDefault === 'true')

const name = ref('')
const content = ref('')
const isDefault = ref(false)
const saving = ref(false)
const loading = ref(false)

onMounted(async () => {
  if (setDefault.value) isDefault.value = true
  if (isNew.value) return

  loading.value = true
  try {
    const templates = await fetchPromptTemplates()
    const t = templates.find(x => x.id === templateId.value)
    if (!t) { router.push('/presets'); return }
    name.value = t.name
    content.value = t.content
    isDefault.value = setDefault.value || t.is_default
  } catch (e) {
    showError(e instanceof Error ? e.message : '読み込みに失敗しました')
  } finally {
    loading.value = false
  }
})

async function save() {
  if (!name.value.trim()) { showError('テンプレート名を入力してください'); return }
  if (!content.value.trim()) { showError('プロンプト本文を入力してください'); return }

  saving.value = true
  try {
    const body = { name: name.value.trim(), content: content.value.trim(), is_default: isDefault.value }
    if (isNew.value) {
      await createPromptTemplate(body)
    } else {
      await updatePromptTemplate(templateId.value!, body)
    }
    router.push('/presets')
  } catch (e) {
    showError(e instanceof Error ? e.message : '保存に失敗しました')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.edit {
  padding: 24px;
  max-width: 720px;
}

.edit__header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.edit__title {
  font-size: 1.1rem;
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

.btn-back:hover { color: #2c2416; }

.loading {
  color: #7a6a55;
  padding: 32px;
  text-align: center;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form__group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form__group--row {
  flex-direction: row;
  align-items: center;
}

.form__label {
  font-size: 13px;
  font-weight: bold;
  color: #2c2416;
}

.required {
  color: #a03030;
}

.form__hint {
  font-size: 12px;
  color: #9a8a76;
  margin: 0;
}

.form__hint code {
  background: #f0ece0;
  border-radius: 3px;
  padding: 1px 5px;
  font-family: monospace;
  font-size: 12px;
}

.form__input {
  padding: 7px 10px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 14px;
  font-family: inherit;
  color: #2c2416;
  background: #fff;
}

.form__textarea {
  padding: 8px 10px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 13px;
  font-family: inherit;
  color: #2c2416;
  background: #fff;
  resize: vertical;
  min-height: 200px;
  line-height: 1.6;
}

.form__input:focus,
.form__textarea:focus {
  outline: none;
  border-color: #4a6fa5;
}

.form__checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #2c2416;
  cursor: pointer;
}

.form__footer {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  padding-top: 8px;
  border-top: 1px solid #e0d8c8;
}

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

.btn:hover:not(:disabled) { background: #f0ece0; }

.btn--primary {
  background: #4a6fa5;
  border-color: #4a6fa5;
  color: #fff;
}

.btn--primary:hover:not(:disabled) { background: #3a5f95; }

.btn:disabled {
  opacity: 0.4;
  cursor: default;
}
</style>
