<template>
  <div class="overlay" @click.self="$emit('close')">
    <div class="modal">
      <div class="modal-header">
        <span>添加下载任务</span>
        <button class="btn-close" @click="$emit('close')">✕</button>
      </div>

      <!-- 标签页切换 -->
      <div class="tab-bar">
        <button :class="['tab', { active: mode === 'magnet' }]" @click="mode = 'magnet'">
          🔗 磁力链接
        </button>
        <button :class="['tab', { active: mode === 'torrent' }]" @click="mode = 'torrent'">
          📄 Torrent 文件
        </button>
      </div>

      <div class="modal-body">

        <!-- 磁力链接模式 -->
        <template v-if="mode === 'magnet'">
          <label class="field-label">磁力链接</label>
          <textarea
            v-model="magnet"
            class="input-magnet"
            placeholder="magnet:?xt=urn:btih:..."
            rows="4"
            autofocus
          />
        </template>

        <!-- Torrent 文件模式 -->
        <template v-else>
          <label class="field-label">Torrent 文件</label>
          <div class="torrent-row">
            <input
              class="input-path"
              :value="torrentPath || ''"
              placeholder="点击右侧按钮选择 .torrent 文件"
              readonly
            />
            <button class="btn-browse" @click="pickTorrent" :disabled="picking">
              {{ picking ? '...' : '浏览' }}
            </button>
          </div>
        </template>

        <!-- 保存路径（两种模式共用） -->
        <label class="field-label">保存路径</label>
        <div class="torrent-row">
          <input
            v-model="savePath"
            class="input-path"
            type="text"
            placeholder="选择或输入保存目录"
          />
          <button class="btn-browse" @click="pickFolder" :disabled="picking">
            {{ picking ? '...' : '浏览' }}
          </button>
        </div>

        <div v-if="error" class="error-msg">{{ error }}</div>
      </div>

      <div class="modal-footer">
        <button class="btn-cancel" @click="$emit('close')">取消</button>
        <button class="btn-confirm" :disabled="loading" @click="submit">
          {{ loading ? '添加中...' : '开始下载' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { downloadApi, systemApi } from '../api/index.js'

const emit = defineEmits(['close', 'added'])

const mode      = ref('magnet')
const magnet    = ref('')
const torrentPath = ref('')
const savePath  = ref('./downloads')
const loading   = ref(false)
const picking   = ref(false)
const error     = ref('')

// 选择 .torrent 文件
async function pickTorrent() {
  picking.value = true
  try {
    const res = await systemApi.pickTorrent()
    if (res.ok && res.path) torrentPath.value = res.path
  } catch (e) {
    error.value = '文件选择失败：' + e.message
  } finally {
    picking.value = false
  }
}

// 选择保存文件夹
async function pickFolder() {
  picking.value = true
  try {
    const res = await systemApi.pickFolder()
    if (res.ok && res.path) savePath.value = res.path
  } catch (e) {
    error.value = '路径选择失败：' + e.message
  } finally {
    picking.value = false
  }
}

async function submit() {
  error.value = ''

  if (mode.value === 'magnet') {
    // ── 磁力链接提交 ──
    if (!magnet.value.trim().startsWith('magnet:')) {
      error.value = '请输入有效的磁力链接（以 magnet: 开头）'
      return
    }
    loading.value = true
    try {
      await downloadApi.add(magnet.value.trim(), savePath.value.trim())
      emit('added')
      emit('close')
    } catch (e) {
      error.value = '添加失败：' + (e.response?.data?.detail ?? e.message)
    } finally {
      loading.value = false
    }

  } else {
    // ── Torrent 文件提交 ──
    if (!torrentPath.value) {
      error.value = '请先选择 .torrent 文件'
      return
    }
    loading.value = true
    try {
      await downloadApi.addTorrent(torrentPath.value, savePath.value.trim())
      emit('added')
      emit('close')
    } catch (e) {
      error.value = '添加失败：' + (e.response?.data?.detail ?? e.message)
    } finally {
      loading.value = false
    }
  }
}
</script>

<style scoped>
.overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.65);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.modal {
  background: #161822; border-radius: 14px;
  border: 1px solid #2a2d3e; width: 520px; max-width: 95vw;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 18px 20px; border-bottom: 1px solid #2a2d3e;
  font-size: 15px; font-weight: 600; color: #e2e8f0;
}
.btn-close {
  background: none; border: none; color: #555;
  font-size: 16px; cursor: pointer; padding: 4px;
}
.btn-close:hover { color: #fff; }

/* 标签页 */
.tab-bar {
  display: flex; border-bottom: 1px solid #2a2d3e;
}
.tab {
  flex: 1; padding: 10px; background: none; border: none;
  color: #666; font-size: 13px; cursor: pointer;
  transition: color 0.2s, border-bottom 0.2s;
  border-bottom: 2px solid transparent;
}
.tab:hover { color: #aaa; }
.tab.active { color: #7c8cff; border-bottom: 2px solid #7c8cff; }

.modal-body { padding: 20px; display: flex; flex-direction: column; gap: 10px; }
.field-label { font-size: 12px; color: #7c8cff; font-weight: 600; }

.input-magnet, .input-path {
  background: #0f1117; border: 1px solid #2a2d3e;
  border-radius: 8px; color: #e2e8f0; padding: 10px 12px;
  font-size: 13px; width: 100%; resize: none; outline: none;
  font-family: monospace; transition: border-color 0.2s;
  box-sizing: border-box;
}
.input-magnet:focus, .input-path:focus { border-color: #7c8cff; }

/* 路径行：输入框 + 浏览按钮 */
.torrent-row {
  display: flex; gap: 8px; align-items: center;
}
.torrent-row .input-path { flex: 1; }

.btn-browse {
  background: #1e2130; border: 1px solid #2a2d3e;
  color: #aaa; border-radius: 8px;
  padding: 9px 14px; cursor: pointer; white-space: nowrap;
  font-size: 13px; transition: color 0.2s, border-color 0.2s;
}
.btn-browse:hover:not(:disabled) { color: #fff; border-color: #7c8cff; }
.btn-browse:disabled { opacity: 0.4; cursor: not-allowed; }

.error-msg {
  background: #2f1a1a; color: #f87171;
  border-radius: 6px; padding: 8px 12px; font-size: 13px;
}

.modal-footer {
  display: flex; justify-content: flex-end; gap: 10px;
  padding: 16px 20px; border-top: 1px solid #2a2d3e;
}
.btn-cancel {
  background: #1e2130; border: none; color: #aaa;
  border-radius: 8px; padding: 8px 20px; cursor: pointer;
}
.btn-cancel:hover { color: #fff; }
.btn-confirm {
  background: #7c8cff; border: none; color: #fff;
  border-radius: 8px; padding: 8px 20px; cursor: pointer;
  font-weight: 600; transition: background 0.2s;
}
.btn-confirm:hover:not(:disabled) { background: #5a6ef0; }
.btn-confirm:disabled { opacity: 0.5; cursor: not-allowed; }
</style>