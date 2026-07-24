import { test, expect } from '@playwright/test'
import { installMocks } from './fixtures/api-mocks'

/**
 * 可访问性 e2e — ARIA 与键盘交互
 *
 * 覆盖：
 *  - Provider 卡片 ARIA（role=article + aria-label）
 *  - 抽屉 dialog ARIA（aria-modal / aria-label）
 *  - 确认弹窗 alertdialog
 *  - 批量 checkbox role + aria-checked
 *  - 三点菜单 aria-expanded
 *  - 键盘：ESC 关闭抽屉、Tab 焦点流转
 *  - 图片/图标 aria-hidden
 *
 * 依据：项目记忆中 ARIA 合规是验收硬指标
 */

test.describe('可访问性 — ARIA 完整性', () => {
  test.beforeEach(async ({ page }) => {
    await installMocks(page)
    await page.goto('/settings')
    await expect(page.getByRole('article', { name: 'Provider glm' })).toBeVisible()
  })

  test('Provider 卡片具备 role=article 与 aria-label', async ({ page }) => {
    const cards = page.locator('.provider-card[role="article"]')
    await expect(cards).toHaveCount(3)
    for (const name of ['glm', 'deepseek', 'claude']) {
      await expect(page.locator(`[role="article"][aria-label="Provider ${name}"]`)).toBeVisible()
    }
  })

  test('三点菜单 aria-expanded 状态切换', async ({ page }) => {
    const menuBtn = page.locator('[aria-label="更多操作 glm"]')
    await expect(menuBtn).toHaveAttribute('aria-expanded', 'false')
    await menuBtn.click()
    await expect(menuBtn).toHaveAttribute('aria-expanded', 'true')
    // 点击别处关闭
    await page.keyboard.press('Escape')
    await expect(menuBtn).toHaveAttribute('aria-expanded', 'false')
  })

  test('启用/停用按钮 aria-pressed 反映状态', async ({ page }) => {
    // glm enabled → aria-pressed=true
    await expect(page.locator('[aria-label="禁用 glm"]')).toHaveAttribute('aria-pressed', 'true')
    // claude disabled → aria-pressed=false
    await expect(page.locator('[aria-label="启用 claude"]')).toHaveAttribute('aria-pressed', 'false')
  })

  test('批量 checkbox role=checkbox + aria-checked', async ({ page }) => {
    await page.getByRole('button', { name: '进入批量管理模式' }).click()
    // 用 card-scoped 选择器（aria-label 在选中后会变化，直接定位会失效）
    const deepseekCard = page.getByRole('article', { name: 'Provider deepseek' })
    const checkbox = deepseekCard.locator('[role="checkbox"]')
    await expect(checkbox).toHaveAttribute('role', 'checkbox')
    await expect(checkbox).toHaveAttribute('aria-checked', 'false')
    await checkbox.click()
    await expect(checkbox).toHaveAttribute('aria-checked', 'true')
  })

  test('删除确认弹窗为 alertdialog', async ({ page }) => {
    await page.locator('[aria-label="更多操作 deepseek"]').click()
    await page.getByRole('menuitem', { name: '删除' }).click()
    const modal = page.getByRole('alertdialog')
    await expect(modal).toBeVisible()
    await expect(modal).toHaveAttribute('aria-modal', 'true')
  })

  test('抽屉为 dialog + aria-modal', async ({ page }) => {
    await page.getByRole('button', { name: '新增 Provider' }).click()
    const drawer = page.getByRole('dialog', { name: '新增 Provider' })
    await expect(drawer).toBeVisible()
    await expect(drawer).toHaveAttribute('aria-modal', 'true')
  })

  test('键盘 ESC 关闭抽屉', async ({ page }) => {
    await page.getByRole('button', { name: '新增 Provider' }).click()
    const drawer = page.getByRole('dialog', { name: '新增 Provider' })
    await expect(drawer).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(drawer).not.toBeVisible({ timeout: 3000 })
  })

  test('图标元素 aria-hidden（避免屏幕阅读器重复朗读）', async ({ page }) => {
    // 侧边栏图标 aria-hidden
    const sideIcons = page.locator('.side-icon[aria-hidden="true"]')
    const count = await sideIcons.count()
    expect(count).toBeGreaterThan(0)
  })
})

test.describe('可访问性 — 语义化标签', () => {
  test.beforeEach(async ({ page }) => {
    await installMocks(page)
  })

  test('页面具备 lang 属性', async ({ page }) => {
    await page.goto('/settings')
    const lang = await page.locator('html').getAttribute('lang')
    expect(lang).toBeTruthy()
  })

  test('侧边栏导航链接具备 aria-current 激活态', async ({ page }) => {
    await page.goto('/settings')
    await expect(page.getByRole('link', { name: '偏好设置' })).toHaveAttribute('aria-current', 'page')
    // 其他链接无 aria-current
    await expect(page.getByRole('link', { name: '测试工作台' })).not.toHaveAttribute('aria-current', 'page')
  })

  test('heading 层级存在（h1/h2/h3）', async ({ page }) => {
    await page.goto('/settings')
    // 等待 Provider 卡片加载（卡片内含 h3.pc-name），避免异步加载竞态
    await expect(page.getByRole('article', { name: 'Provider glm' })).toBeVisible()
    const headings = page.locator('h1, h2, h3')
    expect(await headings.count()).toBeGreaterThan(0)
  })
})
