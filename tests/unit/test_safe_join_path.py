#!/usr/bin/env python3
"""测试路径安全工具函数

验证 core.utils.safe_join_path 的功能：
  - 正常路径拼接
  - 子目录路径支持
  - 路径穿越（../../../）应被阻止
  - 绝对路径应被阻止

注意：该函数由其他并行任务（A-01）添加；若尚未实现，本文件中的测试会因
ImportError 失败，待函数落地后即可通过。
"""

import sys
from pathlib import Path

import pytest

# 将项目根目录加入 sys.path，确保可直接 import 项目模块
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_safe_join_path_normal():
    """正常路径拼接"""
    from core.utils import safe_join_path

    # resolve 基准目录，消除 macOS 下 /tmp -> /private/tmp 符号链接差异
    base = str(Path("/tmp/base").resolve())
    result = safe_join_path("/tmp/base", "file.txt")
    assert str(result).startswith(base)
    assert result.name == "file.txt"


def test_safe_join_path_subdirectory():
    """子目录路径"""
    from core.utils import safe_join_path

    base = str(Path("/tmp/base").resolve())
    result = safe_join_path("/tmp/base", "subdir/file.txt")
    assert str(result).startswith(base)


def test_safe_join_path_traversal_blocked():
    """路径穿越应被阻止"""
    from core.utils import safe_join_path

    with pytest.raises(ValueError, match="路径穿越"):
        safe_join_path("/tmp/base", "../../../etc/passwd")


def test_safe_join_path_absolute_path_blocked():
    """绝对路径应被阻止"""
    from core.utils import safe_join_path

    with pytest.raises(ValueError, match="路径穿越"):
        safe_join_path("/tmp/base", "/etc/passwd")
