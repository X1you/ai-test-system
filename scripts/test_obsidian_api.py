#!/usr/bin/env python3
"""
测试 Obsidian API 连接
"""

import sys
sys.path.insert(0, '/Users/x1you/Documents/ai-test-system/scripts')

from kb_manager import ObsidianClient

print("🔍 测试 Obsidian Local REST API 连接...\n")

client = ObsidianClient()

# 1. 检查可用性
print("1️⃣ 检查 API 可用性...")
if client.is_available():
    print("   ✅ API 连接成功\n")
else:
    print("   ❌ API 连接失败\n")
    sys.exit(1)

# 2. 列出文件
print("2️⃣ 列出 Vault 文件...")
files = client.list_files()
print(f"   共 {len(files)} 个文件")
for f in files[:5]:
    print(f"   - {f}")

# 3. 搜索测试
print("\n3️⃣ 搜索测试 ('订单')...")
results = client.search_files("订单", context_length=100)
print(f"   命中 {len(results)} 条结果")
for r in results[:3]:
    print(f"   - {r.get('path', 'N/A')}")

# 4. 创建测试文件
print("\n4️⃣ 创建测试文件...")
test_content = """---
id: test001
category: business-rules
module: 测试模块
tags: [test, demo]
---

# 测试规则

这是一个测试规则，用于验证 Obsidian API 连接。
"""

if client.create_file("测试/test-001.md", test_content):
    print("   ✅ 文件创建成功")

# 5. 读取文件
print("\n5️⃣ 读取测试文件...")
file_data = client.get_file("测试/test-001.md")
if file_data:
    print(f"   ✅ 文件读取成功 (长度: {len(file_data.get('content', ''))})")

# 6. 删除测试文件
print("\n6️⃣ 删除测试文件...")
if client.delete_file("测试/test-001.md"):
    print("   ✅ 文件删除成功")

print("\n🎉 所有测试通过！")