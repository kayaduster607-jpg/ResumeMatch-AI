from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .config import PLATFORMS, build_detail_url, build_search_url, normalize_platforms
from .models import JobItem, clean_text
from .parsers import (
    DETAIL_EXTRACTOR_JS,
    DOM_EXTRACTOR_JS,
    extract_detail_from_json,
    extract_jobs_from_json,
    parse_json_from_body_text,
)
from .runtime import BROWSER_INSTALL_HELP, WINDOWS_PLAYWRIGHT_HELP, ensure_windows_playwright_event_loop_policy


ProgressFn = Callable[[str], None]


@dataclass
class CrawlOptions:
    keyword: str
    city: str
    platforms: list[str]
    pages: int = 1
    per_platform_limit: int = 80
    total_limit: int = 200
    fetch_detail: bool = True
    strict_city: bool = True
    keyword_filter: bool = False
    headless: bool = False
    state_path: str = ".job_crawler/state.json"
    output_dir: str = "outputs/job_crawler"
    delay: float = 1.5
    render_wait: float = 2.5
    timeout_ms: int = 30000
    experience: str = ""
    degree: str = ""
    job_type: str = ""

    @classmethod
    def make(
        cls,
        *,
        keyword: str,
        city: str,
        platforms: str | list[str] | None = None,
        **kwargs: Any,
    ) -> "CrawlOptions":
        ensure_windows_playwright_event_loop_policy()
        return cls(keyword=keyword, city=city, platforms=normalize_platforms(platforms), **kwargs)


class CrawlerRuntimeError(RuntimeError):
    pass


def _import_playwright():
    try:
        from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
        return async_playwright, PlaywrightTimeoutError
    except ImportError as exc:
        raise CrawlerRuntimeError(
            "缺少 Playwright。请先执行：\n"
            "  pip install -r requirements-crawler.txt\n"
            "  python -m playwright install chromium"
        ) from exc


async def _launch_chromium(pw: Any, *, headless: bool) -> Any:
    """Launch Chromium with clearer diagnostics and a local Chrome fallback."""
    launch_kwargs = {
        "headless": headless,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    }
    try:
        return await pw.chromium.launch(**launch_kwargs)
    except NotImplementedError as exc:
        raise CrawlerRuntimeError(WINDOWS_PLAYWRIGHT_HELP) from exc
    except Exception as exc:
        message = str(exc)
        # If bundled Chromium has not been installed, try a system Chrome/Edge once.
        if "Executable doesn't exist" in message or "playwright install" in message.lower():
            for channel in ("chrome", "msedge"):
                try:
                    return await pw.chromium.launch(channel=channel, **launch_kwargs)
                except Exception:
                    pass
            raise CrawlerRuntimeError(BROWSER_INSTALL_HELP) from exc
        raise CrawlerRuntimeError(f"打开浏览器失败：{message or repr(exc)}") from exc


def _should_capture(platform: str, url: str, headers: dict[str, str] | None = None) -> bool:
    low = url.lower()
    if not any(domain in low for domain in PLATFORMS[platform].domains):
        return False
    keywords = {
        "boss": ("joblist", "job/detail", "zpgeek", "search/job"),
        "zhaopin": ("api", "position", "job", "search", "sou"),
        "liepin": ("api", "job", "search", "zhaopin"),
        "qiancheng": ("api", "job", "search", "joblist", "position"),
    }[platform]
    if any(k in low for k in keywords):
        return True
    content_type = ""
    if headers:
        content_type = headers.get("content-type", "").lower()
    return "json" in content_type


async def login(platforms: str | list[str] | None = None, state_path: str = ".job_crawler/state.json") -> Path:
    """Open browser pages for all selected sites and save cookies/local storage."""
    async_playwright, _ = _import_playwright()
    selected = normalize_platforms(platforms)
    state_file = Path(state_path)
    state_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        async with async_playwright() as pw:
            browser = await _launch_chromium(pw, headless=False)
            context = await browser.new_context(
                viewport={"width": 1440, "height": 960},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
            )
            for platform in selected:
                cfg = PLATFORMS[platform]
                page = await context.new_page()
                print(f"\n打开 {cfg.name}: {cfg.home_url}")
                try:
                    await page.goto(cfg.home_url, wait_until="domcontentloaded", timeout=45000)
                except Exception as exc:
                    print(f"{cfg.name} 首页加载异常，可在打开的浏览器中手动访问登录页：{exc}")
                await asyncio.to_thread(input, f"请在浏览器里完成 {cfg.name} 登录，然后回到终端按 Enter 继续...")
            await context.storage_state(path=str(state_file))
            await browser.close()
    except NotImplementedError as exc:
        raise CrawlerRuntimeError(WINDOWS_PLAYWRIGHT_HELP) from exc

    print(f"\n登录态已保存：{state_file}")
    return state_file


async def crawl_jobs(options: CrawlOptions, progress: ProgressFn | None = None) -> list[JobItem]:
    """Crawl selected platforms and return filtered normalized jobs."""
    emit = progress or (lambda msg: print(msg, flush=True))
    async_playwright, _ = _import_playwright()

    state_file = Path(options.state_path)
    storage_state = str(state_file) if state_file.exists() else None
    if not storage_state:
        emit(f"未找到登录态文件 {state_file}，将以未登录状态尝试；如结果少或失败，请先运行 login。")

    all_jobs: list[JobItem] = []
    seen: set[str] = set()

    try:
        async with async_playwright() as pw:
            browser = await _launch_chromium(pw, headless=options.headless)
            context = await browser.new_context(
                storage_state=storage_state,
                viewport={"width": 1440, "height": 960},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
            )

            for platform in options.platforms:
                cfg = PLATFORMS[platform]
                emit(f"\n[{cfg.name}] 开始搜索：关键词={options.keyword}，城市={options.city}，页数={options.pages}")
                platform_count = 0
                for page_num in range(1, options.pages + 1):
                    if platform_count >= options.per_platform_limit or len(all_jobs) >= options.total_limit:
                        break
                    try:
                        page_jobs = await _search_page(context, platform, options, page_num, emit)
                    except Exception as exc:
                        emit(f"[{cfg.name}] 第 {page_num} 页失败：{exc}")
                        continue

                    filtered = _filter_jobs(page_jobs, options)
                    emit(f"[{cfg.name}] 第 {page_num} 页抓到 {len(page_jobs)} 条，过滤后 {len(filtered)} 条")

                    for job in filtered:
                        if platform_count >= options.per_platform_limit or len(all_jobs) >= options.total_limit:
                            break
                        key = job.key()
                        if key in seen:
                            continue
                        seen.add(key)
                        if options.fetch_detail:
                            try:
                                await _fetch_detail(context, job, options, emit)
                            except Exception as exc:
                                emit(f"[{cfg.name}] 详情失败：{job.title} / {exc}")
                        all_jobs.append(job)
                        platform_count += 1
                        await asyncio.sleep(max(options.delay, 0))

                emit(f"[{cfg.name}] 完成：累计保留 {platform_count} 条")

            await context.close()
            await browser.close()
    except NotImplementedError as exc:
        raise CrawlerRuntimeError(WINDOWS_PLAYWRIGHT_HELP) from exc

    return all_jobs


async def _search_page(context: Any, platform: str, options: CrawlOptions, page_num: int, emit: ProgressFn) -> list[JobItem]:
    page = await context.new_page()
    page.set_default_timeout(options.timeout_ms)
    url = build_search_url(
        platform,
        options.keyword,
        options.city,
        page=page_num,
        experience=options.experience,
        degree=options.degree,
        job_type=options.job_type,
    )
    network_jobs: list[JobItem] = []
    network_seen: set[str] = set()

    async def on_response(response: Any) -> None:
        try:
            if not _should_capture(platform, response.url, response.headers):
                return
            data = None
            try:
                data = await response.json()
            except Exception:
                try:
                    body = await response.text()
                    data = parse_json_from_body_text(body)
                except Exception:
                    data = None
            if data is None:
                return
            for job in extract_jobs_from_json(platform, data, source_url=response.url):
                key = job.key()
                if key not in network_seen:
                    network_seen.add(key)
                    network_jobs.append(job)
        except Exception:
            return

    page.on("response", lambda response: asyncio.create_task(on_response(response)))

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=options.timeout_ms)
    except Exception as exc:
        emit(f"[{PLATFORMS[platform].name}] 页面加载异常，继续尝试解析：{exc}")

    # BOSS API URL often renders JSON directly in body.
    if platform == "boss":
        try:
            body_text = await page.locator("body").inner_text(timeout=5000)
            data = parse_json_from_body_text(body_text)
            if data is not None:
                for job in extract_jobs_from_json(platform, data, source_url=url):
                    key = job.key()
                    if key not in network_seen:
                        network_seen.add(key)
                        network_jobs.append(job)
        except Exception:
            pass

    try:
        await page.wait_for_load_state("networkidle", timeout=min(options.timeout_ms, 12000))
    except Exception:
        pass
    await asyncio.sleep(max(options.render_wait, 0))

    # DOM fallback catches sites whose network JSON is encrypted/renamed or not captured.
    dom_jobs: list[JobItem] = []
    try:
        dom_items = await page.evaluate(DOM_EXTRACTOR_JS, platform)
        for item in dom_items or []:
            for job in extract_jobs_from_json(platform, item, source_url=url):
                dom_jobs.append(job)
    except Exception:
        pass

    await page.close()
    merged: list[JobItem] = []
    seen: set[str] = set()
    for job in network_jobs + dom_jobs:
        key = job.key()
        if key not in seen:
            seen.add(key)
            merged.append(job)
    return merged


def _filter_jobs(jobs: list[JobItem], options: CrawlOptions) -> list[JobItem]:
    out: list[JobItem] = []
    for job in jobs:
        if options.strict_city and not job.has_city(options.city):
            continue
        if options.keyword_filter and not job.has_keyword(options.keyword):
            continue
        out.append(job)
    return out


async def _fetch_detail(context: Any, job: JobItem, options: CrawlOptions, emit: ProgressFn) -> None:
    # Already has enough usable JD text from an API response.
    if len(clean_text(job.description)) >= 300:
        return

    # BOSS has a stable detail JSON endpoint when securityId exists.
    if job.platform == "boss" and job.security_id:
        await _fetch_boss_detail_api(context, job, options)
        if len(clean_text(job.description)) >= 80:
            return

    url = build_detail_url(job.platform, job.job_id, job.url)
    if not url:
        return
    page = await context.new_page()
    page.set_default_timeout(options.timeout_ms)
    detail_payloads: list[dict[str, str]] = []

    async def on_response(response: Any) -> None:
        try:
            if not _should_capture(job.platform, response.url, response.headers):
                return
            try:
                data = await response.json()
            except Exception:
                return
            detail = extract_detail_from_json(job.platform, data)
            if detail:
                detail_payloads.append(detail)
        except Exception:
            return

    page.on("response", lambda response: asyncio.create_task(on_response(response)))
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=options.timeout_ms)
        try:
            await page.wait_for_load_state("networkidle", timeout=12000)
        except Exception:
            pass
        await asyncio.sleep(1.0)
        detail = detail_payloads[-1] if detail_payloads else None
        if not detail:
            detail = await page.evaluate(DETAIL_EXTRACTOR_JS)
        _apply_detail(job, detail or {})
    finally:
        await page.close()


async def _fetch_boss_detail_api(context: Any, job: JobItem, options: CrawlOptions) -> None:
    page = await context.new_page()
    try:
        await page.goto(PLATFORMS["boss"].home_url, wait_until="domcontentloaded", timeout=options.timeout_ms)
        data = await page.evaluate(
            """
            async (sid) => {
              const resp = await fetch(`https://www.zhipin.com/wapi/zpgeek/job/detail.json?securityId=${encodeURIComponent(sid)}`, {
                credentials: 'include',
                headers: { 'Accept': 'application/json, text/plain, */*' }
              });
              return await resp.json();
            }
            """,
            job.security_id,
        )
        detail = extract_detail_from_json("boss", data)
        if detail:
            _apply_detail(job, detail)
    finally:
        await page.close()


def _apply_detail(job: JobItem, detail: dict[str, Any]) -> None:
    title = clean_text(detail.get("title"), 160)
    company = clean_text(detail.get("company"), 160)
    salary = clean_text(detail.get("salary"), 120)
    city = clean_text(detail.get("city"), 120)
    description = clean_text(detail.get("description") or detail.get("raw_text"), 20000)
    url = clean_text(detail.get("url"), 400)
    if title and not job.title:
        job.title = title
    if company and not job.company:
        job.company = company
    if salary and not job.salary:
        job.salary = salary
    if city and not job.city:
        job.city = city
    if description and len(description) > len(job.description):
        job.description = description
    if url and not job.url:
        job.url = url
