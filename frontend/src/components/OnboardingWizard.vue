<template>
  <div class="onboarding-overlay">
    <div class="onboarding-card">

      <!-- ステップインジケーター -->
      <div v-if="currentStep !== 'welcome' && currentStep !== 'done'" class="onboarding-steps">
        <span
          v-for="i in 3"
          :key="i"
          class="onboarding-steps__dot"
          :class="{ 'onboarding-steps__dot--active': stepIndex === i, 'onboarding-steps__dot--done': stepIndex > i }"
        />
      </div>

      <!-- ── Welcome ── -->
      <template v-if="currentStep === 'welcome'">
        <div class="onboarding-card__title">Scry へようこそ</div>
        <div class="onboarding-card__body">
          <p class="onboarding-card__lead">MTG の対戦ログを記録・分析するツールです。</p>
          <div class="onboarding-feature-list">
            <div class="onboarding-feature-item">
              <span class="onboarding-feature-item__icon">📊</span>
              <div>
                <div class="onboarding-feature-item__title">統計・勝率</div>
                <div class="onboarding-feature-item__desc">フォーマット・デッキ・対戦相手別に勝率を集計</div>
              </div>
            </div>
            <div class="onboarding-feature-item">
              <span class="onboarding-feature-item__icon">📁</span>
              <div>
                <div class="onboarding-feature-item__title">自動インポート</div>
                <div class="onboarding-feature-item__desc">MTGO / MTGA（Surveil 経由）のログを自動で取り込み</div>
              </div>
            </div>
            <div class="onboarding-feature-item">
              <span class="onboarding-feature-item__icon">🤖</span>
              <div>
                <div class="onboarding-feature-item__title">AI 分析</div>
                <div class="onboarding-feature-item__desc">Claude による対戦内容の分析（APIキーが必要）</div>
              </div>
            </div>
          </div>
          <p class="onboarding-card__sub">セットアップは約2分で完了します。</p>
        </div>
        <div class="onboarding-card__footer">
          <button class="onboarding-btn onboarding-btn--ghost" @click="skipAll">スキップ</button>
          <button class="onboarding-btn onboarding-btn--primary" @click="next">セットアップを開始する →</button>
        </div>
      </template>

      <!-- ── Step 1: ゲーム選択 ── -->
      <template v-else-if="currentStep === 'games'">
        <div class="onboarding-card__title">使用するゲームを選択</div>
        <div class="onboarding-card__body">
          <p class="onboarding-card__desc">インポート設定を行うゲームを選択してください（複数選択可）。</p>
          <div class="onboarding-game-list">
            <label class="onboarding-game-item" :class="{ 'onboarding-game-item--selected': selectedGames.has('mtgo') }">
              <input type="checkbox" :checked="selectedGames.has('mtgo')" @change="toggleGame('mtgo')" class="onboarding-game-item__check" />
              <div class="onboarding-game-item__body">
                <div class="onboarding-game-item__name">MTGO</div>
                <div class="onboarding-game-item__desc">ログファイル（.dat）からインポートします</div>
              </div>
            </label>
            <label class="onboarding-game-item" :class="{ 'onboarding-game-item--selected': selectedGames.has('mtga') }">
              <input type="checkbox" :checked="selectedGames.has('mtga')" @change="toggleGame('mtga')" class="onboarding-game-item__check" />
              <div class="onboarding-game-item__body">
                <div class="onboarding-game-item__name">MTGA（Surveil 経由）</div>
                <div class="onboarding-game-item__desc">Surveil が出力する JSON ファイルからインポートします</div>
              </div>
            </label>
          </div>
        </div>
        <div class="onboarding-card__footer">
          <button class="onboarding-btn onboarding-btn--ghost" @click="skipAll">スキップ</button>
          <div class="onboarding-card__footer-right">
            <button class="onboarding-btn" @click="back">戻る</button>
            <button
              class="onboarding-btn onboarding-btn--primary"
              :disabled="selectedGames.size === 0"
              @click="next"
            >次へ</button>
          </div>
        </div>
      </template>

      <!-- ── Step 2: インポート設定 ── -->
      <template v-else-if="currentStep === 'import'">
        <div class="onboarding-card__title">インポートの設定</div>
        <div class="onboarding-card__body">

          <!-- MTGO セクション -->
          <template v-if="selectedGames.has('mtgo')">
            <div class="onboarding-section-label">MTGO</div>
            <div class="onboarding-field">
              <div class="onboarding-field__label">登録フォルダ</div>
              <div class="onboarding-field__row">
                <span class="onboarding-field__path">{{ mtgoFolder ?? '未選択' }}</span>
                <button class="onboarding-btn onboarding-btn--sm" @click="selectMtgoFolder">選択</button>
                <button v-if="mtgoFolder" class="onboarding-btn onboarding-btn--sm onboarding-btn--ghost" @click="mtgoFolder = null">クリア</button>
              </div>
              <div class="onboarding-field__hint">例: C:\Users\[名前]\AppData\Local\Apps\2.0</div>
            </div>
          </template>

          <!-- MTGA セクション -->
          <template v-if="selectedGames.has('mtga')">
            <div class="onboarding-section-label" :style="selectedGames.has('mtgo') ? 'margin-top: 20px' : ''">MTGA（Surveil）</div>
            <div class="onboarding-field">
              <div class="onboarding-field__label">Surveil フォルダ</div>
              <div class="onboarding-field__row">
                <span class="onboarding-field__path">{{ surveilFolder ?? '未選択' }}</span>
                <button class="onboarding-btn onboarding-btn--sm" @click="selectSurveilFolder">選択</button>
                <button v-if="surveilFolder" class="onboarding-btn onboarding-btn--sm onboarding-btn--ghost" @click="surveilFolder = null">クリア</button>
              </div>
              <div class="onboarding-field__hint">Surveil の出力先 matches/ フォルダを指定してください</div>
            </div>
            <div class="onboarding-field">
              <div class="onboarding-field__label">MTGA インストールフォルダ <span class="onboarding-field__optional">（省略可）</span></div>
              <div class="onboarding-field__row">
                <span class="onboarding-field__path">{{ mtgaFolder ?? '未選択' }}</span>
                <button class="onboarding-btn onboarding-btn--sm" @click="selectMtgaFolder">選択</button>
                <button v-if="mtgaFolder" class="onboarding-btn onboarding-btn--sm onboarding-btn--ghost" @click="mtgaFolder = null">クリア</button>
              </div>
              <div class="onboarding-field__hint">例: C:\Program Files\Wizards of the Coast\MTGA</div>
            </div>
          </template>

          <!-- 自動インポート（共通） -->
          <div class="onboarding-field" style="margin-top: 8px; border-top: 1px solid #f0ece0; padding-top: 14px;">
            <label class="onboarding-toggle">
              <input type="checkbox" v-model="autoImport" />
              自動インポートを有効にする
            </label>
            <div class="onboarding-field__hint">選択したゲームのフォルダを定期的にスキャンし、新しい試合を自動で取り込みます。</div>
          </div>

          <p class="onboarding-card__sub">フォルダは後から「設定」→「インポート」画面でも変更できます。</p>
        </div>
        <div class="onboarding-card__footer">
          <button class="onboarding-btn onboarding-btn--ghost" @click="skipAll">スキップ</button>
          <div class="onboarding-card__footer-right">
            <button class="onboarding-btn" @click="back">戻る</button>
            <button class="onboarding-btn onboarding-btn--primary" @click="next">次へ</button>
          </div>
        </div>
      </template>

      <!-- ── Step 3: AI 分析 ── -->
      <template v-else-if="currentStep === 'ai'">
        <div class="onboarding-card__title">AI 分析の設定 <span class="onboarding-card__optional">（任意）</span></div>
        <div class="onboarding-card__body">
          <p class="onboarding-card__desc">
            Anthropic の API キーを設定すると、対戦ログを Claude に分析させる AI 分析機能を使えます。
          </p>
          <div class="onboarding-field">
            <div class="onboarding-field__label">Anthropic API キー</div>
            <input
              v-model="apiKey"
              type="password"
              class="onboarding-input"
              placeholder="sk-ant-..."
              autocomplete="off"
            />
          </div>
          <p class="onboarding-card__sub">API キーは後から「設定」→「Anthropic API キー」で設定・変更できます。</p>
        </div>
        <div class="onboarding-card__footer">
          <button class="onboarding-btn onboarding-btn--ghost" @click="skipAll">スキップ</button>
          <div class="onboarding-card__footer-right">
            <button class="onboarding-btn" @click="back">戻る</button>
            <button
              class="onboarding-btn onboarding-btn--primary"
              :disabled="saving"
              @click="complete"
            >{{ saving ? '保存中...' : '完了' }}</button>
          </div>
        </div>
      </template>

      <!-- ── 完了 ── -->
      <template v-else-if="currentStep === 'done'">
        <div class="onboarding-card__title">セットアップ完了</div>
        <div class="onboarding-card__body">
          <div class="onboarding-done-icon">✅</div>
          <div class="onboarding-summary">
            <div v-if="mtgoFolder" class="onboarding-summary__item">
              <span class="onboarding-summary__label">MTGO フォルダ</span>
              <span class="onboarding-summary__value">{{ mtgoFolder }}</span>
            </div>
            <div v-if="surveilFolder" class="onboarding-summary__item">
              <span class="onboarding-summary__label">Surveil フォルダ</span>
              <span class="onboarding-summary__value">{{ surveilFolder }}</span>
            </div>
            <div v-if="mtgaFolder" class="onboarding-summary__item">
              <span class="onboarding-summary__label">MTGA フォルダ</span>
              <span class="onboarding-summary__value">{{ mtgaFolder }}</span>
            </div>
            <div class="onboarding-summary__item">
              <span class="onboarding-summary__label">自動インポート</span>
              <span class="onboarding-summary__value">{{ autoImport ? '有効' : '無効' }}</span>
            </div>
            <div class="onboarding-summary__item">
              <span class="onboarding-summary__label">AI 分析</span>
              <span class="onboarding-summary__value">{{ apiKey ? '設定済み' : '未設定' }}</span>
            </div>
          </div>
          <p class="onboarding-card__sub">まずはログをインポートしてみましょう。</p>
        </div>
        <div class="onboarding-card__footer onboarding-card__footer--done">
          <button class="onboarding-btn" @click="goTo('/settings')">設定を確認する</button>
          <button class="onboarding-btn onboarding-btn--primary" @click="goTo('/import')">ログをインポートする</button>
        </div>
      </template>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { updateSettings } from '../api/settings'
import { setSurveilFolder } from '../api/import'
import { setMtgaFolder, syncMtgaCards } from '../api/admin'
import { useToast } from '../composables/useToast'

const emit = defineEmits<{ complete: [] }>()

const router = useRouter()
const { showError } = useToast()

type Step = 'welcome' | 'games' | 'import' | 'ai' | 'done'
const STEP_ORDER: Step[] = ['welcome', 'games', 'import', 'ai', 'done']

const currentStep = ref<Step>('welcome')
const saving = ref(false)

// Step 1
const selectedGames = ref<Set<'mtgo' | 'mtga'>>(new Set())

// Step 2
const mtgoFolder = ref<string | null>(null)
const surveilFolder = ref<string | null>(null)
const mtgaFolder = ref<string | null>(null)
const autoImport = ref(false)

// Step 3
const apiKey = ref('')

const stepIndex = computed(() => {
  const idx = STEP_ORDER.indexOf(currentStep.value)
  // welcome=0, games=1, import=2, ai=3, done=4
  // インジケーターは 1〜3 を対象
  return idx
})

function toggleGame(game: 'mtgo' | 'mtga') {
  const s = new Set(selectedGames.value)
  if (s.has(game)) s.delete(game)
  else s.add(game)
  selectedGames.value = s
}

function next() {
  const idx = STEP_ORDER.indexOf(currentStep.value)
  currentStep.value = STEP_ORDER[idx + 1]
}

function back() {
  const idx = STEP_ORDER.indexOf(currentStep.value)
  currentStep.value = STEP_ORDER[idx - 1]
}

async function skipAll() {
  saving.value = true
  try {
    await updateSettings({ onboarding_completed: true })
  } catch { /* ignore */ } finally {
    saving.value = false
  }
  emit('complete')
}

async function selectMtgoFolder() {
  const path = await window.electronAPI.selectFolder()
  if (path) mtgoFolder.value = path
}

async function selectSurveilFolder() {
  const path = await window.electronAPI.selectFolder()
  if (path) surveilFolder.value = path
}

async function selectMtgaFolder() {
  const path = await window.electronAPI.selectFolder()
  if (path) mtgaFolder.value = path
}

async function complete() {
  saving.value = true
  try {
    await updateSettings({
      quick_import_folder: mtgoFolder.value,
      auto_import_enabled: autoImport.value,
      ...(apiKey.value ? { api_key: apiKey.value } : {}),
      onboarding_completed: true,
    })
    if (surveilFolder.value) {
      await setSurveilFolder(surveilFolder.value)
    }
    if (mtgaFolder.value) {
      await setMtgaFolder(mtgaFolder.value)
      await syncMtgaCards(mtgaFolder.value)
    }
    currentStep.value = 'done'
  } catch {
    showError('設定の保存に失敗しました')
  } finally {
    saving.value = false
  }
}

function goTo(path: string) {
  emit('complete')
  router.push(path)
}
</script>

<style scoped>
.onboarding-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.onboarding-card {
  background: #fff;
  border-radius: 12px;
  width: 560px;
  max-width: 95vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.24);
}

/* ステップインジケーター */
.onboarding-steps {
  display: flex;
  gap: 6px;
  padding: 20px 28px 0;
}

.onboarding-steps__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #e0d8c8;
  transition: background 0.2s;
}

.onboarding-steps__dot--active {
  background: #4a6fa5;
}

.onboarding-steps__dot--done {
  background: #7aaa7a;
}

/* カード共通 */
.onboarding-card__title {
  font-size: 20px;
  font-weight: bold;
  color: #2c2416;
  padding: 24px 28px 0;
}

.onboarding-card__optional {
  font-size: 13px;
  font-weight: normal;
  color: #9a8a76;
}

.onboarding-card__body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 28px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.onboarding-card__lead {
  font-size: 15px;
  color: #2c2416;
}

.onboarding-card__desc {
  font-size: 13px;
  color: #5a4a35;
  line-height: 1.6;
}

.onboarding-card__sub {
  font-size: 12px;
  color: #9a8a76;
  margin-top: 4px;
}

.onboarding-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 28px;
  border-top: 1px solid #f0ece0;
  gap: 8px;
}

.onboarding-card__footer--done {
  justify-content: flex-end;
}

.onboarding-card__footer-right {
  display: flex;
  gap: 8px;
}

/* ウェルカム */
.onboarding-feature-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: #faf7f0;
  border-radius: 8px;
  padding: 16px;
}

.onboarding-feature-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.onboarding-feature-item__icon {
  font-size: 20px;
  line-height: 1.4;
  flex-shrink: 0;
}

.onboarding-feature-item__title {
  font-size: 13px;
  font-weight: bold;
  color: #2c2416;
  margin-bottom: 2px;
}

.onboarding-feature-item__desc {
  font-size: 12px;
  color: #7a6a55;
}

/* Step 1: ゲーム選択 */
.onboarding-game-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.onboarding-game-item {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 2px solid #e0d8c8;
  border-radius: 8px;
  padding: 14px 16px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.onboarding-game-item:hover {
  border-color: #c8b89a;
  background: #faf7f0;
}

.onboarding-game-item--selected {
  border-color: #4a6fa5;
  background: #f0f4fb;
}

.onboarding-game-item__check {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  cursor: pointer;
}

.onboarding-game-item__name {
  font-size: 14px;
  font-weight: bold;
  color: #2c2416;
  margin-bottom: 2px;
}

.onboarding-game-item__desc {
  font-size: 12px;
  color: #7a6a55;
}

/* Step 2: インポート設定 */
.onboarding-section-label {
  font-size: 11px;
  font-weight: bold;
  color: #7a6a55;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid #e0d8c8;
  padding-bottom: 6px;
}

.onboarding-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.onboarding-field__label {
  font-size: 12px;
  color: #5a4a35;
  font-weight: bold;
}

.onboarding-field__optional {
  font-weight: normal;
  color: #9a8a76;
}

.onboarding-field__row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.onboarding-field__path {
  flex: 1;
  font-size: 12px;
  color: #5a4a35;
  background: #f5f2ea;
  border: 1px solid #e0d8c8;
  border-radius: 4px;
  padding: 5px 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.onboarding-field__hint {
  font-size: 11px;
  color: #a09080;
}

.onboarding-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #2c2416;
  cursor: pointer;
}

.onboarding-toggle input {
  width: 14px;
  height: 14px;
  cursor: pointer;
}

/* Step 3: AI キー */
.onboarding-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #c8b89a;
  border-radius: 6px;
  font-size: 13px;
  background: #fff;
  color: #2c2416;
  font-family: monospace;
}

.onboarding-input:focus {
  outline: none;
  border-color: #4a6fa5;
}

/* 完了 */
.onboarding-done-icon {
  font-size: 48px;
  text-align: center;
  margin: 8px 0;
}

.onboarding-summary {
  background: #faf7f0;
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.onboarding-summary__item {
  display: flex;
  gap: 12px;
  font-size: 13px;
}

.onboarding-summary__label {
  color: #7a6a55;
  width: 140px;
  flex-shrink: 0;
}

.onboarding-summary__value {
  color: #2c2416;
  font-weight: bold;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ボタン */
.onboarding-btn {
  padding: 8px 18px;
  border: 1px solid #c8b89a;
  border-radius: 6px;
  background: #faf7f0;
  color: #2c2416;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  white-space: nowrap;
}

.onboarding-btn:hover:not(:disabled) {
  background: #f0ece0;
}

.onboarding-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.onboarding-btn--primary {
  background: #4a6fa5;
  border-color: #4a6fa5;
  color: #fff;
}

.onboarding-btn--primary:hover:not(:disabled) {
  background: #3a5f95;
}

.onboarding-btn--ghost {
  background: none;
  border-color: transparent;
  color: #9a8a76;
  font-size: 12px;
  padding: 8px 10px;
}

.onboarding-btn--ghost:hover:not(:disabled) {
  background: none;
  color: #5a4a35;
  text-decoration: underline;
}

.onboarding-btn--sm {
  padding: 4px 10px;
  font-size: 12px;
  flex-shrink: 0;
}
</style>
