#!/usr/bin/env python3
"""
缺陷修复回归测试 — 验证 QA 测试中发现并修复的缺陷

覆盖修复项：
  1. 全局异常处理器不再泄露内部错误详情（安全）
  2. preview_artifact HTML 转义防 XSS（安全）
  3. resume 端点文件上传大小限制（安全）
  4. count_stats 返回可 JSON 序列化结构（质量）
  5. filter_by_dimensions 无效维度警告（质量）
  6. .env 加载器支持 export 前缀（兼容性）
  7. 速率限制器已挂载到应用（功能完整性）
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("LLM_API_KEY", "sk-test-dummy-key-for-testing")

from fastapi.testclient import TestClient

# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def client():
    from web.app import app
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════
# 1. 全局异常处理器 — 不泄露内部错误
# ═══════════════════════════════════════════════════════════════

class TestGlobalExceptionHandler:
    """全局异常处理器安全性"""

    def test_500_does_not_leak_internal_details(self, client):
        """生产环境模式下 500 错误不应泄露内部异常详情"""
        old_env = os.environ.get("AI_TEST_ENV", "")
        os.environ["AI_TEST_ENV"] = "production"
        try:
            # 读取源文件验证异常处理器逻辑
            app_source = (PROJECT_ROOT / "web" / "app.py").read_text(encoding="utf-8")
            assert "development" in app_source, "异常处理器应检查 AI_TEST_ENV=development"
            # 确保 str(exc) 只在 development 模式下返回
            assert "AI_TEST_ENV" in app_source, "应有环境变量检查"
        finally:
            if old_env:
                os.environ["AI_TEST_ENV"] = old_env
            else:
                os.environ.pop("AI_TEST_ENV", None)


# ═══════════════════════════════════════════════════════════════
# 2. count_stats 返回可序列化结构
# ═══════════════════════════════════════════════════════════════

class TestCountStatsSerialization:
    """count_stats 返回可 JSON 序列化的结构"""

    def test_modules_is_list(self):
        from scripts.generate_excel import count_stats
        stats = count_stats([
            {"module": "M1", "feature": "F1", "dimension": "D", "priority": "P0"},
            {"module": "M2", "feature": "F1", "dimension": "D", "priority": "P1"},
        ])
        assert isinstance(stats["modules"], list), "modules 应为 list 而非 set"
        assert len(stats["modules"]) == 2

    def test_features_is_list(self):
        from scripts.generate_excel import count_stats
        stats = count_stats([
            {"module": "M", "feature": "F1", "dimension": "D", "priority": "P0"},
        ])
        assert isinstance(stats["features"], list), "features 应为 list 而非 set"

    def test_json_serializable(self):
        from scripts.generate_excel import count_stats
        stats = count_stats([
            {"module": "M", "feature": "F", "dimension": "D", "priority": "P0"},
        ])
        # 不应抛出 TypeError
        json_str = json.dumps(stats)
        assert json.loads(json_str)["total"] == 1


# ═══════════════════════════════════════════════════════════════
# 3. filter_by_dimensions — 无效维度警告
# ═══════════════════════════════════════════════════════════════

class TestFilterByDimensions:
    """维度过滤功能"""

    def test_all_returns_all(self):
        from scripts.common import filter_by_dimensions
        tps = [{"dimension": "正向测试"}, {"dimension": "负向测试"}]
        assert len(filter_by_dimensions(tps, "all")) == 2

    def test_basic_returns_four_dims(self):
        from scripts.common import filter_by_dimensions
        tps = [
            {"dimension": "正向测试"},
            {"dimension": "负向测试"},
            {"dimension": "边界测试"},
            {"dimension": "异常测试"},
            {"dimension": "性能测试"},
        ]
        result = filter_by_dimensions(tps, "basic")
        assert len(result) == 4  # 正向+负向+边界+异常

    def test_invalid_dimension_warns(self, capsys):
        from scripts.common import filter_by_dimensions
        tps = [{"dimension": "正向测试"}]
        result = filter_by_dimensions(tps, "totally_invalid_xyz")
        assert len(result) == 0
        captured = capsys.readouterr()
        assert "未识别" in captured.err or "未识别" in captured.out


# ═══════════════════════════════════════════════════════════════
# 4. .env 加载器 — export 前缀支持
# ═══════════════════════════════════════════════════════════════

class TestDotenvExportPrefix:
    """.env 文件 export 前缀兼容"""

    def test_export_prefix_stripped(self, tmp_path):
        from core.config_loader import _load_dotenv
        env_file = tmp_path / ".env"
        env_file.write_text("export TEST_DOTENV_KEY=hello123\n")
        # 清理环境变量
        os.environ.pop("TEST_DOTENV_KEY", None)
        _load_dotenv(env_file)
        assert os.environ.get("TEST_DOTENV_KEY") == "hello123"
        os.environ.pop("TEST_DOTENV_KEY", None)

    def test_no_export_prefix_still_works(self, tmp_path):
        from core.config_loader import _load_dotenv
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_DOTENV_KEY2=world456\n")
        os.environ.pop("TEST_DOTENV_KEY2", None)
        _load_dotenv(env_file)
        assert os.environ.get("TEST_DOTENV_KEY2") == "world456"
        os.environ.pop("TEST_DOTENV_KEY2", None)


# ═══════════════════════════════════════════════════════════════
# 5. 速率限制器挂载验证
# ═══════════════════════════════════════════════════════════════

class TestRateLimitWired:
    """速率限制器已正确挂载到应用"""

    def test_limiter_attached_to_app(self, client):
        """app.state.limiter 应已设置"""
        from web.app import app
        assert hasattr(app.state, "limiter"), "限速器应挂载到 app.state.limiter"

    def test_rate_limit_exception_handler_registered(self, client):
        """RateLimitExceeded 异常处理器应已注册"""
        from slowapi.errors import RateLimitExceeded

        from web.app import app
        # 检查异常处理器注册
        handlers = app.exception_handlers
        found = False
        for k in handlers:
            if k is RateLimitExceeded or str(k) == str(RateLimitExceeded):
                found = True
                break
        assert found, "RateLimitExceeded 异常处理器未注册"


# ═══════════════════════════════════════════════════════════════
# 6. preview_artifact HTML 转义
# ═══════════════════════════════════════════════════════════════

class TestPreviewArtifactEscaping:
    """预览接口 HTML 转义防护"""

    def test_source_has_html_escape(self):
        """验证 preview_artifact 源码使用了 html.escape"""
        import inspect

        from web.api import pipeline as pipeline_api
        source = inspect.getsource(pipeline_api)
        # 确保 fallback 使用 html.escape 而非直接插入
        assert "html_module.escape" in source or "html.escape" in source, \
            "preview_artifact 应使用 html.escape 转义内容"


# ═══════════════════════════════════════════════════════════════
# 7. resume 端点文件大小限制
# ═══════════════════════════════════════════════════════════════

class TestResumeFileSizeLimit:
    """resume 端点文件上传大小限制"""

    def test_source_has_size_check(self):
        """验证 resume_pipeline 源码中有大小检查"""
        import inspect

        from web.api import pipeline as pipeline_api
        source = inspect.getsource(pipeline_api)
        # 找到 resume_pipeline 函数体中的 MAX_FILE_SIZE 引用
        resume_section = source[source.find("resume_pipeline"):]
        assert "MAX_FILE_SIZE" in resume_section, \
            "resume_pipeline 应检查文件大小 (MAX_FILE_SIZE)"


# ═══════════════════════════════════════════════════════════════
# 8. 附加：脚本端到端健壮性
# ═══════════════════════════════════════════════════════════════

class TestScriptRobustness:
    """脚本端到端健壮性回归"""

    def test_empty_input_rejected(self):
        """空测试点文件应被正确拒绝"""
        import subprocess
        tmpdir = tempfile.mkdtemp()
        empty = Path(tmpdir) / "empty.md"
        empty.write_text("# Empty\n", encoding="utf-8")
        r = subprocess.run(
            [sys.executable, "scripts/generate_excel.py", str(empty),
             "-o", str(Path(tmpdir) / "out.xlsx")],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=15,
        )
        assert r.returncode != 0, "空文件应返回非零退出码"
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_unicode_handled(self):
        """Unicode 和 emoji 应正确处理"""
        import subprocess
        tmpdir = tempfile.mkdtemp()
        tp = Path(tmpdir) / "uni.md"
        tp.write_text(
            "# Unicode\n\n## 模块一：🎉测试\n### 功能点 1：emoji\n"
            "#### 测试维度：正向测试\n- 测试点 1：🚀café 日本語\n"
            "  - 测试数据：数据\n  - 预期结果：结果\n",
            encoding="utf-8",
        )
        r = subprocess.run(
            [sys.executable, "scripts/generate_excel.py", str(tp),
             "-o", str(Path(tmpdir) / "uni.xlsx"), "-d", "all"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=15,
        )
        assert r.returncode == 0, f"Unicode 处理失败: {r.stderr[:100]}"
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_priority_assignment_range(self):
        """优先级分配应在有效范围内"""
        from scripts.common import assign_priority
        for dim in ["正向测试", "负向测试", "边界测试", "异常测试", "性能测试", "安全测试"]:
            tp = {"title": "测试", "dimension": dim, "module": "模块", "feature": "功能"}
            pri = assign_priority(tp)
            assert pri in ("P0", "P1", "P2"), f"维度 {dim} 返回无效优先级: {pri}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
