/**
 * useStats — 落地页数字统计 composable
 *
 * 当前为静态数据，预留未来动态化（如从后端 ROI 接口拉取实际数据）。
 * 字段说明：
 *   - autoRate    自动化率「80%」
 *   - savedHours  平均止损工时「4h+」
 *   - steps       流水线步骤数「8」
 *   - modes       用例输出模式「3」（Excel / XMind / 双格式）
 */
import { ref } from 'vue'

export interface StatsData {
  autoRate: string
  savedHours: string
  steps: string
  modes: string
}

export function useStats() {
  // 静态数据 —— 后续可替换为 ref + onMounted 异步拉取
  const stats = ref<StatsData>({
    autoRate: '80%',
    savedHours: '4h+',
    steps: '8',
    modes: '3',
  })

  /**
   * 预留：从后端动态加载统计数据
   * async function loadStats() { stats.value = await fetchStats() }
   */
  function setStats(data: Partial<StatsData>) {
    stats.value = { ...stats.value, ...data }
  }

  return {
    stats,
    setStats,
  }
}
