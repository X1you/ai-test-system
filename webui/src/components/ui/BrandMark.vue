<script setup lang="ts">
/**
 * BrandMark — 品牌 logo + 名称
 * 内联「打勾 B」SVG（mask 方式），SVG 用 currentColor 跟随 var(--fg)
 * 旁边显示 "Bard" 文字
 */
withDefaults(
  defineProps<{
    size?: number | string
  }>(),
  {
    size: 28,
  },
)
</script>

<template>
  <span class="brand-mark" :style="{ '--brand-size': typeof size === 'number' ? size + 'px' : size }">
    <svg
      class="brand-logo"
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <mask id="bardLogoMask">
        <rect width="100" height="100" fill="white" />
        <path
          d="M 22 50 L 37 65 L 59 40"
          stroke="black"
          stroke-width="7"
          stroke-linecap="square"
          stroke-linejoin="miter"
          fill="none"
        />
        <circle cx="59" cy="40" r="8" fill="black" />
      </mask>
      <path
        d="M 25 12 H 58 C 74 12 85 22 85 36 C 85 46 73 50 62 50 C 76 50 88 56 88 72 C 88 84 74 88 58 88 H 25 Z"
        fill="currentColor"
        mask="url(#bardLogoMask)"
      />
    </svg>
    <span class="brand-name">Bard</span>
  </span>
</template>

<style scoped>
.brand-mark {
  display: inline-flex;
  align-items: center;
  gap: 0.4em;
  color: var(--fg);
}

.brand-logo {
  width: var(--brand-size);
  height: var(--brand-size);
  color: var(--fg);
  flex-shrink: 0;
}

.brand-name {
  font-family: var(--font-serif);
  font-weight: 700;
  font-size: calc(var(--brand-size) * 0.78);
  letter-spacing: -0.01em;
  color: var(--fg);
  line-height: 1;
}
</style>
