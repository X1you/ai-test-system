#!/usr/bin/env python3
"""
Phase 2 持久化层集成测试

验证：数据模型 CRUD → Repository → Pipeline 状态持久化 → 重启恢复
"""

import sys
from pathlib import Path

import pytest

# 设置项目根路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    """每个测试使用独立的临时数据库"""
    db_path = tmp_path / "test_app.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))

    # 重置 DB 引擎缓存
    from db.session import init_db, reset_engine
    reset_engine()
    init_db()

    yield

    reset_engine()


class TestModels:
    """数据模型测试"""

    def test_pipeline_create(self):
        """Pipeline 记录可创建"""
        from db.repository import PipelineRepository
        repo = PipelineRepository()
        p = repo.create_pipeline(
            pipeline_id="test-001",
            requirements_path="/tmp/req.md",
            mode="semi",
            output_dir="/tmp/output/test-001",
        )
        assert p.id == "test-001"
        assert p.status == "pending"
        assert p.tenant_id is None  # Track B 预留字段存在

    def test_pipeline_query(self):
        """Pipeline 可查询"""
        from db.repository import PipelineRepository
        repo = PipelineRepository()
        repo.create_pipeline(
            pipeline_id="test-002",
            requirements_path="/tmp/req.md",
            output_dir="/tmp/output/test-002",
        )
        p = repo.get_pipeline("test-002")
        assert p is not None
        assert p.requirements_path == "/tmp/req.md"

    def test_pipeline_not_found(self):
        """不存在的 Pipeline 返回 None"""
        from db.repository import PipelineRepository
        repo = PipelineRepository()
        assert repo.get_pipeline("nonexistent") is None


class TestRepository:
    """Repository CRUD 测试"""

    def test_update_status(self):
        """更新 Pipeline 状态"""
        from db.repository import PipelineRepository
        repo = PipelineRepository()
        repo.create_pipeline(
            pipeline_id="test-003",
            requirements_path="/tmp/req.md",
            output_dir="/tmp/output/test-003",
        )
        repo.update_pipeline_status("test-003", "running")
        p = repo.get_pipeline("test-003")
        assert p.status == "running"
        assert p.finished_at is None

        repo.update_pipeline_status("test-003", "completed")
        p = repo.get_pipeline("test-003")
        assert p.status == "completed"
        assert p.finished_at is not None

    def test_record_step(self):
        """记录步骤"""
        from db.repository import PipelineRepository
        repo = PipelineRepository()
        repo.create_pipeline(
            pipeline_id="test-004",
            requirements_path="/tmp/req.md",
            output_dir="/tmp/output/test-004",
        )

        repo.record_step("test-004", 1, "需求分析", "completed", "3 模块")
        repo.record_step("test-004", 2, "知识库检索", "completed", "命中 5 条")

        steps = repo.get_steps("test-004")
        assert len(steps) == 2
        assert steps[0].step_id == 1
        assert steps[0].status == "completed"
        assert steps[1].step_id == 2

        completed = repo.get_completed_step_ids("test-004")
        assert completed == [1, 2]

    def test_record_artifact(self):
        """记录产物"""
        from db.repository import PipelineRepository
        repo = PipelineRepository()
        repo.create_pipeline(
            pipeline_id="test-005",
            requirements_path="/tmp/req.md",
            output_dir="/tmp/output/test-005",
        )

        repo.record_artifact(
            "test-005", "testcases.xlsx", "测试用例", "xlsx", 10240
        )
        repo.record_artifact(
            "test-005", "test_report.md", "测试报告", "md", 4096
        )

        artifacts = repo.get_artifacts("test-005")
        assert len(artifacts) == 2
        assert artifacts[0].type == "xlsx"
        assert artifacts[0].size == 10240

    def test_list_pipelines(self):
        """列出 Pipeline"""
        from db.repository import PipelineRepository
        repo = PipelineRepository()
        for i in range(5):
            repo.create_pipeline(
                pipeline_id=f"list-{i:03d}",
                requirements_path="/tmp/req.md",
                output_dir=f"/tmp/output/list-{i:03d}",
            )
        pipelines = repo.list_pipelines(limit=3)
        assert len(pipelines) == 3

    def test_user_crud(self):
        """用户 CRUD"""
        from db.repository import PipelineRepository
        repo = PipelineRepository()
        repo.create_user("admin", "hash123", "admin", "api-key-001")
        user = repo.get_user_by_username("admin")
        assert user is not None
        assert user.role == "admin"
        assert user.api_key == "api-key-001"

        user_by_key = repo.get_user_by_api_key("api-key-001")
        assert user_by_key is not None
        assert user_by_key.username == "admin"


class TestRestartRecovery:
    """重启恢复测试 — 核心验收场景"""

    def test_pipeline_survives_engine_reset(self):
        """Pipeline 状态在引擎重置后（模拟重启）仍然保留"""
        from db.repository import PipelineRepository
        from db.session import init_db, reset_engine

        # 1. 创建 Pipeline 并记录步骤
        repo = PipelineRepository()
        repo.create_pipeline(
            pipeline_id="restart-001",
            requirements_path="/tmp/req.md",
            mode="auto",
            output_dir="/tmp/output/restart-001",
        )
        repo.update_pipeline_status("restart-001", "running")
        repo.record_step("restart-001", 1, "需求分析", "completed")
        repo.record_step("restart-001", 2, "知识库检索", "completed")

        # 2. 模拟重启 — 重置引擎缓存
        reset_engine()
        init_db()

        # 3. 验证数据仍然存在
        repo2 = PipelineRepository()
        p = repo2.get_pipeline("restart-001")
        assert p is not None
        assert p.status == "running"
        assert p.mode == "auto"

        steps = repo2.get_steps("restart-001")
        assert len(steps) == 2
        completed = repo2.get_completed_step_ids("restart-001")
        assert 1 in completed
        assert 2 in completed
