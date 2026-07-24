<script setup lang="ts">
import { ref } from 'vue'
import { Search } from 'lucide-vue-next'
import FileDropZone from '@/components/FileDropZone.vue'
import PipelineLaunchModal from '@/components/PipelineLaunchModal.vue'
import TaskList from '@/components/TaskList.vue'
import StagePane from '@/components/StagePane.vue'
import { useToastStore } from '@/composables/useToast'

const toast = useToastStore()
const showModal = ref(false)
const selectedFile = ref<File | null>(null)
// 搜索 loading 态（防重复请求 + 视觉反馈）
const searching = ref(false)

function onFileSelected(file: File) {
  selectedFile.value = file
  showModal.value = true
}
</script>

<template>
  <div class="workbench-view">
    <!-- 顶部任务栏（统一 56px） -->
    <header class="topbar">
      <div class="task-roi-strip">
        <span>AI 测试效能工作台</span>
      </div>
      <div class="search-box" :class="{ 'is-loading': searching }">
        <Search aria-hidden="true" :size="16" />
        <input
          type="text"
          placeholder="搜索任务或 PRD..."
          :aria-busy="searching || undefined"
          aria-label="搜索任务或 PRD"
        />
      </div>
    </header>

    <!-- 拖拽上传区 -->
    <FileDropZone @file-selected="onFileSelected" />

    <!-- 工作内容区：左列表 + 右舞台（移动端纵向堆叠） -->
    <div class="workbench-content">
      <TaskList />
      <StagePane />
    </div>

    <!-- 启动弹窗 -->
    <PipelineLaunchModal v-model="showModal" :file="selectedFile" />
  </div>
</template>

<style scoped>
.workbench-view {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: var(--bg);
}
.topbar {
  height: 56px;
  padding: 0 1.25rem;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  gap: 1rem;
}
.task-roi-strip {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: var(--text-sm);
  color: var(--muted-fg);
  font-weight: var(--weight-semibold);
}
.search-box {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.65rem;
  border: 1px solid var(--border);
  font-size: var(--text-sm);
  color: var(--muted-fg);
  background: var(--muted);
  min-width: 220px;
  min-height: 44px;
  transition: border-color var(--duration-normal);
}
.search-box:focus-within {
  border-color: var(--fg);
  background: var(--bg);
}
.search-box input {
  flex: 1;
  font-size: var(--text-sm);
}
.workbench-content {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

/* 移动端：< 768px 双栏纵向堆叠，允许整区滚动 */
@media (max-width: 767px) {
  .topbar {
    padding: 0 0.75rem 0 3.5rem; /* 左侧留出汉堡按钮空间 */
  }
  .search-box {
    min-width: 0;
    flex: 1;
  }
  .workbench-content {
    flex-direction: column;
    overflow-y: auto;
  }
}
</style>
