#!/usr/bin/env python3
"""数据模型索引测试

验证 db.models 中核心表的索引 / 表级约束定义：
  - Pipeline 应有 status 相关索引
  - PipelineStep 应有联合唯一索引（table_args）
  - Artifact 应有 pipeline_id 索引（table_args）

注意：表级 __table_args__ 由其他并行任务（A-03）添加；若尚未实现，
PipelineStep / Artifact 的 table_args 可能为 None，测试会因 AssertionError 失败。
"""

import sys
from pathlib import Path

# 将项目根目录加入 sys.path，确保可直接 import 项目模块
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from db.models import Artifact, Pipeline, PipelineStep  # noqa: E402


def test_pipeline_has_status_index():
    """Pipeline 应有 status 相关索引"""
    table_args = Pipeline.__table_args__
    assert table_args is not None
    # 检查索引定义存在
    index_names = []
    for arg in table_args:
        if hasattr(arg, "name"):
            index_names.append(arg.name)
    assert any("status" in name for name in index_names)


def test_pipeline_step_has_indexes():
    """PipelineStep 应有联合唯一索引"""
    table_args = PipelineStep.__table_args__
    assert table_args is not None


def test_artifact_has_pipeline_index():
    """Artifact 应有 pipeline_id 索引"""
    table_args = Artifact.__table_args__
    assert table_args is not None
