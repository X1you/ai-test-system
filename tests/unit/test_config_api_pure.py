#!/usr/bin/env python3
"""
web/api/config.py 纯函数单元测试。

覆盖 _patch_yaml_file：行级 YAML 键值替换，保留注释和原始格式。
这是 PUT /api/config 的核心逻辑，直接操作用户的 config.yaml 文件，
任何 bug 都会破坏用户配置，因此需要严格测试。

测试用 tmp_path 隔离，不触碰真实 config.yaml。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


class TestPatchYamlFile:
    """测试 _patch_yaml_file 行级替换"""

    def _patch(self, tmp_path):
        from web.api.config import _patch_yaml_file

        return _patch_yaml_file

    def test_update_existing_key(self, tmp_path):
        """替换已存在的键值，保留缩进"""
        from web.api.config import _patch_yaml_file

        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "llm:\n  provider: deepseek\n  model: deepseek-chat\n",
            encoding="utf-8",
        )
        _patch_yaml_file(cfg, {"llm": {"model": "deepseek-v3"}})
        content = cfg.read_text(encoding="utf-8")
        assert "model: deepseek-v3" in content
        # 未更新的键保留
        assert "provider: deepseek" in content

    def test_update_multiple_keys_same_section(self, tmp_path):
        """同段多键同时更新"""
        from web.api.config import _patch_yaml_file

        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "llm:\n  provider: deepseek\n  model: old\n  temperature: 0.3\n",
            encoding="utf-8",
        )
        _patch_yaml_file(cfg, {"llm": {"model": "new", "temperature": 0.7}})
        content = cfg.read_text(encoding="utf-8")
        assert "model: new" in content
        assert "temperature: 0.7" in content
        assert "provider: deepseek" in content

    def test_preserve_comments(self, tmp_path):
        """保留注释行（不误改注释里的内容）"""
        from web.api.config import _patch_yaml_file

        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "llm:\n  # 这是 provider 注释\n  provider: deepseek\n",
            encoding="utf-8",
        )
        _patch_yaml_file(cfg, {"llm": {"provider": "glm"}})
        content = cfg.read_text(encoding="utf-8")
        assert "# 这是 provider 注释" in content
        assert "provider: glm" in content

    def test_bool_value_formatted(self, tmp_path):
        """布尔值格式化为 true/false（非 Python 的 True/False）"""
        from web.api.config import _patch_yaml_file

        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "pipeline:\n  self_check: false\n",
            encoding="utf-8",
        )
        _patch_yaml_file(cfg, {"pipeline": {"self_check": True}})
        content = cfg.read_text(encoding="utf-8")
        assert "self_check: true" in content
        # 不应出现 Python 风格的 True
        assert "True" not in content

    def test_append_new_section(self, tmp_path):
        """更新段在文件中不存在时，末尾追加全新段"""
        from web.api.config import _patch_yaml_file

        cfg = tmp_path / "config.yaml"
        cfg.write_text("llm:\n  provider: deepseek\n", encoding="utf-8")
        _patch_yaml_file(cfg, {"output": {"format": "excel"}})
        content = cfg.read_text(encoding="utf-8")
        assert "output:" in content
        assert "format: excel" in content

    def test_preserves_other_sections(self, tmp_path):
        """更新 A 段不影响 B 段"""
        from web.api.config import _patch_yaml_file

        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "llm:\n  provider: deepseek\n\npipeline:\n  default_mode: semi\n",
            encoding="utf-8",
        )
        _patch_yaml_file(cfg, {"llm": {"provider": "glm"}})
        content = cfg.read_text(encoding="utf-8")
        assert "provider: glm" in content
        assert "default_mode: semi" in content
