<template>
  <v-chart :option="option" autoresize style="height: 200px;" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import type { DeckStat } from '../../api/stats'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent])

const props = defineProps<{ data: DeckStat[] }>()

const option = computed(() => ({
  grid: { left: 48, right: 16, top: 24, bottom: 48 },
  tooltip: {
    trigger: 'axis',
    formatter: (params: any) => {
      const d = props.data[params[0].dataIndex]
      return `${d.deck_name}<br/>試合数: ${d.matches}<br/>勝率: ${(d.win_rate * 100).toFixed(1)}%`
    },
  },
  xAxis: {
    type: 'category',
    data: props.data.map(d => d.deck_name),
    axisLabel: {
      color: '#7a6a55',
      rotate: props.data.length > 3 ? 15 : 0,
      overflow: 'truncate',
      width: 80,
    },
    axisTick: { show: false },
    axisLine: { lineStyle: { color: '#e0d8c8' } },
  },
  yAxis: {
    type: 'value',
    min: 0,
    max: 1,
    axisLabel: {
      color: '#7a6a55',
      formatter: (v: number) => `${(v * 100).toFixed(0)}%`,
    },
    splitLine: { lineStyle: { color: '#e0d8c8' } },
  },
  series: [
    {
      type: 'bar',
      data: props.data.map(d => d.win_rate),
      barMaxWidth: 60,
      itemStyle: { color: '#4a6fa5' },
      label: {
        show: true,
        position: 'top',
        color: '#7a6a55',
        formatter: (p: any) => `${(p.value * 100).toFixed(1)}%`,
      },
    },
  ],
}))
</script>
