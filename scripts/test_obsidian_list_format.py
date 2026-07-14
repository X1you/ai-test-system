#!/usr/bin/env python3
"""
测试 Obsidian API list_files 返回格式
"""

import urllib.request
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

req = urllib.request.Request(
    f"{API_BASE}/",
    headers=headers,
    method="GET"
)

with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
    result = json.loads(response.read().decode('utf-8'))
    print("返回类型:", type(result))
    print("\n返回内容:")
    print(json.dumps(result, ensure_ascii=False, indent=2))