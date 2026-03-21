<template>
  <div class="task-list">
    <div class="list-header">
      <span class="list-title">下载任务</span>
      <!-- 分开显示下载中 / 做种中数量 -->
      <div class="list-counts">
        <span v-if="downloadingCount > 0" class="count-badge count-dl">
          ↓ {{ downloadingCount }} 下载中
        </span>
        <span v-if="seedingCount > 0" class="count-badge count-seed">
          ↑ {{ seedingCount }} 做种中
        </span>
        <span v-if="downloadingCount === 0 && seedingCount === 0" class="list-count">
          {{ tasks.length }} 个任务
        </span>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="tasks.length === 0" class="empty">
      <div class="empty-icon">📭</div>
      <div class="empty-text">暂无下载任务</div>
      <div class="empty-sub">点击右上角「添加磁力」开始下载</div>
    </div>

    <!-- 任务卡片列表 -->
    <TransitionGroup name="task" tag="div" class="cards">
      <TaskCard
        v-for="task in sortedTasks"
        :key="task.id"
        :task="task"
        @pause="$emit('pause', $event)"
        @resume="$emit('resume', $event)"
        @remove="$emit('remove', $event)"
        @stop-seed="$emit('stop-seed', $event)"
      />
    </TransitionGroup>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import TaskCard from './TaskCard.vue'

const props = defineProps({ tasks: Array })
defineEmits(['pause', 'resume', 'remove', 'stop-seed'])

// 下载中数量
const downloadingCount = computed(() =>
  props.tasks.filter(t => t.state === 'downloading').length
)

// 做种中数量
const seedingCount = computed(() =>
  props.tasks.filter(t => t.state === 'seeding').length
)

// 排序：下载中 → 暂停 → 做种中 → 其他
// 保证做种任务沉到列表底部，不干扰正在下载的任务视线
const ORDER = { downloading: 0, metadata: 1, checking: 2, paused: 3, seeding: 4, error: 5 }
const sortedTasks = computed(() =>
  [...props.tasks].sort((a, b) =>
    (ORDER[a.state] ?? 9) - (ORDER[b.state] ?? 9)
  )
)
</script>

<style scoped>
.task-list { display: flex; flex-direction: column; gap: 12px; }

.list-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0 4px;
}
.list-title { font-size: 15px; font-weight: 600; color: #e2e8f0; }

.list-counts { display: flex; gap: 8px; align-items: center; }
.list-count  { font-size: 12px; color: #555; }

.count-badge {
  font-size: 11px; font-weight: 600;
  padding: 2px 8px; border-radius: 10px;
}
.count-dl   { background: #1a2f4a; color: #60a5fa; }
.count-seed { background: #1a2f1a; color: #4ade80; }

.empty {
  text-align: center; padding: 60px 0;
  color: #444; display: flex; flex-direction: column; align-items: center; gap: 8px;
}
.empty-icon { font-size: 48px; }
.empty-text { font-size: 16px; color: #555; }
.empty-sub  { font-size: 13px; color: #3a3f55; }

.cards { display: flex; flex-direction: column; gap: 12px; }

.task-enter-active, .task-leave-active { transition: all 0.3s ease; }
.task-enter-from { opacity: 0; transform: translateY(-10px); }
.task-leave-to   { opacity: 0; transform: translateX(20px); }
</style>