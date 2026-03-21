<template>
  <div class="chart-card">
    <div class="chart-header">
      <span class="chart-title">实时速度</span>
      <span class="chart-peak">峰值 {{ peakSpeed }} KB/s</span>
    </div>
    <!-- tooltip 气泡 -->
    <div
      v-if="tooltip.visible"
      class="tooltip"
      :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }"
    >
      <div class="tt-time">{{ tooltip.time }}</div>
      <div class="tt-speed">{{ tooltip.speed }}</div>
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

const props = defineProps({ history: Array })
const canvas = ref(null)

// ── 边距常量（与 draw 共用） ──────────────────────────────
const PAD_LEFT   = 56
const PAD_RIGHT  = 12
const PAD_TOP    = 10
const PAD_BOTTOM = 22

// ── tooltip 状态 ──────────────────────────────────────────
const tooltip = reactive({ visible: false, x: 0, y: 0, time: '', speed: '' })

// 当前 hover 的数据点索引（-1 = 无）
const hoverIdx = ref(-1)

const peakSpeed = computed(() =>
  props.history?.length ? Math.max(...props.history.map(h => h.speed)) : 0
)

function fmtSpeed(val) {
  if (val >= 1024) return (val / 1024).toFixed(2) + ' MB/s'
  return val.toFixed(1) + ' KB/s'
}

// ── 核心绘制 ──────────────────────────────────────────────
function draw(hIdx = -1) {
  const el = canvas.value
  if (!el) return
  const ctx = el.getContext('2d')
  const W = el.width  = el.offsetWidth
  const H = el.height = el.offsetHeight
  const data = props.history ?? []

  ctx.clearRect(0, 0, W, H)

  const chartW = W - PAD_LEFT - PAD_RIGHT
  const chartH = H - PAD_TOP  - PAD_BOTTOM

  // Y 轴圆整
  const maxVal  = Math.max(...data.map(d => d.speed), 1)
  const yTicks  = 4
  const rawStep = maxVal / yTicks
  const mag     = Math.pow(10, Math.floor(Math.log10(rawStep)))
  const niceStep = Math.ceil(rawStep / mag) * mag
  const yMax    = niceStep * yTicks

  const toX = i => PAD_LEFT + (i / Math.max(data.length - 1, 1)) * chartW
  const toY = v => PAD_TOP  + chartH - (v / yMax) * chartH

  // ── Y 轴网格 + 标签 ──────────────────────────────────────
  ctx.font         = '10px monospace'
  ctx.textAlign    = 'right'
  ctx.textBaseline = 'middle'

  for (let i = 0; i <= yTicks; i++) {
    const val = niceStep * i
    const y   = toY(val)

    ctx.beginPath()
    ctx.strokeStyle = i === 0 ? '#3a3d50' : '#2a2d3e'
    ctx.lineWidth   = 1
    ctx.setLineDash(i === 0 ? [] : [3, 4])
    ctx.moveTo(PAD_LEFT, y)
    ctx.lineTo(PAD_LEFT + chartW, y)
    ctx.stroke()
    ctx.setLineDash([])

    ctx.fillStyle = '#555'
    ctx.fillText(fmtSpeed(val), PAD_LEFT - 6, y)
  }

  // ── X 轴刻度 ──────────────────────────────────────────────
  if (data.length >= 2) {
    const xTickCount = Math.min(5, data.length)
    const idxStep    = Math.floor((data.length - 1) / (xTickCount - 1))

    ctx.textAlign    = 'center'
    ctx.textBaseline = 'top'
    ctx.fillStyle    = '#555'

    for (let t = 0; t < xTickCount; t++) {
      const idx = Math.min(t * idxStep, data.length - 1)
      const x   = toX(idx)

      ctx.beginPath()
      ctx.strokeStyle = '#3a3d50'
      ctx.lineWidth   = 1
      ctx.moveTo(x, PAD_TOP + chartH)
      ctx.lineTo(x, PAD_TOP + chartH + 4)
      ctx.stroke()

      const secsAgo = data.length - 1 - idx
      ctx.fillText(secsAgo === 0 ? '现在' : `-${secsAgo}s`, x, PAD_TOP + chartH + 6)
    }
  }

  // ── 轴线 ─────────────────────────────────────────────────
  ctx.beginPath()
  ctx.strokeStyle = '#3a3d50'
  ctx.lineWidth   = 1
  ctx.moveTo(PAD_LEFT, PAD_TOP)
  ctx.lineTo(PAD_LEFT, PAD_TOP + chartH)
  ctx.lineTo(PAD_LEFT + chartW, PAD_TOP + chartH)
  ctx.stroke()

  if (data.length < 2) return

  // ── 渐变填充 + 折线 ───────────────────────────────────────
  const grad = ctx.createLinearGradient(0, PAD_TOP, 0, PAD_TOP + chartH)
  grad.addColorStop(0, 'rgba(124,140,255,0.35)')
  grad.addColorStop(1, 'rgba(124,140,255,0.01)')

  ctx.beginPath()
  ctx.moveTo(toX(0), toY(data[0].speed))
  data.forEach((d, i) => ctx.lineTo(toX(i), toY(d.speed)))
  ctx.lineTo(toX(data.length - 1), PAD_TOP + chartH)
  ctx.lineTo(toX(0),               PAD_TOP + chartH)
  ctx.closePath()
  ctx.fillStyle = grad
  ctx.fill()

  ctx.beginPath()
  ctx.strokeStyle = '#7c8cff'
  ctx.lineWidth   = 2
  ctx.lineJoin    = 'round'
  data.forEach((d, i) => {
    i === 0 ? ctx.moveTo(toX(i), toY(d.speed))
            : ctx.lineTo(toX(i), toY(d.speed))
  })
  ctx.stroke()

  // ── Hover 十字准线 ────────────────────────────────────────
  if (hIdx >= 0 && hIdx < data.length) {
    const hx = toX(hIdx)
    const hy = toY(data[hIdx].speed)

    // 竖线（从 X 轴到顶部）
    ctx.beginPath()
    ctx.strokeStyle = 'rgba(200,200,255,0.35)'
    ctx.lineWidth   = 1
    ctx.setLineDash([4, 3])
    ctx.moveTo(hx, PAD_TOP)
    ctx.lineTo(hx, PAD_TOP + chartH)
    ctx.stroke()

    // 横线（从 Y 轴到右边）
    ctx.beginPath()
    ctx.moveTo(PAD_LEFT, hy)
    ctx.lineTo(PAD_LEFT + chartW, hy)
    ctx.stroke()
    ctx.setLineDash([])

    // X 轴投影点（小三角/刻度高亮）
    ctx.beginPath()
    ctx.fillStyle = '#a0aaff'
    ctx.arc(hx, PAD_TOP + chartH, 3, 0, Math.PI * 2)
    ctx.fill()

    // Y 轴投影点
    ctx.beginPath()
    ctx.arc(PAD_LEFT, hy, 3, 0, Math.PI * 2)
    ctx.fill()

    // 数据点圆圈
    ctx.beginPath()
    ctx.strokeStyle = '#fff'
    ctx.lineWidth   = 1.5
    ctx.fillStyle   = '#7c8cff'
    ctx.arc(hx, hy, 5, 0, Math.PI * 2)
    ctx.fill()
    ctx.stroke()
  }
}

// ── 鼠标交互 ──────────────────────────────────────────────
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

  // 只在绘图区内响应
  if (
    mouseX < PAD_LEFT || mouseX > PAD_LEFT + chartW ||
    mouseY < PAD_TOP  || mouseY > PAD_TOP  + chartH
  ) {
    onMouseLeave()
    return
  }

  // 找最近数据点
  const ratio = (mouseX - PAD_LEFT) / chartW
  const idx   = Math.round(ratio * (data.length - 1))
  const clampedIdx = Math.max(0, Math.min(idx, data.length - 1))

  if (clampedIdx === hoverIdx.value) return
  hoverIdx.value = clampedIdx
  draw(clampedIdx)

  // 更新 tooltip 位置（跟随鼠标，偏移避免遮挡）
  const secsAgo = data.length - 1 - clampedIdx
  tooltip.time    = secsAgo === 0 ? '现在' : `-${secsAgo}s`
  tooltip.speed   = fmtSpeed(data[clampedIdx].speed)
  tooltip.visible = true

  // 气泡位置：鼠标右上方，超出右边界时翻转
  const tipW = 90
  const offX = mouseX + tipW + 16 > el.offsetWidth ? -tipW - 8 : 12
  tooltip.x = mouseX + offX
  tooltip.y = Math.max(PAD_TOP, mouseY - 36)
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
  background: #161822; border-radius: 12px;
  padding: 16px; border: 1px solid #2a2d3e;
}
.chart-header {
  display: flex; justify-content: space-between;
  margin-bottom: 10px; font-size: 13px;
}
.chart-title { color: #7c8cff; font-weight: 600; }
.chart-peak  { color: #555; }
.chart-canvas {
  width: 100%; height: 120px; display: block;
  cursor: crosshair;
}

/* ── Tooltip 气泡 ── */
.tooltip {
  position: absolute;
  pointer-events: none;
  background: #1e2030;
  border: 1px solid #3a3d50;
  border-radius: 6px;
  padding: 5px 10px;
  font-size: 11px;
  line-height: 1.6;
  white-space: nowrap;
  z-index: 10;
  box-shadow: 0 2px 8px rgba(0,0,0,0.4);
}
.tt-time  { color: #888; }
.tt-speed { color: #a0aaff; font-weight: 600; font-size: 12px; }
</style>