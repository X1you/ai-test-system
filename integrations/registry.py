#!/usr/bin/env python3
"""
AdapterRegistry — 插件注册表

装饰器注册 + 目录自动发现。
"""

import importlib
import pkgutil
from typing import Dict, Type

from integrations.base import BaseAdapter, AdapterConfig


class AdapterRegistry:
    """适配器注册表"""

    _adapters: Dict[str, Type[BaseAdapter]] = {}

    @classmethod
    def register(cls, platform: str):
        """装饰器：注册适配器类

        用法:
            @AdapterRegistry.register("testrail")
            class TestRailAdapter(BaseAdapter):
                ...
        """
        def decorator(adapter_cls: Type[BaseAdapter]):
            cls._adapters[platform] = adapter_cls
            return adapter_cls
        return decorator

    @classmethod
    def get_adapter(cls, platform: str, config: AdapterConfig) -> BaseAdapter:
        """获取适配器实例"""
        adapter_cls = cls._adapters.get(platform)
        if not adapter_cls:
            available = ", ".join(cls.list_platforms())
            raise ValueError(
                f"未注册的平台: '{platform}'。"
                f"可用平台: {available}"
            )
        return adapter_cls(config)

    @classmethod
    def list_platforms(cls) -> list:
        """列出已注册的平台"""
        return list(cls._adapters.keys())

    @classmethod
    def auto_discover(cls, package: str = "integrations.adapters"):
        """自动发现并加载 adapters/ 目录下的所有适配器

        在应用启动时调用:
            AdapterRegistry.auto_discover()
        """
        try:
            pkg = importlib.import_module(package)
        except ModuleNotFoundError:
            return

        for _importer, modname, _ispkg in pkgutil.iter_modules(pkg.__path__):
            full_name = f"{package}.{modname}"
            try:
                importlib.import_module(full_name)
            except Exception as e:
                import logging
                logging.warning(f"加载适配器 {full_name} 失败: {e}")
