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


def _migrate_legacy_llm_config(llm: dict) -> tuple[dict, bool]:
    """将旧版 LLM 配置（单 provider + fallback 列表）迁移为新 schema（providers 列表）。

    旧 schema:
        llm:
          provider: deepseek
          api_key: ...
          base_url: ...
          model: deepseek-chat
          fallback: [{provider, api_key, ...}, ...]

    新 schema:
        llm:
          default: <name>
          providers: [{name, protocol, ...}, ...]

    Returns:
        (迁移后的 llm dict, 是否发生了迁移)
    """
    # 已经是新 schema（顶层有 providers 列表且非空）→ 不迁移
    if isinstance(llm.get("providers"), list) and llm["providers"]:
        return llm, False

    # 旧 schema 特征：顶层有 provider/api_key/base_url/model 之一，且无 providers
    has_legacy_main = any(
        k in llm for k in ("provider", "api_key", "base_url", "model")
    )
    if not has_legacy_main:
        return llm, False

    providers: list[dict] = []

    # 提取主 provider（去掉 fallback 字段）
    main = {k: v for k, v in llm.items() if k != "fallback"}
    if main.get("api_key") or main.get("base_url") or main.get("model"):
        main.setdefault("name", main.get("provider", "default"))
        main.setdefault("protocol", "openai_compatible")
        main.setdefault("enabled", True)
        main.setdefault("priority", 0)
        providers.append(main)

    # 提取 fallback 列表
    for i, fb in enumerate(llm.get("fallback", []) or []):
        if not isinstance(fb, dict):
            continue
        fb = dict(fb)
        fb.setdefault("name", fb.get("provider", f"fallback_{i}"))
        fb.setdefault("protocol", "openai_compatible")
        fb.setdefault("enabled", True)
        fb.setdefault("priority", i + 1)
        providers.append(fb)

    if not providers:
        return llm, False

    new_llm: dict = {"providers": providers}
    if main.get("name"):
        new_llm["default"] = main["name"]
    # 保留其它顶层字段（如 _migrated 标记）
    for k, v in llm.items():
        if k not in ("fallback", "provider", "api_key", "base_url", "model", "temperature", "max_tokens", "timeout", "retry", "providers", "default"):
            new_llm.setdefault(k, v)
    new_llm["_migrated"] = True
    return new_llm, True


def load_config(config_path: str | None = None) -> dict:
    """
    加载配置

    优先级：
      1. 指定的 config_path
      2. 项目根目录的 config.yaml
      3. DEFAULT_CONFIG

    Returns:
        合并后的完整配置字典

    Side effects:
        若检测到旧版 LLM schema（单 provider + fallback 列表），
        自动迁移为新 schema（providers 列表），并写回 config.yaml。
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
    config["output"]["dir"] = _expand_path(config["output"].get("dir", ""))

    # 7. 旧版 LLM 配置自动迁移（单 provider → providers 列表）
    if isinstance(config.get("llm"), dict):
        new_llm, migrated = _migrate_legacy_llm_config(config["llm"])
        if migrated:
            _logger.info(
                "llm_config_migrated",
                message="检测到旧版 LLM 配置（单 provider 格式），已自动迁移为 providers 列表格式",
                new_providers=[p.get("name") for p in new_llm.get("providers", [])],
            )
            config["llm"] = new_llm
            # 写回 YAML（让下次启动不再触发迁移）
            try:
                import yaml as _yaml
                cfg_path.write_text(
                    _yaml.safe_dump(_strip_runtime_markers(config), allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
                _logger.info("llm_config_migrated_written", path=str(cfg_path))
            except Exception as e:
                _logger.warning("llm_config_migrate_write_failed", error=str(e))

    return config


def _strip_runtime_markers(config: dict) -> dict:
    """去掉运行时标记字段（以 _ 开头），保证写回 YAML 时不含内部状态。"""
    out = {}
    for k, v in config.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict):
            out[k] = _strip_runtime_markers(v)
        else:
            out[k] = v
    return out


def validate_config(config: dict) -> list:
    """
    校验配置，返回错误消息列表（空列表 = 校验通过）

    适配多 Provider schema：
      - 新 schema（providers 列表）：每个 provider 至少一个 enable 且配置 model
      - 旧 schema（顶层 api_key/model）：保留兼容
    """
    errors = []

    llm = config.get("llm", {})
    providers = llm.get("providers", []) if isinstance(llm, dict) else []

    if providers and isinstance(providers, list) and len(providers) > 0:
        # 新 schema：校验 providers 列表
        enabled = [p for p in providers if isinstance(p, dict) and p.get("enabled", True)]
        if not enabled:
            errors.append("所有 LLM provider 都被禁用（enabled=false），请至少启用一个")
        else:
            # 至少一个 provider 有 api_key（OpenAI 协议）或 model
            any_usable = False
            for p in enabled:
                protocol = p.get("protocol", "openai_compatible")
                has_model = bool(p.get("model"))
                if protocol == "openai_compatible" or protocol == "anthropic":
                    if has_model and p.get("api_key"):
                        any_usable = True
                        break
                elif protocol == "custom_http":
                    if has_model and (p.get("endpoint") or p.get("base_url")):
                        any_usable = True
                        break
            if not any_usable:
                errors.append("所有启用的 LLM provider 都缺少必要的 api_key/model 配置")
    else:
        # 旧 schema 兼容
        if not llm.get("api_key"):
            errors.append(
                "LLM API Key 未配置。请在 .env 中设置 LLM_API_KEY，或在 config.yaml 中填写 api_key。"
            )
    if not llm.get("base_url"):
        errors.append("LLM base_url 未配置。")
    if not llm.get("model"):
        errors.append("LLM model 未配置。")

    return errors
