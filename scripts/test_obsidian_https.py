#!/usr/bin/env python3
"""
测试 Obsidian API 连接 (HTTPS)
"""

import urllib.request
import urllib.error
import json
import ssl

API_BASE = "https://localhost:27124"
API_KEY = "0cf2c62343bb2f9fed9e8e40ac5be1c2a124380969a1802100b4c6216b96ef2f"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 创建 SSL context (忽略证书验证，仅用于测试)
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

    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        if e.code == 404:
            return None
        raise
    except Exception as e:
        print(f"Request Error: {str(e)}")
        raise

print("🔍 测试 Obsidian HTTPS API 连接...\n")

# 1. 根目录
print("1️⃣ 测试根目录请求...")
result = request("GET", "/")
if result:
    print("   ✅ 连接成功")
    print(f"   响应: {json.dumps(result, ensure_ascii=False, indent=2)[:200]}")

# 2. 列出文件
print("\n2️⃣ 列出文件...")
result = request("GET", "/?directory=")
if result:
    files = result.get('files', [])
    print(f"   共 {len(files)} 个文件")
    for f in files[:5]:
        print(f"   - {f}")

# 3. 搜索测试
print("\n3️⃣ 搜索测试...")
result = request("POST", "/search", {
    "query": "订单",
    "contextLength": 100
})
if result:
    results = result.get('results', [])
    print(f"   命中 {len(results)} 条结果")
    for r in results[:3]:
        print(f"   - {r.get('path', 'N/A')}")

print("\n🎉 HTTPS 测试完成！")