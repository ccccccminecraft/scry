<template>
  <v-chart :option="option" autoresize style="height: 100%; min-height: 180px;" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import type { WinRatePoint } from '../../api/stats'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent])

const props = defineProps<{ data: WinRatePoint[] }>()

const option = computed(() => {
  // 累積勝率を計算
  let wins = 0
  const points = props.data.map((p, i) => {
    if (p.won) wins++
    return [p.match_index, wins / (i + 1)]
  })

  return {
    grid: { left: 48, right: 16, top: 16, bottom: 32 },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const d = props.data[params[0].dataIndex]
        const rate = (params[0].value[1] * 100).toFixed(1)
        const result = d.won ? '勝' : '敗'
        return `#${d.match_index} (${result})<br/>累積勝率: ${rate}%`
      },
    },
    xAxis: {
      type: 'value',
      name: '試合',
      nameTextStyle: { color: '#7a6a55' },
      axisLabel: { color: '#7a6a55' },
      splitLine: { lineStyle: { color: '#e0d8c8' } },
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
        type: 'line',
        data: points,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#4a6fa5', width: 2 },
        areaStyle: { color: 'rgba(74,111,165,0.1)' },
      },
    ],
  }
})
</script>
