<template>
  <div class="task-card" :class="stateClass">
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
        <button v-if="task.state === 'downloading'" @click="$emit('pause', task.id)" class="btn-ctrl">⏸</button>
        <button v-if="task.state === 'paused'" @click="$emit('resume', task.id)" class="btn-ctrl">▶</button>
        <button @click="confirmRemove" class="btn-ctrl btn-del">✕</button>
      </div>
    </div>

    <!-- 进度条 -->
    <div class="progress-wrap">
      <div class="progress-bar" :style="{ width: task.progress + '%' }"></div>
    </div>

    <!-- 底部统计 -->
    <div class="task-footer">
      <span class="speed-down">↓ {{ formatSpeed(task.download_speed) }}</span>
      <span class="speed-up">↑ {{ formatSpeed(task.upload_speed) }}</span>
      <span class="progress-pct">{{ task.progress.toFixed(1) }}%</span>
      <span class="eta">ETA {{ formatEta(task.eta) }}</span>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({ task: Object })
const emit = defineEmits(['pause', 'resume', 'remove'])

const stateMap = {
  downloading: { label: '下载中', cls: 'state-dl' },
  paused:      { label: '已暂停', cls: 'state-pause' },
  seeding:     { label: '做种中', cls: 'state-seed' },
  checking:    { label: '校验中', cls: 'state-check' },
  metadata:    { label: '获取元数据', cls: 'state-meta' },
  error:       { label: '错误',   cls: 'state-err' },
}

const stateLabel = computed(() => stateMap[props.task.state]?.label ?? props.task.state)
const stateClass = computed(() => stateMap[props.task.state]?.cls ?? '')

const fileIcon = computed(() => {
  const name = props.task.name?.toLowerCase() ?? ''
  if (/\.(mp4|mkv|avi|mov)$/.test(name)) return '🎬'
  if (/\.(mp3|flac|aac)$/.test(name)) return '🎵'
  if (/\.(zip|rar|7z)$/.test(name)) return '📦'
  if (/\.(pdf|doc|txt)$/.test(name)) return '📄'
  return '📁'
})

function confirmRemove() {
  if (confirm(`确定删除任务 "${props.task.name}"？`)) {
    emit('remove', props.task.id)
  }
}

function formatSpeed(bps = 0) {
  if (bps < 1024) return `${bps} B/s`
  if (bps < 1048576) return `${(bps / 1024).toFixed(1)} KB/s`
  return `${(bps / 1048576).toFixed(2)} MB/s`
}

function formatSize(bytes = 0) {
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1073741824) return `${(bytes / 1048576).toFixed(1)} MB`
  return `${(bytes / 1073741824).toFixed(2)} GB`
}

function formatEta(sec = 0) {
  if (!sec || sec < 0) return '--'
  if (sec < 60) return `${sec}s`
  if (sec < 3600) return `${Math.floor(sec / 60)}m ${sec % 60}s`
  return `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`
}

import { computed } from 'vue'
</script>

<style scoped>
.task-card {
  background: #161822; border-radius: 12px;
  padding: 16px; border: 1px solid #2a2d3e;
  transition: border-color 0.2s;
}
.task-card:hover { border-color: #3a3f5e; }

.task-header { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.task-icon { font-size: 28px; flex-shrink: 0; }
.task-info { flex: 1; min-width: 0; }
.task-name {
  font-size: 14px; font-weight: 600; color: #e2e8f0;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  margin-bottom: 6px;
}
.task-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.meta-item { font-size: 12px; color: #555; }

.tag {
  font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 600;
}
.state-dl    { background: #1a2f4a; color: #60a5fa; }
.state-pause { background: #2a2520; color: #f59e0b; }
.state-seed  { background: #1a2f1a; color: #4ade80; }
.state-check { background: #2a1f2a; color: #c084fc; }
.state-meta  { background: #1e2130; color: #94a3b8; }
.state-err   { background: #2f1a1a; color: #f87171; }

.task-actions { display: flex; gap: 6px; flex-shrink: 0; }
.btn-ctrl {
  background: #1e2130; border: none; color: #aaa;
  border-radius: 6px; width: 32px; height: 32px;
  font-size: 14px; cursor: pointer; transition: all 0.2s;
}
.btn-ctrl:hover { background: #2a2d3e; color: #fff; }
.btn-del:hover  { background: #3f1f1f; color: #f87171; }

.progress-wrap {
  height: 4px; background: #1e2130; border-radius: 2px; margin-bottom: 10px; overflow: hidden;
}
.progress-bar {
  height: 100%; background: linear-gradient(90deg, #7c8cff, #4ade80);
  border-radius: 2px; transition: width 0.5s ease;
}

.task-footer { display: flex; gap: 16px; font-size: 12px; }
.speed-down { color: #4ade80; }
.speed-up   { color: #60a5fa; }
.progress-pct { color: #7c8cff; margin-left: auto; }
.eta { color: #555; }
</style>