/**
 * API 路径常量 — 避免硬编码散落各处
 * 实际前缀 /api/v1（由 useApi.ts 的 BASE 变量添加）
 */

export const API = {
  PIPELINE: {
    START: '/pipeline/start',
    LIST: '/pipeline/list',
    PROGRESS: (id: string) => `/pipeline/${id}/progress`,
    STATUS: (id: string) => `/pipeline/${id}/status`,
    CANCEL: (id: string) => `/pipeline/${id}/cancel`,
    RESUME: (id: string) => `/pipeline/${id}/resume`,
    ARTIFACTS: (id: string) => `/pipeline/${id}/artifacts`,
    ARTIFACT_DOWNLOAD: (id: string, name: string) =>
      `/pipeline/${id}/artifacts/${name}`,
    PREVIEW: (id: string, name: string) => `/pipeline/${id}/preview/${name}`,
    EXPORT_PYTEST: (id: string) => `/pipeline/${id}/export_pytest_project`,
    STREAM: (id: string) => `/pipeline/${id}/stream`,
  },
  KNOWLEDGE: {
    STATUS: '/knowledge/status',
    SEARCH: '/knowledge/search',
    IMPORT: '/knowledge/import',
    ADD: '/knowledge/add',
    UPDATE_CONFIG: '/knowledge/update_config',
    CURRENT_CONFIG: '/knowledge/current_config',
  },
  CONFIG: {
    GET: '/config',
    PUT: '/config',
    /** 单 provider 测试连接（不入库） */
    TEST_PROVIDER: '/config/test_provider',
    /** 切换默认 provider */
    SET_DEFAULT: '/config/set_default',
    /** 列 provider 列表 */
    LIST_PROVIDERS: '/config/providers',
    /** V1：拖拽排序（故障转移顺序）— 入参是按新顺序排列的 name 列表 */
    REORDER_PROVIDERS: '/config/reorder_providers',
    /** V2：批量启用/禁用 — { names: string[], enabled: boolean } */
    BATCH_TOGGLE: '/config/batch_toggle',
    /** V2：批量删除 — { names: string[] }（默认 provider 拒绝，列表不会清空） */
    BATCH_DELETE: '/config/batch_delete',
  },
  /** V4：LLM 用量统计（进程级内存聚合，重启清空） */
  USAGE: {
    LLM: '/usage/llm',
    RESET: '/usage/reset',
  },
  // 健康检查端点：后端挂载在根路径（非 /api/v1），供 k8s/Docker 探针使用。
  // 调用时需在 useApi 传 { absolute: true } 跳过 /api/v1 前缀拼接。
  HEALTH: {
    LIVE: '/health/live',
    READY: '/health/ready',
  },
} as const
