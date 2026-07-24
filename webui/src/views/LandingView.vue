<script setup lang="ts">
/**
 * LandingView — 落地页主视图（演示 B 纯白叙事诗还原）
 * 组合：导航 + Hero + 流水线 + 价值主张 + 统计带 + 页脚 CTA
 * 通过 useReveal 注册全局滚动揭示动画
 */
import { useReveal } from '@/composables/useReveal'
import { useRouter } from 'vue-router'
import LandingNavbar from '@/components/landing/LandingNavbar.vue'
import HeroSection from '@/components/landing/HeroSection.vue'
import PipelineSteps from '@/components/landing/PipelineSteps.vue'
import ValueProps from '@/components/landing/ValueProps.vue'
import StatsBand from '@/components/landing/StatsBand.vue'

const router = useRouter()

// 注册滚动揭示动画
useReveal()

const goWorkbench = () => {
  router.push('/workbench')
}
</script>

<template>
  <div class="landing-page">
    <LandingNavbar />

    <main>
      <HeroSection />
      <PipelineSteps />
      <ValueProps />
      <StatsBand />

      <!-- 页脚 CTA -->
      <section class="footer-cta">
        <div class="footer-inner" data-reveal>
          <p class="footer-eyebrow">READY</p>
          <h2 class="footer-title">
            把第一个需求，<em>交给 Bard</em>
          </h2>
          <p class="footer-sub">
            无需安装客户端，浏览器打开即用。从一份需求文档开始，看见八步流水线的全部力量。
          </p>
          <button class="footer-button" @click="goWorkbench">
            开始使用
            <span class="arrow" aria-hidden="true">→</span>
          </button>
        </div>
      </section>

      <footer class="landing-footer">
        <div class="footer-meta">
          <span class="footer-brand">Bard</span>
          <span class="footer-copy">AI 测试效能倍增器 · 演示 B 还原</span>
        </div>
      </footer>
    </main>
  </div>
</template>

<style scoped>
.landing-page {
  background: var(--bg);
  color: var(--fg);
}

/* ─── 滚动揭示动画基础样式（供 useReveal 使用） ─── */
.landing-page :deep([data-reveal]) {
  opacity: 0;
  transform: translateY(24px);
  transition:
    opacity var(--duration-slow) var(--ease-out),
    transform var(--duration-slow) var(--ease-out);
  transition-delay: 0ms;
}
.landing-page :deep([data-reveal].is-visible) {
  opacity: 1;
  transform: none;
}
.landing-page :deep([data-reveal][data-reveal-delay].is-visible) {
  transition-delay: var(--reveal-delay, 0ms);
}

/* ─── 页脚 CTA ─── */
.footer-cta {
  padding: 140px var(--space-3xl);
  text-align: center;
  background: var(--bg);
}
.footer-inner {
  max-width: 640px;
  margin: 0 auto;
}
.footer-eyebrow {
  font-size: 0.75rem;
  letter-spacing: 0.22em;
  color: var(--muted-fg);
  margin-bottom: var(--space-lg);
}
.footer-title {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 700;
  font-size: clamp(2.2rem, 5.5vw, 3.6rem);
  line-height: 1.1;
  letter-spacing: -0.02em;
  color: var(--fg);
  margin-bottom: var(--space-xl);
}
.footer-title em {
  font-style: italic;
}
.footer-sub {
  font-size: 1rem;
  line-height: 1.7;
  color: var(--muted-fg);
  margin-bottom: var(--space-3xl);
}
.footer-button {
  display: inline-flex;
  align-items: center;
  gap: var(--space-sm);
  height: 54px;
  padding: 0 var(--space-3xl);
  font-size: 1rem;
  font-weight: 500;
  color: var(--bg);
  background: var(--fg);
  border-radius: var(--radius-full);
  transition: opacity var(--duration-fast) var(--ease),
    transform var(--duration-fast) var(--ease);
}
.footer-button:hover {
  opacity: 0.86;
  transform: translateY(-1px);
}
.footer-button .arrow {
  transition: transform var(--duration-fast) var(--ease);
}
.footer-button:hover .arrow {
  transform: translateX(4px);
}

/* ─── 页脚信息 ─── */
.landing-footer {
  padding: var(--space-2xl) var(--space-3xl);
  border-top: 1px solid var(--border-light);
  background: var(--bg);
}
.footer-meta {
  max-width: var(--content-max-width);
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--space-md);
}
.footer-brand {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 700;
  font-size: 1.1rem;
  color: var(--fg);
}
.footer-copy {
  font-size: 0.8rem;
  color: var(--muted-fg);
}
</style>
