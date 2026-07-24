<script setup lang="ts">
/**
 * HeroSection — 落地页主视觉
 * - Playfair Display italic 大标题「把重复的80%交给Bard」
 * - 副标题：一句话价值描述
 * - 主 CTA「开始使用 →」跳转 /workbench（router.push）
 * - 次级锚点 CTA「了解流水线」
 */
import { useRouter } from 'vue-router'

const router = useRouter()

const goWorkbench = () => {
  router.push('/workbench')
}

const scrollToPipeline = () => {
  const el = document.getElementById('pipeline')
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>

<template>
  <section class="hero" id="top">
    <div class="hero-inner">
      <p class="hero-eyebrow" data-reveal>
        <span class="dot" aria-hidden="true"></span>
        AI 测试效能倍增器
      </p>

      <h1 class="hero-title" data-reveal data-reveal-delay="80">
        把重复的<em>80%</em><br />
        交给<span class="brand-italic">Bard</span>
      </h1>

      <p class="hero-subtitle" data-reveal data-reveal-delay="180">
        从需求漏洞扫描到工程价值量化，八步流水线让测试工程师聚焦在
        真正需要人类判断的那 20%。
      </p>

      <div class="hero-cta-row" data-reveal data-reveal-delay="280">
        <button class="cta-primary" @click="goWorkbench">
          开始使用
          <span class="arrow" aria-hidden="true">→</span>
        </button>
        <button class="cta-secondary" @click="scrollToPipeline">
          了解流水线
        </button>
      </div>

      <p class="hero-footnote" data-reveal data-reveal-delay="380">
        不需要替换流程 · 接入即用 · 数据本地化
      </p>
    </div>

    <!-- 纯白叙事诗底纹：极细网格线 -->
    <div class="hero-grid" aria-hidden="true"></div>
  </section>
</template>

<style scoped>
.hero {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 120px var(--space-3xl) 80px;
  overflow: hidden;
  background: var(--bg);
}

.hero-inner {
  position: relative;
  z-index: 2;
  max-width: 880px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: 0.8rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--muted-fg);
  margin-bottom: var(--space-3xl);
}
.hero-eyebrow .dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--fg);
  display: inline-block;
}

.hero-title {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 700;
  font-size: clamp(2.8rem, 8vw, 5.5rem);
  line-height: 1.04;
  letter-spacing: -0.02em;
  color: var(--fg);
  margin-bottom: var(--space-3xl);
}
.hero-title em {
  font-style: italic;
  position: relative;
}
.hero-title .brand-italic {
  font-style: italic;
}

.hero-subtitle {
  max-width: 560px;
  font-size: 1.05rem;
  line-height: 1.7;
  color: var(--muted-fg);
  margin-bottom: var(--space-3xl);
}

.hero-cta-row {
  display: flex;
  align-items: center;
  gap: var(--space-lg);
  margin-bottom: var(--space-xl);
  flex-wrap: wrap;
  justify-content: center;
}

.cta-primary {
  display: inline-flex;
  align-items: center;
  gap: var(--space-sm);
  height: 52px;
  padding: 0 var(--space-3xl);
  font-size: 1rem;
  font-weight: 500;
  letter-spacing: 0.01em;
  color: var(--bg);
  background: var(--fg);
  border-radius: var(--radius-full);
  transition: transform var(--duration-fast) var(--ease),
    opacity var(--duration-fast) var(--ease);
}
.cta-primary:hover {
  opacity: 0.86;
  transform: translateY(-1px);
}
.cta-primary .arrow {
  transition: transform var(--duration-fast) var(--ease);
}
.cta-primary:hover .arrow {
  transform: translateX(4px);
}

.cta-secondary {
  display: inline-flex;
  align-items: center;
  height: 52px;
  padding: 0 var(--space-2xl);
  font-size: 1rem;
  color: var(--fg);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-full);
  background: transparent;
  transition: background-color var(--duration-fast) var(--ease),
    border-color var(--duration-fast) var(--ease);
}
.cta-secondary:hover {
  background: var(--hover-bg);
  border-color: var(--fg);
}

.hero-footnote {
  font-size: 0.8rem;
  letter-spacing: 0.05em;
  color: var(--muted-fg);
}

/* 极细网格底纹（叙事诗质感） */
.hero-grid {
  position: absolute;
  inset: 0;
  z-index: 1;
  background-image:
    linear-gradient(to right, var(--border-light) 1px, transparent 1px),
    linear-gradient(to bottom, var(--border-light) 1px, transparent 1px);
  background-size: 80px 80px;
  -webkit-mask-image: radial-gradient(ellipse at center, #000 0%, transparent 75%);
  mask-image: radial-gradient(ellipse at center, #000 0%, transparent 75%);
  opacity: 0.5;
  pointer-events: none;
}

@media (max-width: 720px) {
  .hero {
    padding: 100px var(--space-xl) 60px;
  }
}
</style>
