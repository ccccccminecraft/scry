<template>
  <div class="analysis">
    <!-- APIキー未設定 -->
    <div v-if="apiKeyConfigured === false" class="analysis__no-key">
      <p class="analysis__no-key-msg">APIキーが設定されていません</p>
      <router-link to="/settings" class="analysis__no-key-link">設定画面へ →</router-link>
    </div>

    <!-- 読み込み中 -->
    <div v-else-if="apiKeyConfigured === null" class="analysis__loading">
      読み込み中...
    </div>

    <!-- メイン -->
    <template v-else>
      <SessionBar
        :sessions="sessions"
        :current-id="currentSessionId"
        @select="selectSession"
        @new="startNewSession"
      />

      <div class="analysis__main">
        <h1 class="analysis__title">AI 分析</h1>
        <!-- ツールバー -->
        <div class="analysis__toolbar">
          <div class="analysis__toolbar-group">
            <label class="analysis__toolbar-label">プレイヤー</label>
            <select v-model="playerModel" class="analysis__select">
              <option v-for="p in playerList" :key="p" :value="p">{{ p }}</option>
            </select>
          </div>
          <div class="analysis__toolbar-group">
            <label class="analysis__toolbar-label">テンプレート</label>
            <select v-model="selectedTemplateId" class="analysis__select">
              <option v-for="t in promptTemplates" :key="t.id" :value="t.id">{{ t.name }}</option>
            </select>
          </div>
          <div class="analysis__toolbar-group">
            <label class="analysis__toolbar-label">質問セット</label>
            <select v-model="selectedSetId" class="analysis__select">
              <option :value="null">（なし）</option>
              <option v-for="s in questionSets" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </div>
          <div class="analysis__toolbar-actions">
            <button
              v-if="currentSessionId"
              class="analysis__btn analysis__btn--danger"
              @click="deleteCurrentSession"
            >この会話を削除</button>
            <button class="analysis__btn" @click="startNewSession">会話をリセット</button>
          </div>
        </div>

        <!-- フィルター行 -->
        <div class="analysis__filters">
          <FilterBar :show-player="false" />
        </div>

        <!-- チャットメッセージ -->
        <div ref="chatRef" class="analysis__messages">
          <ChatMessage
            v-for="(m, i) in messages"
            :key="i"
            :message="m"
          />
          <ChatMessage
            v-if="streamingContent"
            :message="{ role: 'assistant', content: streamingContent }"
            :streaming="true"
          />
          <div v-if="messages.length === 0 && !streamingContent && !streaming" class="analysis__empty">
            <template v-if="readyToStart">
              <button class="analysis__start-btn" @click="startChat">会話を開始する</button>
            </template>
            <template v-else>
              「＋ 新規」を押して会話を開始してください
            </template>
          </div>
        </div>

        <!-- 質問ボタン -->
        <div v-if="currentQuestionItems.length > 0 && !isReadOnly" class="analysis__questions">
          <button
            v-for="q in currentQuestionItems"
            :key="q.id"
            class="analysis__question-btn"
            :disabled="streaming"
            @click="sendMessage(q.text)"
          >{{ q.text }}</button>
        </div>

        <!-- 入力エリア -->
        <div v-if="!isReadOnly" class="analysis__input-area">
          <textarea
            v-model="inputText"
            class="analysis__textarea"
            rows="3"
            placeholder="メッセージを入力… (Enter で送信 / Shift+Enter で改行)"
            :disabled="streaming"
            @keydown.enter.exact.prevent="onEnter"
          />
          <button
            class="analysis__send-btn"
            :disabled="streaming || !inputText.trim()"
            @click="sendMessage(inputText)"
          >
            {{ streaming ? '生成中…' : '送信' }}
          </button>
        </div>

        <div v-else class="analysis__readonly-banner">
          <span>過去の会話（読み取り専用）</span>
          <button class="analysis__btn analysis__btn--continue" @click="isReadOnly = false">続きから会話する</button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onActivated } from 'vue'

defineOptions({ name: 'AnalysisView' })
import { useToast } from '../composables/useToast'
import { fetchSettings } from '../api/settings'
import { useFilterState } from '../composables/useFilterState'
import {
  fetchSessions, fetchSessionDetail, deleteSession,
  fetchPromptTemplates, fetchQuestionSets, streamChat,
  type ChatMessage as ChatMsg, type SessionSummary,
  type PromptTemplate, type QuestionSet,
} from '../api/analysis'
import ChatMessage from '../components/ChatMessage.vue'
import SessionBar from '../components/SessionBar.vue'
import FilterBar from '../components/FilterBar.vue'

const { showError } = useToast()
const {
  playerModel,
  deckIds, decks, versionId, opponentDecks, dateFrom, dateTo,
  player, opponent, format,
  playerList,
  init,
} = useFilterState()

// ── 状態 ─────────────────────────────────────────────────────────────────
const apiKeyConfigured = ref<boolean | null>(null)
const promptTemplates = ref<PromptTemplate[]>([])
const selectedTemplateId = ref<number | null>(null)
const questionSets = ref<QuestionSet[]>([])
const selectedSetId = ref<number | null>(null)
const sessions = ref<SessionSummary[]>([])
const currentSessionId = ref<number | null>(null)
const isReadOnly = ref(false)
const readyToStart = ref(false)
const messages = ref<ChatMsg[]>([])
const inputText = ref('')
const streaming = ref(false)
const streamingContent = ref('')
const chatRef = ref<HTMLElement | null>(null)
let abortController: AbortController | null = null

const currentQuestionItems = computed(() => {
  if (selectedSetId.value === null) return []
  const qs = questionSets.value.find(s => s.id === selectedSetId.value)
  return qs?.items ?? []
})

// ── スクロール ────────────────────────────────────────────────────────────
async function scrollToBottom() {
  await nextTick()
  if (chatRef.value) {
    chatRef.value.scrollTop = chatRef.value.scrollHeight
  }
}

watch([messages, streamingContent], scrollToBottom)

// ── 初期化 ────────────────────────────────────────────────────────────────
const _initialized = ref(false)

async function initData() {
  try {
    const settings = await fetchSettings()
    apiKeyConfigured.value = settings.api_key_configured
    if (!settings.api_key_configured) return

    const [templates, qSets] = await Promise.all([
      fetchPromptTemplates(),
      fetchQuestionSets(),
    ])

    promptTemplates.value = templates
    questionSets.value = qSets

    if (!_initialized.value) {
      const defaultTemplate = templates.find(t => t.is_default) ?? templates[0]
      if (defaultTemplate) selectedTemplateId.value = defaultTemplate.id

      const defaultSet = qSets.find(s => s.is_default) ?? qSets[0]
      if (defaultSet) selectedSetId.value = defaultSet.id

      const playerSet = await init()
      // playerSet=true なら watch(player) が loadSessions を呼ぶ
      if (!playerSet && player.value) await loadSessions()
      _initialized.value = true
    } else if (player.value) {
      await loadSessions()
    }
  } catch {
    showError('初期化に失敗しました')
  }
}

onMounted(initData)
onActivated(initData)

// ── セッション管理 ────────────────────────────────────────────────────────
async function loadSessions() {
  try {
    sessions.value = await fetchSessions(player.value)
  } catch {
    showError('セッション一覧の取得に失敗しました')
  }
}

async function startNewSession() {
  abortController?.abort()
  streaming.value = false
  messages.value = []
  streamingContent.value = ''
  currentSessionId.value = null
  isReadOnly.value = false
  readyToStart.value = !!player.value
}

async function startChat() {
  readyToStart.value = false
  await sendMessage(`こんにちは`, true)
}

async function selectSession(id: number) {
  abortController?.abort()
  streaming.value = false
  streamingContent.value = ''
  isReadOnly.value = true
  readyToStart.value = false
  currentSessionId.value = id
  try {
    const detail = await fetchSessionDetail(id)
    messages.value = detail.messages.map(m => ({ role: m.role, content: m.content }))
    opponent.value = detail.filter_opponent ?? ''
    decks.value = detail.filter_deck ? [detail.filter_deck] : []
    opponentDecks.value = detail.filter_opponent_deck ? [detail.filter_opponent_deck] : []
    format.value = detail.filter_format ?? ''
    dateFrom.value = detail.filter_date_from ?? ''
    dateTo.value = detail.filter_date_to ?? ''
  } catch {
    showError('セッションの取得に失敗しました')
  }
}

async function deleteCurrentSession() {
  if (!currentSessionId.value) return
  if (!confirm('この会話を削除しますか？')) return
  try {
    await deleteSession(currentSessionId.value)
    sessions.value = sessions.value.filter(s => s.id !== currentSessionId.value)
    await startNewSession()
  } catch {
    showError('削除に失敗しました')
  }
}

// ── メッセージ送信 ────────────────────────────────────────────────────────
async function sendMessage(text: string, isGreeting = false) {
  if (streaming.value || !text.trim()) return

  if (!isGreeting) {
    messages.value = [...messages.value, { role: 'user', content: text }]
    inputText.value = ''
  }

  streaming.value = true
  streamingContent.value = ''
  abortController = new AbortController()

  const history: ChatMsg[] = messages.value.slice(0, isGreeting ? undefined : -1)

  await streamChat(
    {
      player: player.value,
      prompt_template_id: selectedTemplateId.value,
      session_id: currentSessionId.value,
      message: text,
      history: history.length > 0 ? history : undefined,
      opponent: opponent.value || null,
      deck: deckIds.value.length > 0 ? null : (decks.value[0] ?? null),
      deck_id: (deckIds.value.length === 1 && !versionId.value) ? deckIds.value[0] : null,
      version_id: (deckIds.value.length === 1 && versionId.value) ? versionId.value : null,
      opponent_deck: opponentDecks.value[0] ?? null,
      format: format.value || null,
      date_from: dateFrom.value || null,
      date_to: dateTo.value || null,
    },
    {
      onDelta(delta) {
        streamingContent.value += delta
      },
      onDone(sessionId) {
        messages.value = [
          ...messages.value,
          { role: 'assistant', content: streamingContent.value },
        ]
        streamingContent.value = ''
        streaming.value = false
        currentSessionId.value = sessionId
        loadSessions()
      },
      onError(msg) {
        if (streamingContent.value) {
          messages.value = [
            ...messages.value,
            { role: 'assistant', content: streamingContent.value + '\n（エラーが発生しました）' },
          ]
          streamingContent.value = ''
        }
        streaming.value = false
        showError(msg)
      },
    },
    abortController.signal,
  )
}

function onEnter() {
  sendMessage(inputText.value)
}

// ── watch ─────────────────────────────────────────────────────────────────
watch(player, async () => {
  await loadSessions()
})
</script>

<style scoped>
.analysis {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* APIキー未設定 */
.analysis__no-key {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.analysis__no-key-msg {
  font-size: 15px;
  color: #7a6a55;
}

.analysis__no-key-link {
  color: #4a6fa5;
  font-size: 14px;
}

.analysis__loading {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #7a6a55;
  font-size: 14px;
}

/* メインエリア */
.analysis__main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fff;
}

.analysis__title {
  font-size: 1.2rem;
  font-weight: bold;
  color: #2c2416;
  padding: 16px 16px 0;
}

/* ツールバー */
.analysis__toolbar {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 10px 16px;
  background: #fff;
  border-bottom: 1px solid #e0d8c8;
  flex-wrap: wrap;
}

.analysis__toolbar-group {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.analysis__toolbar-label {
  font-size: 10px;
  color: #7a6a55;
}

.analysis__select {
  padding: 3px 6px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 11px;
  background: #fff;
  color: #2c2416;
}

.analysis__toolbar-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
  align-items: flex-end;
}

.analysis__btn {
  padding: 5px 12px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  background: #faf7f0;
  font-size: 12px;
  cursor: pointer;
  color: #2c2416;
}

.analysis__btn:hover {
  background: #f0ece0;
}

.analysis__btn--danger {
  color: #a03030;
  border-color: #d8a0a0;
}

/* フィルター行 */
.analysis__filters {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 8px 16px;
  background: #faf7f0;
  border-bottom: 1px solid #e0d8c8;
  flex-wrap: wrap;
}


/* チャットメッセージ */
.analysis__messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.analysis__empty {
  color: #b0a090;
  font-size: 13px;
  text-align: center;
  margin-top: 40px;
}

.analysis__start-btn {
  padding: 10px 28px;
  background: #4a6fa5;
  border: none;
  border-radius: 6px;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}

.analysis__start-btn:hover {
  background: #3a5f95;
}

/* 質問ボタン */
.analysis__questions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 16px;
  background: #faf7f0;
  border-top: 1px solid #e0d8c8;
}

.analysis__question-btn {
  padding: 5px 12px;
  border: 1px solid #c8b89a;
  border-radius: 16px;
  background: #fff;
  font-size: 12px;
  cursor: pointer;
  color: #4a6fa5;
}

.analysis__question-btn:hover:not(:disabled) {
  background: #eef3fa;
  border-color: #4a6fa5;
}

.analysis__question-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

/* 入力エリア */
.analysis__input-area {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  background: #fff;
  border-top: 1px solid #e0d8c8;
  align-items: flex-end;
}

.analysis__textarea {
  flex: 1;
  padding: 8px 10px;
  border: 1px solid #c8b89a;
  border-radius: 6px;
  font-size: 13px;
  font-family: inherit;
  resize: none;
  background: #fff;
  color: #2c2416;
}

.analysis__textarea:disabled {
  background: #f5f2ec;
}

.analysis__send-btn {
  padding: 8px 20px;
  background: #4a6fa5;
  border: none;
  border-radius: 6px;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
}

.analysis__send-btn:hover:not(:disabled) {
  background: #3a5f95;
}

.analysis__send-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

/* 読み取り専用バナー */
.analysis__readonly-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 10px 16px;
  background: #faf7f0;
  border-top: 1px solid #e0d8c8;
  font-size: 12px;
  color: #7a6a55;
}

.analysis__btn--continue {
  background: #4a6fa5;
  border-color: #4a6fa5;
  color: #fff;
  font-size: 12px;
}
</style>
