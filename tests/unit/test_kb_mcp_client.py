#!/usr/bin/env python3
"""测试 core/kb/mcp_client.py — MCPClient + ObsidianAPIClient + extract_keywords。

覆盖目标：
  - ObsidianAPIClient: __init__(ssl) / _request(HTTPError/404/异常) / search / is_available
  - extract_keywords: 标题提取 / 模块标签 / 内容3-gram / 停用词 / 去重
  - MCPClient: _generate_id / _safe_path / _parse_yaml_frontmatter
  - list_files / read_file(各种失败) / create_file / update_file / delete_file
  - search(三层: API/标签/全文) / status / _format_obsidian_note
  - create_mcp_client 便捷函数

设计：使用 tmp_path 构造真实临时目录作为 vault（避免 mock Path 操作），
     Obsidian API 用 Mock 替换，不发起真实 HTTP。
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════════
# ObsidianAPIClient
# ═══════════════════════════════════════════════════════════════


class TestObsidianAPIClientInit:
    """测试 ObsidianAPIClient 初始化。"""

    def test_init_https_ssl_disabled(self):
        # 测试 https + ssl_verify=False 创建不校验证书的 ssl_context
        from core.kb.mcp_client import ObsidianAPIClient

        c = ObsidianAPIClient(base_url="https://localhost:27124", api_key="k", ssl_verify=False)
        assert c._ssl_context is not None
        assert c._ssl_context.check_hostname is False

    def test_init_http_no_ssl_context(self):
        # 测试 http 不创建 ssl_context
        from core.kb.mcp_client import ObsidianAPIClient

        c = ObsidianAPIClient(base_url="http://localhost:27123", ssl_verify=True)
        assert c._ssl_context is None

    def test_init_strips_trailing_slash(self):
        # 测试 base_url 去掉尾部斜杠
        from core.kb.mcp_client import ObsidianAPIClient

        c = ObsidianAPIClient(base_url="http://localhost:27123/")
        assert c.base_url == "http://localhost:27123"


class TestObsidianAPIRequest:
    """测试 ObsidianAPIClient._request 方法。"""

    def test_request_success(self):
        # 测试正常请求返回 JSON
        from core.kb.mcp_client import ObsidianAPIClient

        c = ObsidianAPIClient(base_url="http://localhost:1", api_key="key")
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_resp)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_ctx):
            result = c._request("GET", "/test")
        assert result == {"ok": True}

    def test_request_with_data_and_ssl_context(self):
        # 测试带 data 的 POST 请求 + ssl_context 传入
        from core.kb.mcp_client import ObsidianAPIClient

        c = ObsidianAPIClient(base_url="https://localhost:1", ssl_verify=False)
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{}'
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_resp)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_ctx) as mock_urlopen:
            c._request("POST", "/p", data={"q": 1})
            call_kwargs = mock_urlopen.call_args[1]
            assert "context" in call_kwargs

    def test_request_404_returns_none(self):
        # 测试 404 错误返回 None
        import urllib.error

        from core.kb.mcp_client import ObsidianAPIClient

        c = ObsidianAPIClient(base_url="http://localhost:1")
        err = urllib.error.HTTPError("url", 404, "Not Found", {}, None)
        with patch("urllib.request.urlopen", side_effect=err):
            result = c._request("GET", "/missing")
        assert result is None

    def test_request_http_error_500_raises(self):
        # 测试非 404 HTTP 错误抛出异常
        import urllib.error

        from core.kb.mcp_client import ObsidianAPIClient

        c = ObsidianAPIClient(base_url="http://localhost:1")
        err = urllib.error.HTTPError("url", 500, "Server Error", {}, None)
        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(urllib.error.HTTPError):
                c._request("GET", "/fail")

    def test_request_connection_error_raises(self):
        # 测试连接异常抛出
        from core.kb.mcp_client import ObsidianAPIClient

        c = ObsidianAPIClient(base_url="http://localhost:1")
        with patch("urllib.request.urlopen", side_effect=ConnectionError("refused")):
            with pytest.raises(ConnectionError):
                c._request("GET", "/x")


class TestObsidianAPISearch:
    """测试 ObsidianAPIClient.search 方法。"""

    def test_search_with_context_success(self):
        # 测试 search-with-context 端点成功返回结果
        from core.kb.mcp_client import ObsidianAPIClient

        c = ObsidianAPIClient(base_url="http://localhost:1")
        with patch.object(c, "_request", return_value={"results": [{"f": 1}]}):
            result = c.search("kw")
        assert result == [{"f": 1}]

    def test_search_context_fails_fallback_search(self):
        # 测试 search-with-context 失败后回退到 /search 端点
        from core.kb.mcp_client import ObsidianAPIClient

        c = ObsidianAPIClient(base_url="http://localhost:1")

        call_count = [0]

        def mock_req(method, path, data=None, timeout=10.0):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("context failed")
            return {"results": [{"f": 2}]}

        with patch.object(c, "_request", side_effect=mock_req):
            result = c.search("kw")
        assert result == [{"f": 2}]

    def test_search_all_fail_returns_empty(self):
        # 测试两个端点都失败时返回空列表
        from core.kb.mcp_client import ObsidianAPIClient

        c = ObsidianAPIClient(base_url="http://localhost:1")
        with patch.object(c, "_request", side_effect=Exception("err")):
            result = c.search("kw")
        assert result == []


class TestObsidianAPIIsAvailable:
    """测试 ObsidianAPIClient.is_available 方法。"""

    def test_is_available_true(self):
        # 测试探测成功返回 True
        from core.kb.mcp_client import ObsidianAPIClient

        c = ObsidianAPIClient(base_url="http://localhost:1")
        with patch.object(c, "_request", return_value={}):
            assert c.is_available() is True

    def test_is_available_all_ports_fail(self):
        # 测试所有端口探测失败返回 False
        from core.kb.mcp_client import ObsidianAPIClient

        c = ObsidianAPIClient(base_url="")
        with patch.object(c, "_request", side_effect=Exception("nope")):
            assert c.is_available() is False


# ═══════════════════════════════════════════════════════════════
# extract_keywords
# ═══════════════════════════════════════════════════════════════


class TestExtractKeywords:
    """测试 extract_keywords 关键词提取函数。"""

    def test_extract_from_title_strips_id_prefix(self):
        # 测试去掉 TC-001 编号前缀后提取标题关键词
        from core.kb.mcp_client import extract_keywords

        tags = extract_keywords("TC-001 登录验证")
        assert any("登录" in t or "验证" in t for t in tags)

    def test_extract_from_module(self):
        # 测试模块名作为标签（取最后一段）
        from core.kb.mcp_client import extract_keywords

        tags = extract_keywords("短题", module="项目/批次/订单模块")
        assert "订单模块" in tags

    def test_extract_strips_stopwords(self):
        # 测试停用词被过滤
        from core.kb.mcp_client import extract_keywords

        tags = extract_keywords("测试 用例 功能")
        # "测试" "用例" "功能" 都是停用词，应被过滤
        assert len(tags) == 0

    def test_extract_from_content_trigram(self):
        # 测试内容中的高频 3-gram 补充标签
        from core.kb.mcp_client import extract_keywords

        tags = extract_keywords("ab", content="支付超时 支付超时 支付超时")
        # 应从内容提取 "支付超" 等 trigram
        assert len(tags) > 0

    def test_extract_dedup_and_limit(self):
        # 测试去重和 max_tags 截断
        from core.kb.mcp_client import extract_keywords

        tags = extract_keywords("登录 注册 退出 绑定", max_tags=2)
        assert len(tags) <= 2

    def test_extract_empty_title(self):
        # 测试空标题返回空列表
        from core.kb.mcp_client import extract_keywords

        assert extract_keywords("") == []


# ═══════════════════════════════════════════════════════════════
# MCPClient — 路径/ID/frontmatter 工具方法
# ═══════════════════════════════════════════════════════════════


class TestMCPClientUtilities:
    """测试 MCPClient 的工具方法。"""

    def test_generate_id(self, tmp_path):
        # 测试 _generate_id 返回 12 位 md5 前缀
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        id_val = client._generate_id("test content")
        assert len(id_val) == 12

    def test_safe_path_valid(self, tmp_path):
        # 测试 vault 内合法路径通过校验
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        p = client._safe_path("sub/file.md")
        assert str(tmp_path) in str(p)

    def test_safe_path_traversal_blocked(self, tmp_path):
        # 测试路径穿越攻击被拒绝（ValueError）
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        with pytest.raises(ValueError, match="非法路径"):
            client._safe_path("../../etc/passwd")

    def test_parse_yaml_frontmatter_with_yaml(self, tmp_path):
        # 测试标准 YAML frontmatter 解析
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        content = "---\nid: abc\ntitle: 测试\n---\n正文"
        fm = client._parse_yaml_frontmatter(content)
        assert fm.get("id") == "abc"
        assert fm.get("title") == "测试"

    def test_parse_yaml_frontmatter_no_frontmatter(self, tmp_path):
        # 测试无 frontmatter 返回空 dict
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        assert client._parse_yaml_frontmatter("纯正文内容") == {}

    def test_parse_yaml_frontmatter_malformed(self, tmp_path):
        # 测试损坏的 YAML frontmatter 安全降级为空 dict
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        content = "---\n: : : bad yaml\n---\n正文"
        result = client._parse_yaml_frontmatter(content)
        assert isinstance(result, dict)

    def test_parse_yaml_frontmatter_no_delimiter_close(self, tmp_path):
        # 测试只有开头 --- 但无结尾分隔的情况
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        content = "---\nid: x"
        result = client._parse_yaml_frontmatter(content)
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════
# MCPClient — list_files / read_file
# ═══════════════════════════════════════════════════════════════


class TestListFiles:
    """测试 MCPClient.list_files 方法。"""

    def test_list_files_all_categories(self, tmp_path):
        # 测试列出所有分类下的文件
        from core.kb.mcp_client import MCPClient, CATEGORY_PATHS

        # 创建一个分类目录下的 md 文件
        cat_dir = tmp_path / CATEGORY_PATHS["business-rules"]
        cat_dir.mkdir(parents=True)
        (cat_dir / "rule1.md").write_text("x")
        (cat_dir / "sub" / "rule2.md").parent.mkdir(parents=True)
        (cat_dir / "sub" / "rule2.md").write_text("y")

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        files = client.list_files()
        assert len(files) == 2

    def test_list_files_by_category(self, tmp_path):
        # 测试按指定分类列出文件
        from core.kb.mcp_client import MCPClient, CATEGORY_PATHS

        for cat in ["business-rules", "pitfalls"]:
            d = tmp_path / CATEGORY_PATHS[cat]
            d.mkdir(parents=True)
            (d / "f.md").write_text("x")

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        files = client.list_files(category="business-rules")
        assert len(files) == 1
        assert "rule" in files[0] or "f.md" in files[0]

    def test_list_files_category_not_exists(self, tmp_path):
        # 测试指定分类目录不存在时返回空
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        assert client.list_files(category="business-rules") == []

    def test_list_files_empty_vault(self, tmp_path):
        # 测试空 vault 返回空列表
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        assert client.list_files() == []


class TestReadFile:
    """测试 MCPClient.read_file 方法。"""

    def test_read_file_success(self, tmp_path):
        # 测试正常读取文件
        from core.kb.mcp_client import MCPClient, CATEGORY_PATHS

        cat_dir = tmp_path / CATEGORY_PATHS["business-rules"]
        cat_dir.mkdir(parents=True)
        fpath = cat_dir / "note.md"
        fpath.write_text("hello", encoding="utf-8")

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        rel = str(fpath.relative_to(tmp_path))
        result = client.read_file(rel)
        assert result is not None
        assert result["content"] == "hello"

    def test_read_file_not_exists(self, tmp_path):
        # 测试文件不存在返回 None
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        assert client.read_file("nonexistent.md") is None

    def test_read_file_traversal_blocked(self, tmp_path):
        # 测试路径穿越被阻止返回 None
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        assert client.read_file("../../etc/passwd") is None

    def test_read_file_too_large(self, tmp_path):
        # 测试超过 MAX_READ_FILE_SIZE 的大文件被跳过返回 None
        from core.kb.mcp_client import MCPClient, CATEGORY_PATHS

        cat_dir = tmp_path / CATEGORY_PATHS["business-rules"]
        cat_dir.mkdir(parents=True)
        fpath = cat_dir / "big.md"
        # 写入超过 2MB 的文件
        fpath.write_bytes(b"x" * (MCPClient.MAX_READ_FILE_SIZE + 100))

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        rel = str(fpath.relative_to(tmp_path))
        assert client.read_file(rel) is None


# ═══════════════════════════════════════════════════════════════
# MCPClient — create_file / update_file / delete_file
# ═══════════════════════════════════════════════════════════════


class TestCreateFile:
    """测试 MCPClient.create_file 方法。"""

    def test_create_file_flat(self, tmp_path):
        # 测试普通分类平铺存储创建成功
        from core.kb.mcp_client import MCPClient, KnowledgeItem

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        item = KnowledgeItem(
            id="", title="测试规则", content="内容",
            category="business-rules", module="mod", tags=["t1"]
        )
        assert client.create_file(item) is True
        assert item.filepath != ""
        # 确认文件确实写入
        assert (tmp_path / item.filepath).exists()

    def test_create_file_historical_cases_with_project(self, tmp_path):
        # 测试历史用例按 项目/批次/ 分层存储
        from core.kb.mcp_client import MCPClient, KnowledgeItem

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        item = KnowledgeItem(
            id="", title="TC-001", content="c",
            category="historical-cases", module="projA/batchB/modC", tags=[]
        )
        assert client.create_file(item) is True
        assert "projA" in item.filepath
        assert "batchB" in item.filepath

    def test_create_file_auto_extract_tags(self, tmp_path):
        # 测试未指定 tags 时自动提取关键词标签
        from core.kb.mcp_client import MCPClient, KnowledgeItem

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        item = KnowledgeItem(
            id="", title="支付验证", content="c",
            category="business-rules", module="支付模块", tags=[]
        )
        client.create_file(item)
        assert len(item.tags) > 0

    def test_create_file_write_failure(self, tmp_path):
        # 测试文件写入失败（OSError）返回 False
        from core.kb.mcp_client import MCPClient, KnowledgeItem

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        item = KnowledgeItem(
            id="", title="t", content="c",
            category="business-rules", module="m", tags=[]
        )
        with patch("builtins.open", side_effect=OSError("disk full")):
            assert client.create_file(item) is False


class TestUpdateFile:
    """测试 MCPClient.update_file 方法。"""

    def test_update_file_success(self, tmp_path):
        # 测试更新已存在文件成功
        from core.kb.mcp_client import MCPClient, CATEGORY_PATHS

        cat_dir = tmp_path / CATEGORY_PATHS["business-rules"]
        cat_dir.mkdir(parents=True)
        f = cat_dir / "old.md"
        f.write_text("old", encoding="utf-8")

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        rel = str(f.relative_to(tmp_path))
        assert client.update_file(rel, "new content") is True
        assert f.read_text() == "new content"

    def test_update_file_not_exists(self, tmp_path):
        # 测试更新不存在的文件返回 False
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        assert client.update_file("nofile.md", "x") is False

    def test_update_file_traversal_blocked(self, tmp_path):
        # 测试更新路径穿越被阻止返回 False
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        assert client.update_file("../../etc/shadow", "x") is False

    def test_update_file_write_error(self, tmp_path):
        # 测试更新时写入异常返回 False
        from core.kb.mcp_client import MCPClient, CATEGORY_PATHS

        cat_dir = tmp_path / CATEGORY_PATHS["business-rules"]
        cat_dir.mkdir(parents=True)
        f = cat_dir / "w.md"
        f.write_text("x")

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        rel = str(f.relative_to(tmp_path))
        with patch("builtins.open", side_effect=OSError("err")):
            assert client.update_file(rel, "new") is False


class TestDeleteFile:
    """测试 MCPClient.delete_file 方法。"""

    def test_delete_file_success(self, tmp_path):
        # 测试删除已存在文件成功
        from core.kb.mcp_client import MCPClient, CATEGORY_PATHS

        cat_dir = tmp_path / CATEGORY_PATHS["business-rules"]
        cat_dir.mkdir(parents=True)
        f = cat_dir / "del.md"
        f.write_text("x")

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        rel = str(f.relative_to(tmp_path))
        assert client.delete_file(rel) is True
        assert not f.exists()

    def test_delete_file_not_exists(self, tmp_path):
        # 测试删除不存在的文件返回 False
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        assert client.delete_file("nofile.md") is False

    def test_delete_file_traversal_blocked(self, tmp_path):
        # 测试删除路径穿越被阻止返回 False
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        assert client.delete_file("../../etc/passwd") is False


# ═══════════════════════════════════════════════════════════════
# MCPClient — search (三层)
# ═══════════════════════════════════════════════════════════════


class TestSearch:
    """测试 MCPClient.search 三层搜索策略。"""

    def test_search_fulltext_match(self, tmp_path):
        # 测试 Layer 3 全文匹配命中
        from core.kb.mcp_client import MCPClient, CATEGORY_PATHS

        cat_dir = tmp_path / CATEGORY_PATHS["business-rules"]
        cat_dir.mkdir(parents=True)
        (cat_dir / "rule.md").write_text(
            "---\nid: r1\ntags: [支付]\n---\n# 支付规则\n支付超时处理", encoding="utf-8"
        )

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        results = client.search("支付")
        assert len(results) >= 1
        assert results[0]["category"] == "business-rules"

    def test_search_query_only_whitespace(self, tmp_path):
        # 测试 query 仅含空白时分词回退到原始 query（覆盖 line 446）
        from core.kb.mcp_client import MCPClient, CATEGORY_PATHS

        cat_dir = tmp_path / CATEGORY_PATHS["business-rules"]
        cat_dir.mkdir(parents=True)
        (cat_dir / "ws.md").write_text("---\ntags: []\n---\n空白测试", encoding="utf-8")

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        # query="  " 全是空格 → keywords 为空 → 回退到 [query.strip().lower()] = [""]
        # 空字符串 "" 是所有字符串子串，因此会匹配所有文件
        results = client.search("  ")
        assert len(results) == 1

    def test_search_with_frontmatter_title(self, tmp_path):
        # 测试 frontmatter 含 title 字段时使用它（覆盖 line 509）
        from core.kb.mcp_client import MCPClient, CATEGORY_PATHS

        cat_dir = tmp_path / CATEGORY_PATHS["business-rules"]
        cat_dir.mkdir(parents=True)
        (cat_dir / "f.md").write_text(
            "---\ntitle: 自定义标题\ntags: [搜索]\n---\n搜索内容", encoding="utf-8"
        )

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        results = client.search("搜索")
        assert len(results) == 1
        assert results[0]["title"] == "自定义标题"

    def test_search_skips_unreadable_file(self, tmp_path):
        # 测试 search 遍历时 read_file 返回 None 被跳过（覆盖 line 480）
        from core.kb.mcp_client import MCPClient, CATEGORY_PATHS

        cat_dir = tmp_path / CATEGORY_PATHS["business-rules"]
        cat_dir.mkdir(parents=True)
        (cat_dir / "good.md").write_text("---\ntags: [命中]\n---\n命中词", encoding="utf-8")

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        # mock list_files 返回一个好文件 + 一个 read_file 返回 None 的文件
        good_rel = str((cat_dir / "good.md").relative_to(tmp_path))
        with patch.object(client, "list_files", return_value=[good_rel, "bad.md"]):
            results = client.search("命中")
        assert len(results) == 1

    def test_search_api_filters_out_non_candidate(self, tmp_path):
        # 测试 API 返回候选集时，不在候选集中的文件被跳过（覆盖 line 476）
        from core.kb.mcp_client import MCPClient, CATEGORY_PATHS

        cat_dir = tmp_path / CATEGORY_PATHS["business-rules"]
        cat_dir.mkdir(parents=True)
        (cat_dir / "in_api.md").write_text("---\ntags: [关键词]\n---\n关键词命中", encoding="utf-8")
        (cat_dir / "not_in_api.md").write_text("---\ntags: [关键词]\n---\n关键词也命中", encoding="utf-8")

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        client._obsidian_api = MagicMock()
        client._obsidian_api_checked = True
        client._obsidian_api_available = True
        in_api_rel = str((cat_dir / "in_api.md").relative_to(tmp_path))
        # API 只返回 in_api.md 作为候选
        client._obsidian_api.search.return_value = [{"filename": in_api_rel}]

        results = client.search("关键词")
        # not_in_api.md 不在 API 候选中，被跳过
        assert len(results) == 1
        assert "in_api" in results[0]["filepath"]

    def test_search_frontmatter_tags_as_string(self, tmp_path):
        # 测试 frontmatter tags 为字符串时拆分（覆盖 line 489）
        from core.kb.mcp_client import MCPClient, CATEGORY_PATHS

        cat_dir = tmp_path / CATEGORY_PATHS["business-rules"]
        cat_dir.mkdir(parents=True)
        # tags 用字符串格式（逗号分隔），模拟无 yaml 时的简单解析
        content = "---\ntags: tag1,tag2\n---\n搜索词命中内容"
        (cat_dir / "strtags.md").write_text(content, encoding="utf-8")

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        results = client.search("搜索词")
        assert len(results) == 1
        # 验证 tags 被拆分为列表
        assert isinstance(results[0]["tags"], list)

    def test_search_tag_match_weighted(self, tmp_path):
        # 测试 Layer 2 标签匹配加权（标签命中得分更高）
        from core.kb.mcp_client import MCPClient, CATEGORY_PATHS

        cat_dir = tmp_path / CATEGORY_PATHS["business-rules"]
        cat_dir.mkdir(parents=True)
        # 文件A：标签命中
        (cat_dir / "a.md").write_text(
            "---\ntags: [登录]\n---\n普通内容", encoding="utf-8"
        )
        # 文件B：仅全文命中
        (cat_dir / "b.md").write_text(
            "---\ntags: [其他]\n---\n登录测试", encoding="utf-8"
        )

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        results = client.search("登录")
        assert len(results) == 2
        # 标签命中的 a.md 应排前面（得分更高）
        assert "a.md" in results[0]["filepath"]

    def test_search_no_match(self, tmp_path):
        # 测试无匹配返回空列表
        from core.kb.mcp_client import MCPClient, CATEGORY_PATHS

        cat_dir = tmp_path / CATEGORY_PATHS["business-rules"]
        cat_dir.mkdir(parents=True)
        (cat_dir / "x.md").write_text("不相关内容")

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        assert client.search("完全不存在的关键词xyz") == []

    def test_search_with_api_available(self, tmp_path):
        # 测试 Layer 1 Obsidian API 可用时的搜索流程
        from core.kb.mcp_client import MCPClient, CATEGORY_PATHS

        cat_dir = tmp_path / CATEGORY_PATHS["business-rules"]
        cat_dir.mkdir(parents=True)
        (cat_dir / "api_match.md").write_text("API搜索结果内容", encoding="utf-8")

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        # mock API 可用 + 返回候选路径
        client._obsidian_api = MagicMock()
        client._obsidian_api_checked = True
        client._obsidian_api_available = True
        client._obsidian_api.search.return_value = [
            {"filename": str(cat_dir / "api_match.md")}
        ]
        results = client.search("API")
        # API 候选集限制了遍历范围，但内容也要匹配
        assert isinstance(results, list)

    def test_search_api_exception_fallback(self, tmp_path):
        # 测试 API 搜索异常时降级到全量遍历
        from core.kb.mcp_client import MCPClient, CATEGORY_PATHS

        cat_dir = tmp_path / CATEGORY_PATHS["business-rules"]
        cat_dir.mkdir(parents=True)
        (cat_dir / "fallback.md").write_text("关键词命中", encoding="utf-8")

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        client._obsidian_api = MagicMock()
        client._obsidian_api_checked = True
        client._obsidian_api_available = True
        client._obsidian_api.search.side_effect = Exception("API down")

        results = client.search("关键词")
        assert len(results) >= 1


class TestCheckObsidianAPI:
    """测试 _check_obsidian_api 延迟检查与缓存。"""

    def test_check_no_api_returns_false(self, tmp_path):
        # 测试无 API client 时返回 False
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        assert client._check_obsidian_api() is False

    def test_check_instance_cache_hit(self, tmp_path):
        # 测试实例级缓存命中（已检查过直接返回）
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=True)
        client._obsidian_api = MagicMock()
        client._obsidian_api_checked = True
        client._obsidian_api_available = True
        assert client._check_obsidian_api() is True

    def test_check_process_cache_hit(self, tmp_path):
        # 测试进程级缓存命中（TTL 内复用结果）
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=True)
        client._obsidian_api = MagicMock()
        client._obsidian_api.base_url = "http://test:1"
        # 预填进程缓存
        import time

        MCPClient._api_probe_cache["http://test:1"] = (time.time(), True)
        assert client._check_obsidian_api() is True
        # 清理
        del MCPClient._api_probe_cache["http://test:1"]

    def test_check_actual_probe(self, tmp_path):
        # 测试实际探测（无缓存时调用 is_available）
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=True)
        client._obsidian_api = MagicMock()
        client._obsidian_api.base_url = "http://probe:1"
        client._obsidian_api.is_available.return_value = True
        # 清除可能存在的缓存
        MCPClient._api_probe_cache.pop("http://probe:1", None)
        assert client._check_obsidian_api() is True
        client._obsidian_api.is_available.assert_called_once()


# ═══════════════════════════════════════════════════════════════
# MCPClient — _format_obsidian_note / status
# ═══════════════════════════════════════════════════════════════


class TestFormatNote:
    """测试 _format_obsidian_note 方法。"""

    def test_format_note_with_yaml(self, tmp_path):
        # 测试格式化 Obsidian Note（YAML frontmatter + 正文）
        from core.kb.mcp_client import MCPClient, KnowledgeItem

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        item = KnowledgeItem(
            id="id1", title="标题", content="正文",
            category="business-rules", module="模块", tags=["t"],
            severity="high", created_at="2024-01-01", updated_at="2024-01-02"
        )
        result = client._format_obsidian_note(item)
        assert "---" in result
        assert "# 标题" in result
        assert "正文" in result
        assert "severity" in result


class TestStatus:
    """测试 MCPClient.status 方法。"""

    def test_status_basic(self, tmp_path):
        # 测试 status 返回知识库概况
        from core.kb.mcp_client import MCPClient, CATEGORY_PATHS

        cat_dir = tmp_path / CATEGORY_PATHS["business-rules"]
        cat_dir.mkdir(parents=True)
        (cat_dir / "a.md").write_text("x")
        (cat_dir / "b.md").write_text("y")

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        result = client.status()
        assert result["source"] == "mcp-obsidian"
        assert result["total"] == 2
        assert result["categories"]["business-rules"] == 2

    def test_status_api_unavailable(self, tmp_path):
        # 测试 API 已检查但不可用时 status 显示 fallback
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=True)
        client._obsidian_api = MagicMock()
        client._obsidian_api_checked = True
        client._obsidian_api_available = False
        result = client.status()
        assert "fallback" in result["search_backend"]

    def test_status_api_available(self, tmp_path):
        # 测试 API 可用时 status 显示 available（覆盖 line 702）
        from core.kb.mcp_client import MCPClient

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=True)
        client._obsidian_api = MagicMock()
        client._obsidian_api_checked = True
        client._obsidian_api_available = True
        result = client.status()
        assert result["search_backend"] == "available"


class TestMCPClientEdgeCases:
    """测试 MCPClient 的边界和异常路径。"""

    def test_ensure_directories_oserror(self, tmp_path):
        # 测试 _ensure_directories 遇到 OSError 时不崩溃（覆盖 289-291）
        from core.kb.mcp_client import MCPClient

        with patch("pathlib.Path.mkdir", side_effect=OSError("permission denied")):
            # 不应抛出异常
            client = MCPClient(vault_path=str(tmp_path / "readonly"), use_obsidian_api=False)
        # client 仍可正常使用
        assert client.vault_path is not None

    def test_read_file_stat_oserror(self, tmp_path):
        # 测试 read_file stat 失败返回 None（覆盖 385-387）
        # _safe_path 内部 resolve() 也调用 stat，所以直接 mock _safe_path 返回的路径对象
        from core.kb.mcp_client import MCPClient, CATEGORY_PATHS

        cat_dir = tmp_path / CATEGORY_PATHS["business-rules"]
        cat_dir.mkdir(parents=True)

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        # mock_path.exists() 返回 True，但 stat() 抛 OSError
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.stat.side_effect = OSError("stat fail")
        with patch.object(client, "_safe_path", return_value=mock_path):
            assert client.read_file("any.md") is None

    def test_read_file_read_oserror(self, tmp_path):
        # 测试 read_file 文件读取 OSError 返回 None（覆盖 392-394）
        from core.kb.mcp_client import MCPClient, CATEGORY_PATHS

        cat_dir = tmp_path / CATEGORY_PATHS["business-rules"]
        cat_dir.mkdir(parents=True)
        f = cat_dir / "readfail.md"
        f.write_text("x")

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        rel = str(f.relative_to(tmp_path))
        with patch("builtins.open", side_effect=OSError("read fail")):
            assert client.read_file(rel) is None

    def test_create_file_path_blocked(self, tmp_path):
        # 测试 create_file 路径校验失败返回 False（覆盖 589-591）
        from core.kb.mcp_client import MCPClient, KnowledgeItem

        client = MCPClient(vault_path=str(tmp_path), use_obsidian_api=False)
        item = KnowledgeItem(
            id="", title="t", content="c",
            category="business-rules", module="m", tags=[]
        )
        with patch.object(client, "_safe_path", side_effect=ValueError("blocked")):
            assert client.create_file(item) is False


# ═══════════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════════


class TestCreateMCPClient:
    """测试 create_mcp_client 便捷函数。"""

    def test_create_mcp_client_default(self, tmp_path):
        # 测试 create_mcp_client 创建实例
        from core.kb import mcp_client as mc_mod

        with patch.object(mc_mod, "MCPClient") as MockC:
            mc_mod.create_mcp_client("/tmp/x")
            MockC.assert_called_once_with("/tmp/x")

    def test_create_mcp_client_none_uses_default(self):
        # 测试不传参数时使用默认 vault 路径
        from core.kb import mcp_client as mc_mod

        with patch.object(mc_mod, "MCPClient") as MockC:
            mc_mod.create_mcp_client(None)
            MockC.assert_called_once()
