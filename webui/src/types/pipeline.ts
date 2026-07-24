/**
 * Pipeline 相关类型定义
 */

// 字面量联合类型，与后端 FormData 字段对齐
export type Mode = 'auto' | 'semi' | 'step'
export type Dimensions = 'basic' | 'all' | 'positive,negative'
export type Formats = 'excel' | 'xmind' | 'excel,xmind'

export type TaskStatus =
  | 'pending'
  | 'running'
  | 'paused'
  | 'done'
  | 'error'
  | 'cancelled'
  | 'interrupted'

export interface TaskListItem {
  pipeline_id: string
  status: TaskStatus
  completed_steps: number
  total_steps: number
  started_at: string
  requirements: string
  mode: string
}

// 后端 _build_steps_view() 只返回 done/running/pending，不返回 paused。
// 暂停状态体现在 pipeline 级别 status='paused'，步骤级需前端推断。
export type StepStatus = 'done' | 'running' | 'pending' | 'paused'

export interface StepProgress {
  id: number
  name: string
  status: StepStatus
  detail: string
}

export interface LogEntry {
  time: string
  level: string
  msg: string
}

export interface PipelineProgress {
  pipeline_id: string
  percent: number
  status: TaskStatus
  mode: string
  completed_steps: number[]
  current_step: number
  steps: StepProgress[]
  logs: LogEntry[]
  kb_ingest?: { cases: number; pitfalls: number }
  llm_stats?: Record<string, any>
  error?: string | null
  started_at: string
}

export interface Artifact {
  name: string
  display_name: string
  size: number
  type: string
}

// 预览接口返回类型判别
export type PreviewResult =
  | { type: 'markdown'; html: string }
  | { type: 'excel'; rows: string[][] }

// 任务列表响应
export interface TaskListResponse {
  items: TaskListItem[]
  pipelines: TaskListItem[] // 向后兼容
  total: number
  page: number
  page_size: number
  pages: number
  keyword: string
  status: string
  all_stats: {
    total: number
    running: number
    done: number
    other: number
  }
}

// 启动流水线响应
export interface StartPipelineResponse {
  pipeline_id: string
  redirect: string
  status: string
}
