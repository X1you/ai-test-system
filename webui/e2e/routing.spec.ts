import { test, expect, type Page, type Locator } from '@playwright/test'
import { installMocks } from './fixtures/api-mocks'

/**
 * 路由 e2e — 前端路由完整性
 *
 * 覆盖：
 *  - 直接 URL 访问各路由
 *  - 404 NotFoundView
 *  - 侧边栏导航激活态
 *  - 侧边栏导航跳转
 *  - 主题切换
 */

test.describe('路由 — 直接访问与导航', () => {
  test.beforeEach(async ({ page }) => {
    await installMocks(page)
  })

  // 移动端侧边栏为抽屉模式（translateX(-100%) off-screen），
  // 坐标点击无法命中视口外元素。用 evaluate 直接派发 DOM click 事件，
  // 绕过 Playwright 坐标命中检测（测试路由逻辑，非抽屉交互）
  async function sidebarClick(page: Page, locator: Locator) {
    const vw = page.viewportSize()?.width ?? 1280
    if (vw < 768) {
      // 移动端：侧边栏 off-screen，直接派发 DOM click
      await locator.evaluate((el) => (el as HTMLElement).click())
    } else {
      await locator.click()
    }
  }

  test('直接访问 /workbench /knowledge /settings 均可达', async ({ page }) => {
    for (const path of ['/workbench', '/knowledge', '/settings']) {
      await page.goto(path)
      await expect(page).toHaveURL(new RegExp(path.replace('/', '\\/')))
      // 页面应有内容（非空白）
      await expect(page.locator('body')).not.toBeEmpty()
    }
  })

  test('未知路由渲染 404 页', async ({ page }) => {
    await page.goto('/this-route-does-not-exist')
    // NotFoundView — 含 404 文案或返回首页链接
    await expect(page.locator('body')).toContainText(/404|Not Found|找不到|不存在/i)
  })

  test('侧边栏导航 — 点击跳转且激活态正确', async ({ page }) => {
    await page.goto('/workbench')

    // 导航到知识库
    await sidebarClick(page, page.getByRole('link', { name: '知识库 (RAG)' }))
    await expect(page).toHaveURL(/\/knowledge/)
    await expect(page.getByRole('link', { name: '知识库 (RAG)' })).toHaveAttribute('aria-current', 'page')

    // 导航到偏好设置
    await sidebarClick(page, page.getByRole('link', { name: '偏好设置' }))
    await expect(page).toHaveURL(/\/settings/)
    await expect(page.getByRole('link', { name: '偏好设置' })).toHaveAttribute('aria-current', 'page')

    // 导航回工作台
    await sidebarClick(page, page.getByRole('link', { name: '测试工作台' }))
    await expect(page).toHaveURL(/\/workbench/)
    await expect(page.getByRole('link', { name: '测试工作台' })).toHaveAttribute('aria-current', 'page')
  })

  test('品牌 logo 点击回首页', async ({ page }) => {
    await page.goto('/settings')
    await sidebarClick(page, page.locator('.brand-mark'))
    await expect(page).toHaveURL(/\/$/)
  })

  test('主题切换按钮可切换', async ({ page }) => {
    await page.goto('/settings')
    const themeBtn = page.locator('.theme-toggle')
    // 主题通过 <html>.classList 的 dark 类切换（见 useTheme.ts）
    const beforeDark = await page.evaluate(() => document.documentElement.classList.contains('dark'))
    await sidebarClick(page, themeBtn)
    const afterDark = await page.evaluate(() => document.documentElement.classList.contains('dark'))
    expect(afterDark).not.toBe(beforeDark)
    // localStorage 持久化
    const stored = await page.evaluate(() => localStorage.getItem('bard-theme'))
    expect(stored).toBeTruthy()
  })
})
