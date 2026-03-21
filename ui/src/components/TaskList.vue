<template>
  <div class="task-list">
    <div class="list-header">
      <span class="list-title">下载任务</span>
      <span class="list-count">{{ tasks.length }} 个任务</span>
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
        v-for="task in tasks"
        :key="task.id"
        :task="task"
        @pause="$emit('pause', $event)"
        @resume="$emit('resume', $event)"
        @remove="$emit('remove', $event)"
      />
    </TransitionGroup>
  </div>
</template>

<script setup>
import TaskCard from './TaskCard.vue'
defineProps({ tasks: Array })
defineEmits(['pause', 'resume', 'remove'])
</script>

<style scoped>
.task-list { display: flex; flex-direction: column; gap: 12px; }
.list-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0 4px;
}
.list-title { font-size: 15px; font-weight: 600; color: #e2e8f0; }
.list-count  { font-size: 12px; color: #555; }

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