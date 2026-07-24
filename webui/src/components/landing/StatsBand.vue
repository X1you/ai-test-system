<script setup lang="ts">
/**
 * StatsBand — 数字统计带
 * 使用 useStats composable 提供数据（当前静态，预留动态化）
 * 演示 B 叙事诗风格：大号 Playfair italic 数字 + 小写说明
 */
import { useStats } from '@/composables/useStats'

const { stats } = useStats()

interface StatItem {
  value: string
  label: string
}

const items = (): StatItem[] => [
  { value: stats.value.autoRate, label: '用例生成自动化率' },
  { value: stats.value.savedHours, label: '平均止损工时 / 漏洞' },
  { value: stats.value.steps, label: '步流水线全链路' },
  { value: stats.value.modes, label: '种用例输出格式' },
]
</script>

<template>
  <section class="stats-band" id="stats">
    <div class="band-inner">
      <div class="stats-row">
        <div
          v-for="(item, i) in items()"
          :key="i"
          class="stat"
          data-reveal
          :data-reveal-delay="String(i * 80)"
        >
          <span class="stat-value">{{ item.value }}</span>
          <span class="stat-label">{{ item.label }}</span>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.stats-band {
  padding: 100px var(--space-3xl);
  background: var(--fg);
  color: var(--bg);
}

.band-inner {
  max-width: var(--content-max-width);
  margin: 0 auto;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-3xl);
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: var(--space-sm);
  padding: 0 var(--space-lg);
  position: relative;
}
.stat:not(:last-child)::after {
  content: '';
  position: absolute;
  right: calc(var(--space-3xl) * -0.5);
  top: 20%;
  bottom: 20%;
  width: 1px;
  background: rgba(255, 255, 255, 0.18);
}

.stat-value {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 700;
  font-size: clamp(2.6rem, 6vw, 4rem);
  line-height: 1;
  letter-spacing: -0.02em;
}
.stat-label {
  font-size: 0.85rem;
  letter-spacing: 0.04em;
  color: var(--muted-fg);
  /* 在反色带上 muted-fg 偏灰，改用半透明前景色保证对比度 */
  color: rgba(255, 255, 255, 0.62);
}

@media (max-width: 860px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-3xl) var(--space-lg);
  }
  .stat:not(:last-child)::after {
    display: none;
  }
}
</style>
