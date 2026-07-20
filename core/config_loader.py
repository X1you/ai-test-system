#!/usr/bin/env python3
"""
配置加载器 — 统一读取 config.yaml + .env 环境变量

支持：
  - YAML 配置文件读取
  - ${VAR_NAME} 变量插值（从环境变量取值）
  - .env 文件自动加载
  - 默认值兜底
"""

import os
import re
import sys
from pathlib import Path
from typing import Any

# 项目根目录（core/ 的上一级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 结构化日志 — structlog 优先，降级到 print（与 core.logger 一致）
try:
    import structlog
    _logger = structlog.get_logger("core.config_loader")
except ImportError:
    class _FallbackLogger:
        def _log(self, level, event, **kw):
            parts = [f"[{level}] [core.config_loader] {event}"]
            parts.extend(f"{k}={v}" for k, v in kw.items())
            print(" ".join(parts), file=sys.stderr)
        def debug(self, e, **k): self._log("DEBUG", e, **k)
        def info(self, e, **k): self._log("INFO", e, **k)
        def warning(self, e, **k): self._log("WARN", e, **k)
        def error(self, e, **k): self._log("ERROR", e, **k)
    _logger = _FallbackLogger()

# 默认配置（config.yaml 不存在时使用）
DEFAULT_CONFIG = {
    "llm": {
        "provider": "deepseek",
        "api_key": "",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "temperature": 0.3,
        "max_tokens": 8192,
        "timeout": 120,
        "retry": 2,
    },
    "knowledge_base": {
        "enabled": True,
        "vault_path": str(Path.home() / "Documents" / "test-interview-kb"),
    },
    "pipeline": {
        "default_mode": "semi",
        "default_dimensions": "basic",
        "default_formats": "excel",
        "self_check": True,
        "max_concurrent": 2,
    },
    "output": {
        "dir": str(PROJECT_ROOT / "output"),
    },
    "integrations": {
        "enabled": False,
    },
}


def _load_dotenv(env_path: Path):
    """加载 .env 文件到环境变量（不覆盖已有的）"""
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # 跳过空行和注释
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            # 去掉 export 前缀（兼容 shell 风格 .env）
            if key.startswith("export "):
                key = key[7:].strip()
            value = value.strip()
            # 去掉引号
            if value and value[0] in ('"', "'") and value[-1] == value[0]:
                value = value[1:-1]
            # 不覆盖已有环境变量
            if key not in os.environ:
                os.environ[key] = value


def _expand_vars(value: Any) -> Any:
    """递归替换 ${VAR_NAME} 和 ${VAR_NAME:-default} 为环境变量值"""
    if isinstance(value, str):
        # 匹配 ${VAR_NAME} 和 ${VAR_NAME:-default} 模式
        def replacer(match):
            var_name = match.group(1)
            default_val = match.group(2) or ""
            env_val = os.environ.get(var_name)
            return env_val if env_val is not None else default_val

        return re.sub(r"\$\{(\w+)(?::-(.*?))?\}", replacer, value)
    elif isinstance(value, dict):
        return {k: _expand_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_expand_vars(item) for item in value]
    return value


def _deep_merge(base: dict, override: dict) -> dict:
    """深度合并两个字典（override 覆盖 base）"""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _expand_path(path_str: str) -> str:
    """展开 ~ 为家目录"""
    if path_str.startswith("~"):
        return str(Path(path_str).expanduser())
    return path_str


def load_config(config_path: str | None = None) -> dict:
    """
    加载配置

    优先级：
      1. 指定的 config_path
      2. 项目根目录的 config.yaml
      3. DEFAULT_CONFIG

    Returns:
        合并后的完整配置字典
    """
    # 1. 加载 .env
    _load_dotenv(PROJECT_ROOT / ".env")

    # 2. 确定配置文件路径
    if config_path:
        cfg_path = Path(config_path)
    else:
        cfg_path = PROJECT_ROOT / "config.yaml"

    # 3. 读取 YAML
    user_config = {}
    if cfg_path.exists():
        try:
            import yaml
            with open(cfg_path, encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
        except ImportError:
            _logger.warning("pyyaml_not_installed", fallback="default_config")
        except Exception as e:
            _logger.warning("config_file_read_failed", path=str(cfg_path), error=str(e), fallback="default_config")

    # 4. 合并
    config = _deep_merge(DEFAULT_CONFIG, user_config)

    # 5. 变量插值
    config = _expand_vars(config)

    # 6. 路径展开
    config["knowledge_base"]["vault_path"] = _expand_path(
        config["knowledge_base"].get("vault_path", "")
    )
    config["output"]["dir"] = _expand_path(config["output"].get("dir", ""))

    return config


def validate_config(config: dict) -> list:
    """
    校验配置，返回错误消息列表（空列表 = 校验通过）
    """
    errors = []

    llm = config.get("llm", {})
    if not llm.get("api_key"):
        errors.append(
            "LLM API Key 未配置。请在 .env 中设置 LLM_API_KEY，或在 config.yaml 中填写 api_key。"
        )
    if not llm.get("base_url"):
        errors.append("LLM base_url 未配置。")
    if not llm.get("model"):
        errors.append("LLM model 未配置。")

    return errors
