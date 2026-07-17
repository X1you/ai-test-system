#!/usr/bin/env python3
"""
MCP Client for Obsidian Vault
提供统一的知识库访问接口，通过 MCP 协议访问 Obsidian
支持三层搜索：Obsidian API → 标签匹配 → 全文遍历
"""

import hashlib
import json
import os
import re
import ssl
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# ============================================================================
# 配置
# ============================================================================

OBSIDIAN_VAULT = Path.home() / "Documents" / "test-interview-kb"

# Obsidian Local REST API 配置 (可选，通过环境变量或项目配置启用)
OBSIDIAN_API_BASE = os.environ.get("OBSIDIAN_API_BASE", "")
OBSIDIAN_API_KEY = os.environ.get("OBSIDIAN_API_KEY", "")
OBSIDIAN_SSL_VERIFY = os.environ.get("OBSIDIAN_SSL_VERIFY", "").lower() == "true"

# API 端口尝试顺序（常用端口优先）
OBSIDIAN_API_PORTS = ["http://localhost:27123", "https://localhost:27124"]

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
    tags: list[str]
    severity: str | None = None
    created_at: str = ""
    updated_at: str = ""
    filepath: str = ""


# ============================================================================
# Obsidian Local REST API 客户端 (可选增强层)
# ============================================================================

class ObsidianAPIClient:
    """Obsidian Local REST API 客户端 — 通过 REST API 搜索 Obsidian 内置索引"""

    def __init__(self, base_url: str = OBSIDIAN_API_BASE,
                 api_key: str = OBSIDIAN_API_KEY,
                 ssl_verify: bool = OBSIDIAN_SSL_VERIFY):
        self.base_url = base_url.rstrip('/') if base_url else ""
        self.api_key = api_key
        self.ssl_verify = ssl_verify
        self._ssl_context = None
        if not ssl_verify and self.base_url.startswith("https"):
            self._ssl_context = ssl.create_default_context()
            self._ssl_context.check_hostname = False
            self._ssl_context.verify_mode = ssl.CERT_NONE

    def _request(self, method: str, path: str, data: dict | None = None) -> Any:
        """发送 HTTP 请求到 Obsidian API"""
        import urllib.error
        import urllib.parse
        import urllib.request

        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req_data = json.dumps(data).encode('utf-8') if data else None
        req = urllib.request.Request(url, data=req_data, headers=headers, method=method.upper())

        try:
            kwargs = {}
            if self._ssl_context:
                kwargs['context'] = self._ssl_context
            with urllib.request.urlopen(req, timeout=10, **kwargs) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        except Exception:
            raise

    def search(self, query: str, context_length: int = 200) -> list[dict]:
        """使用 Obsidian 内置搜索引擎搜索文件"""
        # 优先使用 /search-with-context（返回上下文片段）
        try:
            result = self._request("POST", "/search-with-context", {
                "query": query,
                "contextLength": context_length
            })
            if result is not None:
                return result.get('results', [])
        except Exception:
            pass
        # Fallback: /search 端点
        try:
            result = self._request("POST", "/search", {"query": query})
            if result is not None:
                return result.get('results', [])
        except Exception:
            pass
        return []

    def is_available(self) -> bool:
        """检查 Obsidian API 是否可用（尝试所有配置的端口）"""
        bases_to_try = [self.base_url] if self.base_url else OBSIDIAN_API_PORTS
        for base in bases_to_try:
            try:
                self.base_url = base.rstrip("/")
                # 尝试无 key 请求（部分配置不需要 key）
                self._request("GET", "/")
                return True
            except Exception:
                continue
        return False


# ============================================================================
# 关键词标签提取器
# ============================================================================

# 中文停用词（高频无意义词）
_STOPWORDS = frozenset([
    '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一',
    '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有',
    '看', '好', '自己', '这', '那', '它', '他', '她', '与', '及', '或', '但',
    '测试', '用例', '功能', '模块', '系统', '操作', '数据', '结果', '步骤',
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'to', 'of',
    'in', 'on', 'at', 'by', 'for', 'with', 'test', 'case',
])


def extract_keywords(title: str, content: str = "", module: str = "",
                     max_tags: int = 3) -> list[str]:
    """
    从标题、模块和内容中自动提取关键词标签。

    策略：
    1. 标题去掉编号前缀（TC-xxx）后整体保留 — 标题本身就是最佳关键词
    2. 模块名作为标签（取最后一段，即真实模块名）
    3. 内容中提取高频 CJK 3-gram 补充（仅在标签不足时）
    4. 去停用词，去重，截断到 max_tags
    """
    tags: list[str] = []

    # --- 1. 从标题提取 ---
    # 标题常见格式: "TC-001 登录功能验证" / "并发下单库存超卖"
    # 去掉编号前缀（TC-001 / TC001），保留实际标题作为关键词
    title_clean = re.sub(r'^[A-Za-z]{1,4}[-_]?\d+\s*', '', title).strip()
    if title_clean:
        title_parts = re.split(r'[\s\-_/|：:、，,。()（）\[\]]+', title_clean)
        for part in title_parts:
            part = part.strip()
            if len(part) >= 2 and part.lower() not in _STOPWORDS:
                tags.append(part)

    # --- 2. 模块名作为标签 ---
    # module 可能编码为 "项目名/批次/模块名"，取最后一段
    if module and len(tags) < max_tags:
        mod_parts = module.split('/')
        actual_module = mod_parts[-1].strip() if mod_parts else module.strip()
        if actual_module and len(actual_module) >= 2 and actual_module not in tags:
            tags.append(actual_module)

    # --- 3. 内容高频 3-gram 补充（仅在标签不足时）---
    if len(tags) < max_tags and content:
        from collections import Counter
        # 清理 markdown 标记
        clean = re.sub(r'[#*`\-|>\[\]()]', ' ', content)
        cjk_segments = re.findall(r'[\u4e00-\u9fff]{3,}', clean)
        trigram_freq: Counter = Counter()
        for seg in cjk_segments:
            for i in range(len(seg) - 2):
                trigram = seg[i:i+3]
                # 过滤含停用字的 trigram
                if not any(c in _STOPWORDS for c in trigram[:2]):
                    trigram_freq[trigram] += 1
        # 取高频 3-gram 补充
        for trigram, _ in trigram_freq.most_common(max_tags * 2):
            if trigram not in tags:
                tags.append(trigram)
            if len(tags) >= max_tags:
                break

    # 去重 + 截断
    seen = set()
    unique_tags = []
    for tag in tags:
        tag_lower = tag.lower()
        if tag_lower not in seen:
            seen.add(tag_lower)
            unique_tags.append(tag)
        if len(unique_tags) >= max_tags:
            break

    return unique_tags


# ============================================================================
# MCP 客户端 (抽象层)
# ============================================================================

class MCPClient:
    """MCP 协议客户端 - 直接访问 Obsidian Vault 文件系统，支持三层搜索"""

    def __init__(self, vault_path: str = str(OBSIDIAN_VAULT),
                 use_obsidian_api: bool = True,
                 obsidian_api_base: str = "",
                 obsidian_api_key: str = ""):
        self.vault_path = Path(vault_path)
        self._ensure_directories()
        # Obsidian API 增强层（可选）
        self._obsidian_api: ObsidianAPIClient | None = None
        self._obsidian_api_checked = False
        self._obsidian_api_available = False
        if use_obsidian_api:
            api_key = obsidian_api_key or OBSIDIAN_API_KEY
            api_base = obsidian_api_base or OBSIDIAN_API_BASE
            self._obsidian_api = ObsidianAPIClient(base_url=api_base, api_key=api_key)
            # 延迟检查：首次 search 时才检测可用性

    def _ensure_directories(self):
        """确保分类目录存在

        当 vault 路径不可写（如只读文件系统或权限不足）时，
        不抛出异常，仅在首次写入时才报错。搜索/读取操作仍可正常工作。
        """
        try:
            for cat_path in CATEGORY_PATHS.values():
                (self.vault_path / cat_path).mkdir(parents=True, exist_ok=True)
        except OSError:
            # vault 路径不存在或不可写 — 延迟到实际使用时报错
            pass

    def _generate_id(self, content: str) -> str:
        """生成唯一ID"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:12]

    def _safe_path(self, filepath: str) -> Path:
        """
        安全路径校验 — 防止路径穿越攻击。
        解析后确保路径在 vault_path 内，否则抛出 ValueError。
        """
        vault_resolved = self.vault_path.resolve()
        full_path = (self.vault_path / filepath).resolve()
        # 确保解析后的路径在 vault 目录内
        try:
            full_path.relative_to(vault_resolved)
        except ValueError:
            raise ValueError(f"非法路径访问被拒绝: {filepath}")
        return full_path

    def _parse_yaml_frontmatter(self, content: str) -> dict:
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
                except Exception:
                    # yaml.YAMLError 等格式损坏的 frontmatter → 安全降级为空 dict
                    frontmatter = {}
        return frontmatter

    # -------------------------------------------------------------------------
    # 核心 MCP 接口方法
    # -------------------------------------------------------------------------

    def list_files(self, category: str = None) -> list[str]:
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
                    files = [str(f.relative_to(self.vault_path)) for f in cat_dir.rglob("*.md")]
        else:
            # 列出所有分类下的文件（含子目录，如历史用例的 项目名/批次/ 分层）
            for cat, cat_path in CATEGORY_PATHS.items():
                cat_dir = self.vault_path / cat_path
                if cat_dir.exists():
                    files.extend([str(f.relative_to(self.vault_path)) for f in cat_dir.rglob("*.md")])

        return files

    def read_file(self, filepath: str) -> dict | None:
        """
        MCP: read_file
        读取文件内容
        """
        try:
            full_path = self._safe_path(filepath)
        except ValueError:
            return None
        if not full_path.exists():
            return None

        try:
            with open(full_path, encoding='utf-8') as f:
                content = f.read()
        except OSError:
            return None

        return {
            'content': content,
            'path': filepath,
            'size': len(content)
        }

    def _check_obsidian_api(self) -> bool:
        """延迟检查 Obsidian API 可用性（首次 search 时检查，结果缓存）"""
        if not self._obsidian_api_checked:
            self._obsidian_api_available = self._obsidian_api.is_available() if self._obsidian_api else False
            self._obsidian_api_checked = True
        return self._obsidian_api_available

    def search(self, query: str, category: str = None, limit: int = 20) -> list[dict]:
        """
        MCP: search
        搜索知识库 — 三层搜索策略

        Layer 1: Obsidian API 搜索（可用时，利用 Obsidian 内置索引）
        Layer 2: 标签匹配（YAML frontmatter 中的 tags 字段）
        Layer 3: 全文遍历 + 多关键词 OR 匹配（始终作为最终 fallback）

        匹配策略：将 query 按空格分词，任一词命中即算匹配。
        多词命中数越多，排序越靠前。标签命中加权。
        """
        # 分词：支持中文短语 + 英文单词
        keywords = [kw.strip().lower() for kw in query.split() if kw.strip()]
        if not keywords:
            keywords = [query.strip().lower()]

        # --- Layer 1: Obsidian API 搜索 ---
        # API 可用时，利用 Obsidian 内置搜索引擎获得更精准的匹配
        # 但仍需读取文件做 frontmatter 解析，所以只是减少遍历范围
        api_results: set | None = None  # None=未尝试, set=API返回的文件路径集合
        if self._check_obsidian_api() and self._obsidian_api:
            try:
                api_hits = self._obsidian_api.search(query)
                if api_hits:
                    api_results = set()
                    for hit in api_hits:
                        # API 返回的路径可能是相对路径或绝对路径
                        hit_path = hit.get('filename', '') or hit.get('path', '') or hit.get('file', '')
                        if hit_path:
                            # 标准化路径：只保留 vault 内的相对路径
                            if hit_path.startswith(str(self.vault_path)):
                                hit_path = str(Path(hit_path).relative_to(self.vault_path))
                            api_results.add(hit_path)
            except Exception:
                api_results = None  # API 出错，降级到全量遍历

        # --- Layer 2+3: 文件遍历（带标签匹配）---
        files = self.list_files(category)
        results = []

        for filepath in files:
            # 如果 API 返回了候选集，只检查候选文件（性能优化）
            if api_results is not None and filepath not in api_results:
                continue

            file_data = self.read_file(filepath)
            if not file_data:
                continue

            content = file_data['content']
            content_lower = content.lower()
            filepath_lower = filepath.lower()

            frontmatter = self._parse_yaml_frontmatter(content)
            file_tags = frontmatter.get('tags', [])
            if isinstance(file_tags, str):
                file_tags = [t.strip() for t in file_tags.split(',')]
            tags_lower = [str(t).lower() for t in file_tags]

            # 统计命中关键词数（用于排序）
            hit_count = 0
            tag_hits = 0
            for kw in keywords:
                if kw in content_lower or kw in filepath_lower:
                    hit_count += 1
                # 标签匹配（标签命中加权）
                if any(kw in tag for tag in tags_lower):
                    tag_hits += 1

            # 全文 + 标签命中数合计为 0 → 跳过
            if hit_count == 0 and tag_hits == 0:
                continue

            # 提取标题
            title = Path(filepath).stem
            if 'title' in frontmatter:
                title = frontmatter['title']

            # 确定分类（路径前缀匹配，避免子串误匹配）
            cat_match = None
            for cat_key, cat_path in CATEGORY_PATHS.items():
                if filepath.startswith(cat_path + '/') or filepath == cat_path:
                    cat_match = cat_key
                    break

            # 综合得分：全文命中 (1.0/词) + 标签命中加权 (2.0/词)
            score = hit_count * 1.0 + tag_hits * 2.0

            results.append({
                'id': frontmatter.get('id', self._generate_id(content[:200])),
                'title': title,
                'content': content,
                'category': cat_match or 'unknown',
                'module': frontmatter.get('module', ''),
                'tags': file_tags,
                'severity': frontmatter.get('severity'),
                'filepath': filepath,
                'source': 'obsidian-api' if api_results is not None else 'mcp',
                'hit_count': hit_count,
                'tag_hits': tag_hits,
                'score': score,
            })

        # 按综合得分降序排序（全文命中 + 标签命中加权）
        results.sort(key=lambda x: x.get('score', 0), reverse=True)
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

        # 关键词标签自动提取：用户未指定 tags 时，从标题/模块/内容中提取
        if not item.tags:
            item.tags = extract_keywords(item.title, item.content, item.module)

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
        try:
            full_path = self._safe_path(filepath)
        except ValueError:
            return False
        full_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except OSError:
            return False

        item.filepath = filepath
        return True

    def update_file(self, filepath: str, content: str) -> bool:
        """
        MCP: update_file
        更新文件内容
        """
        try:
            full_path = self._safe_path(filepath)
        except ValueError:
            return False
        if not full_path.exists():
            return False

        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except OSError:
            return False

        return True

    def delete_file(self, filepath: str) -> bool:
        """
        MCP: delete_file
        删除文件
        """
        try:
            full_path = self._safe_path(filepath)
        except ValueError:
            return False
        if not full_path.exists():
            return False

        full_path.unlink()
        return True

    def _format_obsidian_note(self, item: KnowledgeItem) -> str:
        """格式化为 Obsidian Note (YAML frontmatter + wikilinks)"""
        # 直接使用已设置的 updated_at，避免重复调用 datetime.now() 造成不一致
        # YAML frontmatter
        frontmatter = {
            'id': item.id,
            'category': item.category,
            'module': item.module,
            'tags': item.tags,
            'created_at': item.created_at,
            'updated_at': item.updated_at,
        }

        if item.severity:
            frontmatter['severity'] = item.severity

        # 安全序列化 YAML frontmatter — 标准格式（每行一个 key: value）
        fm_lines = ['---']
        try:
            import yaml
            # 一次性 safe_dump 整个 dict，默认 block style 输出标准多行 YAML
            # （每行 `key: value`，列表用 inline `[a, b]` 或 block `- a`，均合法）
            fm_lines.append(
                yaml.safe_dump(
                    frontmatter,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False,
                ).rstrip('\n')
            )
        except ImportError:
            # fallback: 手动序列化（列表用 json，字符串用 json 确保转义）
            import json
            for k, v in frontmatter.items():
                if isinstance(v, list):
                    fm_lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
                else:
                    fm_lines.append(f"{k}: {json.dumps(str(v), ensure_ascii=False)}")
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

    def status(self) -> dict:
        """知识库概况"""
        api_status = 'disabled'
        if self._check_obsidian_api():
            api_status = 'available'
        elif self._obsidian_api_checked:
            api_status = 'unavailable (fallback to file scan)'

        summary = {
            'source': 'mcp-obsidian',
            'search_backend': api_status,
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
