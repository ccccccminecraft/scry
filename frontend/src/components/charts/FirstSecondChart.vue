<template>
  <v-chart :option="option" autoresize style="height: 180px;" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent])

const props = defineProps<{ firstRate: number; secondRate: number }>()

const option = computed(() => ({
  grid: { left: 48, right: 16, top: 24, bottom: 32 },
  tooltip: {
    trigger: 'axis',
    formatter: (params: any) =>
      params.map((p: any) => `${p.name}: ${(p.value * 100).toFixed(1)}%`).join('<br/>'),
  },
  xAxis: {
    type: 'category',
    data: ['先手', '後手'],
    axisLabel: { color: '#7a6a55' },
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
      data: [
        { value: props.firstRate, itemStyle: { color: '#4a6fa5' } },
        { value: props.secondRate, itemStyle: { color: '#c8622a' } },
      ],
      barMaxWidth: 60,
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
