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
          <span class="speed-label dl">↓</span>
          <span class="speed-val">{{ formatSpeed(globalSpeed) }}</span>
        </div>
        <div class="global-speed">
          <span class="speed-label ul">↑</span>
          <span class="speed-val ul-val">{{ formatSpeed(globalUpload) }}</span>
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
        @stop-seed="handleStopSeed"
      />
    </main>

    <AddMagnet     v-if="showAdd"      @close="showAdd = false"      @added="handleAdded" />
    <SettingsPanel v-if="showSettings" @close="showSettings = false" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { downloadApi, subscribeStats } from './api/index.js'
import SpeedChart    from './components/SpeedChart.vue'
import TaskList      from './components/TaskList.vue'
import AddMagnet     from './components/AddMagnet.vue'
import SettingsPanel from './components/SettingsPanel.vue'

const tasks        = ref([])
const globalSpeed  = ref(0)
const globalUpload = ref(0)
const speedHistory = ref([])
const showAdd      = ref(false)
const showSettings = ref(false)

let sse       = null
let pollTimer = null
let sseOk     = false

// ── 统一数据处理 ───────────────────────────────────────────
function applyStats(data) {
  if (data.tasks        != null) tasks.value       = data.tasks
  if (data.global_speed != null) globalSpeed.value = data.global_speed
  if (data.global_ul    != null) globalUpload.value = data.global_ul

  speedHistory.value.push({
    time:     new Date().toLocaleTimeString(),
    download: Math.round((data.global_speed ?? 0) / 1024),
    upload:   Math.round((data.global_ul   ?? 0) / 1024),
  })
  if (speedHistory.value.length > 60) speedHistory.value.shift()
}

// ── 降级轮询 ───────────────────────────────────────────────
async function poll() {
  try {
    const data = await downloadApi.list()
    applyStats({
      tasks:        data.tasks        ?? [],
      global_speed: data.global_speed ?? 0,
      global_ul:    data.global_ul    ?? 0,
    })
  } catch (_) {}
}

// ── 生命周期 ───────────────────────────────────────────────
onMounted(() => {
  sse = subscribeStats((data) => {
    sseOk = true
    applyStats(data)
  })
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

// ── 工具函数 ───────────────────────────────────────────────
function formatSpeed(bps) {
  if (bps < 1024)        return `${bps} B/s`
  if (bps < 1024 * 1024) return `${(bps / 1024).toFixed(1)} KB/s`
  return `${(bps / 1024 / 1024).toFixed(2)} MB/s`
}

// ── 事件处理 ───────────────────────────────────────────────
async function handleAdded()    { showAdd.value = false }
async function handlePause(id)  { await downloadApi.pause(id) }
async function handleResume(id) { await downloadApi.resume(id) }

async function handleRemove({ id, intent }) {
  try   { await downloadApi.remove(id, intent) }
  catch (e) { console.error('[handleRemove]', e) }
}

async function handleStopSeed(id) {
  try   { await downloadApi.stopSeed(id) }
  catch (e) { console.error('[handleStopSeed]', e) }
}
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
  display: flex; align-items: center; gap: 4px;
}
.speed-label    { opacity: 0.7; font-size: 13px; }
.speed-label.ul { color: #fb923c; }
.speed-label.dl { color: #4ade80; }
.ul-val         { color: #fb923c; }

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