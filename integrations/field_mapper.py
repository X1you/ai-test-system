#!/usr/bin/env python3
"""
FieldMapper — 字段映射引擎

配置驱动（YAML），支持正向/反向双向转换。
支持 type: join（List→字符串）、type: lookup（运行时查询）、值映射表 三种转换器。
"""

from pathlib import Path
from typing import Any

# 转换配置中的保留键，在值映射表反向查找时需跳过
_RESERVED_KEYS = frozenset({"default", "type", "separator", "template", "cache"})


class FieldMapper:
    """字段映射引擎 — 配置驱动的双向转换"""

    def __init__(self, mapping_path: str = ""):
        self.mapping: dict[str, Any] = (
            self._load_mapping(mapping_path) if mapping_path else {}
        )
        # 缓存反转后的值映射表（{transform_name: {platform_val: canonical_key}}）
        self._reverse_cache: dict[str, dict] = {}

    @classmethod
    def load(cls, mapping_path: str) -> "FieldMapper":
        """类方法：从路径加载并返回 FieldMapper 实例"""
        return cls(mapping_path)

    def _load_mapping(self, path: str) -> dict:
        """从 YAML 文件加载映射配置"""
        p = Path(path)
        if not p.exists():
            return {}
        try:
            import yaml
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except ImportError:
            raise ImportError("需要 PyYAML 来加载字段映射配置（pip install pyyaml）")

    def _parse_field_spec(self, platform_spec: Any) -> tuple[str, str | None]:
        """解析字段映射规格，返回 (platform_field, transform_name)"""
        if isinstance(platform_spec, dict):
            return platform_spec["field"], platform_spec.get("transform")
        return platform_spec, None

    def to_platform(self, case_dict: dict) -> dict[str, Any]:
        """内部 → 平台格式（正向映射 + 正向转换）"""
        field_mapping = self.mapping.get("field_mapping", {})
        transforms = self.mapping.get("transforms", {})
        result: dict[str, Any] = {}

        for canonical_field, platform_spec in field_mapping.items():
            value = case_dict.get(canonical_field)
            if value is None:
                continue

            platform_field, transform_name = self._parse_field_spec(platform_spec)

            if transform_name and transform_name in transforms:
                value = self._apply_transform(value, transforms[transform_name])

            result[platform_field] = value

        return result

    def to_canonical(self, platform_dict: dict) -> dict[str, Any]:
        """平台 → 内部格式（反向映射 + 反向转换）"""
        field_mapping = self.mapping.get("field_mapping", {})
        transforms = self.mapping.get("transforms", {})
        result: dict[str, Any] = {}

        for canonical_field, platform_spec in field_mapping.items():
            platform_field, transform_name = self._parse_field_spec(platform_spec)

            value = platform_dict.get(platform_field)
            if value is not None:
                if transform_name and transform_name in transforms:
                    value = self._reverse_transform(
                        value, transforms[transform_name], transform_name
                    )
                result[canonical_field] = value

        return result

    # ─── 转换器 ───

    @staticmethod
    def _apply_transform(value: Any, transform_spec: dict) -> Any:
        """正向转换（内部值 → 平台值）

        支持三种 type：
          - join:    List → 用 separator 拼接的字符串
          - template: 模板替换 ``{value}``
          - lookup:  运行时查找（由 Adapter 处理），原样返回
          - 默认:    值映射表（如 ``{P0: 1, default: 2}``）
        """
        if not isinstance(transform_spec, dict):
            return value

        transform_type = transform_spec.get("type")

        if transform_type == "join":
            if isinstance(value, list):
                sep = transform_spec.get("separator", "\n")
                return sep.join(str(v) for v in value)
            return value

        if transform_type == "template":
            template_str = transform_spec.get("template", "{value}")
            return template_str.replace("{value}", str(value))

        if transform_type == "lookup":
            return value  # 运行时查找表，由 Adapter 处理

        # 默认：值映射表
        if isinstance(value, str) and value in transform_spec:
            return transform_spec[value]
        return transform_spec.get("default", value)

    def _reverse_transform(
        self, value: Any, transform_spec: dict, transform_name: str
    ) -> Any:
        """反向转换（平台值 → 内部值）

        支持三种 type：
          - join:    用 separator 分割为 List
          - lookup:  原样返回
          - 默认:    值映射表反向查找（结果缓存）
        """
        if not isinstance(transform_spec, dict):
            return value

        transform_type = transform_spec.get("type")

        if transform_type == "join":
            sep = transform_spec.get("separator", "\n")
            if isinstance(value, str):
                return value.split(sep)
            return value

        if transform_type == "lookup":
            return value

        # 默认：值映射表反向查找（带缓存）
        reverse_map = self._reverse_cache.get(transform_name)
        if reverse_map is None:
            reverse_map = self._build_reverse_map(transform_spec)
            self._reverse_cache[transform_name] = reverse_map
        return reverse_map.get(value, value)

    @staticmethod
    def _build_reverse_map(transform_spec: dict) -> dict:
        """构建值映射表的反转字典（val → key），跳过保留键"""
        return {
            val: key
            for key, val in transform_spec.items()
            if key not in _RESERVED_KEYS
        }
