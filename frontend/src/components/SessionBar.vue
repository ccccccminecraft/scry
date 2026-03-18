<template>
  <div class="session-bar">
    <div class="session-bar__header">
      <span class="session-bar__label">会話履歴</span>
      <button class="session-bar__new" @click="$emit('new')">＋ 新規</button>
    </div>
    <div class="session-bar__list">
      <div
        v-for="s in sessions"
        :key="s.id"
        class="session-bar__item"
        :class="{ 'session-bar__item--active': s.id === currentId }"
        @click="$emit('select', s.id)"
      >
        <div class="session-bar__title">{{ truncate(s.title) }}</div>
        <div class="session-bar__date">{{ formatDate(s.updated_at) }}</div>
      </div>
      <div v-if="sessions.length === 0" class="session-bar__empty">履歴なし</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SessionSummary } from '../api/analysis'

defineProps<{
  sessions: SessionSummary[]
  currentId: number | null
}>()

defineEmits<{
  select: [id: number]
  new: []
}>()

function truncate(s: string): string {
  return s.length > 14 ? s.slice(0, 14) + '…' : s
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${m}/${day}`
}
</script>

<style scoped>
.session-bar {
  width: 180px;
  flex-shrink: 0;
  background: #faf7f0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e0d8c8;
}

.session-bar__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 12px 8px;
  border-bottom: 1px solid #e0d8c8;
}

.session-bar__label {
  font-size: 11px;
  color: #7a6a55;
  font-weight: bold;
}

.session-bar__new {
  font-size: 11px;
  padding: 2px 8px;
  background: #4a6fa5;
  color: #fff;
  border: none;
  border-radius: 3px;
  cursor: pointer;
}

.session-bar__new:hover {
  background: #3a5f95;
}

.session-bar__list {
  flex: 1;
  overflow-y: auto;
}

.session-bar__item {
  padding: 8px 12px;
  cursor: pointer;
  border-bottom: 1px solid #e0d8c8;
}

.session-bar__item:hover {
  background: #f0ece0;
}

.session-bar__item--active {
  background: #e8f0fa;
  border-left: 3px solid #4a6fa5;
}

.session-bar__title {
  font-size: 12px;
  color: #2c2416;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-bar__date {
  font-size: 10px;
  color: #7a6a55;
  margin-top: 2px;
}

.session-bar__empty {
  font-size: 12px;
  color: #7a6a55;
  padding: 16px 12px;
  text-align: center;
}
</style>
