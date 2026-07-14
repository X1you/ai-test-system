#!/usr/bin/env python3
"""
MCP Client for Obsidian Vault
提供统一的知识库访问接口，通过 MCP 协议访问 Obsidian
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import hashlib
import re

# ============================================================================
# 配置
# ============================================================================

OBSIDIAN_VAULT = Path("/Users/x1you/Documents/test-interview-kb")

# 分类目录映射
CATEGORY_PATHS = {
    'business-rules': '📋 业务规则',
    'historical-cases': '🏆 历史用例',
    'pitfalls': '⚠️ 线上坑点',
    'templates': '📝 用例模板',
    'data-dictionary': '📖 数据字典',
    'business-specs': '📘 业务规范',
    'team-standards': '📐 团队规范',
}

# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class KnowledgeItem:
    """知识条目模型"""
    id: str
    title: str
    content: str
    category: str
    module: str
    tags: List[str]
    severity: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    filepath: str = ""


# ============================================================================
# MCP 客户端 (抽象层)
# ============================================================================

class MCPClient:
    """MCP 协议客户端 - 直接访问 Obsidian Vault 文件系统"""

    def __init__(self, vault_path: str = str(OBSIDIAN_VAULT)):
        self.vault_path = Path(vault_path)
        self._ensure_directories()

    def _ensure_directories(self):
        """确保分类目录存在"""
        for cat_path in CATEGORY_PATHS.values():
            (self.vault_path / cat_path).mkdir(parents=True, exist_ok=True)

    def _generate_id(self, content: str) -> str:
        """生成唯一ID"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:12]

    def _parse_yaml_frontmatter(self, content: str) -> Dict:
        """解析 YAML frontmatter"""
        frontmatter = {}
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 2:
                try:
                    import yaml
                    frontmatter = yaml.safe_load(parts[1]) or {}
                except ImportError:
                    # 简单解析 key: value 格式
                    for line in parts[1].strip().split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            frontmatter[key.strip()] = value.strip()
        return frontmatter

    # -------------------------------------------------------------------------
    # 核心 MCP 接口方法
    # -------------------------------------------------------------------------

    def list_files(self, category: str = None) -> List[str]:
        """
        MCP: list_files
        列出知识库中的文件
        """
        files = []

        if category:
            cat_path = CATEGORY_PATHS.get(category)
            if cat_path:
                cat_dir = self.vault_path / cat_path
                if cat_dir.exists():
                    files = [str(f.relative_to(self.vault_path)) for f in cat_dir.glob("*.md")]
        else:
            # 列出所有分类下的文件
            for cat, cat_path in CATEGORY_PATHS.items():
                cat_dir = self.vault_path / cat_path
                if cat_dir.exists():
                    files.extend([str(f.relative_to(self.vault_path)) for f in cat_dir.glob("*.md")])

        return files

    def read_file(self, filepath: str) -> Optional[Dict]:
        """
        MCP: read_file
        读取文件内容
        """
        full_path = self.vault_path / filepath
        if not full_path.exists():
            return None

        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return {
            'content': content,
            'path': filepath,
            'size': len(content)
        }

    def search(self, query: str, category: str = None, limit: int = 20) -> List[Dict]:
        """
        MCP: search
        搜索知识库
        """
        files = self.list_files(category)
        results = []

        for filepath in files:
            file_data = self.read_file(filepath)
            if not file_data:
                continue

            content = file_data['content']

            # 简单的文本匹配
            if query.lower() in content.lower() or query.lower() in filepath.lower():
                frontmatter = self._parse_yaml_frontmatter(content)

                # 提取标题
                title = Path(filepath).stem
                if 'title' in frontmatter:
                    title = frontmatter['title']

                # 确定分类
                cat_match = None
                for cat, cat_path in CATEGORY_PATHS.items():
                    if cat_path in filepath:
                        cat_match = cat
                        break

                results.append({
                    'id': frontmatter.get('id', self._generate_id(content[:200])),
                    'title': title,
                    'content': content,
                    'category': cat_match or 'unknown',
                    'module': frontmatter.get('module', ''),
                    'severity': frontmatter.get('severity'),
                    'filepath': filepath,
                    'source': 'mcp'
                })

        return results[:limit]

    def create_file(self, item: KnowledgeItem) -> bool:
        """
        MCP: create_file
        创建新知识条目

        目录策略:
        - historical-cases: 🏆 历史用例/{项目名}/{批次}/TC-xxx.md
          (item.module 编码为 "项目名/批次/模块名" 时自动分层)
        - 其他分类: 平铺存储
        """
        item.id = item.id or self._generate_id(item.title + item.content)
        now = datetime.now().isoformat()
        item.created_at = item.created_at or now
        item.updated_at = now

        safe_title = re.sub(r'[\\/*?:"<>|]', '-', item.title)[:50]

        # 历史用例按项目维度归档
        if item.category == 'historical-cases' and '/' in item.module:
            # module 编码为 "项目名/批次/模块名"
            parts = item.module.split('/', 2)
            project = parts[0] if len(parts) > 0 else '未分类项目'
            batch = parts[1] if len(parts) > 1 else '未分类批次'
            actual_module = parts[2] if len(parts) > 2 else ''
            # 目录: 🏆 历史用例/项目名/批次/
            category_display = CATEGORY_PATHS.get(item.category, item.category)
            date_prefix = datetime.now().strftime("%Y-%m-%d")
            filename = f"{safe_title}.md"
            filepath = f"{category_display}/{project}/{batch}/{filename}"
            # YAML frontmatter 中保存真实模块名
            display_module = actual_module or item.module
        else:
            # 其他分类或无项目信息: 平铺
            category_display = CATEGORY_PATHS.get(item.category, item.category)
            date_prefix = datetime.now().strftime("%Y-%m-%d")
            filename = f"{date_prefix} {safe_title}.md"
            filepath = f"{category_display}/{filename}"
            display_module = item.module

        # 格式化内容
        item.module = display_module
        content = self._format_obsidian_note(item)

        # 写入文件
        full_path = self.vault_path / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)

        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

        item.filepath = filepath
        return True

    def update_file(self, filepath: str, content: str) -> bool:
        """
        MCP: update_file
        更新文件内容
        """
        full_path = self.vault_path / filepath
        if not full_path.exists():
            return False

        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return True

    def delete_file(self, filepath: str) -> bool:
        """
        MCP: delete_file
        删除文件
        """
        full_path = self.vault_path / filepath
        if not full_path.exists():
            return False

        full_path.unlink()
        return True

    def _format_obsidian_note(self, item: KnowledgeItem) -> str:
        """格式化为 Obsidian Note (YAML frontmatter + wikilinks)"""
        now = datetime.now().isoformat()

        # YAML frontmatter
        frontmatter = {
            'id': item.id,
            'category': item.category,
            'module': item.module,
            'tags': item.tags,
            'created_at': item.created_at,
            'updated_at': now,
        }

        if item.severity:
            frontmatter['severity'] = item.severity

        fm_lines = ['---']
        for k, v in frontmatter.items():
            if isinstance(v, list):
                fm_lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
            else:
                fm_lines.append(f"{k}: {v}")
        fm_lines.append('---')

        # 内容
        content_lines = fm_lines + [
            '',
            f"# {item.title}",
            '',
            f"**模块**: [[{item.module}]]" if item.module else "**模块**: 未指定",
            '',
            item.content
        ]

        return '\n'.join(content_lines)

    # -------------------------------------------------------------------------
    # 便捷方法
    # -------------------------------------------------------------------------

    def status(self) -> Dict:
        """知识库概况"""
        summary = {
            'source': 'mcp-obsidian',
            'categories': {},
            'total': 0,
            'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        for cat in CATEGORY_PATHS.keys():
            files = self.list_files(cat)
            summary['categories'][cat] = len(files)
            summary['total'] += len(files)

        return summary


# ============================================================================
# 导出便捷函数
# ============================================================================

def create_mcp_client(vault_path: str = None) -> MCPClient:
    """创建 MCP 客户端实例"""
    return MCPClient(vault_path or str(OBSIDIAN_VAULT))