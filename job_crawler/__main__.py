from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .crawler import CrawlOptions, CrawlerRuntimeError, crawl_jobs, login
from .exporters import export_all
from .ranking import rank_jobs
from .runtime import run_async


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m job_crawler",
        description="一键爬取 BOSS / 智联 / 猎聘 / 前程无忧岗位，并按简历匹配度筛选排序。",
    )
    sub = parser.add_subparsers(dest="command")

    p_login = sub.add_parser("login", help="打开浏览器登录招聘网站，并保存登录态")
    p_login.add_argument("--platforms", default="all", help="all 或 boss,zhaopin,liepin,qiancheng")
    p_login.add_argument("--state", default=".job_crawler/state.json", help="登录态保存路径")

    p_run = sub.add_parser("run", help="爬取岗位、评分筛选、导出报告")
    p_run.add_argument("--resume", help="简历路径，支持 txt/pdf/docx；不填会交互询问")
    p_run.add_argument("--keyword", help="搜索关键词，如：产品经理 / Python 后端 / AI实习生；不填会交互询问")
    p_run.add_argument("--city", help="城市中文名或平台城市 code，如：广州；不填会交互询问")
    p_run.add_argument("--platforms", default="all", help="all 或 boss,zhaopin,liepin,qiancheng")
    p_run.add_argument("--pages", type=int, default=1, help="每个平台爬取页数")
    p_run.add_argument("--per-platform-limit", type=int, default=60, help="每个平台最多保留岗位数")
    p_run.add_argument("--total-limit", type=int, default=200, help="总岗位上限")
    p_run.add_argument("--top", type=int, default=50, help="最终导出的 Top 数量，0 表示不限制")
    p_run.add_argument("--min-score", type=float, default=50, help="低于该匹配分的岗位不导出；默认 50")
    p_run.add_argument("--state", default=".job_crawler/state.json", help="登录态文件路径")
    p_run.add_argument("--out", default="outputs/job_crawler", help="导出目录")
    p_run.add_argument("--headless", action="store_true", help="无头模式运行；首次调试建议不要开")
    p_run.add_argument("--no-detail", action="store_true", help="只抓搜索页，不进入详情页")
    p_run.add_argument("--no-strict-city", action="store_true", help="关闭严格城市过滤")
    p_run.add_argument("--keyword-filter", action="store_true", help="额外要求岗位标题/详情包含搜索关键词")
    p_run.add_argument("--delay", type=float, default=1.5, help="岗位详情请求间隔秒数")
    p_run.add_argument("--render-wait", type=float, default=2.5, help="搜索页渲染等待秒数")
    p_run.add_argument("--timeout-ms", type=int, default=30000, help="单页面超时时间，毫秒")
    p_run.add_argument("--experience", default="", help="平台经验筛选 code，可留空")
    p_run.add_argument("--degree", default="", help="平台学历筛选 code，可留空")
    p_run.add_argument("--job-type", default="", help="平台岗位类型 code，可留空")

    p_sample = sub.add_parser("sample-config", help="生成配置示例 JSON")
    p_sample.add_argument("--path", default="crawler_config.example.json")
    return parser


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    no_command = args.command is None
    if no_command:
        args = _interactive_menu(parser)

    try:
        if args.command == "login":
            run_async(login(platforms=args.platforms, state_path=args.state))
            return

        if args.command == "sample-config":
            _write_sample_config(args.path)
            return

        if args.command == "run":
            interactive = no_command or not args.resume or not args.keyword or not args.city
            if interactive:
                _fill_run_prompts(args, ask_optional=True)
            else:
                _validate_run_args(args)
            _run_pipeline(args)
            return

        parser.print_help()
    except (CrawlerRuntimeError, RuntimeError, FileNotFoundError, ValueError) as exc:
        print(f"\n错误：{exc}", file=sys.stderr)
        raise SystemExit(2) from exc


def _interactive_menu(parser: argparse.ArgumentParser) -> argparse.Namespace:
    print("\nResumeMatch-AI 岗位爬虫")
    print("1. 一键爬取岗位并分析")
    print("2. 登录/更新四个招聘网站登录态")
    print("3. 生成配置示例")
    choice = _prompt_text("请选择", default="1", required=True)
    mapping = {"1": "run", "2": "login", "3": "sample-config"}
    command = mapping.get(choice.strip(), "run")
    return parser.parse_args([command])


def _fill_run_prompts(args: argparse.Namespace, *, ask_optional: bool) -> None:
    sample_resume = Path("backend/data/samples/sample_resume.txt")
    resume_default = args.resume or (str(sample_resume) if sample_resume.exists() else "")
    args.resume = _prompt_text("简历路径（txt/pdf/docx）", default=resume_default, required=True)
    args.keyword = _prompt_text("要搜索的岗位关键词，例如 产品经理 / Python后端 / AI实习生", default=args.keyword or "", required=True)
    args.city = _prompt_text("目标城市，例如 广州 / 深圳 / 北京", default=args.city or "广州", required=True)

    if ask_optional:
        args.platforms = _prompt_text("搜索平台：all 或 boss,zhaopin,liepin,qiancheng", default=args.platforms or "all", required=True)
        args.pages = _prompt_int("每个平台爬取页数", default=args.pages or 1, minimum=1)
        args.min_score = _prompt_float("最低匹配分，0-100", default=args.min_score if args.min_score is not None else 50, minimum=0, maximum=100)
        args.top = _prompt_int("最终导出 Top 数量，0 表示不限制", default=args.top if args.top is not None else 50, minimum=0)
        quick = _prompt_bool("是否先快速扫描，不进入详情页", default=False)
        args.no_detail = bool(args.no_detail or quick)
    _validate_run_args(args)


def _validate_run_args(args: argparse.Namespace) -> None:
    missing = []
    if not args.resume:
        missing.append("--resume 简历路径")
    if not args.keyword:
        missing.append("--keyword 搜索岗位关键词")
    if not args.city:
        missing.append("--city 城市")
    if missing:
        raise ValueError("缺少必要参数：" + "，".join(missing) + "。也可以直接运行 python -m job_crawler 进入交互模式。")
    if not Path(args.resume).exists():
        raise FileNotFoundError(f"简历文件不存在：{args.resume}")


def _run_pipeline(args: argparse.Namespace) -> None:
    options = CrawlOptions.make(
        keyword=args.keyword,
        city=args.city,
        platforms=args.platforms,
        pages=args.pages,
        per_platform_limit=args.per_platform_limit,
        total_limit=args.total_limit,
        fetch_detail=not args.no_detail,
        strict_city=not args.no_strict_city,
        keyword_filter=args.keyword_filter,
        headless=args.headless,
        state_path=args.state,
        output_dir=args.out,
        delay=args.delay,
        render_wait=args.render_wait,
        timeout_ms=args.timeout_ms,
        experience=args.experience,
        degree=args.degree,
        job_type=args.job_type,
    )
    print(
        f"\n开始执行：关键词={args.keyword}，城市={args.city}，平台={','.join(options.platforms)}，"
        f"每站页数={args.pages}，最低匹配分={args.min_score}"
    )
    jobs = run_async(crawl_jobs(options))
    print(f"\n爬取完成：过滤后共有 {len(jobs)} 条岗位，开始匹配评分...")
    ranked, meta = rank_jobs(args.resume, jobs, min_score=args.min_score, top=args.top, keyword=args.keyword)
    meta.update({
        "keyword": args.keyword,
        "city": args.city,
        "platforms": options.platforms,
        "pages": args.pages,
        "min_score": args.min_score,
        "top": args.top,
        "strict_city": options.strict_city,
        "fetch_detail": options.fetch_detail,
    })
    files = export_all(ranked, args.out, keyword=args.keyword, city=args.city, meta=meta)
    print(f"\n筛选完成：导出 {len(ranked)} 条岗位")
    for kind, path in files.items():
        if kind == "xlsx_error":
            print(f"- xlsx 未导出：{path}")
        else:
            print(f"- {kind}: {path}")
    if ranked:
        print("\nTop 5：")
        for idx, job in enumerate(ranked[:5], 1):
            level = getattr(job, "match_level", "") or "-"
            print(f"{idx}. {job.total_score:.0f}分｜{level}｜{job.platform_name}｜{job.title}｜{job.company}｜{job.location_text()}")
    else:
        print("\n没有达到条件的岗位。可以降低 --min-score、关闭 --keyword-filter，或使用 --no-strict-city 检查源数据。")


def _write_sample_config(path_text: str) -> None:
    path = Path(path_text)
    sample: dict[str, Any] = {
        "resume": "backend/data/samples/sample_resume.txt",
        "keyword": "AI开发实习生",
        "city": "广州",
        "platforms": "all",
        "pages": 1,
        "per_platform_limit": 60,
        "total_limit": 200,
        "top": 50,
        "min_score": 50,
        "state": ".job_crawler/state.json",
        "out": "outputs/job_crawler",
        "strict_city": True,
        "fetch_detail": True,
    }
    path.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成：{path}")


def _prompt_text(label: str, *, default: str = "", required: bool = False) -> str:
    while True:
        suffix = f" [{default}]" if default else ""
        value = input(f"{label}{suffix}: ").strip()
        if not value and default:
            value = default
        if value or not required:
            return value
        print("这里不能为空，请重新输入。")


def _prompt_int(label: str, *, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    while True:
        raw = input(f"{label} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("请输入整数。")
            continue
        if minimum is not None and value < minimum:
            print(f"不能小于 {minimum}。")
            continue
        if maximum is not None and value > maximum:
            print(f"不能大于 {maximum}。")
            continue
        return value


def _prompt_float(label: str, *, default: float, minimum: float | None = None, maximum: float | None = None) -> float:
    while True:
        raw = input(f"{label} [{default:g}]: ").strip()
        if not raw:
            return float(default)
        try:
            value = float(raw)
        except ValueError:
            print("请输入数字。")
            continue
        if minimum is not None and value < minimum:
            print(f"不能小于 {minimum:g}。")
            continue
        if maximum is not None and value > maximum:
            print(f"不能大于 {maximum:g}。")
            continue
        return value


def _prompt_bool(label: str, *, default: bool = False) -> bool:
    default_text = "Y/n" if default else "y/N"
    raw = input(f"{label} [{default_text}]: ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes", "1", "true", "是", "好"}


if __name__ == "__main__":
    main()
