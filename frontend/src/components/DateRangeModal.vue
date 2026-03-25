<template>
  <div class="drm-overlay" @click.self="close">
    <div class="drm">
      <div class="drm__header">
        <span class="drm__title">対戦期間を設定</span>
        <button class="drm__close" @click="close">✕</button>
      </div>

      <div class="drm__calendars">
        <!-- 左カレンダー -->
        <div class="drm__cal">
          <div class="drm__cal-nav">
            <button class="drm__nav-btn" @click="prevMonth">◀</button>
            <span class="drm__cal-title">{{ monthLabel(leftYear, leftMonth) }}</span>
            <button class="drm__nav-btn drm__nav-btn--hidden">▶</button>
          </div>
          <div class="drm__grid">
            <div v-for="d in DOW" :key="d" class="drm__dow">{{ d }}</div>
            <div v-for="cell in leftCells" :key="cell.key" class="drm__cell-wrap">
              <button
                v-if="cell.date"
                class="drm__cell"
                :class="cellClass(cell.date)"
                @click="selectDate(cell.date)"
                @mouseenter="hoverDate = cell.date"
                @mouseleave="hoverDate = null"
              >{{ cell.date.getDate() }}</button>
              <div v-else class="drm__cell drm__cell--empty" />
            </div>
          </div>
        </div>

        <!-- 右カレンダー -->
        <div class="drm__cal">
          <div class="drm__cal-nav">
            <button class="drm__nav-btn drm__nav-btn--hidden">◀</button>
            <span class="drm__cal-title">{{ monthLabel(rightYear, rightMonth) }}</span>
            <button class="drm__nav-btn" @click="nextMonth">▶</button>
          </div>
          <div class="drm__grid">
            <div v-for="d in DOW" :key="d" class="drm__dow">{{ d }}</div>
            <div v-for="cell in rightCells" :key="cell.key" class="drm__cell-wrap">
              <button
                v-if="cell.date"
                class="drm__cell"
                :class="cellClass(cell.date)"
                @click="selectDate(cell.date)"
                @mouseenter="hoverDate = cell.date"
                @mouseleave="hoverDate = null"
              >{{ cell.date.getDate() }}</button>
              <div v-else class="drm__cell drm__cell--empty" />
            </div>
          </div>
        </div>
      </div>

      <div class="drm__footer">
        <div class="drm__range-label">
          <span class="drm__range-item">
            開始: <strong>{{ fromLabel }}</strong>
          </span>
          <span class="drm__range-sep">〜</span>
          <span class="drm__range-item">
            終了: <strong>{{ toLabel }}</strong>
          </span>
        </div>
        <div class="drm__actions">
          <button class="drm__btn" @click="clearDates">クリア</button>
          <button class="drm__btn drm__btn--primary" @click="close">確定</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  dateFrom: string
  dateTo: string
}>()

const emit = defineEmits<{
  'update:dateFrom': [v: string]
  'update:dateTo': [v: string]
  'close': []
}>()

const DOW = ['月', '火', '水', '木', '金', '土', '日']

// 表示月の基点（左カレンダー）
const today = new Date()
const baseYear = ref(props.dateFrom ? parseInt(props.dateFrom.slice(0, 4)) : today.getFullYear())
const baseMonth = ref(props.dateFrom ? parseInt(props.dateFrom.slice(5, 7)) - 1 : today.getMonth())

const leftYear = computed(() => baseYear.value)
const leftMonth = computed(() => baseMonth.value)
const rightYear = computed(() => baseMonth.value === 11 ? baseYear.value + 1 : baseYear.value)
const rightMonth = computed(() => baseMonth.value === 11 ? 0 : baseMonth.value + 1)

const hoverDate = ref<Date | null>(null)

// 選択中の日付（内部管理）
const fromDate = ref<Date | null>(props.dateFrom ? parseDate(props.dateFrom) : null)
const toDate = ref<Date | null>(props.dateTo ? parseDate(props.dateTo) : null)
// 選択ステップ: 'from' = 次クリックで開始日, 'to' = 次クリックで終了日
const step = ref<'from' | 'to'>(fromDate.value && !toDate.value ? 'to' : 'from')

function parseDate(s: string): Date | null {
  if (!s) return null
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function toISO(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function monthLabel(y: number, m: number): string {
  return `${y}年${m + 1}月`
}

function prevMonth() {
  if (baseMonth.value === 0) {
    baseYear.value--
    baseMonth.value = 11
  } else {
    baseMonth.value--
  }
}

function nextMonth() {
  if (baseMonth.value === 11) {
    baseYear.value++
    baseMonth.value = 0
  } else {
    baseMonth.value++
  }
}

function buildCells(year: number, month: number) {
  const first = new Date(year, month, 1)
  // 月曜始まり: 月=0, 火=1 ... 日=6
  const startDow = (first.getDay() + 6) % 7
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const cells: { date: Date | null; key: string }[] = []
  for (let i = 0; i < startDow; i++) {
    cells.push({ date: null, key: `empty-${i}` })
  }
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({ date: new Date(year, month, d), key: `${year}-${month}-${d}` })
  }
  return cells
}

const leftCells = computed(() => buildCells(leftYear.value, leftMonth.value))
const rightCells = computed(() => buildCells(rightYear.value, rightMonth.value))

function selectDate(d: Date) {
  if (step.value === 'from') {
    fromDate.value = d
    toDate.value = null
    step.value = 'to'
    emit('update:dateFrom', toISO(d))
    emit('update:dateTo', '')
  } else {
    // 開始日より前を選んだ場合は開始日として再設定
    if (fromDate.value && d < fromDate.value) {
      fromDate.value = d
      toDate.value = null
      emit('update:dateFrom', toISO(d))
      emit('update:dateTo', '')
    } else {
      toDate.value = d
      step.value = 'from'
      emit('update:dateTo', toISO(d))
    }
  }
}

function isSameDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear()
    && a.getMonth() === b.getMonth()
    && a.getDate() === b.getDate()
}

function cellClass(d: Date) {
  const from = fromDate.value
  const to = toDate.value
  const hover = hoverDate.value

  const isFrom = from && isSameDay(d, from)
  const isTo = to && isSameDay(d, to)

  // プレビュー終端（終了日未選択時はホバー位置まで）
  const rangeEnd = to ?? (step.value === 'to' && hover ? hover : null)
  const inRange = from && rangeEnd && d > from && d < rangeEnd

  return {
    'drm__cell--from': isFrom,
    'drm__cell--to': isTo,
    'drm__cell--in-range': inRange,
    'drm__cell--today': isSameDay(d, today),
  }
}

function clearDates() {
  fromDate.value = null
  toDate.value = null
  step.value = 'from'
  emit('update:dateFrom', '')
  emit('update:dateTo', '')
}

function close() {
  emit('close')
}

const fromLabel = computed(() => fromDate.value ? toISO(fromDate.value) : '未設定')
const toLabel = computed(() => toDate.value ? toISO(toDate.value) : '未設定')
</script>

<style scoped>
.drm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 300;
}

.drm {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
  display: flex;
  flex-direction: column;
  max-width: 95vw;
}

.drm__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 10px;
  border-bottom: 1px solid #e0d8c8;
}

.drm__title {
  font-size: 13px;
  font-weight: bold;
  color: #2c2416;
}

.drm__close {
  background: none;
  border: none;
  font-size: 14px;
  color: #7a6a55;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}
.drm__close:hover { color: #2c2416; }

.drm__calendars {
  display: flex;
  gap: 0;
  padding: 16px;
}

.drm__cal {
  width: 224px;
  flex-shrink: 0;
}
.drm__cal + .drm__cal {
  border-left: 1px solid #e0d8c8;
  margin-left: 16px;
  padding-left: 16px;
}

.drm__cal-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.drm__cal-title {
  font-size: 13px;
  font-weight: bold;
  color: #2c2416;
}

.drm__nav-btn {
  background: none;
  border: none;
  color: #7a6a55;
  cursor: pointer;
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 3px;
}
.drm__nav-btn:hover { background: #f0ece0; color: #2c2416; }
.drm__nav-btn--hidden { visibility: hidden; }

.drm__grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 1px;
}

.drm__dow {
  text-align: center;
  font-size: 10px;
  color: #9a8a75;
  padding: 2px 0 4px;
}

.drm__cell-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
}

.drm__cell {
  width: 28px;
  height: 28px;
  border: none;
  background: none;
  border-radius: 50%;
  font-size: 12px;
  font-family: inherit;
  color: #2c2416;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.drm__cell:hover { background: #f0ece0; }
.drm__cell--empty { pointer-events: none; }

.drm__cell--today {
  font-weight: bold;
  color: #4a6fa5;
}

.drm__cell--from,
.drm__cell--to {
  background: #4a6fa5;
  color: #fff;
  border-radius: 50%;
}
.drm__cell--from:hover,
.drm__cell--to:hover {
  background: #3a5f95;
}

.drm__cell--in-range {
  background: #d8e4f4;
  border-radius: 0;
  color: #2c2416;
}

.drm__footer {
  border-top: 1px solid #e0d8c8;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.drm__range-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #7a6a55;
}

.drm__range-item strong {
  color: #2c2416;
  font-weight: bold;
}

.drm__range-sep {
  color: #b0a090;
}

.drm__actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.drm__btn {
  padding: 5px 14px;
  border: 1px solid #c8b89a;
  border-radius: 4px;
  background: #faf7f0;
  font-size: 12px;
  font-family: inherit;
  color: #2c2416;
  cursor: pointer;
}
.drm__btn:hover { background: #f0ece0; }

.drm__btn--primary {
  background: #4a6fa5;
  border-color: #4a6fa5;
  color: #fff;
}
.drm__btn--primary:hover { background: #3a5f95; }
</style>
