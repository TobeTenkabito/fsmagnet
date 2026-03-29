<template>
  <div class="chart-card" ref="cardRef">
    <div class="chart-header">
      <span class="chart-title">实时速度</span>
      <div class="legend">
        <span class="legend-item dl"><i></i>下载</span>
        <span class="legend-item ul"><i></i>上传</span>
      </div>
      <span class="chart-peak">峰值 {{ peakDownload }} KB/s</span>
    </div>
    <div
      v-if="tooltip.visible"
      class="tooltip"
      :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }"
    >
      <div class="tt-time">{{ tooltip.time }}</div>
      <div class="tt-dl">↓ {{ tooltip.dl }}</div>
      <div class="tt-ul">↑ {{ tooltip.ul }}</div>
    </div>
    <canvas
      ref="canvas"
      class="chart-canvas"
      @mousemove="onMouseMove"
      @mouseleave="onMouseLeave"
    />
  </div>
</template>

<script setup>
import { ref, watch, computed, onMounted, nextTick, reactive } from 'vue'

const props  = defineProps({ history: Array })
const canvas  = ref(null)
const cardRef = ref(null)

const PAD_LEFT   = 56
const PAD_RIGHT  = 12
const PAD_TOP    = 10
const PAD_BOTTOM = 22

const tooltip  = reactive({ visible: false, x: 0, y: 0, time: '', dl: '', ul: '' })
const hoverIdx = ref(-1)

// 从 CSS 变量读取当前主题颜色（供 Canvas 使用）
function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

const peakDownload = computed(() =>
  props.history?.length ? Math.max(...props.history.map(h => h.download ?? h.speed ?? 0)) : 0
)

function fmtSpeed(val) {
  if (val >= 1024) return (val / 1024).toFixed(2) + ' MB/s'
  return (val ?? 0).toFixed(1) + ' KB/s'
}

function draw(hIdx = -1) {
  const el = canvas.value
  if (!el) return
  const ctx = el.getContext('2d')
  const W = el.width  = el.offsetWidth
  const H = el.height = el.offsetHeight
  const data = props.history ?? []

  // 每次绘制时读取最新主题颜色
  const colorDl      = cssVar('--speed-dl')      || '#7c8cff'
  const colorUl      = cssVar('--speed-ul')      || '#fb923c'
  const fillDl       = cssVar('--speed-dl-fill') || 'rgba(124,140,255,0.35)'
  const fillUl       = cssVar('--speed-ul-fill') || 'rgba(251,146,60,0.28)'
  const colorGrid    = cssVar('--chart-grid')    || '#2a2d3e'
  const colorAxis    = cssVar('--chart-axis')    || '#3a3d50'
  const colorLabel   = cssVar('--chart-label')   || '#555'

  ctx.clearRect(0, 0, W, H)

  const chartW = W - PAD_LEFT - PAD_RIGHT
  const chartH = H - PAD_TOP  - PAD_BOTTOM

  const allVals = data.flatMap(d => [d.download ?? d.speed ?? 0, d.upload ?? 0])
  const maxVal  = Math.max(...allVals, 1)
  const yTicks  = 4
  const rawStep = maxVal / yTicks
  const mag     = Math.pow(10, Math.floor(Math.log10(rawStep)))
  const niceStep = Math.ceil(rawStep / mag) * mag
  const yMax    = niceStep * yTicks

  const toX = i => PAD_LEFT + (i / Math.max(data.length - 1, 1)) * chartW
  const toY = v => PAD_TOP  + chartH - (v / yMax) * chartH

  // Y 轴网格 + 标签
  ctx.font         = '10px monospace'
  ctx.textAlign    = 'right'
  ctx.textBaseline = 'middle'
  for (let i = 0; i <= yTicks; i++) {
    const val = niceStep * i
    const y   = toY(val)
    ctx.beginPath()
    ctx.strokeStyle = i === 0 ? colorAxis : colorGrid
    ctx.lineWidth   = 1
    ctx.setLineDash(i === 0 ? [] : [3, 4])
    ctx.moveTo(PAD_LEFT, y)
    ctx.lineTo(PAD_LEFT + chartW, y)
    ctx.stroke()
    ctx.setLineDash([])
    ctx.fillStyle = colorLabel
    ctx.fillText(fmtSpeed(val), PAD_LEFT - 6, y)
  }

  // X 轴刻度
  if (data.length >= 2) {
    const xTickCount = Math.min(5, data.length)
    const idxStep    = Math.floor((data.length - 1) / (xTickCount - 1))
    ctx.textAlign    = 'center'
    ctx.textBaseline = 'top'
    ctx.fillStyle    = colorLabel
    for (let t = 0; t < xTickCount; t++) {
      const idx = Math.min(t * idxStep, data.length - 1)
      const x   = toX(idx)
      ctx.beginPath()
      ctx.strokeStyle = colorAxis
      ctx.lineWidth   = 1
      ctx.moveTo(x, PAD_TOP + chartH)
      ctx.lineTo(x, PAD_TOP + chartH + 4)
      ctx.stroke()
      const secsAgo = data.length - 1 - idx
      ctx.fillText(secsAgo === 0 ? '现在' : `-${secsAgo}s`, x, PAD_TOP + chartH + 6)
    }
  }

  // 轴线
  ctx.beginPath()
  ctx.strokeStyle = colorAxis
  ctx.lineWidth   = 1
  ctx.moveTo(PAD_LEFT, PAD_TOP)
  ctx.lineTo(PAD_LEFT, PAD_TOP + chartH)
  ctx.lineTo(PAD_LEFT + chartW, PAD_TOP + chartH)
  ctx.stroke()

  if (data.length < 2) return

  // 下载：渐变填充 + 折线
  const gradDl = ctx.createLinearGradient(0, PAD_TOP, 0, PAD_TOP + chartH)
  gradDl.addColorStop(0, fillDl)
  gradDl.addColorStop(1, 'rgba(0,0,0,0)')
  ctx.beginPath()
  data.forEach((d, i) => {
    const v = d.download ?? d.speed ?? 0
    i === 0 ? ctx.moveTo(toX(i), toY(v)) : ctx.lineTo(toX(i), toY(v))
  })
  ctx.lineTo(toX(data.length - 1), PAD_TOP + chartH)
  ctx.lineTo(toX(0), PAD_TOP + chartH)
  ctx.closePath()
  ctx.fillStyle = gradDl
  ctx.fill()

  ctx.beginPath()
  ctx.strokeStyle = colorDl
  ctx.lineWidth   = 2
  ctx.lineJoin    = 'round'
  data.forEach((d, i) => {
    const v = d.download ?? d.speed ?? 0
    i === 0 ? ctx.moveTo(toX(i), toY(v)) : ctx.lineTo(toX(i), toY(v))
  })
  ctx.stroke()

  // 上传：渐变填充 + 折线
  const gradUl = ctx.createLinearGradient(0, PAD_TOP, 0, PAD_TOP + chartH)
  gradUl.addColorStop(0, fillUl)
  gradUl.addColorStop(1, 'rgba(0,0,0,0)')
  ctx.beginPath()
  data.forEach((d, i) => {
    const v = d.upload ?? 0
    i === 0 ? ctx.moveTo(toX(i), toY(v)) : ctx.lineTo(toX(i), toY(v))
  })
  ctx.lineTo(toX(data.length - 1), PAD_TOP + chartH)
  ctx.lineTo(toX(0), PAD_TOP + chartH)
  ctx.closePath()
  ctx.fillStyle = gradUl
  ctx.fill()

  ctx.beginPath()
  ctx.strokeStyle = colorUl
  ctx.lineWidth   = 2
  ctx.lineJoin    = 'round'
  data.forEach((d, i) => {
    const v = d.upload ?? 0
    i === 0 ? ctx.moveTo(toX(i), toY(v)) : ctx.lineTo(toX(i), toY(v))
  })
  ctx.stroke()

  // Hover 十字准线
  if (hIdx >= 0 && hIdx < data.length) {
    const hx   = toX(hIdx)
    const dlV  = data[hIdx].download ?? data[hIdx].speed ?? 0
    const ulV  = data[hIdx].upload   ?? 0
    const hyDl = toY(dlV)
    const hyUl = toY(ulV)

    ctx.beginPath()
    ctx.strokeStyle = 'rgba(200,200,255,0.35)'
    ctx.lineWidth   = 1
    ctx.setLineDash([4, 3])
    ctx.moveTo(hx, PAD_TOP)
    ctx.lineTo(hx, PAD_TOP + chartH)
    ctx.stroke()
    ctx.setLineDash([])

    ctx.beginPath()
    ctx.fillStyle = colorDl
    ctx.arc(hx, PAD_TOP + chartH, 3, 0, Math.PI * 2)
    ctx.fill()

    ctx.beginPath()
    ctx.strokeStyle = '#fff'
    ctx.lineWidth   = 1.5
    ctx.fillStyle   = colorDl
    ctx.arc(hx, hyDl, 5, 0, Math.PI * 2)
    ctx.fill(); ctx.stroke()

    ctx.beginPath()
    ctx.strokeStyle = '#fff'
    ctx.lineWidth   = 1.5
    ctx.fillStyle   = colorUl
    ctx.arc(hx, hyUl, 5, 0, Math.PI * 2)
    ctx.fill(); ctx.stroke()
  }
}

function onMouseMove(e) {
  const el = canvas.value
  if (!el) return
  const data = props.history ?? []
  if (data.length < 2) return
  const rect   = el.getBoundingClientRect()
  const mouseX = e.clientX - rect.left
  const mouseY = e.clientY - rect.top
  const chartW = el.offsetWidth  - PAD_LEFT - PAD_RIGHT
  const chartH = el.offsetHeight - PAD_TOP  - PAD_BOTTOM
  if (mouseX < PAD_LEFT || mouseX > PAD_LEFT + chartW || mouseY < PAD_TOP || mouseY > PAD_TOP + chartH) {
    onMouseLeave(); return
  }
  const ratio      = (mouseX - PAD_LEFT) / chartW
  const idx        = Math.round(ratio * (data.length - 1))
  const clampedIdx = Math.max(0, Math.min(idx, data.length - 1))
  if (clampedIdx === hoverIdx.value) return
  hoverIdx.value = clampedIdx
  draw(clampedIdx)
  const secsAgo = data.length - 1 - clampedIdx
  const d = data[clampedIdx]
  tooltip.time    = secsAgo === 0 ? '现在' : `-${secsAgo}s`
  tooltip.dl      = fmtSpeed(d.download ?? d.speed ?? 0)
  tooltip.ul      = fmtSpeed(d.upload   ?? 0)
  tooltip.visible = true
  const tipW = 110
  const offX = mouseX + tipW + 16 > el.offsetWidth ? -tipW - 8 : 12
  tooltip.x = mouseX + offX
  tooltip.y = Math.max(PAD_TOP, mouseY - 44)
}

function onMouseLeave() {
  if (hoverIdx.value === -1) return
  hoverIdx.value  = -1
  tooltip.visible = false
  draw(-1)
}

watch(() => props.history, () => draw(hoverIdx.value), { deep: true })
onMounted(() => nextTick(() => draw()))
</script>

<style scoped>
.chart-card {
  position: relative;
  background: var(--bg-card); border-radius: 12px;
  padding: 16px; border: 1px solid var(--border);
  transition: background 0.3s, border-color 0.3s;
}
.chart-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 10px; font-size: 13px;
}
.chart-title { color: var(--accent); font-weight: 600; }
.chart-peak  { color: var(--text-muted); }

.legend { display: flex; gap: 14px; }
.legend-item {
  display: flex; align-items: center; gap: 5px;
  font-size: 12px; color: var(--text-sub);
}
.legend-item i { display: inline-block; width: 20px; height: 2px; border-radius: 1px; }
.legend-item.dl i { background: var(--speed-dl); }
.legend-item.ul i { background: var(--speed-ul); }

.chart-canvas { width: 100%; height: 120px; display: block; cursor: crosshair; }

.tooltip {
  position: absolute; pointer-events: none;
  background: var(--tooltip-bg); border: 1px solid var(--border-light);
  border-radius: 6px; padding: 6px 10px;
  font-size: 11px; line-height: 1.8; white-space: nowrap;
  z-index: 10; box-shadow: 0 2px 8px rgba(0,0,0,0.4);
}
.tt-time { color: var(--text-muted); }
.tt-dl   { color: var(--speed-dl); font-weight: 600; }
.tt-ul   { color: var(--speed-ul); font-weight: 600; }
</style>