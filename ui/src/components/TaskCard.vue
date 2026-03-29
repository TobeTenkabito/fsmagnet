<template>
  <div class="task-card" :class="[stateClass, { 'is-seeding': isSeeding }]">
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
      <div class="task-actions">
        <button v-if="task.state === 'downloading'" @click="$emit('pause', task.id)" class="btn-ctrl" title="暂停下载">⏸</button>
        <button v-if="task.state === 'paused'"      @click="$emit('resume', task.id)" class="btn-ctrl" title="恢复">▶</button>
        <button v-if="isSeeding"                    @click="$emit('stop-seed', task.id)" class="btn-ctrl btn-seed-pause" title="停止做种（保留文件）">⏹</button>
        <div class="remove-wrap">
          <button @click.stop="toggleMenu" class="btn-ctrl btn-del" title="删除">✕</button>
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

    <div class="progress-wrap">
      <div class="progress-bar" :class="{ 'progress-seeding': isSeeding }" :style="{ width: task.progress + '%' }"></div>
    </div>

    <div v-if="!isSeeding" class="task-footer">
      <span class="speed-down">↓ {{ formatSpeed(task.download_speed) }}</span>
      <span class="speed-up">↑ {{ formatSpeed(task.upload_speed) }}</span>
      <span class="progress-pct">{{ task.progress.toFixed(1) }}%</span>
      <span class="eta">ETA {{ formatEta(task.eta) }}</span>
    </div>

    <div v-else class="task-footer">
      <span class="speed-up">↑ {{ formatSpeed(task.upload_speed) }}</span>
      <span class="seed-uploaded">累计上传 {{ formatSize(task.total_uploaded ?? 0) }}</span>
      <span class="seed-ratio" :class="ratioClass">分享率 {{ formatRatio(task.ratio) }}</span>
      <span class="seed-time">做种 {{ formatSeedTime(task.seeding_time) }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({ task: Object })
const emit = defineEmits(['pause', 'resume', 'remove', 'stop-seed'])

const stateMap = {
  downloading: { label: '下载中',    cls: 'state-dl'    },
  paused:      { label: '已暂停',    cls: 'state-pause'  },
  seeding:     { label: '做种中',    cls: 'state-seed'   },
  checking:    { label: '校验中',    cls: 'state-check'  },
  metadata:    { label: '获取元数据', cls: 'state-meta'  },
  error:       { label: '错误',      cls: 'state-err'    },
}

const stateLabel = computed(() => stateMap[props.task.state]?.label ?? props.task.state)
const stateClass = computed(() => stateMap[props.task.state]?.cls ?? '')
const isSeeding  = computed(() => props.task.state === 'seeding')

const fileIcon = computed(() => {
  const name = props.task.name?.toLowerCase() ?? ''
  if (/\.(mp4|mkv|avi|mov)$/.test(name)) return '🎬'
  if (/\.(mp3|flac|aac)$/.test(name))    return '🎵'
  if (/\.(zip|rar|7z)$/.test(name))      return '📦'
  if (/\.(pdf|doc|txt)$/.test(name))     return '📄'
  return '📁'
})

const ratioClass = computed(() => {
  const r = props.task.ratio ?? 0
  if (r >= 2.0) return 'ratio-high'
  if (r >= 1.0) return 'ratio-mid'
  return 'ratio-low'
})

const menuOpen = ref(false)
function toggleMenu() { menuOpen.value = !menuOpen.value }
function doRemove(intent) { menuOpen.value = false; emit('remove', { id: props.task.id, intent }) }
function onClickOutside() { menuOpen.value = false }
onMounted(() => document.addEventListener('click', onClickOutside))
onUnmounted(() => document.removeEventListener('click', onClickOutside))

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
function formatRatio(ratio = 0) { return (ratio ?? 0).toFixed(2) }
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
  background: var(--bg-card);
  border-radius: 12px;
  padding: 16px;
  border: 1px solid var(--border);
  transition: border-color 0.2s, background 0.3s;
  position: relative;
}
.task-card:hover { border-color: var(--border-light); }
.task-card.is-seeding { border-color: var(--card-seeding-border); }
.task-card.is-seeding:hover { border-color: var(--card-seeding-border-hover); }

.task-header { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.task-icon   { font-size: 28px; flex-shrink: 0; }
.task-info   { flex: 1; min-width: 0; }
.task-name {
  font-size: 14px; font-weight: 600; color: var(--text-main);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  margin-bottom: 6px;
}
.task-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.meta-item { font-size: 12px; color: var(--text-muted); }

/* 状态标签 */
.tag { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
.state-dl    { background: var(--tag-dl-bg);    color: var(--tag-dl-color); }
.state-pause { background: var(--tag-pause-bg); color: var(--tag-pause-color); }
.state-seed  { background: var(--tag-seed-bg);  color: var(--tag-seed-color); }
.state-check { background: var(--tag-check-bg); color: var(--tag-check-color); }
.state-meta  { background: var(--tag-meta-bg);  color: var(--tag-meta-color); }
.state-err   { background: var(--tag-err-bg);   color: var(--tag-err-color); }

/* 操作按钮 */
.task-actions { display: flex; gap: 6px; flex-shrink: 0; }
.btn-ctrl {
  background: var(--btn-ctrl-bg); border: none; color: var(--btn-ctrl-color);
  border-radius: 6px; width: 32px; height: 32px;
  font-size: 14px; cursor: pointer; transition: all 0.2s;
}
.btn-ctrl:hover       { background: var(--bg-hover2); color: var(--text-main); }
.btn-seed-pause:hover { background: var(--card-seeding-border); color: var(--tag-seed-color); }
.btn-del:hover        { background: var(--tag-err-bg); color: var(--tag-err-color); }

/* 删除意图菜单 */
.remove-wrap { position: relative; }
.intent-menu {
  position: absolute; right: 0; top: 38px; z-index: 100;
  background: var(--intent-menu-bg); border: 1px solid var(--border);
  border-radius: 10px; padding: 8px; width: 200px;
  box-shadow: var(--shadow-modal);
}
.intent-title {
  font-size: 11px; color: var(--text-muted); padding: 2px 6px 8px;
  border-bottom: 1px solid var(--border); margin-bottom: 6px;
}
.intent-item {
  display: flex; align-items: center; gap: 10px;
  width: 100%; background: none; border: none;
  color: var(--text-main); padding: 8px; border-radius: 6px;
  cursor: pointer; text-align: left; transition: background 0.15s;
}
.intent-item:hover              { background: var(--bg-hover2); }
.intent-item.intent-danger      { color: var(--intent-danger-color); }
.intent-item.intent-danger:hover{ background: var(--intent-danger-hover); }
.intent-icon  { font-size: 16px; flex-shrink: 0; }
.intent-label { font-size: 13px; font-weight: 600; }
.intent-sub   { font-size: 11px; color: var(--text-muted); margin-top: 1px; }

.menu-enter-active, .menu-leave-active { transition: all 0.15s ease; }
.menu-enter-from, .menu-leave-to { opacity: 0; transform: translateY(-6px) scale(0.97); }

/* 进度条 */
.progress-wrap {
  height: 4px; background: var(--progress-bg);
  border-radius: 2px; margin-bottom: 10px; overflow: hidden;
}
.progress-bar {
  height: 100%;
  background: var(--progress-dl);
  border-radius: 2px; transition: width 0.5s ease;
}
.progress-bar.progress-seeding {
  background: var(--progress-seed);
  width: 100% !important;
}

/* Footer */
.task-footer { display: flex; gap: 16px; font-size: 12px; align-items: center; }
.speed-down   { color: var(--tag-seed-color); }
.speed-up     { color: var(--tag-dl-color); }
.progress-pct { color: var(--accent); margin-left: auto; }
.eta          { color: var(--text-muted); }

.seed-uploaded { color: var(--text-sub); }
.seed-time     { color: var(--text-muted); margin-left: auto; }
.seed-ratio    { font-weight: 600; }
.ratio-low  { color: var(--ratio-low); }
.ratio-mid  { color: var(--ratio-mid); }
.ratio-high { color: var(--ratio-high); }
</style>