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
    mode = args.mode  # None → pipeline.resume 默认 auto

    pipeline = Pipeline(config, args.output)
    pipeline.resume(dimensions=dimensions, formats=formats, mode=mode)
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


def cmd_ingest(args):
    """手动回灌知识库"""
    config = _load_and_validate(args.config)
    if config is None:
        return 1

    from pathlib import Path

    source = Path(args.source)
    if not source.exists():
        print(f"❌ 源文件不存在: {args.source}", file=sys.stderr)
        return 1

    # 用 Pipeline 的回灌方法（复用验证逻辑）
    pipeline = Pipeline(config, args.output)
    count = pipeline._ingest_to_kb(
        source_file=str(source),
        category=args.category,
        module=args.module,
        project=args.project,
        batch=args.batch,
    )

    print()
    print(f"{'═' * 50}")
    if count > 0:
        print(f"  ✅ 回灌成功 — {count} 条知识写入 Vault")
    else:
        print("  ⚠️  回灌 0 条（源文件为空/格式不匹配/知识库未启用）")
    print(f"  📁 分类: {args.category}")
    kb = config.get("knowledge_base", {})
    print(f"  📂 Vault: {kb.get('vault_path', 'N/A')}")
    print(f"{'═' * 50}")
    return 0 if count > 0 else 1


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
  python cli.py run examples/demo_requirements.md          # 半自动全流程（推荐首次使用）
  python cli.py run examples/demo_requirements.md --mode auto  # 全自动模式（无人工干预）
  python cli.py run examples/demo_requirements.md -d all   # 全6维测试（含性能/安全）
  python cli.py run examples/order_requirements.md -f excel,xmind  # Excel+XMind 同时输出
  python cli.py status -o output/                          # 查看 Pipeline 进度
  python cli.py resume -o output/                          # 手工填完测试结果后续跑（默认auto模式，不二次暂停）
  python cli.py resume -o output/ --mode semi              # 半自动模式resume（如要重审评审报告）
  python cli.py ingest output/run/testcases.xlsx --category historical-cases --project myproj  # 回灌测试用例
        """,
    )
    subparsers = parser.add_subparsers(dest="command")

    default_output = str(PROJECT_ROOT / "output")

    # run
    p_run = subparsers.add_parser(
        "run", help="执行全流程 Pipeline",
        description="全流程自动化：需求分析→知识库检索→测试点→生成用例→评审→人工执行→报告"
    )
    p_run.add_argument("requirements", help="需求文档路径（.md 格式）")
    p_run.add_argument("-o", "--output", default=default_output, help="输出目录（默认 ./output/）")
    p_run.add_argument(
        "--mode", choices=["auto", "semi", "step"], default=None,
        help="执行模式: auto(全自动连续) / semi(半自动,AI步骤后暂停确认,默认) / step(逐步骤手动触发)"
    )
    p_run.add_argument(
        "-d", "--dimensions", default=None,
        help="测试维度: basic(正/负/边界/异常 4维) / all(含性能/安全 6维) / positive,negative(自定义)"
    )
    p_run.add_argument(
        "-f", "--formats", default=None,
        help="输出格式: excel / xmind / excel,xmind（同时输出）"
    )
    p_run.add_argument("--config", default=None, help="配置文件路径（默认 config.yaml）")

    # resume
    p_resume = subparsers.add_parser(
        "resume", help="从断点继续 Pipeline（Step6 填完执行结果后用）",
        description="Step6 人工执行测试填完 Excel 后，运行此命令从断点继续生成报告"
    )
    p_resume.add_argument("-o", "--output", default=default_output, help="Pipeline 输出目录")
    p_resume.add_argument("-d", "--dimensions", default=None,
                          help="后续步骤的测试维度（默认沿用原始配置）")
    p_resume.add_argument("-f", "--formats", default=None,
                          help="后续步骤的输出格式（默认沿用原始配置）")
    p_resume.add_argument("--mode", choices=["auto", "semi", "step"], default=None,
                          help="执行模式（覆盖原始模式，默认 auto：resume 应快速完成后续步骤）")
    p_resume.add_argument("--config", default=None)

    # status
    p_status = subparsers.add_parser("status", help="查看 Pipeline 状态")
    p_status.add_argument("-o", "--output", default=default_output, help="输出目录")
    p_status.add_argument("--config", default=None)

    # ingest — 手动回灌知识库
    p_ingest = subparsers.add_parser(
        "ingest", help="手动回灌知识库（用例/坑点/规则）"
    )
    p_ingest.add_argument("source", help="源文件路径（Excel 或 Markdown）")
    p_ingest.add_argument(
        "--category",
        required=True,
        choices=[
            "historical-cases",
            "pitfalls",
            "business-rules",
            "templates",
            "data-dictionary",
            "business-specs",
            "team-standards",
        ],
        help="知识库分类",
    )
    p_ingest.add_argument("--module", default="", help="所属模块")
    p_ingest.add_argument("--project", default="", help="项目名（历史用例归档）")
    p_ingest.add_argument("--batch", default="", help="批次名（默认当天）")
    p_ingest.add_argument("-o", "--output", default=default_output, help="输出目录（取 project 默认值）")
    p_ingest.add_argument("--config", default=None)

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
        "ingest": cmd_ingest,
        "config": cmd_config,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
