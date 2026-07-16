#!/usr/bin/env python3
"""
TestRail Mock Server — 用于集成测试
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class MockTestRailHandler(BaseHTTPRequestHandler):
    """TestRail Mock Server"""

    _cases: dict = {}
    _next_id: int = 1

    def do_GET(self):
        path = self.path
        if "get_user/current" in path:
            self._json(200, {"id": 1, "name": "test", "email": "test@test.com"})
        elif "get_cases" in path:
            self._json(200, {"cases": list(self._cases.values())})
        elif "get_sections" in path:
            self._json(200, {"sections": []})
        elif "get_results_for_run" in path:
            self._json(200, [])
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        path = self.path
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))

        if "add_case" in path:
            cid = self._next_id
            self._next_id += 1
            body["id"] = cid
            self._cases[cid] = body
            self._json(200, body)

        elif "update_case" in path:
            parts = path.rstrip("/").split("/")
            if parts[-1].isdigit():
                cid = int(parts[-1])
                self._cases[cid] = {**self._cases.get(cid, {}), **body}
                self._json(200, self._cases[cid])
            else:
                self._json(404, {"error": "not found"})

        elif "add_section" in path:
            cid = self._next_id
            self._next_id += 1
            body["id"] = cid
            self._json(200, body)

        elif "add_result_for_case" in path:
            self._json(200, {"id": 1, "status_id": body.get("status_id", 1)})

        elif "add_run" in path:
            cid = self._next_id
            self._next_id += 1
            body["id"] = cid
            self._json(200, body)

        else:
            self._json(404, {"error": "not found"})

    def _json(self, code: int, data: dict):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


def create_mock_server(host: str = "localhost", port: int = 0) -> HTTPServer:
    """创建 Mock Server，返回 (server, port)"""
    server = HTTPServer((host, port), MockTestRailHandler)
    port = server.server_address[1]
    return server, port


# ─── 测试用例 ───

def test_push_test_cases():
    """TestRail Mock Server 集成测试"""
    server, port = create_mock_server()

    from integrations.adapters.testrail import TestRailAdapter
    from integrations.base import AdapterConfig

    config = AdapterConfig(
        platform="testrail",
        base_url=f"http://localhost:{port}",
        username="test@test.com",
        api_key="mock-key",
        project_id="1",
        field_mapping_path="integrations/mappings/testrail_mapping.yaml",
    )

    adapter = TestRailAdapter(config)
    assert adapter.health_check(), "Health check failed"

    cases = [TestCase(id="TC-001", title="测试登录", module="登录")]
    result = adapter.push_test_cases(cases)

    assert result.pushed == 1, f"Expected 1 pushed, got {result.pushed}"
    assert result.failed == 0, f"Expected 0 failed, got {result.failed}"
    assert cases[0].external_id, "External ID should be set"
    print(f"  ✅ push_test_cases: pushed={result.pushed}, failed={result.failed}")

    server.shutdown()


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from integrations.models import TestCase

    print("TestRail Mock Server 测试:")
    try:
        test_push_test_cases()
        print("  全部通过 ✅")
    except Exception as e:
        print(f"  ❌ 失败: {e}")
