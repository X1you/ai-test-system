#!/usr/bin/env python3
"""
新增功能测试 — 第二批优化项

覆盖：
  - LLMCache 缓存层（P-01）
  - core/errors 异常层次（Q-04）
  - core/logger 统一日志（A-01）
  - core/multi_tenant 多租户（A-03）
  - CSRF 中间件（S-02）
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestLLMCache:
    """P-01: LLM 调用缓存层"""

    def test_cache_hit_miss(self):
        """缓存命中和未命中"""
        from core.llm_cache import LLMCache

        cache = LLMCache(maxsize=10, ttl=60)
        assert cache.get("model-a", "", "hello", 0) is None  # 未命中

        cache.set("model-a", "", "hello", "world", 0)
        result = cache.get("model-a", "", "hello", 0)
        assert result == "world"  # 命中

    def test_cache_temperature_nonzero_skipped(self):
        """temperature > 0 时不缓存"""
        from core.llm_cache import LLMCache

        cache = LLMCache(maxsize=10, ttl=60)
        cache.set("model", "", "prompt", "response", 0.7)
        assert cache.get("model", "", "prompt", 0.7) is None

    def test_cache_stats(self):
        """缓存统计"""
        from core.llm_cache import LLMCache

        cache = LLMCache(maxsize=10, ttl=60)
        cache.set("m", "", "p1", "r1", 0)
        cache.get("m", "", "p1", 0)   # hit
        cache.get("m", "", "p2", 0)   # miss
        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_cache_lru_eviction(self):
        """LRU 淘汰策略"""
        from core.llm_cache import LLMCache

        cache = LLMCache(maxsize=2, ttl=60)
        cache.set("m", "", "p1", "r1", 0)
        cache.set("m", "", "p2", "r2", 0)
        cache.set("m", "", "p3", "r3", 0)  # 应淘汰最老的 p1
        assert cache.get("m", "", "p1", 0) is None
        assert cache.get("m", "", "p2", 0) == "r2"

    def test_cache_clear(self):
        """清空缓存"""
        from core.llm_cache import LLMCache

        cache = LLMCache(maxsize=10, ttl=60)
        cache.set("m", "", "p", "r", 0)
        cache.clear()
        assert cache.get("m", "", "p", 0) is None


class TestAppError:
    """Q-04: 异常处理标准化"""

    def test_app_error_to_dict(self):
        """AppError 序列化为 dict"""
        from core.errors import ValidationError

        err = ValidationError("参数无效")
        d = err.to_dict()
        assert d["error"] == "VALIDATION_ERROR"
        assert d["detail"] == "参数无效"

    def test_pipeline_not_found(self):
        """PipelineNotFoundError 状态码"""
        from core.errors import PipelineNotFoundError

        err = PipelineNotFoundError("abc123")
        assert err.status_code == 404
        assert err.error_code == "PIPELINE_NOT_FOUND"

    def test_llm_unavailable(self):
        """LLMUnavailableError 状态码"""
        from core.errors import LLMUnavailableError

        err = LLMUnavailableError()
        assert err.status_code == 503

    def test_concurrency_limit(self):
        """ConcurrencyLimitError 状态码"""
        from core.errors import ConcurrencyLimitError

        err = ConcurrencyLimitError()
        assert err.status_code == 429

    def test_error_registry(self):
        """错误码注册表完整性"""
        from core.errors import ERROR_REGISTRY

        assert "PIPELINE_NOT_FOUND" in ERROR_REGISTRY
        assert "LLM_TIMEOUT" in ERROR_REGISTRY
        assert "VALIDATION_ERROR" in ERROR_REGISTRY


class TestLogger:
    """A-01: 结构化日志"""

    def test_get_logger_returns_logger(self):
        """get_logger 返回可用日志器"""
        from core.logger import get_logger

        logger = get_logger("test-module")
        assert logger is not None
        logger.info("test_event", key="value")

    def test_print_logger_fallback(self):
        """_PrintLogger 降级日志器"""
        from core.logger import _PrintLogger

        pl = _PrintLogger("fallback")
        pl.info("test")
        pl.warning("warn test")
        pl.error("error test")


class TestMultiTenant:
    """A-03: 多租户支持"""

    def test_tenant_context_set_get(self):
        """租户上下文设置和获取"""
        from core.multi_tenant import (
            TenantContext,
            get_current_tenant,
            reset_tenant_context,
            set_tenant_context,
        )

        ctx = TenantContext(tenant_id="t1", tenant_name="租户1")
        token = set_tenant_context(ctx)
        current = get_current_tenant()
        assert current is not None
        assert current.tenant_id == "t1"
        reset_tenant_context(token)
        assert get_current_tenant() is None

    def test_require_tenant_id_default(self):
        """无上下文时返回 default"""
        from core.multi_tenant import require_tenant_id

        assert require_tenant_id() == "default"

    def test_tenant_manager_create(self):
        """租户管理器创建租户"""
        from core.multi_tenant import TenantManager

        mgr = TenantManager()
        tenant = mgr.create_tenant("测试租户")
        assert tenant.name == "测试租户"
        assert len(tenant.id) > 0
        assert mgr.get_tenant(tenant.id) is not None

    def test_tenant_manager_suspend(self):
        """租户停用"""
        from core.multi_tenant import TenantManager

        mgr = TenantManager()
        tenant = mgr.create_tenant("待停用")
        assert mgr.suspend_tenant(tenant.id) is True
        suspended = mgr.get_tenant(tenant.id)
        assert suspended is not None
        assert suspended.status == "suspended"

    def test_tenant_concurrency_check(self):
        """并发配额检查"""
        from core.multi_tenant import TenantManager

        mgr = TenantManager()
        tenant = mgr.create_tenant("限流测试", max_concurrent=2)
        assert mgr.check_concurrency(tenant.id, 1) is True
        assert mgr.check_concurrency(tenant.id, 2) is False

    def test_default_tenant_cannot_delete(self):
        """默认租户不可删除"""
        from core.multi_tenant import TenantManager

        mgr = TenantManager()
        assert mgr.delete_tenant("default") is False


class TestCSRFMiddleware:
    """S-02: CSRF 防护中间件"""

    def test_csrf_token_generation(self):
        """CSRF Token 生成"""
        from web.middleware.csrf import generate_csrf_token

        token1 = generate_csrf_token()
        token2 = generate_csrf_token()
        assert len(token1) > 20
        assert token1 != token2  # 每次生成不同
