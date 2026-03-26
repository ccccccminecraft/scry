<template>
  <div class="detail">
    <div class="detail__back">
      <button class="btn-back" @click="$router.back()">← 戻る</button>
    </div>

    <div v-if="loading" class="detail__loading">読み込み中...</div>

    <template v-else-if="detail">
      <!-- ヘッダー -->
      <div class="detail__header">
        <div class="detail__date">{{ formatDate(detail.date) }}</div>
        <span v-if="detail.format" class="detail__badge">{{ detail.format }}</span>
        <div class="detail__vs">
          {{ detail.players[0]?.player_name }} vs {{ detail.players[1]?.player_name }}
        </div>
        <div class="detail__winner">勝者: {{ detail.match_winner }}</div>
      </div>

      <!-- プレイヤー情報 -->
      <div class="detail__players">
        <div v-for="p in detail.players" :key="p.player_name" class="player-row">
          <span class="player-row__name">{{ p.player_name }}</span>

          <!-- アーキタイプインライン編集 -->
          <span class="player-row__label">アーキタイプ:</span>
          <template v-if="deckEditing[p.player_name]">
            <input
              v-model="deckDraft[p.player_name]"
              class="player-row__input"
              @keydown.enter="confirmDeck(p)"
              @keydown.esc="cancelDeck(p)"
              @blur="confirmDeck(p)"
              autofocus
            />
          </template>
          <template v-else>
            <span class="player-row__deck">{{ p.deck_name ?? '未設定' }}</span>
            <button class="btn-edit" @click="startDeckEdit(p)">✎</button>
          </template>

          <!-- ゲームプラン -->
          <span class="player-row__label">ゲームプラン:</span>
          <select
            class="player-row__select"
            :value="p.game_plan ?? ''"
            :disabled="gamePlanSaving[p.player_name]"
            @change="onGamePlanChange(p, ($event.target as HTMLSelectElement).value)"
          >
            <option value="">未設定</option>
            <option value="aggro">aggro</option>
            <option value="midrange">midrange</option>
            <option value="control">control</option>
            <option value="combo">combo</option>
          </select>

          <!-- デッキバージョン -->
          <span class="player-row__label">使用デッキ:</span>
          <span class="player-row__deck-ver">{{ p.deck_version_label ?? '未設定' }}</span>
          <button class="btn-edit" @click="openDeckVersionModal(p)">✎</button>
          <button v-if="p.deck_version_id" class="btn-unlink" @click="unlinkDeckVersion(p)">✕</button>
        </div>
      </div>

    <!-- デッキバージョン選択モーダル -->
    <div v-if="dvModal.visible" class="modal-overlay" @click.self="dvModal.visible = false">
      <div class="modal">
        <div class="modal__title">使用デッキを設定</div>
        <div class="modal__field">
          <label class="modal__label">デッキ</label>
          <select v-model="dvModal.deckId" class="modal__select" @change="onDvDeckChange">
            <option :value="null">選択してください</option>
            <option v-for="d in dvModal.decks" :key="d.id" :value="d.id">
              {{ d.name }}{{ d.format ? ` (${d.format})` : '' }}
            </option>
          </select>
        </div>
        <div class="modal__field">
          <label class="modal__label">バージョン</label>
          <select v-model="dvModal.versionId" class="modal__select" :disabled="!dvModal.deckId">
            <option :value="null">選択してください</option>
            <option v-for="v in dvModal.versions" :key="v.id" :value="v.id">
              v{{ v.version_number }}{{ v.memo ? ` — ${v.memo}` : '' }} ({{ v.main_count }}枚)
            </option>
          </select>
        </div>
        <div class="modal__footer">
          <button class="modal__btn" @click="dvModal.visible = false">キャンセル</button>
          <button
            class="modal__btn modal__btn--primary"
            :disabled="!dvModal.versionId"
            @click="saveDeckVersion"
          >設定</button>
        </div>
      </div>
    </div>

      <!-- ゲーム一覧 -->
      <div class="detail__games">
        <GameAccordion
          v-for="g in detail.games"
          :key="g.game_id"
          :game="g"
          :match-id="detail.match_id"
        />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import GameAccordion from '../components/GameAccordion.vue'
import { fetchMatchDetail, patchPlayer, putDeckVersion, deleteDeckVersion, type MatchDetail, type PlayerInfo } from '../api/matches'
import { fetchDecks, fetchVersions, type Deck, type DeckVersionSummary } from '../api/decklist'
import { useToast } from '../composables/useToast'

const route = useRoute()
const { showError } = useToast()

const detail = ref<MatchDetail | null>(null)
const loading = ref(false)
const deckEditing = reactive<Record<string, boolean>>({})
const deckDraft = reactive<Record<string, string>>({})
const gamePlanSaving = reactive<Record<string, boolean>>({})

// デッキバージョン選択モーダル
const dvModal = reactive<{
  visible: boolean
  targetPlayer: PlayerInfo | null
  decks: Deck[]
  deckId: number | null
  versions: DeckVersionSummary[]
  versionId: number | null
}>({
  visible: false,
  targetPlayer: null,
  decks: [],
  deckId: null,
  versions: [],
  versionId: null,
})

onMounted(async () => {
  loading.value = true
  try {
    const matchId = route.params.match_id as string
    detail.value = await fetchMatchDetail(matchId)
    for (const p of detail.value.players) {
      deckEditing[p.player_name] = false
      deckDraft[p.player_name] = p.deck_name ?? ''
    }
  } catch (e) {
    showError(e instanceof Error ? e.message : '対戦詳細の取得に失敗しました')
  } finally {
    loading.value = false
  }
})

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('ja-JP', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

function startDeckEdit(p: PlayerInfo) {
  deckDraft[p.player_name] = p.deck_name ?? ''
  deckEditing[p.player_name] = true
}

async function confirmDeck(p: PlayerInfo) {
  if (!deckEditing[p.player_name]) return
  deckEditing[p.player_name] = false
  const newName = deckDraft[p.player_name].trim() || null
  if (newName === (p.deck_name ?? null)) return
  try {
    await patchPlayer(detail.value!.match_id, p.player_name, { deck_name: newName })
    p.deck_name = newName
  } catch (e) {
    showError(e instanceof Error ? e.message : 'アーキタイプの更新に失敗しました')
    deckDraft[p.player_name] = p.deck_name ?? ''
  }
}

function cancelDeck(p: PlayerInfo) {
  deckEditing[p.player_name] = false
  deckDraft[p.player_name] = p.deck_name ?? ''
}

async function onGamePlanChange(p: PlayerInfo, value: string) {
  const newPlan = value || null
  if (newPlan === p.game_plan) return
  gamePlanSaving[p.player_name] = true
  try {
    await patchPlayer(detail.value!.match_id, p.player_name, { game_plan: newPlan })
    p.game_plan = newPlan
  } catch (e) {
    showError(e instanceof Error ? e.message : 'ゲームプランの更新に失敗しました')
  } finally {
    gamePlanSaving[p.player_name] = false
  }
}

async function openDeckVersionModal(p: PlayerInfo) {
  dvModal.targetPlayer = p
  dvModal.deckId = null
  dvModal.versions = []
  dvModal.versionId = null
  try {
    dvModal.decks = await fetchDecks()
  } catch {
    showError('デッキ一覧の取得に失敗しました')
    return
  }
  dvModal.visible = true
}

async function onDvDeckChange() {
  dvModal.versions = []
  dvModal.versionId = null
  if (!dvModal.deckId) return
  try {
    dvModal.versions = await fetchVersions(dvModal.deckId)
  } catch {
    showError('バージョン一覧の取得に失敗しました')
  }
}

async function saveDeckVersion() {
  if (!dvModal.targetPlayer || !dvModal.versionId) return
  try {
    await putDeckVersion(detail.value!.match_id, dvModal.targetPlayer.player_name, dvModal.versionId)
    const v = dvModal.versions.find(v => v.id === dvModal.versionId)
    const d = dvModal.decks.find(d => d.id === dvModal.deckId)
    dvModal.targetPlayer.deck_version_id = dvModal.versionId
    dvModal.targetPlayer.deck_version_label = d && v ? `${d.name} v${v.version_number}` : null
    dvModal.visible = false
  } catch {
    showError('デッキバージョンの設定に失敗しました')
  }
}

async function unlinkDeckVersion(p: PlayerInfo) {
  try {
    await deleteDeckVersion(detail.value!.match_id, p.player_name)
    p.deck_version_id = null
    p.deck_version_label = null
  } catch {
    showError('デッキバージョンの解除に失敗しました')
  }
}
</script>

<style scoped>
.detail {
  padding: 24px;
}

.btn-back {
  background: #faf7f0;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  color: #2c2416;
  font-size: 12px;
  padding: 5px 12px;
  margin-bottom: 16px;
  cursor: pointer;
}
.btn-back:hover { background: #f0ece0; }

.detail__loading {
  color: #7a6a55;
  padding: 32px 0;
  text-align: center;
}

.detail__header {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #d8cfc0;
}

.detail__date   { color: #7a6a55; font-size: 13px; }
.detail__badge  { background: #4a6fa5; color: #fff; padding: 2px 8px; border-radius: 3px; font-size: 12px; }
.detail__vs     { font-size: 1.1rem; font-weight: bold; }
.detail__winner { color: #5a7a4a; font-size: 13px; }

.detail__players {
  margin-bottom: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.player-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #faf7f0;
  border: 1px solid #e8e0d0;
  border-radius: 4px;
  flex-wrap: wrap;
}

.player-row__name  { font-weight: bold; min-width: 120px; }
.player-row__label { color: #7a6a55; font-size: 13px; }
.player-row__deck  { color: #2c2416; min-width: 80px; }

.player-row__input {
  padding: 3px 8px;
  border: 1px solid #4a6fa5;
  border-radius: 3px;
  font-size: 14px;
  font-family: inherit;
  min-width: 160px;
}

.btn-edit {
  background: none;
  border: none;
  color: #7a6a55;
  padding: 0 4px;
  font-size: 13px;
  cursor: pointer;
}
.btn-edit:hover { color: #4a6fa5; }

.player-row__select {
  padding: 3px 8px;
  border: 1px solid #c8b89a;
  border-radius: 3px;
  font-size: 14px;
  font-family: inherit;
  background: #fff;
}
.player-row__select:disabled { opacity: 0.5; }

.player-row__deck-ver {
  color: #2c2416;
  font-size: 13px;
  min-width: 80px;
}

.btn-unlink {
  background: none;
  border: none;
  color: #a03030;
  padding: 0 4px;
  font-size: 12px;
  cursor: pointer;
}
.btn-unlink:hover { color: #cc0000; }

.detail__games { margin-top: 8px; }

/* モーダル */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}

.modal {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  width: 400px;
  max-width: 90vw;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.modal__title {
  font-size: 14px;
  font-weight: bold;
  color: #2c2416;
}

.modal__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.modal__label {
  font-size: 12px;
  color: #7a6a55;
}

.modal__select {
  padding: 6px 10px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  font-size: 13px;
  background: #fff;
  color: #2c2416;
  font-family: inherit;
}
.modal__select:disabled { opacity: 0.5; }

.modal__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.modal__btn {
  padding: 6px 16px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  background: #faf7f0;
  font-size: 13px;
  cursor: pointer;
  color: #2c2416;
  font-family: inherit;
}
.modal__btn:hover { background: #f0ece0; }

.modal__btn--primary {
  background: #4a6fa5;
  border-color: #4a6fa5;
  color: #fff;
}
.modal__btn--primary:hover:not(:disabled) { background: #3a5f95; }
.modal__btn--primary:disabled { opacity: 0.4; cursor: default; }
</style>
