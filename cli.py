#!/usr/bin/env python3
"""
AI 测试用例生成系统 — CLI 入口

用法:
    python cli.py run <requirements.md> [options]    # 执行全流程
    python cli.py resume [--output DIR]               # 从断点继续
    python cli.py status [--output DIR]               # 查看状态
    python cli.py config                              # 查看当前配置

选项:
    -o, --output DIR      输出目录（默认 ./output）
    --mode MODE           auto | semi | step（默认 semi）
    -d, --dimensions DIM  basic | all | positive,negative（默认 basic）
    -f, --formats FMT     excel | xmind | excel,xmind（默认 excel）
    --config FILE         配置文件路径（默认 config.yaml）
"""

import argparse
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config_loader import load_config, validate_config
from core.pipeline import Pipeline

# 延迟导入：只在需要时导入 LLMClient，避免 config 命令受影响
# LLMError 在需要时再导入


def cmd_run(args):
    """执行全流程"""
    config = _load_and_validate(args.config)
    if config is None:
        return 1

    mode = args.mode or config.get("pipeline", {}).get("default_mode", "semi")
    dimensions = args.dimensions or config.get("pipeline", {}).get("default_dimensions", "basic")
    formats = args.formats or config.get("pipeline", {}).get("default_formats", "excel")

    req_path = Path(args.requirements)
    if not req_path.exists():
        print(f"❌ 需求文档不存在: {args.requirements}", file=sys.stderr)
        return 1

    try:
        from core.llm_client import LLMError

        pipeline = Pipeline(config, args.output)
        pipeline.run(
            requirements_file=str(req_path),
            mode=mode,
            dimensions=dimensions,
            formats=formats,
        )
    except LLMError as e:
        print(f"\n❌ {e}", file=sys.stderr)
        return 1

    return 0


def cmd_resume(args):
    """从断点继续"""
    config = _load_and_validate(args.config)
    if config is None:
        return 1

    dimensions = args.dimensions or config.get("pipeline", {}).get("default_dimensions", "basic")
    formats = args.formats or config.get("pipeline", {}).get("default_formats", "excel")

    pipeline = Pipeline(config, args.output)
    pipeline.resume(dimensions=dimensions, formats=formats)
    return 0


def cmd_status(args):
    """查看状态"""
    config = load_config(args.config)
    pipeline = Pipeline(config, args.output)
    pipeline.status()
    return 0


def cmd_config(args):
    """查看当前配置"""
    config = load_config(args.config)

    print("═" * 60)
    print("  ⚙️  当前配置")
    print("═" * 60)
    print()

    llm = config.get("llm", {})
    print(f"  LLM Provider:  {llm.get('provider', 'N/A')}")
    print(f"  LLM Model:     {llm.get('model', 'N/A')}")
    print(f"  LLM Base URL:  {llm.get('base_url', 'N/A')}")
    api_key = llm.get("api_key", "")
    masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else ("***" if api_key else "未配置")
    print(f"  LLM API Key:   {masked}")
    print()

    kb = config.get("knowledge_base", {})
    print(f"  知识库启用:     {kb.get('enabled', False)}")
    print(f"  Vault 路径:    {kb.get('vault_path', 'N/A')}")
    print()

    pipe = config.get("pipeline", {})
    print(f"  默认模式:       {pipe.get('default_mode', 'semi')}")
    print(f"  默认维度:       {pipe.get('default_dimensions', 'basic')}")
    print(f"  默认格式:       {pipe.get('default_formats', 'excel')}")
    print(f"  AI 自检:        {'✅' if pipe.get('self_check') else '❌'}")
    print()

    # 校验
    errors = validate_config(config)
    if errors:
        print("  ⚠️  配置问题:")
        for err in errors:
            print(f"     - {err}")
    else:
        print("  ✅ 配置校验通过")

    return 0


def _load_and_validate(config_path: str = ""):
    """加载并校验配置，失败返回 None"""
    config = load_config(config_path or None)
    errors = validate_config(config)
    if errors:
        print("❌ 配置校验失败:", file=sys.stderr)
        for err in errors:
            print(f"   - {err}", file=sys.stderr)
        print("\n请参考 .env.example 和 config.yaml 配置，或运行 'python cli.py config' 查看", file=sys.stderr)
        return None
    return config


def main():
    parser = argparse.ArgumentParser(
        description="AI 测试用例生成系统 — 从需求到测试报告的全流程自动化",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python cli.py config                                    # 查看当前配置
  python cli.py run examples/demo_requirements.md          # 半自动全流程
  python cli.py run examples/demo_requirements.md --mode auto  # 全自动
  python cli.py run examples/demo_requirements.md -d all   # 全6维测试
  python cli.py status -o output/                          # 查看进度
  python cli.py resume -o output/                          # 从断点继续
        """,
    )
    subparsers = parser.add_subparsers(dest="command")

    default_output = str(PROJECT_ROOT / "output")

    # run
    p_run = subparsers.add_parser("run", help="执行全流程 Pipeline")
    p_run.add_argument("requirements", help="需求文档路径 (Markdown)")
    p_run.add_argument("-o", "--output", default=default_output, help="输出目录")
    p_run.add_argument(
        "--mode", choices=["auto", "semi", "step"], default=None, help="执行模式"
    )
    p_run.add_argument("-d", "--dimensions", default=None, help="测试维度")
    p_run.add_argument("-f", "--formats", default=None, help="输出格式")
    p_run.add_argument("--config", default=None, help="配置文件路径")

    # resume
    p_resume = subparsers.add_parser("resume", help="从断点继续")
    p_resume.add_argument("-o", "--output", default=default_output, help="输出目录")
    p_resume.add_argument("-d", "--dimensions", default=None)
    p_resume.add_argument("-f", "--formats", default=None)
    p_resume.add_argument("--config", default=None)

    # status
    p_status = subparsers.add_parser("status", help="查看 Pipeline 状态")
    p_status.add_argument("-o", "--output", default=default_output, help="输出目录")
    p_status.add_argument("--config", default=None)

    # config
    p_config = subparsers.add_parser("config", help="查看当前配置")
    p_config.add_argument("--config", default=None)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "run": cmd_run,
        "resume": cmd_resume,
        "status": cmd_status,
        "config": cmd_config,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
