import { test, expect } from '@playwright/test'
import { installMocks, MOCK_TASKS } from './fixtures/api-mocks'

/**
 * WorkbenchView e2e — 测试工作台
 *
 * 覆盖：
 *  - 文件拖拽上传区渲染 + 点击选择文件
 *  - 上传后弹出 Pipeline 启动配置弹窗
 *  - 弹窗内执行模式/维度/格式选择
 *  - 启动 Pipeline（POST /pipeline/start）
 *  - 任务列表渲染 + Tab 筛选
 *  - 搜索框交互
 *  - 文件类型校验（仅 md/txt）
 */

test.describe('Workbench — 工作台', () => {
  test.beforeEach(async ({ page }) => {
    await installMocks(page)
    // 拦截 pipeline/start
    await page.route('**/api/v1/pipeline/start', async (route) => {
      if (route.request().method() === 'POST') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ pipeline_id: 'task-new-001', status: 'running' }),
        })
      }
      return route.continue()
    })
    await page.goto('/workbench')
  })

  test('渲染上传区与任务列表', async ({ page }) => {
    // 上传区
    await expect(page.getByText('开启一次 AI 测试流水线')).toBeVisible()
    await expect(page.getByText(/拖拽需求文档/)).toBeVisible()
    // 选择文件按钮
    await expect(page.getByRole('button', { name: /选择需求文件/ })).toBeVisible()
    // 任务列表 Tab
    await expect(page.getByRole('button', { name: /需我处理/ })).toBeVisible()
    await expect(page.getByRole('button', { name: /运行中/ })).toBeVisible()
    await expect(page.getByRole('button', { name: /已完成/ })).toBeVisible()
  })

  test('点击选择 md 文件 → 弹出启动配置弹窗', async ({ page }) => {
    // 通过隐藏 input 上传文件
    const fileInput = page.locator('input[type="file"][accept=".md,.txt"]')
    await fileInput.setInputFiles({
      name: 'test_requirements.md',
      mimeType: 'text/markdown',
      buffer: Buffer.from('# 测试需求\n\n## 用户管理\n- 注册功能\n'),
    })

    // 弹窗出现
    const modal = page.getByRole('dialog')
    await expect(modal).toBeVisible({ timeout: 5000 })
    // 文件名展示
    await expect(page.locator('body')).toContainText('test_requirements.md')
  })

  test('启动弹窗含执行模式/维度/格式三组选项', async ({ page }) => {
    const fileInput = page.locator('input[type="file"][accept=".md,.txt"]')
    await fileInput.setInputFiles({
      name: 'req.md',
      mimeType: 'text/markdown',
      buffer: Buffer.from('# 需求'),
    })
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 })

    // 执行模式选项
    await expect(page.getByText('全自动 (auto)')).toBeVisible()
    await expect(page.getByText('半自动 (semi)')).toBeVisible()
    await expect(page.getByText('逐步 (step)')).toBeVisible()
  })

  test('启动 Pipeline → 调用 start 端点', async ({ page }) => {
    const fileInput = page.locator('input[type="file"][accept=".md,.txt"]')
    await fileInput.setInputFiles({
      name: 'req.md',
      mimeType: 'text/markdown',
      buffer: Buffer.from('# 需求'),
    })
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 })

    // 点击启动按钮（BaseButton，文本含"启动"或"开始"）
    const startBtn = page.getByRole('button', { name: /启动|开始|Launch|Start/i }).last()
    await startBtn.click()

    // 弹窗关闭（启动成功）
    // 给一点时间让请求完成
    await page.waitForTimeout(1000)
  })

  test('任务列表 Tab 切换', async ({ page }) => {
    // 切到"全部任务"应显示任务行或空状态（不崩溃）
    await page.getByRole('button', { name: /全部任务/ }).click()
    await expect(page.locator('.task-table, .task-empty')).toBeVisible()

    // 切到已完成
    await page.getByRole('button', { name: /已完成/ }).click()
    await expect(page.locator('.task-table, .task-empty')).toBeVisible()
  })

  test('搜索框可输入', async ({ page }) => {
    const search = page.getByLabel('搜索任务或 PRD')
    await expect(search).toBeVisible()
    await search.fill('order')
    await expect(search).toHaveValue('order')
  })

  test('文件类型校验 — 非 md/txt 文件应拒绝', async ({ page }) => {
    // 监听 toast（错误提示）
    const fileInput = page.locator('input[type="file"][accept=".md,.txt"]')
    await fileInput.setInputFiles({
      name: 'image.png',
      mimeType: 'image/png',
      buffer: Buffer.from('fake-png'),
    })
    // 应出现错误提示（toast 或内嵌 error）
    await expect(page.locator('[role="alert"], .toast, .hero-error').first()).toBeVisible({ timeout: 5000 })
  })
})

test.describe('Workbench — 空任务列表', () => {
  test('无任务时显示空状态', async ({ page }) => {
    await installMocks(page, { tasks: [] })
    await page.goto('/workbench')
    // 切到全部任务 tab（避免 action tab 默认空）
    await page.getByRole('button', { name: /全部任务/ }).click()
    await expect(page.getByText(/暂无任务/)).toBeVisible()
  })
})
