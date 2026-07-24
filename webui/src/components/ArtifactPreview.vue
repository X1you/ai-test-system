<script setup lang="ts">
import type { PreviewResult } from '@/types/pipeline'

const props = defineProps<{
  data: PreviewResult | null
  artifactName: string
  pipelineId: string
}>()
</script>

<template>
  <div class="artifact-content">
    <!-- Markdown 预览 -->
    <div v-if="data?.type === 'markdown'" class="md-preview" v-html="data.html" />

    <!-- Excel 预览 -->
    <div v-else-if="data?.type === 'excel'" class="excel-preview">
      <table class="table-preview">
        <tbody>
          <tr v-for="(row, ri) in data.rows" :key="ri">
            <td v-for="(cell, ci) in row" :key="ci" :class="{ 'header-cell': ri === 0 }">
              {{ cell }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 兜底：不支持预览 -->
    <div v-else class="preview-fallback">
      <p>📋 此格式不支持在线预览</p>
      <a :href="`/api/v1/pipeline/${pipelineId}/artifacts/${artifactName}`" class="btn-secondary" download>
        ⬇ 下载文件
      </a>
    </div>
  </div>
</template>

<style scoped>
.artifact-content {
  flex: 1;
}
.md-preview {
  border: 1px solid var(--border);
  padding: 1rem;
  background: var(--muted);
  line-height: 1.6;
  font-size: 0.82rem;
}
.md-preview :deep(table) {
  border-collapse: collapse;
  width: 100%;
}
.md-preview :deep(th),
.md-preview :deep(td) {
  border: 1px solid var(--border);
  padding: 0.5rem;
}
.excel-preview {
  overflow-x: auto;
}
.table-preview {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}
.table-preview td {
  border: 1px solid var(--border);
  padding: 0.65rem 0.75rem;
  text-align: left;
}
.header-cell {
  background: var(--muted);
  font-weight: 700;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  text-transform: uppercase;
}
.preview-fallback {
  text-align: center;
  padding: 3rem;
  color: var(--muted-fg);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}
.preview-fallback .btn-secondary {
  text-decoration: none;
}
</style>
