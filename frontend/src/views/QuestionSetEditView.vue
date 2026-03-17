<template>
  <div class="edit">
    <div class="edit__header">
      <button class="btn-back" @click="$router.push('/presets')">← 戻る</button>
      <h1 class="edit__title">{{ isNew ? '質問セット新規作成' : '質問セット編集' }}</h1>
    </div>

    <div v-if="loading" class="loading">読み込み中...</div>

    <form v-else class="form" @submit.prevent="save">
      <div class="form__group">
        <label class="form__label">セット名 <span class="required">*</span></label>
        <input
          v-model="name"
          type="text"
          class="form__input"
          placeholder="例: 基本分析セット"
          maxlength="100"
        />
      </div>

      <div class="form__group">
        <div class="items-header">
          <label class="form__label">質問一覧</label>
          <button type="button" class="btn-add" @click="addItem">+ 質問を追加</button>
        </div>

        <div v-if="items.length === 0" class="items-empty">質問がありません</div>

        <ul class="items-list">
          <li v-for="(item, idx) in items" :key="item.draftKey" class="item">
            <div class="item__order">
              <button type="button" class="order-btn" :disabled="idx === 0" @click="moveUp(idx)">▲</button>
              <button type="button" class="order-btn" :disabled="idx === items.length - 1" @click="moveDown(idx)">▼</button>
            </div>
            <input
              v-model="item.text"
              type="text"
              class="item__input"
              :placeholder="`質問 ${idx + 1}`"
            />
            <button type="button" class="item__delete" @click="removeItem(idx)">✕</button>
          </li>
        </ul>
      </div>

      <div class="form__group form__group--row">
        <label class="form__checkbox">
          <input type="checkbox" v-model="isDefault" />
          このセットを既定にする
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
import { fetchQuestionSets } from '../api/analysis'
import { createQuestionSet, updateQuestionSet } from '../api/presets'
import { useToast } from '../composables/useToast'

const route = useRoute()
const router = useRouter()
const { showError } = useToast()

const setId = computed(() => {
  const id = route.params.id
  return id ? Number(id) : null
})
const isNew = computed(() => setId.value === null)
const setDefault = computed(() => route.query.setDefault === 'true')

interface DraftItem { draftKey: number; text: string }

const name = ref('')
const isDefault = ref(false)
const items = ref<DraftItem[]>([])
const saving = ref(false)
const loading = ref(false)
let nextKey = -1

onMounted(async () => {
  if (setDefault.value) isDefault.value = true
  if (isNew.value) return

  loading.value = true
  try {
    const sets = await fetchQuestionSets()
    const qs = sets.find(x => x.id === setId.value)
    if (!qs) { router.push('/presets'); return }
    name.value = qs.name
    isDefault.value = setDefault.value || qs.is_default
    items.value = qs.items.map(i => ({ draftKey: i.id, text: i.text }))
  } catch (e) {
    showError(e instanceof Error ? e.message : '読み込みに失敗しました')
  } finally {
    loading.value = false
  }
})

function addItem() {
  items.value.push({ draftKey: nextKey--, text: '' })
}

function removeItem(idx: number) {
  items.value.splice(idx, 1)
}

function moveUp(idx: number) {
  if (idx === 0) return
  const arr = items.value
  ;[arr[idx - 1], arr[idx]] = [arr[idx], arr[idx - 1]]
}

function moveDown(idx: number) {
  if (idx === items.value.length - 1) return
  const arr = items.value
  ;[arr[idx], arr[idx + 1]] = [arr[idx + 1], arr[idx]]
}

async function save() {
  if (!name.value.trim()) { showError('セット名を入力してください'); return }
  if (items.value.some(i => !i.text.trim())) { showError('空の質問があります'); return }

  saving.value = true
  try {
    const body = {
      name: name.value.trim(),
      is_default: isDefault.value,
      items: items.value.map((item, idx) => ({
        text: item.text.trim(),
        display_order: idx + 1,
      })),
    }
    if (isNew.value) {
      await createQuestionSet(body)
    } else {
      await updateQuestionSet(setId.value!, body)
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

.form__input {
  padding: 7px 10px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 14px;
  font-family: inherit;
  color: #2c2416;
  background: #fff;
}

.form__input:focus {
  outline: none;
  border-color: #4a6fa5;
}

/* 質問リスト */
.items-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.btn-add {
  background: none;
  border: 1px solid #4a6fa5;
  border-radius: 4px;
  color: #4a6fa5;
  font-size: 12px;
  padding: 4px 10px;
  cursor: pointer;
  font-family: inherit;
}

.btn-add:hover { background: #f0f4fa; }

.items-empty {
  font-size: 13px;
  color: #9a8a76;
  padding: 16px;
  text-align: center;
  border: 1px dashed #d0c8b8;
  border-radius: 6px;
}

.items-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.item {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #fff;
  border: 1px solid #e0d8c8;
  border-radius: 6px;
  padding: 6px 10px;
}

.item__order {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.order-btn {
  background: none;
  border: none;
  color: #9a8a76;
  font-size: 10px;
  cursor: pointer;
  padding: 1px 3px;
  line-height: 1;
}

.order-btn:disabled {
  opacity: 0.25;
  cursor: default;
}

.order-btn:not(:disabled):hover { color: #4a6fa5; }

.item__input {
  flex: 1;
  padding: 5px 8px;
  border: 1px solid #d0c8b8;
  border-radius: 4px;
  font-size: 13px;
  font-family: inherit;
  color: #2c2416;
  background: #faf7f0;
}

.item__input:focus {
  outline: none;
  border-color: #4a6fa5;
  background: #fff;
}

.item__delete {
  background: none;
  border: none;
  color: #b0a090;
  font-size: 12px;
  cursor: pointer;
  padding: 4px 6px;
}

.item__delete:hover { color: #a03030; }

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
