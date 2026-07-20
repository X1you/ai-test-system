#!/usr/bin/env python3
"""
Knowledge Base Manager - 本地 Markdown + Obsidian REST API 双方案支持
支持检索、添加、导出、回灌知识，优先使用 Obsidian API，fallback 到本地文件
"""

import argparse
import hashlib
import json
import math
import os
import re
import ssl
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

# 结构化日志 — structlog 优先，降级到 print（与 core.logger 一致）
try:
    import structlog
    _logger = structlog.get_logger("core.kb.kb_manager")
except ImportError:
    class _FallbackLogger:
        def _log(self, level, event, **kw):
            parts = [f"[{level}] [core.kb.kb_manager] {event}"]
            parts.extend(f"{k}={v}" for k, v in kw.items())
            print(" ".join(parts), file=sys.stderr)
        def debug(self, e, **k): self._log("DEBUG", e, **k)
        def info(self, e, **k): self._log("INFO", e, **k)
        def warning(self, e, **k): self._log("WARN", e, **k)
        def error(self, e, **k): self._log("ERROR", e, **k)
    _logger = _FallbackLogger()


# ============================================================================
# 配置
# ============================================================================

OBSIDIAN_API_BASE = os.environ.get("OBSIDIAN_API_BASE", "https://localhost:27124")
OBSIDIAN_API_KEY = os.environ.get("OBSIDIAN_API_KEY", "")
OBSIDIAN_VAULT = os.environ.get("OBSIDIAN_VAULT", str(Path.home() / "Documents" / "test-interview-kb"))
OBSIDIAN_SSL_VERIFY = False  # 本地测试，忽略证书验证

LOCAL_KB_DIR = os.path.expanduser("~/Documents/ai-test-system/knowledge-base")


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class KnowledgeItem:
    """知识条目模型"""
    id: str  # 唯一ID (MD5 hash)
    title: str
    content: str
    category: str  # business-rules / historical-cases / pitfalls / templates
    module: str  # 所属模块，如 "订单支付"
    tags: list[str]
    severity: str | None = None  # high/medium/low (仅坑点)
    created_at: str = ""
    updated_at: str = ""
    source: str = "local"  # local / obsidian


# ============================================================================
# BM25 检索引擎 (纯标准库实现)
# ============================================================================

class BM25Engine:
    """BM25 检索引擎，支持中文"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = []
        self.doc_freqs = []
        self.idf = {}
        self.doc_lens = []
        self.avgdl = 0

    def tokenize(self, text: str) -> list[str]:
        """中文分词：按字符 + 按词 (简单版)"""
        # 字符级分词
        chars = list(text)
        # 2-gram 词级分词
        bigrams = [text[i:i+2] for i in range(len(text)-1)]
        return chars + bigrams

    def index(self, documents: list[dict[str, Any]]):
        """建立索引"""
        self.corpus = documents
        self.doc_freqs = []
        self.doc_lens = []
        vocab = set()

        for doc in documents:
            tokens = self.tokenize(doc['title'] + " " + doc['content'])
            freq = defaultdict(int)
            for token in tokens:
                freq[token] += 1
                vocab.add(token)
            self.doc_freqs.append(freq)
            self.doc_lens.append(len(tokens))

        if len(self.doc_lens) > 0:
            self.avgdl = sum(self.doc_lens) / len(self.doc_lens)

        # 计算 IDF
        N = len(documents)
        for token in vocab:
            df = sum(1 for doc_freq in self.doc_freqs if token in doc_freq)
            self.idf[token] = math.log((N - df + 0.5) / (df + 0.5) + 1)

    def search(self, query: str, top_k: int = 20) -> list[dict[str, Any]]:
        """检索"""
        query_tokens = self.tokenize(query)
        scores = []

        for idx, doc in enumerate(self.corpus):
            score = 0
            doc_freq = self.doc_freqs[idx]
            doc_len = self.doc_lens[idx]

            for token in query_tokens:
                if token in doc_freq:
                    tf = doc_freq[token]
                    idf = self.idf.get(token, 0)
                    numerator = tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                    score += idf * numerator / denominator

            if score > 0:
                scores.append((score, idx, doc))

        # 按分数排序
        scores.sort(reverse=True, key=lambda x: x[0])
        return [doc for _, _, doc in scores[:top_k]]


# ============================================================================
# Obsidian API 客户端
# ============================================================================

class ObsidianClient:
    """Obsidian Local REST API 客户端"""

    def __init__(self, base_url: str = OBSIDIAN_API_BASE, api_key: str = OBSIDIAN_API_KEY, ssl_verify: bool = False):
        self.base_url = base_url
        self.api_key = api_key
        self.ssl_verify = ssl_verify
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        # 创建 SSL context
        if not ssl_verify:
            self.ssl_context = ssl.create_default_context()
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
        else:
            self.ssl_context = None

    def _request(self, method: str, path: str, data: dict | None = None) -> Any:
        """发送请求"""
        import urllib.error
        import urllib.request

        url = f"{self.base_url}{path}"
        req_data = json.dumps(data).encode('utf-8') if data else None

        req = urllib.request.Request(
            url,
            data=req_data,
            headers=self.headers,
            method=method.upper()
        )

        try:
            kwargs = {}
            if not self.ssl_verify and self.ssl_context:
                kwargs['context'] = self.ssl_context

            with urllib.request.urlopen(req, timeout=10, **kwargs) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise Exception(f"Obsidian API 请求失败: {e.code} {e.reason}")
        except Exception as e:
            raise Exception(f"Obsidian API 连接失败: {str(e)}")

    def list_files(self, directory: str = "") -> list[dict]:
        """列出文件 (支持目录和全局)"""
        import urllib.parse

        if not directory:
            # 列出所有文件
            result = self._request("GET", "/")
        else:
            # URL 编码目录名
            directory_encoded = urllib.parse.quote(directory)
            result = self._request("GET", f"/?directory={directory_encoded}")

        if result and 'files' in result:
            return result['files']
        return result or []

    def get_file(self, filepath: str) -> dict | None:
        """获取文件内容 (URL 编码路径)"""
        import urllib.parse
        filepath_encoded = urllib.parse.quote(filepath)
        result = self._request("GET", f"/{filepath_encoded}")
        return result

    def create_file(self, filepath: str, content: str) -> bool:
        """创建文件 (URL 编码路径)"""
        import urllib.parse
        filepath_encoded = urllib.parse.quote(filepath)
        result = self._request("POST", f"/{filepath_encoded}", {"content": content})
        return result is not None

    def update_file(self, filepath: str, content: str) -> bool:
        """更新文件 (URL 编码路径)"""
        import urllib.parse
        filepath_encoded = urllib.parse.quote(filepath)
        result = self._request("PUT", f"/{filepath_encoded}", {"content": content})
        return result is not None

    def delete_file(self, filepath: str) -> bool:
        """删除文件 (URL 编码路径)"""
        import urllib.parse
        filepath_encoded = urllib.parse.quote(filepath)
        result = self._request("DELETE", f"/{filepath_encoded}")
        return result is not None

    def search_files(self, query: str, context_length: int = 200) -> list[dict]:
        """搜索文件 (使用 /search-with-context 端点)"""
        try:
            result = self._request("POST", "/search-with-context", {
                "query": query,
                "contextLength": context_length
            })
            return result.get('results', []) if result else []
        except Exception as e:
            _logger.debug("obsidian_search_context_failed", query=query, error=str(e))
            # Fallback 到 /search
            try:
                result = self._request("POST", "/search", {"query": query})
                return result.get('results', []) if result else []
            except Exception as e2:
                _logger.debug("obsidian_search_fallback_failed", query=query, error=str(e2))
                return []

    def is_available(self) -> bool:
        """检查 API 是否可用"""
        try:
            result = self._request("GET", "/")
            return result is not None
        except Exception as e:
            _logger.debug("obsidian_api_unavailable", error=str(e))
            return False


# ============================================================================
# 知识库管理器 (核心)
# ============================================================================

class KnowledgeBaseManager:
    """知识库管理器 - 本地 + Obsidian 双方案"""

    def __init__(self, kb_dir: str | None = None, use_obsidian: bool = True):
        self.kb_dir = Path(kb_dir or LOCAL_KB_DIR)
        self.use_obsidian = use_obsidian
        self.obsidian = ObsidianClient(ssl_verify=False)

        # 分类目录映射 (Obsidian 使用 wikilinks)
        self.category_paths = {
            'business-rules': '📋 业务规则',
            'historical-cases': '🏆 历史用例',
            'pitfalls': '⚠️ 线上坑点',
            'templates': '📝 用例模板'
        }

        # 确保本地目录存在
        for cat_dir in self.category_paths.keys():
            (self.kb_dir / cat_dir).mkdir(parents=True, exist_ok=True)

    def _generate_id(self, content: str) -> str:
        """生成唯一ID"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:12]

    def _obsidian_filepath(self, category: str, title: str) -> str:
        """生成 Obsidian 文件路径 (带 wikilinks)"""
        category_display = self.category_paths.get(category, category)
        # 使用日期前缀 + 标题
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        safe_title = re.sub(r'[\\/*?:"<>|]', '-', title)[:50]
        filename = f"{date_prefix} {safe_title}.md"
        return f"{category_display}/{filename}"

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
                except Exception as e:
                    # yaml.YAMLError 等格式损坏的 frontmatter → 安全降级为空 dict
                    _logger.debug("yaml_frontmatter_parse_failed", error=str(e))
                    frontmatter = {}
        return frontmatter
        """格式化为 Obsidian Note (YAML frontmatter + wikilinks)"""
        now = datetime.now().isoformat()

        frontmatter = {
            'id': item.id,
            'category': item.category,
            'module': item.module,
            'tags': item.tags,
            'created_at': item.created_at or now,
            'updated_at': now,
        }

        if item.severity:
            frontmatter['severity'] = item.severity

        # YAML frontmatter（安全序列化，使用 json 转义特殊字符）
        fm_lines = ['---']
        for k, v in frontmatter.items():
            if isinstance(v, list):
                fm_lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
            else:
                fm_lines.append(f"{k}: {json.dumps(str(v), ensure_ascii=False)}")
        fm_lines.append('---')

        # 内容 (支持 wikilinks)
        content_lines = fm_lines + [
            '',
            f"# {item.title}",
            '',
            f"**模块**: [[{item.module}]]",
            '',
            item.content
        ]

        return '\n'.join(content_lines)

    # -------------------------------------------------------------------------
    # 核心操作
    # -------------------------------------------------------------------------

    def search(self, query: str, category: str = None, limit: int = 20) -> list[dict]:
        """检索知识库"""
        all_items = []

        if self.use_obsidian and self.obsidian.is_available():
            # 使用 Obsidian API 搜索
            try:
                # 先尝试本地搜索 (因为 search-with-context 可能不支持)
                files = self.obsidian.list_files()

                # 搜索内容
                for file_path in files:
                    if not file_path.endswith('.md'):
                        continue

                    # 检查是否匹配查询
                    if query.lower() in file_path.lower():
                        # 匹配文件名
                        file_data = self.obsidian.get_file(file_path)
                        if file_data:
                            category_match = None
                            for cat, cat_path in self.category_paths.items():
                                if cat_path in file_path:
                                    category_match = cat
                                    break

                            if category and category_match != category:
                                continue

                            frontmatter = self._parse_yaml_frontmatter(file_data.get('content', ''))
                            all_items.append({
                                'id': frontmatter.get('id', self._generate_id(file_path)),
                                'title': frontmatter.get('title', Path(file_path).stem),
                                'content': file_data.get('content', ''),
                                'category': category_match or 'unknown',
                                'module': frontmatter.get('module', ''),
                                'severity': frontmatter.get('severity'),
                                'source': 'obsidian',
                                'filepath': file_path
                            })

            except Exception as e:
                print(f"⚠️ Obsidian 检索失败，fallback 到本地: {e}", file=sys.stderr)

        # 本地文件搜索 (fallback 或补充)
        if not all_items or not self.use_obsidian:
            # 分词：多关键词 OR 匹配（与 MCP 层 search 逻辑一致）
            keywords = [kw.strip().lower() for kw in query.split() if kw.strip()]
            if not keywords:
                keywords = [query.strip().lower()]

            for cat, cat_dir in self.category_paths.items():
                if category and cat != category:
                    continue

                cat_path = self.kb_dir / cat
                if not cat_path.exists():
                    continue

                for md_file in cat_path.glob("*.md"):
                    with open(md_file, encoding='utf-8') as f:
                        content = f.read()
                        content_lower = content.lower()
                        stem_lower = md_file.stem.lower()

                    # 多关键词 OR 匹配
                    matched = any(kw in content_lower or kw in stem_lower for kw in keywords)
                    if matched:
                        all_items.append({
                            'id': self._generate_id(content[:200]),
                            'title': md_file.stem,
                            'content': content,
                            'category': cat,
                            'module': '',
                            'severity': None,
                            'source': 'local',
                            'filepath': str(md_file)
                        })

        # BM25 重排序
        if all_items:
            engine = BM25Engine()
            engine.index(all_items)
            all_items = engine.search(query, min(limit, len(all_items)))

        return all_items

    def add(self, item: KnowledgeItem) -> bool:
        """添加知识条目"""
        item.id = item.id or self._generate_id(item.title + item.content)
        now = datetime.now().isoformat()
        item.created_at = item.created_at or now
        item.updated_at = now

        if self.use_obsidian and self.obsidian.is_available():
            # 保存到 Obsidian
            filepath = self._obsidian_filepath(item.category, item.title)
            content = self._format_obsidian_note(item)
            try:
                if self.obsidian.create_file(filepath, content):
                    print(f"✅ 已保存到 Obsidian: {filepath}")
                    return True
            except Exception as e:
                print(f"⚠️ Obsidian 保存失败，fallback 到本地: {e}", file=sys.stderr)

        # Fallback 到本地
        category_dir = self.kb_dir / item.category
        filename = f"{item.created_at[:10]}_{item.title}.md"
        filepath = category_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {item.title}\n\n")
            f.write(f"**模块**: {item.module}\n")
            f.write(f"**分类**: {item.category}\n")
            if item.severity:
                f.write(f"**严重级别**: {item.severity}\n")
            f.write(f"**标签**: {', '.join(item.tags)}\n\n")
            f.write(item.content)

        print(f"✅ 已保存到本地: {filepath}")
        return True

    def ingest(self, source_file: str, category: str, module: str = "") -> int:
        """回灌知识 (从 Excel 或 Markdown)"""
        if not os.path.exists(source_file):
            print(f"❌ 文件不存在: {source_file}")
            return 0

        count = 0

        if source_file.endswith('.xlsx'):
            if not OPENPYXL_AVAILABLE:
                print("❌ openpyxl 未安装，无法处理 Excel 文件")
                print("   安装: pip install openpyxl")
                return 0

            # Excel 回灌
            wb = openpyxl.load_workbook(source_file)
            ws = wb.active

            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or len(row) < 3:
                    continue

                title = str(row[0] or '')
                content = str(row[1] or '')
                tags = str(row[2] or '').split(',')

                if title and content:
                    item = KnowledgeItem(
                        id='',
                        title=title,
                        content=content,
                        category=category,
                        module=module,
                        tags=[t.strip() for t in tags if t.strip()]
                    )
                    if self.add(item):
                        count += 1

        elif source_file.endswith('.md'):
            # Markdown 回灌
            with open(source_file, encoding='utf-8') as f:
                content = f.read()
                title = Path(source_file).stem

                item = KnowledgeItem(
                    id='',
                    title=title,
                    content=content,
                    category=category,
                    module=module,
                    tags=[category, module]
                )
                if self.add(item):
                    count += 1

        else:
            print(f"❌ 不支持的文件格式: {source_file}")
            return 0

        print(f"✅ 已回灌 {count} 条知识到知识库")
        return count

    def export(self, query: str, output_file: str = "knowledge-context.md") -> str:
        """导出增强上下文 (Markdown 格式)"""
        results = self.search(query, limit=50)

        # 按分类分组
        grouped = defaultdict(list)
        for item in results:
            grouped[item['category']].append(item)

        # 生成 Markdown
        lines = [
            "# 知识库增强上下文",
            "",
            f"> 检索关键词: {query} | 命中 {len(results)} 条相关知识",
            "",
            f"> 来源: {'Obsidian Vault' if self.use_obsidian and self.obsidian.is_available() else '本地 Markdown'}",
            ""
        ]

        for category, items in grouped.items():
            cat_display = {
                'business-rules': '📋 业务规则',
                'historical-cases': '🏆 历史优质用例',
                'pitfalls': '⚠️ 线上坑点',
                'templates': '📝 用例模板'
            }.get(category, category)

            lines.append(f"## {cat_display} ({len(items)} 条)")

            for idx, item in enumerate(items, 1):
                lines.append(f"### {idx}. [[{item['filepath']}]]" if item['source'] == 'obsidian' else f"### {idx}. [{item['title']}]({item['filepath']})")
                lines.append(f"**模块**: {item.get('module', 'N/A')}")
                if item.get('severity'):
                    lines.append(f"**严重级别**: {item['severity']}")

                # 提取内容片段 (前 500 字)
                content_preview = item['content'][:500]
                if '---' in content_preview:
                    content_preview = content_preview.split('---', 2)[-1].strip()

                lines.append(content_preview + ("..." if len(item['content']) > 500 else ""))
                lines.append("")

        # 写入文件
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f"✅ 已导出知识上下文: {output_path}")
        return str(output_path)

    def status(self) -> dict:
        """知识库概况"""
        summary = {
            'source': 'obsidian' if self.use_obsidian and self.obsidian.is_available() else 'local',
            'categories': {},
            'total': 0,
            'last_updated': None
        }

        if self.use_obsidian and self.obsidian.is_available():
            # 统计 Obsidian Vault
            try:
                files = self.obsidian.list_files()
                for filepath in files:
                    # filepath 可能是 str 或 dict（API 返回），统一处理
                    fp_str = filepath if isinstance(filepath, str) else filepath.get('path', '') if isinstance(filepath, dict) else ''
                    if not fp_str or not fp_str.endswith('.md'):
                        continue

                    category = 'unknown'
                    for cat, cat_path in self.category_paths.items():
                        if fp_str.startswith(cat_path + '/') or fp_str == cat_path:
                            category = cat
                            break

                    summary['categories'][category] = summary['categories'].get(category, 0) + 1
                    summary['total'] += 1

                summary['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                print(f"⚠️ Obsidian 状态查询失败: {e}", file=sys.stderr)

        # 本地统计
        for cat, cat_dir in self.category_paths.items():
            cat_path = self.kb_dir / cat
            if cat_path.exists():
                count = len(list(cat_path.glob("*.md")))
                summary['categories'][cat] = summary['categories'].get(cat, 0) + count
                summary['total'] += count

        return summary


# ============================================================================
# CLI 入口
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="知识库管理器")
    subparsers = parser.add_subparsers(dest='command', required=True)

    # search 命令
    search_parser = subparsers.add_parser('search', help='检索知识库')
    search_parser.add_argument('query', help='检索关键词')
    search_parser.add_argument('--category', choices=['business-rules', 'historical-cases', 'pitfalls', 'templates'], help='限定分类')
    search_parser.add_argument('--limit', type=int, default=20, help='返回条数')
    search_parser.add_argument('--kb-dir', help='知识库目录 (仅本地模式)')

    # add 命令
    add_parser = subparsers.add_parser('add', help='添加单条知识')
    add_parser.add_argument('--category', required=True, choices=['business-rules', 'historical-cases', 'pitfalls', 'templates'])
    add_parser.add_argument('--title', required=True, help='标题')
    add_parser.add_argument('--content', required=True, help='内容')
    add_parser.add_argument('--module', default='', help='所属模块')
    add_parser.add_argument('--tags', default='', help='标签 (逗号分隔)')
    add_parser.add_argument('--severity', choices=['high', 'medium', 'low'], help='严重级别 (仅坑点)')
    add_parser.add_argument('--kb-dir', help='知识库目录 (仅本地模式)')

    # ingest 命令
    ingest_parser = subparsers.add_parser('ingest', help='回灌知识文件')
    ingest_parser.add_argument('source_file', help='源文件 (Excel 或 Markdown)')
    ingest_parser.add_argument('--category', required=True, choices=['business-rules', 'historical-cases', 'pitfalls', 'templates'])
    ingest_parser.add_argument('--module', default='', help='所属模块')
    ingest_parser.add_argument('--kb-dir', help='知识库目录 (仅本地模式)')

    # export 命令
    export_parser = subparsers.add_parser('export', help='导出增强上下文')
    export_parser.add_argument('query', help='检索关键词')
    export_parser.add_argument('--output', default='knowledge-context.md', help='输出文件路径')
    export_parser.add_argument('--kb-dir', help='知识库目录 (仅本地模式)')

    # status 命令
    status_parser = subparsers.add_parser('status', help='知识库概况')
    status_parser.add_argument('--kb-dir', help='知识库目录 (仅本地模式)')

    args = parser.parse_args()

    # 创建管理器
    kb_dir = getattr(args, 'kb_dir', None) or LOCAL_KB_DIR
    kb = KnowledgeBaseManager(
        kb_dir=kb_dir,
        use_obsidian=True  # 默认启用 Obsidian
    )

    # 执行命令
    if args.command == 'search':
        results = kb.search(args.query, category=args.category, limit=args.limit)
        print(json.dumps(results, ensure_ascii=False, indent=2))

    elif args.command == 'add':
        tags = [t.strip() for t in args.tags.split(',')] if args.tags else []
        item = KnowledgeItem(
            id='',
            title=args.title,
            content=args.content,
            category=args.category,
            module=args.module,
            tags=tags,
            severity=args.severity
        )
        kb.add(item)

    elif args.command == 'ingest':
        kb.ingest(args.source_file, args.category, args.module)

    elif args.command == 'export':
        kb.export(args.query, args.output)

    elif args.command == 'status':
        summary = kb.status()
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
