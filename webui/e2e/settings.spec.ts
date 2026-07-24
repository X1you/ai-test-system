import { test, expect } from '@playwright/test'
import { installMocks, MOCK_PROVIDERS, MOCK_CONFIG } from './fixtures/api-mocks'

/**
 * SettingsView e2e — 系统配置页（最高优先级）
 *
 * 覆盖：
 *  - Provider 卡片渲染（协议徽章 / 状态点 / 默认徽章 / 脱敏 Key）
 *  - 新增 Provider（抽屉 3 步表单：基础信息 → 协议 → 连接信息 + 测试连接）
 *  - 编辑 Provider
 *  - 删除 Provider（二次确认 modal）
 *  - 设为默认 / 启用停用
 *  - 测试连接（成功 + 失败）
 *  - V2 批量操作（进入批量 / 全选 / 批量启用 / 批量删除确认）
 *  - V3 标签筛选
 *  - 协议切换保留字段
 *  - 空状态
 *  - API Key 脱敏（硬约束：sk-xxxx...yyyy）
 */

test.describe('Settings — Provider 管理', () => {
  test.beforeEach(async ({ page }) => {
    await installMocks(page)
    await page.goto('/settings')
    // 等待配置加载完成（providers 渲染）
    await expect(page.getByRole('article', { name: 'Provider glm' })).toBeVisible()
  })

  test('渲染 Provider 卡片网格，含协议徽章/状态点/默认徽章/脱敏 Key', async ({ page }) => {
    // 3 张卡片
    await expect(page.getByRole('article', { name: 'Provider glm' })).toBeVisible()
    await expect(page.getByRole('article', { name: 'Provider deepseek' })).toBeVisible()
    await expect(page.getByRole('article', { name: 'Provider claude' })).toBeVisible()

    // 默认徽章
    await expect(page.locator('.provider-card.is-default .pc-default-badge')).toContainText('默认')

    // 协议徽章
    await expect(page.locator('[aria-label="Provider glm"] .pc-protocol-label')).toContainText('OpenAI 兼容')
    await expect(page.locator('[aria-label="Provider claude"] .pc-protocol-label')).toContainText('Anthropic')

    // API Key 脱敏（硬约束：sk-xxxx...yyyy 格式，绝不完整显示）
    const glmKey = page.locator('[aria-label="Provider glm"] .pc-key code')
    await expect(glmKey).toContainText('...')
    // 完整 key 不应出现在 DOM
    await expect(page.locator('body')).not.toContainText('sk-abcdefgh1234567890wxyz')
  })

  test('新增 Provider — 抽屉 3 步表单填写并保存', async ({ page }) => {
    await page.getByRole('button', { name: '新增 Provider' }).click()

    // 抽屉打开
    const drawer = page.getByRole('dialog', { name: '新增 Provider' })
    await expect(drawer).toBeVisible()

    // 步骤 1：基础信息
    await page.getByLabel('名称（别名）').fill('qwen')
    await page.getByLabel('Vendor').fill('alibaba')

    // 步骤 2：协议（默认 openai_compatible，无需切换）
    await expect(drawer.locator('.dr-section-title', { hasText: '2. 协议' })).toBeVisible()

    // 步骤 3：连接信息
    await page.getByLabel('Base URL').fill('https://dashscope.aliyuncs.com/compatible-mode/v1')
    await page.getByLabel('API Key').fill('sk-qwen-test-key-1234567890')
    await page.getByLabel('模型').fill('qwen-max')

    // 保存
    await drawer.getByRole('button', { name: '保存' }).click()

    // 抽屉关闭 + toast 成功
    await expect(drawer).not.toBeVisible()
    await expect(page.locator('.toast-item').filter({ hasText: 'qwen' })).toBeVisible({ timeout: 5000 })
  })

  test('编辑现有 Provider', async ({ page }) => {
    // 打开 deepseek 的更多菜单 → 编辑
    await page.locator('[aria-label="更多操作 deepseek"]').click()
    await page.getByRole('menuitem', { name: '编辑' }).click()

    const drawer = page.getByRole('dialog', { name: '编辑 deepseek' })
    await expect(drawer).toBeVisible()
    // 名称已预填
    await expect(page.getByLabel('名称（别名）')).toHaveValue('deepseek')
    await expect(page.getByLabel('模型')).toHaveValue('deepseek-chat')

    // 修改模型
    await page.getByLabel('模型').fill('deepseek-reasoner')
    await drawer.getByRole('button', { name: '保存' }).click()
    await expect(drawer).not.toBeVisible()
  })

  test('删除 Provider — 二次确认 modal', async ({ page }) => {
    // deepseek 非默认，可删
    await page.locator('[aria-label="更多操作 deepseek"]').click()
    await page.getByRole('menuitem', { name: '删除' }).click()

    // 确认 modal
    const modal = page.getByRole('alertdialog', { name: '删除 Provider deepseek' })
    await expect(modal).toBeVisible()
    await expect(modal).toContainText('删除 Provider「deepseek」')

    // 取消
    await page.getByRole('button', { name: '取消' }).click()
    await expect(modal).not.toBeVisible()

    // 再次删除并确认
    await page.locator('[aria-label="更多操作 deepseek"]').click()
    await page.getByRole('menuitem', { name: '删除' }).click()
    await expect(modal).toBeVisible()
    await page.getByRole('button', { name: '确认删除' }).click()
    await expect(modal).not.toBeVisible()
  })

  test('默认 Provider 不显示删除项', async ({ page }) => {
    // glm 是默认，菜单不应有"删除"
    await page.locator('[aria-label="更多操作 glm"]').click()
    await expect(page.getByRole('menuitem', { name: '删除' })).toHaveCount(0)
  })

  test('设为默认 — 切换默认 Provider', async ({ page }) => {
    // deepseek 卡片有"设为默认"按钮
    await page.locator('[aria-label="设为默认 deepseek"]').click()
    // toast 成功
    await expect(page.locator('.toast-item').filter({ hasText: 'deepseek' })).toBeVisible({ timeout: 5000 })
  })

  test('启用/停用切换', async ({ page }) => {
    // claude 当前 disabled，按钮 aria-label 为"启用 claude"
    const toggle = page.locator('[aria-label="启用 claude"]')
    await expect(toggle).toBeVisible()
    await toggle.click()
    // toast
    await expect(page.locator('.toast-item').filter({ hasText: 'claude' })).toBeVisible({ timeout: 5000 })
  })

  test('测试连接 — 成功反馈', async ({ page }) => {
    // glm 卡片的测试按钮
    await page.locator('[aria-label="测试连接 glm"]').click()
    // 卡片状态点变为 ok
    await expect(page.locator('[aria-label="Provider glm"] .pc-status-dot.is-ok')).toBeVisible({ timeout: 5000 })
    await expect(page.locator('[aria-label="Provider glm"] .pc-status-text')).toContainText('已联通')
  })

  test('测试连接 — 失败反馈（claude 模拟失败）', async ({ page }) => {
    await page.locator('[aria-label="测试连接 claude"]').click()
    // 状态点 degraded
    await expect(page.locator('[aria-label="Provider claude"] .pc-status-dot.is-degraded')).toBeVisible({ timeout: 5000 })
  })

  test('抽屉内测试连接 + 保存流程', async ({ page }) => {
    await page.getByRole('button', { name: '新增 Provider' }).click()
    const drawer = page.getByRole('dialog', { name: '新增 Provider' })
    await page.getByLabel('名称（别名）').fill('test-drawer')
    await page.getByLabel('Base URL').fill('https://api.test.com/v1')
    await page.getByLabel('API Key').fill('sk-test-key-1234567890abcd')
    await page.getByLabel('模型').fill('test-model')

    // 测试连接（抽屉内）
    await drawer.getByRole('button', { name: '测试连接', exact: true }).click()
    // 测试结果内嵌提示
    await expect(drawer.locator('.dr-test-result')).toBeVisible({ timeout: 5000 })

    await drawer.getByRole('button', { name: '保存' }).click()
    await expect(drawer).not.toBeVisible()
  })

  test('必填校验 — 缺失 name/model 时禁用保存', async ({ page }) => {
    await page.getByRole('button', { name: '新增 Provider' }).click()
    const drawer = page.getByRole('dialog', { name: '新增 Provider' })
    await expect(drawer).toBeVisible()
    // 未填任何字段，保存按钮应禁用
    await expect(drawer.getByRole('button', { name: '保存' })).toBeDisabled()
  })

  test('协议切换 — 切到 custom_http 显示专属字段且保留 name', async ({ page }) => {
    await page.getByRole('button', { name: '新增 Provider' }).click()
    await page.getByLabel('名称（别名）').fill('custom-llm')

    // 切换协议前 base_url 可见
    await expect(page.getByLabel('Base URL')).toBeVisible()

    // 选择 custom_http（ProtocolSelector 内 radio）
    await page.getByRole('radio', { name: /自定义 HTTP/ }).check()

    // custom_http 专属字段出现
    await expect(page.getByLabel('Endpoint')).toBeVisible()
    await expect(page.getByLabel('Body Template (JSON)')).toBeVisible()
    await expect(page.getByLabel('Response Path')).toBeVisible()
    // base_url 字段消失（custom_http 不用 base_url）
    await expect(page.getByLabel('Base URL')).toHaveCount(0)

    // name 保留（硬约束：协议切换不清空已填字段）
    await expect(page.getByLabel('名称（别名）')).toHaveValue('custom-llm')
  })
})

test.describe('Settings — V2 批量操作', () => {
  test.beforeEach(async ({ page }) => {
    await installMocks(page)
    await page.goto('/settings')
    await expect(page.getByRole('article', { name: 'Provider glm' })).toBeVisible()
  })

  test('进入批量模式 → 全选 → 批量启用', async ({ page }) => {
    await page.getByRole('button', { name: '进入批量管理模式' }).click()

    // 批量工具栏出现
    const toolbar = page.getByRole('toolbar', { name: '批量操作工具栏' })
    await expect(toolbar).toBeVisible()

    // 全选
    await page.getByRole('button', { name: /全选/ }).click()
    // 所有卡片选中态
    await expect(page.locator('.provider-card.is-selected')).toHaveCount(3)

    // 批量启用
    await page.getByRole('button', { name: '批量启用' }).click()
    await expect(page.locator('.toast-item').first()).toBeVisible({ timeout: 5000 })
  })

  test('批量删除 — 二次确认', async ({ page }) => {
    await page.getByRole('button', { name: '进入批量管理模式' }).click()

    // 选中 deepseek（非默认）
    await page.locator('[aria-label="选中 deepseek"]').click()
    await expect(page.locator('[aria-label="Provider deepseek"].is-selected')).toBeVisible()

    await page.getByRole('button', { name: '批量删除' }).click()
    const modal = page.getByRole('alertdialog', { name: '批量删除 Provider' })
    await expect(modal).toBeVisible()
    await expect(modal).toContainText('批量删除 1 个 Provider')

    await page.getByRole('button', { name: '确认删除' }).click()
    await expect(modal).not.toBeVisible()
  })

  test('退出批量模式清空选择', async ({ page }) => {
    await page.getByRole('button', { name: '进入批量管理模式' }).click()
    await page.locator('[aria-label="选中 deepseek"]').click()
    await expect(page.locator('.provider-card.is-selected')).toHaveCount(1)

    await page.getByRole('button', { name: '退出批量' }).click()
    await expect(page.locator('.provider-card.is-selected')).toHaveCount(0)
    await expect(page.getByRole('toolbar', { name: '批量操作工具栏' })).toHaveCount(0)
  })

  test('键盘可操作 — Space 切换 checkbox 选择', async ({ page }) => {
    await page.getByRole('button', { name: '进入批量管理模式' }).click()
    const checkbox = page.locator('[aria-label="选中 deepseek"]')
    await checkbox.focus()
    await page.keyboard.press('Space')
    await expect(page.locator('[aria-label="Provider deepseek"].is-selected')).toBeVisible()
  })
})

test.describe('Settings — V3 标签筛选', () => {
  test.beforeEach(async ({ page }) => {
    await installMocks(page)
    await page.goto('/settings')
    await expect(page.getByRole('article', { name: 'Provider glm' })).toBeVisible()
  })

  test('按标签筛选 Provider', async ({ page }) => {
    // 标签筛选栏出现
    const filterBar = page.getByRole('group', { name: '按标签筛选' })
    await expect(filterBar).toBeVisible()

    // 点击 production 标签
    await filterBar.getByText('production', { exact: true }).click()
    // 只显示带 production 标签的（glm + claude）
    await expect(page.locator('.provider-card')).toHaveCount(2)
    await expect(page.getByRole('article', { name: 'Provider deepseek' })).toHaveCount(0)

    // 清除筛选
    await page.getByRole('button', { name: /全部|清除/ }).first().click()
    await expect(page.locator('.provider-card')).toHaveCount(3)
  })
})

test.describe('Settings — 空状态', () => {
  test('无 Provider 时显示空状态引导', async ({ page }) => {
    await installMocks(page, {
      config: { ...MOCK_CONFIG, llm_providers: [], llm_default: null, llm: { provider: 'N/A', model: 'N/A', base_url: 'N/A', api_key: '未配置', temperature: 0.3 } },
    })
    await page.goto('/settings')
    await expect(page.getByText('尚未配置任何 LLM Provider')).toBeVisible()
    // 空状态内有新增按钮
    await expect(page.locator('.empty-state, [class*="empty"]').getByRole('button', { name: '新增 Provider' })).toBeVisible()
  })
})
