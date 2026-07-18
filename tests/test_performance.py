#!/usr/bin/env python3
"""
性能测试 — API 响应时间、并发性能、数据库性能

测试范围：
  - 页面加载时间
  - API 端点响应时间
  - 数据库操作性能
  - 并发请求处理
  - 文件上传性能
"""

import concurrent.futures
import io
import os
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("LLM_API_KEY", "«redacted:sk-…»")


class TestPageLoadPerformance:
    """页面加载性能"""

    def test_index_page_load_time(self, client):
        """首页加载时间 < 500ms"""
        start = time.time()
        resp = client.get("/")
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 0.5, f"首页加载时间 {elapsed:.3f}s > 0.5s"

    def test_login_page_load_time(self, client):
        """登录页加载时间 < 500ms"""
        start = time.time()
        resp = client.get("/login")
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 0.5, f"登录页加载时间 {elapsed:.3f}s > 0.5s"

    def test_pipelines_page_load_time(self, client):
        """Pipeline 列表页加载时间 < 500ms"""
        start = time.time()
        resp = client.get("/pipelines")
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 0.5, f"Pipeline 列表页加载时间 {elapsed:.3f}s > 0.5s"


class TestAPIResponseTime:
    """API 响应时间"""

    def test_health_endpoint_fast(self, client):
        """健康检查 < 100ms"""
        # 预热
        client.get("/health")

        start = time.time()
        resp = client.get("/health")
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 0.2, f"健康检查响应时间 {elapsed:.3f}s > 0.2s"

    def test_config_api_fast(self, client):
        """配置 API < 200ms"""
        start = time.time()
        resp = client.get("/api/config")
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 0.3, f"配置 API 响应时间 {elapsed:.3f}s > 0.3s"

    def test_pipeline_list_fast(self, client):
        """Pipeline 列表 < 200ms"""
        start = time.time()
        resp = client.get("/api/pipeline/list")
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 0.3, f"Pipeline 列表响应时间 {elapsed:.3f}s > 0.3s"

    def test_auth_api_fast(self, client):
        """认证 API 响应 < 200ms"""
        start = time.time()
        resp = client.post("/api/auth/login", json={
            "username": "test", "password": "test",
        })
        elapsed = time.time() - start
        assert resp.status_code in (200, 401)
        assert elapsed < 0.3, f"认证 API 响应时间 {elapsed:.3f}s > 0.3s"


class TestConcurrentRequests:
    """并发请求"""

    def test_concurrent_health_checks(self, client):
        """10 个并发健康检查请求"""
        def make_request():
            return client.get("/health")

        start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        elapsed = time.time() - start
        assert all(r.status_code == 200 for r in results)
        # 10 个并发请求应在 2 秒内完成
        assert elapsed < 2.0, f"10 并发健康检查耗时 {elapsed:.3f}s > 2.0s"

    def test_concurrent_config_api(self, client):
        """5 个并发配置 API 请求"""
        def make_request():
            return client.get("/api/config")

        start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        elapsed = time.time() - start
        assert all(r.status_code == 200 for r in results)
        assert elapsed < 2.0, f"5 并发配置 API 耗时 {elapsed:.3f}s > 2.0s"


class TestDatabasePerformance:
    """数据库性能"""

    @pytest.fixture(autouse=True)
    def isolated_db(self, monkeypatch, tmp_path):
        """每个测试使用独立的临时数据库"""
        db_path = tmp_path / "test_perf.db"
        monkeypatch.setenv("DATABASE_PATH", str(db_path))

        from db.session import init_db, reset_engine
        reset_engine()
        init_db()

        yield

        reset_engine()

    def test_bulk_insert_performance(self):
        """批量插入 100 条 Pipeline 记录 < 1s"""
        from db.repository import PipelineRepository

        repo = PipelineRepository()

        start = time.time()
        for i in range(100):
            repo.create_pipeline(
                pipeline_id=f"perf-{i:04d}",
                requirements_path="/tmp/req.md",
                output_dir=f"/tmp/output/perf-{i:04d}",
            )
        elapsed = time.time() - start

        assert elapsed < 1.0, f"100 条插入耗时 {elapsed:.3f}s > 1.0s"

    def test_query_performance(self):
        """查询 Pipeline 性能"""
        from db.repository import PipelineRepository

        repo = PipelineRepository()
        repo.create_pipeline(
            pipeline_id="query-test",
            requirements_path="/tmp/req.md",
            output_dir="/tmp/output/test",
        )

        start = time.time()
        for _ in range(50):
            p = repo.get_pipeline("query-test")
        elapsed = time.time() - start

        assert elapsed < 0.5, f"50 次查询耗时 {elapsed:.3f}s > 0.5s"

    def test_list_performance(self):
        """列表查询性能"""
        from db.repository import PipelineRepository

        repo = PipelineRepository()
        for i in range(50):
            repo.create_pipeline(
                pipeline_id=f"list-perf-{i:04d}",
                requirements_path="/tmp/req.md",
                output_dir=f"/tmp/output/list-perf-{i:04d}",
            )

        start = time.time()
        pipelines = repo.list_pipelines(limit=50)
        elapsed = time.time() - start

        assert len(pipelines) == 50
        assert elapsed < 0.3, f"50 条列表查询耗时 {elapsed:.3f}s > 0.3s"


class TestFileUploadPerformance:
    """文件上传性能"""

    def test_small_file_upload(self, client):
        """小文件上传 < 500ms"""
        content = io.BytesIO(b"# Test requirements\n- Feature 1\n- Feature 2\n")
        start = time.time()
        resp = client.post(
            "/api/pipeline/start",
            files={"file": ("test.md", content, "text/markdown")},
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        elapsed = time.time() - start
        assert resp.status_code == 201
        assert elapsed < 0.5, f"小文件上传耗时 {elapsed:.3f}s > 0.5s"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
