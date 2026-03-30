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
import { ref, onMounted, provide,onUnmounted } from 'vue'
import { downloadApi, subscribeStats, settingsApi } from './api/index.js'
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

// ── 主题初始化（App 启动时执行）────────────────────────
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem('app-theme', theme)
}

async function initTheme() {
  let theme = 'dark'
  try {
    const res = await settingsApi.get()
    const cfg = res?.settings ?? res        // ← 注意层级
    if (cfg?.theme) theme = cfg.theme
  } catch {
    theme = localStorage.getItem('app-theme') || 'dark'
  }
  applyTheme(theme)
}

// 暴露给子组件使用
provide('applyTheme', applyTheme)

onMounted(() => {
  initTheme()
})

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
    const data = await downloadApi.getStats()
    applyStats(data)
  } catch (e) {
    console.warn('poll error', e)
  }
}

// ── SSE 连接 ───────────────────────────────────────────────
function connectSSE() {
  sse = subscribeStats((data) => {
    sseOk = true
    applyStats(data)
  })
  sse.onerror = () => {
    sseOk = false
  }
}

// ── 任务操作 ───────────────────────────────────────────────
async function handlePause(id)    { await downloadApi.pause(id);    await poll() }
async function handleResume(id)   { await downloadApi.resume(id);   await poll() }
async function handleStopSeed(id) { await downloadApi.stopSeed(id); await poll() }
async function handleRemove({ id, intent }) {
  await downloadApi.remove(id, intent)
  await poll()
}
async function handleAdded() {
  showAdd.value = false
  await poll()
  sseOk = false
}

function formatSpeed(bytes) {
  if (!bytes) return '0 KB/s'
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(2) + ' MB/s'
  return (bytes / 1024).toFixed(1) + ' KB/s'
}

onMounted(async () => {
  await initTheme()
  await poll()
  connectSSE()
  pollTimer = setInterval(() => { if (!sseOk) poll() }, 2000)
})

onUnmounted(() => {
  sse?.close?.()
  clearInterval(pollTimer)
})
</script>