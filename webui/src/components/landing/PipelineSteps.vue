<script setup lang="ts">
/**
 * PipelineSteps — 八步流水线展示
 * 演示 B 落地页核心叙事：从需求到价值量化的全链路
 * - hover 高亮步骤号（数字放大 + 反色）
 * - AI 执行 / 人工决策 badge 区分
 */
interface Step {
  no: string
  title: string
  desc: string
  actor: 'ai' | 'human'
}

const steps: Step[] = [
  { no: '01', title: '需求漏洞扫描', desc: '红队思维前置拦截', actor: 'ai' },
  { no: '02', title: '需求智能拆解', desc: '拆分为可测单元', actor: 'ai' },
  { no: '03', title: '知识库 RAG 检索', desc: '自动注入上下文', actor: 'ai' },
  { no: '04', title: '测试点矩阵梳理', desc: '覆盖功能/边界/异常/性能', actor: 'ai' },
  { no: '05', title: 'Excel/XMind 用例生成', desc: '一键输出标准格式', actor: 'ai' },
  { no: '06', title: '人工执行测试', desc: '实际执行测试', actor: 'human' },
  { no: '07', title: 'AI 用例评审', desc: '自动评审质量', actor: 'ai' },
  { no: '08', title: '工程价值量化报告', desc: '自动计算节省工时', actor: 'ai' },
]
</script>

<template>
  <section class="pipeline" id="pipeline">
    <div class="section-inner">
      <header class="section-head" data-reveal>
        <p class="eyebrow">PIPELINE</p>
        <h2 class="section-title">八步流水线，<em>端到端</em></h2>
        <p class="section-sub">
          每一步都为下一步铺路 —— 七步 AI 自动化，一步人工决策。
        </p>
      </header>

      <ol class="steps">
        <li
          v-for="(step, i) in steps"
          :key="step.no"
          class="step"
          :class="{ 'step--human': step.actor === 'human' }"
          data-reveal
          :data-reveal-delay="String(i * 70)"
        >
          <div class="step-no">{{ step.no }}</div>
          <div class="step-body">
            <div class="step-head">
              <h3 class="step-title">{{ step.title }}</h3>
              <span class="step-badge" :class="step.actor === 'human' ? 'badge-human' : 'badge-ai'">
                {{ step.actor === 'human' ? '人工决策' : 'AI 执行' }}
              </span>
            </div>
            <p class="step-desc">{{ step.desc }}</p>
          </div>
          <span v-if="i < steps.length - 1" class="step-arrow" aria-hidden="true">↘</span>
        </li>
      </ol>
    </div>
  </section>
</template>

<style scoped>
.pipeline {
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
  max-width: 520px;
  margin: 0 auto;
  font-size: 1rem;
  line-height: 1.7;
  color: var(--muted-fg);
}

.steps {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0;
  border-top: 1px solid var(--border-light);
  border-left: 1px solid var(--border-light);
}

.step {
  position: relative;
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: var(--space-2xl);
  padding: var(--space-3xl);
  border-right: 1px solid var(--border-light);
  border-bottom: 1px solid var(--border-light);
  background: var(--bg);
  transition: background-color var(--duration-fast) var(--ease);
}
.step:hover {
  background: var(--hover-bg);
}

.step-no {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 700;
  font-size: 2.6rem;
  line-height: 1;
  color: var(--border-light);
  transition: color var(--duration-fast) var(--ease),
    transform var(--duration-fast) var(--ease);
}
.step:hover .step-no {
  color: var(--fg);
  transform: scale(1.08);
}

.step-head {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  flex-wrap: wrap;
  margin-bottom: var(--space-sm);
}
.step-title {
  font-size: 1.15rem;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--fg);
}
.step-desc {
  font-size: 0.92rem;
  color: var(--muted-fg);
  line-height: 1.6;
}

.step-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 var(--space-sm);
  font-size: 0.7rem;
  letter-spacing: 0.04em;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-light);
  color: var(--muted-fg);
}
.badge-ai {
  background: var(--fg);
  color: var(--bg);
  border-color: var(--fg);
}
.badge-human {
  background: transparent;
  color: var(--fg);
  border-color: var(--fg);
  border-style: dashed;
}

.step-arrow {
  position: absolute;
  right: var(--space-lg);
  bottom: var(--space-lg);
  font-size: 0.9rem;
  color: var(--border-light);
  pointer-events: none;
}

.step--human {
  /* 人工决策步骤用轻微底纹区分 */
  background: var(--accent-dim);
}
.step--human:hover {
  background: var(--hover-bg);
}

@media (max-width: 860px) {
  .steps {
    grid-template-columns: 1fr;
  }
  .step {
    padding: var(--space-2xl);
  }
  .step-no {
    font-size: 2rem;
  }
}
</style>
