#!/usr/bin/env python3
"""
AI Agent 自动化测试套件 — 共享配置与 Fixtures

本 conftest 提供：
  - 测试环境初始化与清理
  - 数据库隔离
  - Web 服务生命周期管理
  - 共享测试数据工厂
  - 资源监控器注入
"""

import os
import shutil
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import pytest

# 项目根路径
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# 设置测试环境变量
os.environ.setdefault("LLM_API_KEY", "sk-test-dummy-for-agent-suite")
os.environ.setdefault("AI_TEST_ENV", "development")

# ─── 全局状态 ───

_suite_start_time: datetime | None = None


def get_suite_start_time() -> datetime:
    """获取测试套件启动时间"""
    global _suite_start_time
    if _suite_start_time is None:
        _suite_start_time = datetime.now()
    return _suite_start_time


# ─── 数据库隔离 ───

@pytest.fixture(scope="session")
def db_temp_dir():
    """会话级临时数据库目录"""
    tmp = tempfile.mkdtemp(prefix="ai_test_db_")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, db_temp_dir):
    """每个测试使用独立的数据库路径（隔离）"""
    db_name = f"test_{uuid.uuid4().hex[:8]}.db"
    db_path = Path(db_temp_dir) / db_name
    monkeypatch.setenv("DATABASE_PATH", str(db_path))

    from db.session import init_db, reset_engine
    reset_engine()
    init_db()
    yield
    reset_engine()


# ─── 输出目录隔离 ───

@pytest.fixture
def output_dir(tmp_path):
    """每个测试的独立输出目录"""
    out = tmp_path / "output"
    out.mkdir(exist_ok=True)
    return str(out)


# ─── 测试数据工厂 ───

@pytest.fixture
def sample_requirements_md() -> str:
    """生成示例需求文档内容"""
    return """# 电商平台核心功能需求

## 1. 用户管理模块
### 1.1 用户注册
- 支持手机号注册，需短信验证码验证
- 支持邮箱注册，需邮箱验证
- 密码需满足：8-20位，包含大小写字母和数字
- 同一手机号/邮箱24小时内限注册3次
- 注册成功后自动登录并跳转首页

### 1.2 用户登录
- 支持手机号+密码登录
- 支持邮箱+密码登录
- 支持第三方登录（微信/支付宝）
- 连续5次登录失败锁定账户30分钟
- 支持"记住我"功能（7天免登录）
- 登录成功后返回JWT Token

### 1.3 个人信息管理
- 修改头像（支持上传裁剪）
- 修改昵称（2-20字符，支持中英文和特殊符号）
- 修改密码（需验证原密码）
- 绑定/解绑手机号、邮箱
- 收货地址管理（最多20个地址）

## 2. 商品管理模块
### 2.1 商品浏览
- 商品列表分页展示（每页20条）
- 支持按分类、价格、销量、评分筛选
- 支持关键词搜索（模糊匹配）
- 商品详情页展示图片轮播、规格参数、用户评价
- 浏览历史记录（最近50条）

### 2.2 商品收藏
- 收藏/取消收藏商品
- 收藏列表分页展示
- 收藏商品降价提醒
- 批量管理收藏商品

## 3. 订单管理模块
### 3.1 购物车
- 添加商品到购物车（支持选择规格和数量）
- 修改购物车商品数量
- 删除购物车商品
- 购物车商品选中/取消选中
- 购物车总价实时计算（含优惠）
- 库存不足时提示

### 3.2 订单创建
- 从购物车生成订单
- 选择收货地址
- 支持多种支付方式（微信/支付宝/银行卡）
- 支持优惠券/积分抵扣
- 订单金额计算（商品金额+运费-优惠）
- 生成订单号（格式：YYYYMMDD+12位随机数）

### 3.3 订单管理
- 订单列表（按状态筛选：待付款/待发货/待收货/已完成/已取消）
- 订单详情查看
- 取消订单（仅待付款状态可取消）
- 申请退款/退货
- 确认收货
- 订单评价（评分+文字+图片）

## 4. 支付模块
### 4.1 支付流程
- 发起支付请求
- 支付回调处理
- 支付超时自动取消（30分钟）
- 支付失败重试机制
- 重复支付幂等性保护

### 4.2 退款处理
- 原路退款
- 退款状态跟踪
- 部分退款支持
- 退款到账时间提示

## 5. 系统管理模块
### 5.1 权限管理
- 角色管理（管理员/运营/客服/普通用户）
- 权限分配（菜单权限/按钮权限/数据权限）
- 操作日志记录

### 5.2 数据统计
- 订单统计（日/周/月报表）
- 用户增长统计
- 商品销售排行
- 收入统计图表
"""


@pytest.fixture
def sample_requirements_simple() -> str:
    """简单需求文档（用于快速测试）"""
    return """# 用户登录功能需求

## 功能描述
实现用户登录功能，支持用户名密码登录。

## 详细需求
- 用户名：4-20个字符，支持字母数字下划线
- 密码：6-20个字符，不能为纯数字
- 连续3次失败后需要验证码
- 登录成功后返回token
"""


@pytest.fixture
def sample_requirements_boundary() -> str:
    """边界场景需求文档"""
    return """# 边界与异常场景测试需求

## 1. 输入边界
- 空值输入处理
- 超长字符串输入（10000+字符）
- 特殊字符输入（SQL注入、XSS、Unicode）
- 负数/零值输入
- 并发重复提交

## 2. 状态边界
- 同一资源多次操作幂等性
- 状态流转的非法跳转
- 过期数据访问
- 已删除数据引用
"""


# ─── 超时配置 ───

@pytest.fixture
def long_timeout():
    """长时间操作超时（秒）"""
    return 300  # 5 分钟


@pytest.fixture
def llm_call_timeout():
    """LLM 调用超时（秒）"""
    return 180  # 3 分钟


# ─── 测试结果收集器 ───

class TestResultCollector:
    """线程安全的测试结果收集器"""

    def __init__(self):
        self.results: list = []
        self.start_time = datetime.now()

    def add(self, module: str, test_name: str, status: str,
            duration: float, error: str | None = None,
            details: dict | None = None):
        self.results.append({
            "module": module,
            "test_name": test_name,
            "status": status,
            "duration": round(duration, 3),
            "error": error,
            "details": details or {},
            "timestamp": datetime.now().isoformat(),
        })

    def summary(self) -> dict:
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "passed")
        failed = sum(1 for r in self.results if r["status"] == "failed")
        skipped = sum(1 for r in self.results if r["status"] == "skipped")
        error_count = sum(1 for r in self.results if r["status"] == "error")
        total_duration = sum(r["duration"] for r in self.results)
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": error_count,
            "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
            "total_duration_seconds": round(total_duration, 1),
            "total_duration_minutes": round(total_duration / 60, 1),
        }


@pytest.fixture(scope="session")
def collector():
    """会话级测试结果收集器"""
    return TestResultCollector()
