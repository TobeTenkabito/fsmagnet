<template>
  <div class="task-list">
    <div class="list-header">
      <span class="list-title">下载任务</span>
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

const ORDER = { downloading: 0, metadata: 1, checking: 2, paused: 3, seeding: 4, error: 5 }

const sortedTasks = computed(() =>
  [...(props.tasks ?? [])].sort((a, b) =>
    (ORDER[a.state] ?? 9) - (ORDER[b.state] ?? 9)
  )
)

const downloadingCount = computed(() =>
  (props.tasks ?? []).filter(t => t.state === 'downloading').length
)
const seedingCount = computed(() =>
  (props.tasks ?? []).filter(t => t.state === 'seeding').length
)
</script>

<style scoped>
.task-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* 列表头部 */
.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 2px;
}
.list-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-main);
}
.list-counts {
  display: flex;
  gap: 8px;
  align-items: center;
}
.list-count {
  font-size: 12px;
  color: var(--text-muted);
}

/* 数量徽章 */
.count-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 20px;
}
.count-dl {
  background: var(--count-dl-bg);
  color: var(--count-dl-color);
}
.count-seed {
  background: var(--count-seed-bg);
  color: var(--count-seed-color);
}

/* 空状态 */
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  gap: 8px;
  background: var(--bg-card);
  border-radius: 12px;
  border: 1px dashed var(--border-light);
}
.empty-icon { font-size: 40px; }
.empty-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-sub);
}
.empty-sub {
  font-size: 13px;
  color: var(--text-muted);
}

/* 卡片容器 */
.cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* 列表动画 */
.task-enter-active {
  transition: all 0.3s ease;
}
.task-leave-active {
  transition: all 0.25s ease;
}
.task-enter-from {
  opacity: 0;
  transform: translateY(-10px);
}
.task-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
.task-move {
  transition: transform 0.3s ease;
}
</style>