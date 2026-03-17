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

          <!-- デッキ名インライン編集 -->
          <span class="player-row__label">デッキ名:</span>
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
import { fetchMatchDetail, patchPlayer, type MatchDetail, type PlayerInfo } from '../api/matches'
import { useToast } from '../composables/useToast'

const route = useRoute()
const { showError } = useToast()

const detail = ref<MatchDetail | null>(null)
const loading = ref(false)
const deckEditing = reactive<Record<string, boolean>>({})
const deckDraft = reactive<Record<string, string>>({})
const gamePlanSaving = reactive<Record<string, boolean>>({})

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
    showError(e instanceof Error ? e.message : 'デッキ名の更新に失敗しました')
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
</script>

<style scoped>
.detail {
  padding: 24px;
  max-width: 900px;
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

.detail__games { margin-top: 8px; }
</style>
