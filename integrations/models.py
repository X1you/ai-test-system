#!/usr/bin/env python3
"""
Canonical Model — 内部标准数据模型

所有外部平台的数据先转换为内部模型再流转。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TestCase:
    """内部标准用例模型 — 所有平台的公共最大公约集"""
    id: str                                          # 内部唯一 ID（TC-001）
    external_id: str = ""                            # 外部平台 ID（如 TestRail C123）
    title: str = ""
    module: str = ""                                 # 模块/Section
    feature: str = ""                                # 功能点
    priority: str = ""                               # P0/P1/P2
    dimension: str = ""                              # 正向/负向/边界/异常/性能/安全
    precondition: str = ""
    steps: List[str] = field(default_factory=list)   # 测试步骤
    test_data: str = ""
    expected_result: str = ""
    actual_result: str = ""                          # 实际执行结果
    status: str = ""                                 # passed/failed/blocked/skipped/pending
    tags: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    custom_fields: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestResult:
    """测试执行结果"""
    test_case_id: str
    external_id: str = ""
    status: str = ""                                 # passed/failed/blocked/skipped
    comment: str = ""
    duration: float = 0.0                            # 执行耗时（秒）
    executed_by: str = ""
    executed_at: str = ""
    defect_ids: List[str] = field(default_factory=list)


@dataclass
class TestRun:
    """测试运行（一次完整的测试轮次）"""
    id: str                                          # 内部运行 ID
    external_id: str = ""                            # 平台 Run ID
    name: str = ""
    total: int = 0
    passed: int = 0
    failed: int = 0
    blocked: int = 0
    skipped: int = 0
    started_at: str = ""
    completed_at: str = ""


@dataclass
class Defect:
    """缺陷信息"""
    id: str                                          # 内部缺陷 ID
    external_id: str = ""                            # 平台缺陷 ID（如 JIRA-123）
    title: str = ""
    severity: str = ""                               # critical/major/minor/trivial
    status: str = ""                                 # open/in_progress/resolved/closed
    linked_test_cases: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


@dataclass
class SyncResult:
    """同步结果"""
    sync_id: str                                     # 本次同步追踪 ID
    direction: str = ""                              # push/pull/bidirectional
    pushed: int = 0
    pulled: int = 0
    failed: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    mode: str = ""                                   # incremental/full
    # 以下字段为兼容旧接口
    success_count: int = 0
    success_ids: List[str] = field(default_factory=list)
    error_dict: Dict[str, str] = field(default_factory=dict)


@dataclass
class SyncLogEntry:
    """同步日志条目"""
    sync_id: str
    ts: str                                          # ISO 时间戳
    platform: str
    direction: str                                   # push/pull
    entity_type: str                                 # test_case/test_result/defect
    entity_id: str                                   # 内部 ID
    external_id: str = ""
    action: str = ""                                 # create/update/delete/skip
    status: str = ""                                 # ok/error
    error: str = ""
    detail: str = ""
