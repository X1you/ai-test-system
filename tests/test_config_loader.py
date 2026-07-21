#!/usr/bin/env python3
"""
配置加载器完整测试 — 覆盖所有加载路径、边界条件和异常场景

测试范围：
  - 默认配置加载
  - YAML 文件加载与合并
  - .env 变量加载
  - ${VAR} 变量插值
  - 深度合并逻辑
  - 路径展开 (~)
  - 配置校验
  - 边界条件：空文件、格式错误、缺失字段
"""

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestDefaultConfig:
    """默认配置测试"""

    def test_default_config_has_all_sections(self):
        """默认配置包含所有必需段"""
        from core.config_loader import DEFAULT_CONFIG

        assert "llm" in DEFAULT_CONFIG
        assert "pipeline" in DEFAULT_CONFIG
        assert "output" in DEFAULT_CONFIG
        assert "integrations" in DEFAULT_CONFIG

    def test_default_llm_config(self):
        """默认 LLM 配置包含所有必需字段"""
        from core.config_loader import DEFAULT_CONFIG

        llm = DEFAULT_CONFIG["llm"]
        assert "provider" in llm
        assert "api_key" in llm
        assert "base_url" in llm
        assert "model" in llm
        assert "temperature" in llm
        assert "max_tokens" in llm
        assert "timeout" in llm
        assert "retry" in llm

    def test_load_config_without_yaml(self, monkeypatch, tmp_path):
        """无 config.yaml 时使用默认配置"""
        from core.config_loader import load_config

        # 指向不存在的配置文件
        cfg = load_config(str(tmp_path / "nonexistent.yaml"))
        assert cfg["llm"]["provider"] == "deepseek"
        assert cfg["pipeline"]["default_mode"] == "semi"

    def test_load_config_no_args(self):
        """无参数调用 load_config 使用默认 config.yaml"""
        from core.config_loader import load_config

        cfg = load_config()
        assert "llm" in cfg
        assert "pipeline" in cfg


class TestYAMLConfig:
    """YAML 配置文件加载测试"""

    def test_load_custom_yaml(self, tmp_path, monkeypatch):
        """加载自定义 YAML 配置"""
        from core.config_loader import load_config

        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text("""
llm:
  provider: openai
  model: gpt-4
  api_key: sk-test-key
  temperature: 0.5
pipeline:
  default_mode: auto
""", encoding="utf-8")

        monkeypatch.setenv("LLM_API_KEY", "sk-env-key")
        cfg = load_config(str(yaml_path))
        assert cfg["llm"]["provider"] == "openai"
        assert cfg["llm"]["model"] == "gpt-4"
        assert cfg["llm"]["temperature"] == 0.5
        assert cfg["pipeline"]["default_mode"] == "auto"
        # 未覆盖的字段使用默认值
        assert cfg["llm"]["max_tokens"] == 8192

    def test_partial_override(self, tmp_path, monkeypatch):
        """部分覆盖 — 只覆盖指定字段，其余保持默认"""
        from core.config_loader import load_config

        yaml_path = tmp_path / "partial.yaml"
        yaml_path.write_text("""
llm:
  model: custom-model
""", encoding="utf-8")

        cfg = load_config(str(yaml_path))
        assert cfg["llm"]["model"] == "custom-model"
        # 其余字段保持默认
        assert cfg["llm"]["provider"] == "deepseek"
        assert cfg["llm"]["temperature"] == 0.3

    def test_empty_yaml(self, tmp_path, monkeypatch):
        """空 YAML 文件 — 使用默认配置"""
        from core.config_loader import load_config

        yaml_path = tmp_path / "empty.yaml"
        yaml_path.write_text("", encoding="utf-8")

        cfg = load_config(str(yaml_path))
        assert cfg["llm"]["provider"] == "deepseek"

    def test_malformed_yaml(self, tmp_path, monkeypatch):
        """格式错误的 YAML — 不崩溃，使用默认配置"""
        from core.config_loader import load_config

        yaml_path = tmp_path / "bad.yaml"
        yaml_path.write_text("llm: [unclosed\n", encoding="utf-8")

        cfg = load_config(str(yaml_path))
        assert cfg["llm"]["provider"] == "deepseek"


class TestEnvVarExpansion:
    """环境变量插值测试"""

    def test_simple_variable_expansion(self, tmp_path, monkeypatch):
        """${VAR_NAME} 替换为环境变量值"""
        from core.config_loader import load_config

        monkeypatch.setenv("MY_API_KEY", "sk-my-secret-key")
        yaml_path = tmp_path / "var.yaml"
        yaml_path.write_text("""
llm:
  api_key: ${MY_API_KEY}
""", encoding="utf-8")

        cfg = load_config(str(yaml_path))
        assert cfg["llm"]["api_key"] == "sk-my-secret-key"

    def test_missing_env_var(self, tmp_path, monkeypatch):
        """未设置的环境变量替换为空字符串"""
        from core.config_loader import load_config

        # 确保环境变量不存在
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)

        yaml_path = tmp_path / "missing_var.yaml"
        yaml_path.write_text("""
llm:
  api_key: ${NONEXISTENT_VAR}
""", encoding="utf-8")

        cfg = load_config(str(yaml_path))
        assert cfg["llm"]["api_key"] == ""

    def test_multiple_variables(self, tmp_path, monkeypatch):
        """多个变量同时替换"""
        from core.config_loader import load_config

        monkeypatch.setenv("KEY", "my-key")
        monkeypatch.setenv("URL", "https://api.example.com")
        yaml_path = tmp_path / "multi_var.yaml"
        yaml_path.write_text("""
llm:
  api_key: ${KEY}
  base_url: ${URL}
""", encoding="utf-8")

        cfg = load_config(str(yaml_path))
        assert cfg["llm"]["api_key"] == "my-key"
        assert cfg["llm"]["base_url"] == "https://api.example.com"

    def test_env_var_in_nested_dict(self, tmp_path, monkeypatch):
        """嵌套字典中的变量替换"""
        from core.config_loader import load_config

        monkeypatch.setenv("VAULT_DIR", "/my/vault")
        yaml_path = tmp_path / "nested.yaml"
        yaml_path.write_text("""
knowledge_base:
  vault_path: ${VAULT_DIR}
""", encoding="utf-8")

        cfg = load_config(str(yaml_path))
        assert cfg["knowledge_base"]["vault_path"] == "/my/vault"

    def test_env_var_in_list(self, tmp_path, monkeypatch):
        """列表中的变量替换"""
        from core.config_loader import load_config

        monkeypatch.setenv("HOST1", "server1")
        monkeypatch.setenv("HOST2", "server2")
        yaml_path = tmp_path / "list_var.yaml"
        yaml_path.write_text("""
llm:
  fallback:
    - provider: backup1
      api_key: ${HOST1}
    - provider: backup2
      api_key: ${HOST2}
""", encoding="utf-8")

        cfg = load_config(str(yaml_path))
        fallbacks = cfg["llm"].get("fallback", [])
        assert len(fallbacks) == 2
        assert fallbacks[0]["api_key"] == "server1"
        assert fallbacks[1]["api_key"] == "server2"


class TestDotenvLoading:
    """.env 文件加载测试"""

    def test_dotenv_loads_variables(self, monkeypatch):
        """.env 文件中的变量被加载到环境"""
        from core.config_loader import _load_dotenv

        env_file = PROJECT_ROOT / ".env.test"
        env_file.write_text("TEST_VAR=hello_world\n", encoding="utf-8")

        try:
            monkeypatch.delenv("TEST_VAR", raising=False)
            _load_dotenv(env_file)
            assert os.environ.get("TEST_VAR") == "hello_world"
        finally:
            env_file.unlink(missing_ok=True)

    def test_dotenv_does_not_override_existing(self, monkeypatch):
        """.env 不覆盖已存在的环境变量"""
        from core.config_loader import _load_dotenv

        monkeypatch.setenv("EXISTING_VAR", "original_value")

        env_file = PROJECT_ROOT / ".env.test2"
        env_file.write_text("EXISTING_VAR=override_value\n", encoding="utf-8")

        try:
            _load_dotenv(env_file)
            assert os.environ.get("EXISTING_VAR") == "original_value"
        finally:
            env_file.unlink(missing_ok=True)

    def test_dotenv_skips_comments_and_empty(self, monkeypatch):
        """跳过注释和空行"""
        from core.config_loader import _load_dotenv

        env_file = PROJECT_ROOT / ".env.test3"
        env_file.write_text("""
# This is a comment
REAL_VAR=real_value

# Another comment
""", encoding="utf-8")

        try:
            monkeypatch.delenv("REAL_VAR", raising=False)
            _load_dotenv(env_file)
            assert os.environ.get("REAL_VAR") == "real_value"
        finally:
            env_file.unlink(missing_ok=True)

    def test_dotenv_strips_quotes(self, monkeypatch):
        """去除引号"""
        from core.config_loader import _load_dotenv

        env_file = PROJECT_ROOT / ".env.test4"
        env_file.write_text('QUOTED_VAR="quoted value"\n', encoding="utf-8")

        try:
            monkeypatch.delenv("QUOTED_VAR", raising=False)
            _load_dotenv(env_file)
            assert os.environ.get("QUOTED_VAR") == "quoted value"
        finally:
            env_file.unlink(missing_ok=True)


class TestDeepMerge:
    """深度合并测试"""

    def test_merge_simple_dicts(self):
        """简单合并 — override 覆盖 base"""
        from core.config_loader import _deep_merge

        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_merge_nested_dicts(self):
        """嵌套合并 — 递归合并子字典"""
        from core.config_loader import _deep_merge

        base = {"llm": {"provider": "deepseek", "model": "v3"}}
        override = {"llm": {"model": "v4", "temperature": 0.5}}
        result = _deep_merge(base, override)
        assert result["llm"]["provider"] == "deepseek"
        assert result["llm"]["model"] == "v4"
        assert result["llm"]["temperature"] == 0.5

    def test_merge_override_adds_new_section(self):
        """添加新段"""
        from core.config_loader import _deep_merge

        base = {"llm": {}}
        override = {"new_section": {"key": "value"}}
        result = _deep_merge(base, override)
        assert "new_section" in result
        assert result["new_section"]["key"] == "value"

    def test_merge_override_replaces_non_dict(self):
        """override 的非字典值替换 base 的字典"""
        from core.config_loader import _deep_merge

        base = {"section": {"a": 1, "b": 2}}
        override = {"section": "plain_string"}
        result = _deep_merge(base, override)
        assert result["section"] == "plain_string"


class TestPathExpansion:
    """路径展开测试"""

    def test_tilde_expansion(self):
        """:code:`~` 展开为家目录"""
        from core.config_loader import _expand_path

        expanded = _expand_path("~/Documents/test")
        assert expanded.startswith(str(Path.home()))
        assert expanded.endswith("Documents/test")

    def test_no_tilde_no_change(self):
        """不包含 :code:`~` 的路径不变"""
        from core.config_loader import _expand_path

        assert _expand_path("/absolute/path") == "/absolute/path"
        assert _expand_path("relative/path") == "relative/path"


class TestConfigValidation:
    """配置校验测试"""

    def test_valid_config(self):
        """完整配置校验通过"""
        from core.config_loader import validate_config

        config = {
            "llm": {
                "api_key": "sk-test",
                "base_url": "https://api.example.com",
                "model": "gpt-4",
            }
        }
        errors = validate_config(config)
        assert len(errors) == 0

    def test_missing_api_key(self):
        """缺少 API Key"""
        from core.config_loader import validate_config

        config = {
            "llm": {
                "api_key": "",
                "base_url": "https://api.example.com",
                "model": "gpt-4",
            }
        }
        errors = validate_config(config)
        assert len(errors) > 0
        assert any("api_key" in e.lower() or "API Key" in e for e in errors)

    def test_missing_base_url(self):
        """缺少 base_url"""
        from core.config_loader import validate_config

        config = {
            "llm": {
                "api_key": "sk-test",
                "base_url": "",
                "model": "gpt-4",
            }
        }
        errors = validate_config(config)
        assert len(errors) > 0
        assert any("base_url" in e.lower() for e in errors)

    def test_missing_model(self):
        """缺少 model"""
        from core.config_loader import validate_config

        config = {
            "llm": {
                "api_key": "sk-test",
                "base_url": "https://api.example.com",
                "model": "",
            }
        }
        errors = validate_config(config)
        assert len(errors) > 0
        assert any("model" in e.lower() for e in errors)

    def test_empty_config(self):
        """空配置"""
        from core.config_loader import validate_config

        errors = validate_config({})
        assert len(errors) > 0

    def test_missing_llm_section(self):
        """缺少 llm 段"""
        from core.config_loader import validate_config

        errors = validate_config({"other": {}})
        assert len(errors) > 0


class TestConfigSingleton:
    """配置加载幂等性测试"""

    def test_multiple_loads_return_same_structure(self):
        """多次加载返回相同结构"""
        from core.config_loader import load_config

        cfg1 = load_config()
        cfg2 = load_config()
        assert cfg1.keys() == cfg2.keys()
        assert cfg1["llm"]["provider"] == cfg2["llm"]["provider"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
