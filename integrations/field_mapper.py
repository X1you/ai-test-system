#!/usr/bin/env python3
"""
FieldMapper — 字段映射引擎

配置驱动（YAML），支持正向/反向双向转换。
支持 type: join（List→字符串）、type: lookup（运行时查询）、值映射表 三种转换器。
"""

from pathlib import Path
from typing import Any, Dict, List, Optional


class FieldMapper:
    """字段映射引擎 — 配置驱动的双向转换"""

    def __init__(self, mapping_path: str = ""):
        self.mapping = self._load_mapping(mapping_path) if mapping_path else {}

    @classmethod
    def load(cls, mapping_path: str) -> "FieldMapper":
        """类方法：从路径加载并返回 FieldMapper 实例"""
        return cls(mapping_path)

    def _load_mapping(self, path: str) -> dict:
        p = Path(path)
        if not p.exists():
            return {}
        try:
            import yaml
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except ImportError:
            raise ImportError("需要 PyYAML 来加载字段映射配置")

    def to_platform(self, case_dict: dict) -> dict:
        """内部 → 平台格式"""
        field_mapping = self.mapping.get("field_mapping", {})
        transforms = self.mapping.get("transforms", {})
        result: Dict[str, Any] = {}

        for canonical_field, platform_spec in field_mapping.items():
            value = case_dict.get(canonical_field)
            if value is None:
                continue

            if isinstance(platform_spec, dict):
                platform_field = platform_spec["field"]
                transform_name = platform_spec.get("transform")
            else:
                platform_field = platform_spec
                transform_name = None

            if transform_name and transform_name in transforms:
                value = self._apply_transform(value, transforms[transform_name])

            result[platform_field] = value

        return result

    def to_canonical(self, platform_dict: dict) -> dict:
        """平台 → 内部格式（反向映射）"""
        field_mapping = self.mapping.get("field_mapping", {})
        transforms = self.mapping.get("transforms", {})
        result: Dict[str, Any] = {}

        for canonical_field, platform_spec in field_mapping.items():
            if isinstance(platform_spec, dict):
                platform_field = platform_spec["field"]
                transform_name = platform_spec.get("transform")
            else:
                platform_field = platform_spec
                transform_name = None

            value = platform_dict.get(platform_field)
            if value is not None:
                if transform_name and transform_name in transforms:
                    value = self._reverse_transform(value, transforms[transform_name])
                result[canonical_field] = value

        return result

    @staticmethod
    def _apply_transform(value: Any, transform_spec: dict) -> Any:
        """正向转换（内部值 → 平台值）"""
        if not isinstance(transform_spec, dict):
            return value

        transform_type = transform_spec.get("type")

        if transform_type == "join":
            if isinstance(value, list):
                sep = transform_spec.get("separator", "\n")
                return sep.join(str(v) for v in value)
            return value

        elif transform_type == "template":
            template_str = transform_spec.get("template", "{value}")
            return template_str.replace("{value}", str(value))

        elif transform_type == "lookup":
            # 运行时查找表（由 Adapter 处理），原样返回
            return value

        else:
            # 默认：值映射表（如 priority_map: {P0: 1}）
            if isinstance(value, str) and value in transform_spec:
                return transform_spec[value]
            return transform_spec.get("default", value)

    @staticmethod
    def _reverse_transform(value: Any, transform_spec: dict) -> Any:
        """反向转换（平台值 → 内部值）"""
        if not isinstance(transform_spec, dict):
            return value

        transform_type = transform_spec.get("type")

        if transform_type == "join":
            sep = transform_spec.get("separator", "\n")
            if isinstance(value, str):
                return value.split(sep)
            return value

        elif transform_type == "lookup":
            return value

        else:
            # 默认：值映射表反向查找
            for key, val in transform_spec.items():
                if key != "default" and key != "type" and val == value:
                    return key
            return value
