#!/usr/bin/env python3
"""
迁移本地知识库到 Obsidian Vault
"""

import sys
sys.path.insert(0, '/Users/x1you/Documents/ai-test-system/scripts')

from pathlib import Path
from datetime import datetime
import re

LOCAL_KB_DIR = Path("/Users/x1you/Documents/ai-test-system/knowledge-base")
OBSIDIAN_VAULT = Path("/Users/x1you/Documents/test-interview-kb")

# 分类目录映射
CATEGORY_MAP = {
    'business-rules': '📋 业务规则',
    'historical-cases': '🏆 历史用例',
    'pitfalls': '⚠️ 线上坑点',
    'templates': '📝 用例模板'
}

def parse_local_markdown(file_path: Path, category: str) -> dict:
    """解析本地 Markdown 文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    title = file_path.stem

    # 提取基本信息
    lines = content.split('\n')

    # 查找模块信息
    module = ''
    for line in lines:
        if '模块' in line and '：' in line:
            module = line.split('：', 1)[1].strip()
            break

    # 查找严重级别
    severity = None
    for line in lines:
        if '严重级别' in line and '：' in line:
            severity = line.split('：', 1)[1].strip().lower()
            break

    # 移除标题行，保留内容
    content_body = '\n'.join([l for l in lines if not l.startswith('# ')])

    return {
        'title': title,
        'content': content_body.strip(),
        'category': category,
        'module': module,
        'severity': severity,
        'original_path': str(file_path)
    }

def format_obsidian_note(item: dict, note_id: str) -> str:
    """格式化为 Obsidian Note"""
    now = datetime.now().isoformat()

    # YAML frontmatter
    frontmatter = {
        'id': note_id,
        'category': item['category'],
        'module': item['module'],
        'tags': [item['category'], item['module']] if item['module'] else [item['category']],
        'created_at': now,
        'updated_at': now,
    }

    if item['severity']:
        frontmatter['severity'] = item['severity']

    fm_lines = ['---']
    for k, v in frontmatter.items():
        if isinstance(v, list):
            fm_lines.append(f"{k}: {v}")
        else:
            fm_lines.append(f"{k}: {v}")
    fm_lines.append('---')

    # 内容
    content_lines = fm_lines + [
        '',
        f"# {item['title']}",
        '',
        f"**模块**: [[{item['module']}]]" if item['module'] else "**模块**: 未指定",
        '',
        item['content'],
        '',
        f"---",
        f"*来源: 本地知识库迁移 | 原文件: `{item['original_path']}`*"
    ]

    return '\n'.join(content_lines)

def migrate():
    """执行迁移"""
    print("🚀 开始迁移本地知识库到 Obsidian Vault...\n")

    from kb_manager import KnowledgeBaseManager
    kb = KnowledgeBaseManager(use_obsidian=False)  # 仅使用本地读取

    # 统计
    total_migrated = 0
    failed_files = []

    # 遍历所有分类
    for category, obsidian_dir in CATEGORY_MAP.items():
        local_dir = LOCAL_KB_DIR / category

        if not local_dir.exists():
            print(f"⚠️ 跳过不存在的目录: {local_dir}")
            continue

        # 创建 Obsidian 目标目录
        target_dir = OBSIDIAN_VAULT / obsidian_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        # 遍历所有 Markdown 文件
        md_files = list(local_dir.glob("*.md"))
        print(f"\n📁 {CATEGORY_MAP[category]}: {len(md_files)} 个文件")

        for md_file in md_files:
            try:
                # 解析本地文件
                item = parse_local_markdown(md_file, category)

                # 生成 Note ID
                note_id = md_file.stem[:12]

                # 格式化为 Obsidian Note
                note_content = format_obsidian_note(item, note_id)

                # 保存到 Obsidian Vault
                note_filename = f"{datetime.now().strftime('%Y-%m-%d')}_{item['title']}.md"
                note_path = target_dir / note_filename

                with open(note_path, 'w', encoding='utf-8') as f:
                    f.write(note_content)

                total_migrated += 1
                print(f"  ✅ {md_file.name} → {note_filename}")

            except Exception as e:
                print(f"  ❌ {md_file.name} 迁移失败: {e}")
                failed_files.append((str(md_file), str(e)))

    # 打印摘要
    print("\n" + "="*50)
    print(f"✅ 迁移完成！共迁移 {total_migrated} 个文件")
    if failed_files:
        print(f"\n⚠️ {len(failed_files)} 个文件迁移失败:")
        for path, error in failed_files:
            print(f"  - {path}: {error}")

    print(f"\n📁 Obsidian Vault: {OBSIDIAN_VAULT}")
    print("🔍 请在 Obsidian 中打开 Vault 查看迁移结果")

if __name__ == '__main__':
    migrate()