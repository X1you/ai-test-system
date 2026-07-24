<script setup lang="ts">
/**
 * ValueProps — 「不是替代是倍增」三卡片网格
 * - 卡片 1：需求漏洞左移拦截
 * - 卡片 2：知识库 RAG 增强
 * - 卡片 3：工程 ROI 看板（核心，标记 emphasis）
 */
interface ValueCard {
  no: string
  title: string
  desc: string
  metric: string
  metricLabel: string
  emphasis?: boolean
}

const cards: ValueCard[] = [
  {
    no: '01',
    title: '需求漏洞左移拦截',
    desc: '红队思维前置扫描需求文档，把缺陷拦截在设计阶段，而非测试阶段。',
    metric: '4h+',
    metricLabel: '平均止损 / 漏洞',
  },
  {
    no: '02',
    title: '知识库 RAG 增强',
    desc: '持续沉淀业务规则与历史坑点，生成的用例自带上下文，越用越准。',
    metric: '持续学习',
    metricLabel: '用例回灌 · 自动迭代',
  },
  {
    no: '03',
    title: '工程 ROI 看板',
    desc: '自动量化节省工时、覆盖率提升、缺陷拦截率，让效能可汇报、可追溯。',
    metric: '可量化',
    metricLabel: '价值可量化 · 汇报有据',
    emphasis: true,
  },
]
</script>

<template>
  <section class="value" id="value">
    <div class="section-inner">
      <header class="section-head" data-reveal>
        <p class="eyebrow">VALUE</p>
        <h2 class="section-title">不是替代，<em>是倍增</em></h2>
        <p class="section-sub">
          Bard 不取代测试工程师，而是把重复劳动交给 AI，让人类聚焦判断。
        </p>
      </header>

      <div class="cards">
        <article
          v-for="(card, i) in cards"
          :key="card.no"
          class="card"
          :class="{ 'card--emphasis': card.emphasis }"
          data-reveal
          :data-reveal-delay="String(i * 90)"
        >
          <div class="card-top">
            <span class="card-no">{{ card.no }}</span>
            <span v-if="card.emphasis" class="card-tag">核心</span>
          </div>

          <h3 class="card-title">{{ card.title }}</h3>
          <p class="card-desc">{{ card.desc }}</p>

          <div class="card-metric">
            <span class="metric-value">{{ card.metric }}</span>
            <span class="metric-label">{{ card.metricLabel }}</span>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

<style scoped>
.value {
  padding: 120px var(--space-3xl);
  background: var(--bg);
}

.section-inner {
  max-width: var(--content-max-width);
  margin: 0 auto;
}

.section-head {
  text-align: center;
  margin-bottom: 80px;
}
.eyebrow {
  font-size: 0.75rem;
  letter-spacing: 0.22em;
  color: var(--muted-fg);
  margin-bottom: var(--space-lg);
}
.section-title {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 700;
  font-size: clamp(2rem, 5vw, 3.2rem);
  line-height: 1.1;
  letter-spacing: -0.02em;
  color: var(--fg);
  margin-bottom: var(--space-lg);
}
.section-title em {
  font-style: italic;
}
.section-sub {
  max-width: 560px;
  margin: 0 auto;
  font-size: 1rem;
  line-height: 1.7;
  color: var(--muted-fg);
}

.cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-lg);
}

.card {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: var(--space-3xl);
  background: var(--bg);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  transition: border-color var(--duration-fast) var(--ease),
    transform var(--duration-fast) var(--ease),
    background-color var(--duration-fast) var(--ease);
}
.card:hover {
  border-color: var(--fg);
  transform: translateY(-2px);
}
.card--emphasis {
  background: var(--fg);
  color: var(--bg);
  border-color: var(--fg);
}
.card--emphasis .card-no,
.card--emphasis .card-desc {
  color: var(--muted-fg);
}
.card--emphasis .card-tag {
  background: var(--bg);
  color: var(--fg);
}
.card--emphasis:hover {
  border-color: var(--fg);
  transform: translateY(-2px);
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-2xl);
}
.card-no {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 700;
  font-size: 1.1rem;
  color: var(--muted-fg);
}
.card-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 var(--space-md);
  font-size: 0.68rem;
  letter-spacing: 0.06em;
  border-radius: var(--radius-full);
  background: var(--accent-dim);
  color: var(--muted-fg);
}

.card-title {
  font-size: 1.3rem;
  font-weight: 600;
  letter-spacing: -0.01em;
  margin-bottom: var(--space-md);
}
.card-desc {
  font-size: 0.92rem;
  line-height: 1.7;
  color: var(--muted-fg);
  flex: 1;
  margin-bottom: var(--space-2xl);
}

.card-metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-top: var(--space-xl);
  border-top: 1px solid var(--border-light);
}
.card--emphasis .card-metric {
  border-top-color: rgba(255, 255, 255, 0.2);
}
.metric-value {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 700;
  font-size: 1.8rem;
  line-height: 1.1;
}
.metric-label {
  font-size: 0.8rem;
  color: var(--muted-fg);
}

@media (max-width: 900px) {
  .cards {
    grid-template-columns: 1fr;
  }
}
</style>
