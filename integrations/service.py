#!/usr/bin/env python3
"""
Integration Service — 集成服务层

独立服务，负责：
  - 管理多个平台适配器生命周期
  - 提供 RESTful API 统一访问所有外部平台
  - 双向增量/全量同步引擎
  - 同步日志与错误处理
  - OAuth2/API-Key 认证管理

数据模型转换：
  外部平台数据 ←→ Canonical Model（内部标准模型）
"""

import hashlib
import hmac
import json
import logging
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from integrations.base import AdapterConfig, BaseAdapter
from integrations.field_mapper import FieldMapper
from integrations.models import SyncLogEntry, TestCase, TestResult
from integrations.registry import AdapterRegistry

logger = logging.getLogger("ai-test-system.integrations")


# ═══════════════════════════════════════════════════════════════
# 认证管理器 — OAuth2 / API-Key / Basic Auth
# ═══════════════════════════════════════════════════════════════

class AuthManager:
    """认证管理器 — 支持多种认证方式

    线程安全的令牌存储，支持 OAuth2 令牌和 API Key 两种类型。
    所有方法都是 classmethod，操作类级别的 ``_tokens`` 字典。
    """

    _lock = threading.RLock()
    _tokens: dict[str, dict[str, Any]] = {}

    @classmethod
    def store_oauth_token(
        cls,
        platform: str,
        access_token: str,
        refresh_token: str = "",
        expires_at: int | None = None,
    ) -> str:
        """存储 OAuth2 令牌，返回 token_id"""
        with cls._lock:
            token_id = hashlib.sha256(
                f"{platform}:{access_token}".encode()
            ).hexdigest()[:16]
            cls._tokens[token_id] = {
                "platform": platform,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "created_at": datetime.now().isoformat(),
            }
            logger.info(f"OAuth token stored for {platform} (id={token_id})")
            return token_id

    @classmethod
    def store_api_key(
        cls, platform: str, api_key: str, extra: dict[str, Any] | None = None
    ) -> str:
        """存储 API Key，返回 key_id"""
        with cls._lock:
            key_id = hashlib.sha256(
                f"{platform}:{api_key}".encode()
            ).hexdigest()[:16]
            cls._tokens[key_id] = {
                "platform": platform,
                "type": "api_key",
                "api_key": api_key,
                "extra": extra or {},
                "created_at": datetime.now().isoformat(),
            }
            logger.info(f"API key stored for {platform} (id={key_id})")
            return key_id

    @classmethod
    def get_token(cls, token_id: str) -> dict[str, Any] | None:
        """获取令牌"""
        with cls._lock:
            return cls._tokens.get(token_id)

    @classmethod
    def revoke_token(cls, token_id: str) -> bool:
        """撤销令牌"""
        with cls._lock:
            if token_id in cls._tokens:
                del cls._tokens[token_id]
                logger.info(f"Token revoked (id={token_id})")
                return True
            return False

    @classmethod
    def validate_signature(
        cls, platform: str, body: bytes, signature: str, secret: str
    ) -> bool:
        """验证 HMAC-SHA256 签名"""
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


# ═══════════════════════════════════════════════════════════════
# 简化版 SyncResult — 兼容旧接口
# ═══════════════════════════════════════════════════════════════

@dataclass
class SimpleSyncResult:
    """简化版同步结果 — 用于 API 响应和引擎内部传递"""
    success_count: int = 0
    success_ids: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
# 同步引擎 — 双向增量/全量同步
# ═══════════════════════════════════════════════════════════════

class SyncEngine:
    """同步引擎 — 管理双向数据流

    包装 BaseAdapter，提供增量/全量同步、日志记录和结果转换。
    """

    def __init__(self, adapter: BaseAdapter, platform: str):
        self.adapter = adapter
        self.platform = platform
        self.log: list[SyncLogEntry] = []

    def _log(
        self,
        level: str,
        message: str,
        entity_type: str = "test_case",
        entity_id: str = "",
        external_id: str = "",
        direction: str = "push",
        details: dict[str, Any] | None = None,
    ) -> None:
        """记录同步日志（内存存储 + logger 输出）"""
        entry = SyncLogEntry(
            sync_id=str(uuid.uuid4())[:8],
            ts=datetime.now().isoformat(),
            platform=self.platform,
            direction=direction,
            entity_type=entity_type,
            entity_id=entity_id,
            external_id=external_id,
            action="sync",
            status=level,
            error=message if level == "error" else "",
            detail=json.dumps(details, ensure_ascii=False) if details else "",
        )
        self.log.append(entry)
        if level == "error":
            logger.error(f"[{self.platform}] {message}", extra=details or {})
        elif level == "warn":
            logger.warning(f"[{self.platform}] {message}", extra=details or {})

    def push_test_cases_incremental(
        self, cases: list[TestCase], last_sync: str | None = None
    ) -> SimpleSyncResult:
        """增量推送用例（仅推送 updated_at > last_sync 的用例）"""
        self._log("info", f"开始增量推送用例，总数={len(cases)}")

        # 过滤：仅同步新增或修改的用例
        if last_sync:
            filtered = [c for c in cases if c.updated_at and c.updated_at > last_sync]
        else:
            filtered = cases

        self._log("info", f"过滤后需推送的用例数={len(filtered)}")

        if not filtered:
            return SimpleSyncResult()

        # 调用适配器（返回完整 SyncResult）
        full_result = self.adapter.push_test_cases(filtered)

        result = SimpleSyncResult(
            success_count=full_result.pushed,
            success_ids=[c.id for c in filtered],
            errors={},
        )

        # 记录逐条日志
        for i, case in enumerate(filtered):
            if i < full_result.pushed:
                self._log(
                    "ok", "推送成功",
                    entity_id=case.id, external_id=case.external_id or "",
                )
            elif i < full_result.pushed + full_result.failed:
                idx = min(i - full_result.pushed, len(full_result.errors) - 1)
                err = full_result.errors[idx] if full_result.errors else "unknown"
                self._log("error", f"推送失败: {err}", entity_id=case.id)

        return result

    def pull_test_cases_incremental(
        self, filters: dict[str, Any] | None = None, last_sync: str | None = None
    ) -> SimpleSyncResult:
        """增量拉取用例"""
        self._log("info", "开始增量拉取用例")

        pull_filters = filters or {}
        if last_sync:
            pull_filters["updated_after"] = last_sync

        try:
            cases = self.adapter.pull_test_cases(pull_filters)
            self._log("ok", f"拉取成功，用例数={len(cases)}")
            return SimpleSyncResult(
                success_count=len(cases),
                success_ids=[c.id for c in cases],
            )
        except Exception as e:
            self._log("error", f"拉取失败: {e}")
            return SimpleSyncResult(errors={"pull": str(e)})

    def push_test_results(
        self, run_id: str, results: list[TestResult]
    ) -> SimpleSyncResult:
        """推送执行结果"""
        self._log("info", f"开始推送执行结果，run_id={run_id}，结果数={len(results)}")

        full_result = self.adapter.push_test_results(run_id, results)

        result = SimpleSyncResult(
            success_count=full_result.pushed,
            success_ids=[r.test_case_id for r in results],
        )

        for i, res in enumerate(results):
            if i < full_result.pushed:
                self._log(
                    "ok", "结果推送成功",
                    entity_type="test_result", entity_id=res.test_case_id,
                )

        return result

    def get_sync_log(self, limit: int = 100) -> list[dict[str, Any]]:
        """获取同步日志（最近 limit 条）"""
        return [asdict(entry) for entry in self.log[-limit:]]


# ═══════════════════════════════════════════════════════════════
# Integration Service — 主服务类（单例）
# ═══════════════════════════════════════════════════════════════

class IntegrationService:
    """集成服务 — 统一入口管理所有平台集成（线程安全单例）"""

    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._engines: dict[str, SyncEngine] = {}
        self._field_mappers: dict[str, FieldMapper] = {}

        # 自动发现适配器
        AdapterRegistry.auto_discover()
        logger.info(
            f"IntegrationService 初始化完成，已注册平台: "
            f"{AdapterRegistry.list_platforms()}"
        )

    def get_engine(self, platform: str, config: AdapterConfig) -> SyncEngine:
        """获取或创建同步引擎"""
        if platform not in self._engines:
            adapter = AdapterRegistry.get_adapter(platform, config)

            # 注入 FieldMapper
            if config.field_mapping_path:
                mapper = FieldMapper.load(config.field_mapping_path)
            else:
                mapper = FieldMapper()  # 使用默认映射

            self._field_mappers[platform] = mapper
            self._engines[platform] = SyncEngine(adapter, platform)

            logger.info(f"创建同步引擎: {platform}")

        return self._engines[platform]

    def list_platforms(self) -> list[str]:
        """列出已注册的平台"""
        return AdapterRegistry.list_platforms()

    def validate_config(self, platform: str, config: AdapterConfig) -> bool:
        """验证配置是否有效（尝试创建适配器并健康检查）"""
        try:
            adapter = AdapterRegistry.get_adapter(platform, config)
            return adapter.health_check()
        except Exception as e:
            logger.warning(f"配置验证失败 ({platform}): {e}")
            return False


# ═══════════════════════════════════════════════════════════════
# RESTful API 端点（挂载到 FastAPI）
# ═══════════════════════════════════════════════════════════════

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


# ─── 请求/响应模型 ───

class TestCaseCreate(BaseModel):
    """创建用例请求"""
    platform: str = Field(..., description="目标平台")
    cases: list[dict[str, Any]] = Field(..., description="用例列表（Canonical Model 格式）")
    incremental: bool = Field(False, description="是否增量同步")
    last_sync: str | None = Field(None, description="上次同步时间（增量模式）")


class SyncResultResponse(BaseModel):
    """同步结果响应"""
    success_count: int
    success_ids: list[str]
    errors: dict[str, str]
    log: list[dict[str, Any]]


class ConfigValidateRequest(BaseModel):
    """配置验证请求"""
    platform: str = Field(..., description="平台名称")
    base_url: str = Field(..., description="API 基础 URL")
    auth_type: str = Field(..., description="认证类型：api_key/oauth2/basic")
    api_key: str | None = Field(None, description="API Key")
    username: str | None = Field(None, description="用户名（Basic Auth）")
    password: str | None = Field(None, description="密码（Basic Auth）")


# ─── 依赖注入 ───

def get_integration_service() -> IntegrationService:
    """获取 IntegrationService 单例"""
    return IntegrationService()


# ─── API 辅助函数 ───

def _require_platform(platform: str, service: IntegrationService) -> None:
    """验证平台是否已注册，未注册时抛出 400"""
    if platform not in service.list_platforms():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的 Platform: {platform}",
        )


def _authenticate_engine(engine: SyncEngine, platform: str) -> None:
    """认证引擎，失败时抛出 401"""
    try:
        if not engine.adapter.authenticate():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"{platform} 认证失败",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"{platform} 认证异常: {e}",
        )


# ─── API 端点 ───

@router.get("/platforms")
async def list_platforms(
    service: IntegrationService = Depends(get_integration_service),
):
    """列出已注册的集成平台"""
    return {"platforms": service.list_platforms()}


@router.post("/validate-config")
async def validate_config(
    req: ConfigValidateRequest,
    service: IntegrationService = Depends(get_integration_service),
):
    """验证集成配置是否有效"""
    config = AdapterConfig(
        platform=req.platform,
        base_url=req.base_url,
        username=req.username or "",
        password=req.password or "",
        api_key=req.api_key or "",
    )

    if service.validate_config(req.platform, config):
        return {"status": "ok", "message": f"{req.platform} 连接成功"}
    return {"status": "error", "message": f"{req.platform} 连接失败"}


@router.post("/test-cases/push", response_model=SyncResultResponse)
async def push_test_cases(
    req: TestCaseCreate,
    service: IntegrationService = Depends(get_integration_service),
):
    """推送测试用例到外部平台

    支持：
      - 全量同步（incremental=False）
      - 增量同步（incremental=True + last_sync）
    """
    _require_platform(req.platform, service)

    config = _get_platform_config(req.platform)
    engine = service.get_engine(req.platform, config)
    _authenticate_engine(engine, req.platform)

    canonical_cases = [TestCase(**c) for c in req.cases]

    if req.incremental:
        result = engine.push_test_cases_incremental(canonical_cases, req.last_sync)
    else:
        full_result = engine.adapter.push_test_cases(canonical_cases)
        result = SimpleSyncResult(
            success_count=full_result.pushed,
            success_ids=[c.id for c in canonical_cases],
        )

    return SyncResultResponse(
        success_count=result.success_count,
        success_ids=result.success_ids,
        errors=result.errors,
        log=engine.get_sync_log(limit=10),
    )


@router.get("/test-cases/pull")
async def pull_test_cases(
    platform: str,
    incremental: bool = False,
    last_sync: str | None = None,
    filters: str | None = None,
    service: IntegrationService = Depends(get_integration_service),
):
    """从外部平台拉取测试用例

    支持：
      - 全量拉取
      - 增量拉取（根据 last_sync 过滤）
    """
    _require_platform(platform, service)

    config = _get_platform_config(platform)
    engine = service.get_engine(platform, config)

    filter_dict = json.loads(filters) if filters else {}

    if incremental:
        result = engine.pull_test_cases_incremental(filter_dict, last_sync)
    else:
        cases = engine.adapter.pull_test_cases(filter_dict)
        result = SimpleSyncResult(
            success_count=len(cases),
            success_ids=[c.id for c in cases],
        )

    return {
        "success_count": result.success_count,
        "success_ids": result.success_ids,
        "errors": result.errors,
        "cases": [asdict(c) for c in engine.adapter.pull_test_cases(filter_dict)],
        "log": engine.get_sync_log(limit=10),
    }


@router.post("/test-results/push", response_model=SyncResultResponse)
async def push_test_results(
    platform: str,
    run_id: str,
    results: list[dict[str, Any]],
    service: IntegrationService = Depends(get_integration_service),
):
    """推送测试执行结果"""
    _require_platform(platform, service)

    config = _get_platform_config(platform)
    engine = service.get_engine(platform, config)

    canonical_results = [TestResult(**r) for r in results]
    result = engine.push_test_results(run_id, canonical_results)

    return SyncResultResponse(
        success_count=result.success_count,
        success_ids=result.success_ids,
        errors=result.errors,
        log=engine.get_sync_log(limit=10),
    )


# ─── 平台配置 ───

def _get_platform_config(platform: str) -> AdapterConfig:
    """从环境变量获取平台配置

    实际应用中应从数据库或用户配置读取。
    环境变量命名规则：INTEGRATION_{PLATFORM}_{FIELD}
    """
    env_prefix = f"INTEGRATION_{platform.upper()}_"

    # 默认值：mock_platform 提供测试用的有效配置
    defaults: dict[str, str] = {}
    if platform == "mock_platform":
        defaults = {
            "BASE_URL": "https://test.example.com",
            "API_KEY": "valid_key",
        }

    return AdapterConfig(
        platform=platform,
        base_url=os.environ.get(f"{env_prefix}BASE_URL", defaults.get("BASE_URL", "")),
        api_key=os.environ.get(f"{env_prefix}API_KEY", defaults.get("API_KEY", "")),
        username=os.environ.get(f"{env_prefix}USERNAME", ""),
        password=os.environ.get(f"{env_prefix}PASSWORD", ""),
    )
