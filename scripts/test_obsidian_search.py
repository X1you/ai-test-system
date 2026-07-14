#!/usr/bin/env python3
"""
测试 Obsidian API 搜索 (URL 编码修复)
"""

import urllib.request
import urllib.error
import urllib.parse
import json
import ssl

API_BASE = "https://localhost:27124"
API_KEY = "0cf2c62343bb2f9fed9e8e40ac5be1c2a124380969a1802100b4c6216b96ef2f"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

def request(method, path, data=None):
    url = f"{API_BASE}{path}"
    req_data = json.dumps(data).encode('utf-8') if data else None

    req = urllib.request.Request(
        url,
        data=req_data,
        headers=headers,
        method=method.upper()
    )

    with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
        return json.loads(response.read().decode('utf-8'))

print("🔍 测试 Obsidian API 搜索...")

# 1. 列出所有文件 (URL 编码)
print("\n1️⃣ 列出文件...")
directory_encoded = urllib.parse.quote("🏆 历史用例")
result = request("GET", f"/?directory={directory_encoded}")
files = result.get('files', [])
print(f"   共 {len(files)} 个文件")

# 2. 获取第一个文件内容
if files:
    print("\n2️⃣ 读取第一个文件...")
    file_path = urllib.parse.quote(files[0])
    file_data = request("GET", f"/{file_path}")
    if file_data:
        content = file_data.get('content', '')
        print(f"   文件: {files[0]}")
        print(f"   长度: {len(content)}")
        print(f"   预览: {content[:200]}...")

# 3. 搜索
print("\n3️⃣ 搜索测试...")
result = request("POST", "/search-with-context", {
    "query": "库存",
    "contextLength": 100
})
results = result.get('results', [])
print(f"   命中 {len(results)} 条结果")
for r in results[:2]:
    print(f"   - {r.get('path', 'N/A')}")

print("\n🎉 搜索测试完成！")