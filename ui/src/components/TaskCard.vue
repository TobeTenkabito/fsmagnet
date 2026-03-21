<template>
  <div class="task-card" :class="[stateClass, { 'is-seeding': isSeeding }]">
    <!-- 文件名 + 状态 -->
    <div class="task-header">
      <span class="task-icon">{{ fileIcon }}</span>
      <div class="task-info">
        <div class="task-name" :title="task.name">{{ task.name }}</div>
        <div class="task-meta">
          <span class="tag" :class="stateClass">{{ stateLabel }}</span>
          <span class="meta-item">{{ formatSize(task.total_size) }}</span>
          <span class="meta-item">👥 {{ task.peers }} peers / {{ task.seeds }} seeds</span>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="task-actions">
        <!-- 下载中 → 暂停 -->
        <button
          v-if="task.state === 'downloading'"
          @click="$emit('pause', task.id)"
          class="btn-ctrl"
          title="暂停下载"
        >⏸</button>

        <!-- 暂停中 → 恢复 -->
        <button
          v-if="task.state === 'paused'"
          @click="$emit('resume', task.id)"
          class="btn-ctrl"
          title="恢复"
        >▶</button>

        <!-- 做种中 → 暂停做种 -->
        <button
          v-if="isSeeding"
          @click="$emit('stop-seed', task.id)"
          class="btn-ctrl btn-seed-pause"
          title="停止做种（保留文件）"
        >⏹</button>

        <!-- 删除按钮：点击展开意图菜单 -->
        <div class="remove-wrap">
          <button
            @click.stop="toggleMenu"
            class="btn-ctrl btn-del"
            title="删除"
          >✕</button>
          <!-- 意图菜单 -->
          <Transition name="menu">
            <div v-if="menuOpen" class="intent-menu" @click.stop>
              <div class="intent-title">选择删除方式</div>
              <button class="intent-item" @click="doRemove('remove_task')">
                <span class="intent-icon">🗂</span>
                <div>
                  <div class="intent-label">删除任务</div>
                  <div class="intent-sub">保留已下载文件</div>
                </div>
              </button>
              <button class="intent-item intent-danger" @click="doRemove('delete_all')">
                <span class="intent-icon">🗑</span>
                <div>
                  <div class="intent-label">删除任务和文件</div>
                  <div class="intent-sub">不可恢复</div>
                </div>
              </button>
            </div>
          </Transition>
        </div>
      </div>
    </div>

    <!-- 进度条 -->
    <div class="progress-wrap">
      <div
        class="progress-bar"
        :class="{ 'progress-seeding': isSeeding }"
        :style="{ width: task.progress + '%' }"
      ></div>
    </div>

    <!-- 底部统计：下载中 -->
    <div v-if="!isSeeding" class="task-footer">
      <span class="speed-down">↓ {{ formatSpeed(task.download_speed) }}</span>
      <span class="speed-up">↑ {{ formatSpeed(task.upload_speed) }}</span>
      <span class="progress-pct">{{ task.progress.toFixed(1) }}%</span>
      <span class="eta">ETA {{ formatEta(task.eta) }}</span>
    </div>

    <!-- 底部统计：做种中（替换 ETA，显示 ratio + 上传量） -->
    <div v-else class="task-footer">
      <span class="speed-up">↑ {{ formatSpeed(task.upload_speed) }}</span>
      <span class="seed-uploaded">
        累计上传 {{ formatSize(task.total_uploaded ?? 0) }}
      </span>
      <span class="seed-ratio" :class="ratioClass">
        分享率 {{ formatRatio(task.ratio) }}
      </span>
      <span class="seed-time">
        做种 {{ formatSeedTime(task.seeding_time) }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({ task: Object })
const emit = defineEmits(['pause', 'resume', 'remove', 'stop-seed'])

// ── 状态映射 ──────────────────────────────────────────
const stateMap = {
  downloading: { label: '下载中',   cls: 'state-dl'    },
  paused:      { label: '已暂停',   cls: 'state-pause'  },
  seeding:     { label: '做种中',   cls: 'state-seed'   },
  checking:    { label: '校验中',   cls: 'state-check'  },
  metadata:    { label: '获取元数据', cls: 'state-meta' },
  error:       { label: '错误',     cls: 'state-err'    },
}

const stateLabel = computed(() => stateMap[props.task.state]?.label ?? props.task.state)
const stateClass = computed(() => stateMap[props.task.state]?.cls ?? '')
const isSeeding  = computed(() => props.task.state === 'seeding')

// ── 文件图标 ──────────────────────────────────────────
const fileIcon = computed(() => {
  const name = props.task.name?.toLowerCase() ?? ''
  if (/\.(mp4|mkv|avi|mov)$/.test(name)) return '🎬'
  if (/\.(mp3|flac|aac)$/.test(name))    return '🎵'
  if (/\.(zip|rar|7z)$/.test(name))      return '📦'
  if (/\.(pdf|doc|txt)$/.test(name))     return '📄'
  return '📁'
})

// ── 分享率样式（越高越绿） ────────────────────────────
const ratioClass = computed(() => {
  const r = props.task.ratio ?? 0
  if (r >= 2.0) return 'ratio-high'
  if (r >= 1.0) return 'ratio-mid'
  return 'ratio-low'
})

// ── 删除意图菜单 ──────────────────────────────────────
const menuOpen = ref(false)

function toggleMenu() {
  menuOpen.value = !menuOpen.value
}

function doRemove(intent) {
  menuOpen.value = false
  emit('remove', { id: props.task.id, intent })
}

// 点击外部关闭菜单
function onClickOutside() {
  menuOpen.value = false
}
onMounted(() => document.addEventListener('click', onClickOutside))
onUnmounted(() => document.removeEventListener('click', onClickOutside))

// ── 格式化函数 ────────────────────────────────────────
function formatSpeed(bps = 0) {
  if (bps < 1024)    return `${bps} B/s`
  if (bps < 1048576) return `${(bps / 1024).toFixed(1)} KB/s`
  return `${(bps / 1048576).toFixed(2)} MB/s`
}

function formatSize(bytes = 0) {
  if (bytes < 1048576)    return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1073741824) return `${(bytes / 1048576).toFixed(1)} MB`
  return `${(bytes / 1073741824).toFixed(2)} GB`
}

function formatEta(sec = 0) {
  if (!sec || sec < 0) return '--'
  if (sec < 60)   return `${sec}s`
  if (sec < 3600) return `${Math.floor(sec / 60)}m ${sec % 60}s`
  return `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`
}

function formatRatio(ratio = 0) {
  return (ratio ?? 0).toFixed(2)
}

function formatSeedTime(sec = 0) {
  if (!sec || sec < 60)   return `${sec ?? 0}s`
  if (sec < 3600) return `${Math.floor(sec / 60)}m`
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  return m > 0 ? `${h}h ${m}m` : `${h}h`
}
</script>

<style scoped>
.task-card {
  background: #161822;
  border-radius: 12px;
  padding: 16px;
  border: 1px solid #2a2d3e;
  transition: border-color 0.2s;
  position: relative;
}
.task-card:hover { border-color: #3a3f5e; }

/* 做种中：绿色边框高亮 */
.task-card.is-seeding { border-color: #1a3a1a; }
.task-card.is-seeding:hover { border-color: #2a5a2a; }

/* ── Header ── */
.task-header { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.task-icon   { font-size: 28px; flex-shrink: 0; }
.task-info   { flex: 1; min-width: 0; }
.task-name {
  font-size: 14px; font-weight: 600; color: #e2e8f0;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  margin-bottom: 6px;
}
.task-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.meta-item { font-size: 12px; color: #555; }

/* ── 状态标签 ── */
.tag { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
.state-dl    { background: #1a2f4a; color: #60a5fa; }
.state-pause { background: #2a2520; color: #f59e0b; }
.state-seed  { background: #1a2f1a; color: #4ade80; }
.state-check { background: #2a1f2a; color: #c084fc; }
.state-meta  { background: #1e2130; color: #94a3b8; }
.state-err   { background: #2f1a1a; color: #f87171; }

/* ── 操作按钮 ── */
.task-actions { display: flex; gap: 6px; flex-shrink: 0; }
.btn-ctrl {
  background: #1e2130; border: none; color: #aaa;
  border-radius: 6px; width: 32px; height: 32px;
  font-size: 14px; cursor: pointer; transition: all 0.2s;
}
.btn-ctrl:hover       { background: #2a2d3e; color: #fff; }
.btn-seed-pause:hover { background: #1a2f1a; color: #4ade80; }
.btn-del:hover        { background: #3f1f1f; color: #f87171; }

/* ── 删除意图菜单 ── */
.remove-wrap { position: relative; }
.intent-menu {
  position: absolute; right: 0; top: 38px; z-index: 100;
  background: #1e2130; border: 1px solid #2a2d3e;
  border-radius: 10px; padding: 8px; width: 200px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.5);
}
.intent-title {
  font-size: 11px; color: #555; padding: 2px 6px 8px;
  border-bottom: 1px solid #2a2d3e; margin-bottom: 6px;
}
.intent-item {
  display: flex; align-items: center; gap: 10px;
  width: 100%; background: none; border: none;
  color: #ccc; padding: 8px; border-radius: 6px;
  cursor: pointer; text-align: left; transition: background 0.15s;
}
.intent-item:hover       { background: #2a2d3e; }
.intent-item.intent-danger       { color: #f87171; }
.intent-item.intent-danger:hover { background: #3f1f1f; }
.intent-icon  { font-size: 16px; flex-shrink: 0; }
.intent-label { font-size: 13px; font-weight: 600; }
.intent-sub   { font-size: 11px; color: #555; margin-top: 1px; }

/* 菜单动画 */
.menu-enter-active, .menu-leave-active { transition: all 0.15s ease; }
.menu-enter-from, .menu-leave-to { opacity: 0; transform: translateY(-6px) scale(0.97); }

/* ── 进度条 ── */
.progress-wrap {
  height: 4px; background: #1e2130;
  border-radius: 2px; margin-bottom: 10px; overflow: hidden;
}
.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #7c8cff, #4ade80);
  border-radius: 2px; transition: width 0.5s ease;
}
/* 做种时进度条纯绿 */
.progress-bar.progress-seeding {
  background: #4ade80;
  width: 100% !important;
}

/* ── Footer ── */
.task-footer { display: flex; gap: 16px; font-size: 12px; align-items: center; }
.speed-down    { color: #4ade80; }
.speed-up      { color: #60a5fa; }
.progress-pct  { color: #7c8cff; margin-left: auto; }
.eta           { color: #555; }

/* 做种专属 footer */
.seed-uploaded { color: #94a3b8; }
.seed-time     { color: #555; margin-left: auto; }
.seed-ratio    { font-weight: 600; }
.ratio-low  { color: #f59e0b; }
.ratio-mid  { color: #4ade80; }
.ratio-high { color: #a3e635; }
</style>