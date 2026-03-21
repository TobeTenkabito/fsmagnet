<template>
  <div class="app">
    <header class="topbar">
      <div class="logo">
        <span class="logo-icon">⚡</span>
        <span class="logo-text">FSMagnet</span>
        <span class="logo-sub">极速下载器</span>
      </div>
      <div class="topbar-actions">
        <div class="global-speed">
          <span class="speed-label">↓</span>
          <span class="speed-val">{{ formatSpeed(globalSpeed) }}</span>
        </div>
        <button class="btn-add" @click="showAdd = true">＋ 添加磁力</button>
        <button class="btn-icon" @click="showSettings = true">⚙</button>
      </div>
    </header>

    <main class="main-content">
      <SpeedChart :history="speedHistory" />
      <TaskList
        :tasks="tasks"
        @pause="handlePause"
        @resume="handleResume"
        @remove="handleRemove"
      />
    </main>

    <AddMagnet     v-if="showAdd"      @close="showAdd = false"      @added="handleAdded" />
    <SettingsPanel v-if="showSettings" @close="showSettings = false" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { downloadApi, statsApi, subscribeStats } from './api/index.js'
import SpeedChart    from './components/SpeedChart.vue'
import TaskList      from './components/TaskList.vue'
import AddMagnet     from './components/AddMagnet.vue'
import SettingsPanel from './components/SettingsPanel.vue'

const tasks        = ref([])
const globalSpeed  = ref(0)
const speedHistory = ref([])
const showAdd      = ref(false)
const showSettings = ref(false)

let sse       = null
let pollTimer = null
let sseOk     = false

// ── 统一数据处理 ─────────────────────────────────────────
function applyStats(data) {
  if (data.tasks        != null) tasks.value       = data.tasks
  if (data.global_speed != null) globalSpeed.value = data.global_speed

  speedHistory.value.push({
    time:  new Date().toLocaleTimeString(),
    speed: Math.round((data.global_speed ?? 0) / 1024),
  })
  if (speedHistory.value.length > 60) speedHistory.value.shift()
}

// ── 降级轮询：同时拉任务列表 + 全局统计 ─────────────────
async function poll() {
  try {
    const [listRes, statsRes] = await Promise.all([
      downloadApi.list(),
      statsApi.get(),
    ])
    const merged = {
      tasks:        listRes.data?.tasks        ?? [],
      global_speed: statsRes.data?.stats?.global_speed ?? 0,
      global_ul:    statsRes.data?.stats?.global_ul    ?? 0,
      dht_nodes:    statsRes.data?.stats?.dht_nodes    ?? 0,
    }
    applyStats(merged)
  } catch (_) {}
}

// ── 生命周期 ─────────────────────────────────────────────
onMounted(() => {
  // 优先 SSE
  sse = subscribeStats((data) => {
    sseOk = true
    applyStats(data)
  })

  // 3 秒内 SSE 没数据 → 启动轮询兜底
  setTimeout(() => {
    if (!sseOk) {
      console.warn('[FSMagnet] SSE 未就绪，降级为轮询模式')
      poll()
      pollTimer = setInterval(poll, 2000)
    }
  }, 3000)
})

onUnmounted(() => {
  sse?.close()
  clearInterval(pollTimer)
})

// ── 工具函数 ─────────────────────────────────────────────
function formatSpeed(bps) {
  if (bps < 1024)         return `${bps} B/s`
  if (bps < 1024 * 1024)  return `${(bps / 1024).toFixed(1)} KB/s`
  return `${(bps / 1024 / 1024).toFixed(2)} MB/s`
}

// ── 事件处理 ─────────────────────────────────────────────
async function handleAdded()    { showAdd.value = false }
async function handlePause(id)  { await downloadApi.pause(id) }
async function handleResume(id) { await downloadApi.resume(id) }
async function handleRemove(id) { await downloadApi.remove(id) }
</script>

<style scoped>
.app { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }

.topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px; height: 56px;
  background: #161822; border-bottom: 1px solid #2a2d3e;
  flex-shrink: 0;
}
.logo { display: flex; align-items: center; gap: 8px; }
.logo-icon { font-size: 22px; }
.logo-text { font-size: 18px; font-weight: 700; color: #7c8cff; }
.logo-sub  { font-size: 12px; color: #555; margin-left: 4px; }

.topbar-actions { display: flex; align-items: center; gap: 12px; }
.global-speed {
  background: #1e2130; border-radius: 8px;
  padding: 4px 12px; font-size: 14px; color: #4ade80;
}
.speed-label { margin-right: 4px; opacity: 0.6; }

.btn-add {
  background: #7c8cff; color: #fff; border: none;
  border-radius: 8px; padding: 6px 16px;
  font-size: 14px; cursor: pointer; transition: background 0.2s;
}
.btn-add:hover { background: #5a6ef0; }

.btn-icon {
  background: #1e2130; border: none; color: #aaa;
  border-radius: 8px; width: 36px; height: 36px;
  font-size: 18px; cursor: pointer; transition: color 0.2s;
}
.btn-icon:hover { color: #fff; }

.main-content {
  flex: 1; overflow-y: auto;
  padding: 20px 24px; display: flex; flex-direction: column; gap: 20px;
}
</style>