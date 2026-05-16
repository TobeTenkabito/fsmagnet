<template>
  <div class="overlay" @click.self="$emit('close')">
    <div class="modal" style="width:560px">
      <div class="modal-header">
        <span>{{ mode === 'create' ? '制作 Torrent' : '添加下载任务' }}</span>
        <button class="btn-close" @click="$emit('close')">✕</button>
      </div>

      <div class="tab-bar">
        <button :class="['tab', { active: mode === 'magnet' }]" @click="mode = 'magnet'">🔗 磁力链接</button>
        <button :class="['tab', { active: mode === 'torrent' }]" @click="mode = 'torrent'">📄 Torrent 文件</button>
        <button :class="['tab', { active: mode === 'create' }]" @click="mode = 'create'">🧩 制作 Torrent</button>
      </div>

      <div class="modal-body">
        <template v-if="mode === 'magnet'">
          <label class="field-label">磁力链接</label>
          <textarea v-model="magnet" class="input-magnet" placeholder="magnet:?xt=urn:btih:..." rows="4" autofocus />
        </template>
        <template v-else-if="mode === 'torrent'">
          <label class="field-label">Torrent 文件</label>
          <div class="torrent-row">
            <input class="input-path" :value="torrentPath || ''" placeholder="点击右侧按钮选择 .torrent 文件" readonly />
            <button class="btn-browse" @click="pickTorrent" :disabled="picking">{{ picking ? '...' : '浏览' }}</button>
          </div>
        </template>
        <template v-else>
          <label class="field-label">源文件夹</label>
          <div class="torrent-row">
            <input class="input-path" :value="sourceFolder || ''" placeholder="选择要制作成 Torrent 的文件夹" readonly />
            <button class="btn-browse" @click="pickSourceFolder" :disabled="picking">{{ picking ? '...' : '浏览' }}</button>
          </div>

          <label class="field-label">输出目录</label>
          <div class="torrent-row">
            <input v-model="torrentOutputDir" class="input-path" type="text" placeholder="留空则保存到源文件夹同级目录" />
            <button class="btn-browse" @click="pickOutputFolder" :disabled="picking">{{ picking ? '...' : '浏览' }}</button>
          </div>
        </template>

        <template v-if="mode !== 'create'">
          <label class="field-label">保存路径</label>
          <div class="torrent-row">
            <input v-model="savePath" class="input-path" type="text" placeholder="选择或输入保存目录" />
            <button class="btn-browse" @click="pickFolder" :disabled="picking">{{ picking ? '...' : '浏览' }}</button>
          </div>
        </template>

        <div v-if="error" class="error-msg">{{ error }}</div>
        <div v-if="mode === 'create' && createdPath" class="success-msg">已生成：{{ createdPath }}</div>
      </div>

      <div class="modal-footer">
        <button class="btn-cancel" @click="$emit('close')">取消</button>
        <button class="btn-confirm" :disabled="loading" @click="submit">{{ submitLabel }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { downloadApi, systemApi } from '../api/index.js'

const emit = defineEmits(['close', 'added'])

const mode        = ref('magnet')
const magnet      = ref('')
const torrentPath = ref('')
const savePath    = ref('./downloads')
const sourceFolder = ref('')
const torrentOutputDir = ref('')
const createdPath = ref('')
const loading     = ref(false)
const picking     = ref(false)
const error       = ref('')

const submitLabel = computed(() => {
  if (loading.value) return mode.value === 'create' ? '制作中...' : '添加中...'
  return mode.value === 'create' ? '制作 Torrent' : '开始下载'
})

async function pickTorrent() {
  picking.value = true
  try {
    const res = await systemApi.pickTorrent()
    if (res.ok && res.path) torrentPath.value = res.path
  } catch (e) { error.value = '文件选择失败：' + e.message }
  finally { picking.value = false }
}

async function pickFolder() {
  picking.value = true
  try {
    const res = await systemApi.pickFolder()
    if (res.ok && res.path) savePath.value = res.path
  } catch (e) { error.value = '路径选择失败：' + e.message }
  finally { picking.value = false }
}

async function pickSourceFolder() {
  picking.value = true
  try {
    const res = await systemApi.pickFolder()
    if (res.ok && res.path) sourceFolder.value = res.path
  } catch (e) { error.value = '路径选择失败：' + e.message }
  finally { picking.value = false }
}

async function pickOutputFolder() {
  picking.value = true
  try {
    const res = await systemApi.pickFolder()
    if (res.ok && res.path) torrentOutputDir.value = res.path
  } catch (e) { error.value = '路径选择失败：' + e.message }
  finally { picking.value = false }
}

async function submit() {
  error.value = ''
  createdPath.value = ''
  if (mode.value === 'magnet') {
    if (!magnet.value.trim().startsWith('magnet:')) { error.value = '请输入有效的磁力链接（以 magnet: 开头）'; return }
    loading.value = true
    try { await downloadApi.add(magnet.value.trim(), savePath.value.trim()); emit('added'); emit('close') }
    catch (e) { error.value = '添加失败：' + (e.response?.data?.detail ?? e.message) }
    finally { loading.value = false }
  } else if (mode.value === 'torrent') {
    if (!torrentPath.value) { error.value = '请先选择 .torrent 文件'; return }
    loading.value = true
    try { await downloadApi.addTorrent(torrentPath.value, savePath.value.trim()); emit('added'); emit('close') }
    catch (e) { error.value = '添加失败：' + (e.response?.data?.detail ?? e.message) }
    finally { loading.value = false }
  } else {
    if (!sourceFolder.value) { error.value = '请先选择源文件夹'; return }
    loading.value = true
    try {
      const res = await downloadApi.createTorrent(sourceFolder.value, torrentOutputDir.value.trim())
      createdPath.value = res.output_path
    } catch (e) { error.value = '制作失败：' + (e.response?.data?.detail ?? e.message) }
    finally { loading.value = false }
  }
}
</script>

<style scoped>
/* 标签页 */
.tab-bar { display: flex; border-bottom: 1px solid var(--border); }
.tab {
  flex: 1; padding: 10px; background: none; border: none;
  color: var(--text-muted); font-size: 13px; cursor: pointer;
  transition: color 0.2s, border-bottom 0.2s;
  border-bottom: 2px solid transparent;
}
.tab:hover { color: var(--text-sub); }
.tab.active { color: var(--tab-active); border-bottom: 2px solid var(--tab-active); }

.field-label { font-size: 12px; color: var(--accent); font-weight: 600; }

.input-magnet, .input-path {
  background: var(--bg-input); border: 1px solid var(--border);
  border-radius: 8px; color: var(--text-main); padding: 10px 12px;
  font-size: 13px; width: 100%; resize: none; outline: none;
  font-family: monospace; transition: border-color 0.2s;
  box-sizing: border-box;
}
.input-magnet:focus, .input-path:focus { border-color: var(--accent); }

.torrent-row { display: flex; gap: 8px; align-items: center; }
.torrent-row .input-path { flex: 1; }

.btn-browse {
  background: var(--btn-browse-bg); border: 1px solid var(--border);
  color: var(--text-sub); border-radius: 8px;
  padding: 9px 14px; cursor: pointer; white-space: nowrap;
  font-size: 13px; transition: color 0.2s, border-color 0.2s;
}
.btn-browse:hover:not(:disabled) { color: var(--text-main); border-color: var(--accent); }
.btn-browse:disabled { opacity: 0.4; cursor: not-allowed; }

.error-msg {
  background: var(--error-bg); color: var(--error-color);
  border-radius: 6px; padding: 8px 12px; font-size: 13px;
}

.success-msg {
  background: rgba(16, 185, 129, 0.12); color: #10b981;
  border-radius: 6px; padding: 8px 12px; font-size: 13px;
  word-break: break-all;
}
</style>
