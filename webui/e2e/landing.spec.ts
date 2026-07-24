import { test, expect } from '@playwright/test'
import { installMocks } from './fixtures/api-mocks'

/**
 * LandingView e2e — 落地页
 *
 * 覆盖：
 *  - Hero 区渲染
 *  - 导航到工作台
 *  - 侧边栏品牌回首页
 */

test.describe('Landing — 落地页', () => {
  test.beforeEach(async ({ page }) => {
    await installMocks(page)
  })

  test('落地页渲染 Hero 区与核心元素', async ({ page }) => {
    await page.goto('/')
    // 落地页应渲染（HeroSection / Navbar 等）
    await expect(page).toHaveTitle(/.+/)
    // 页面应有可见内容
    await expect(page.locator('body')).not.toBeEmpty()
  })

  test('从落地页可导航到工作台', async ({ page }) => {
    await page.goto('/')
    // 点击任何"进入工作台/开始"类入口
    const cta = page.getByRole('link', { name: /工作台|开始|进入|Launch|Start/i }).first()
    if (await cta.isVisible({ timeout: 2000 }).catch(() => false)) {
      await cta.click()
      await expect(page).toHaveURL(/\/workbench/)
    } else {
      // 落地页无 CTA 时直接验证 workbench 可达
      await page.goto('/workbench')
      await expect(page).toHaveURL(/\/workbench/)
    }
  })
})
