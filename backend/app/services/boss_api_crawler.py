"""BOSS crawler — Playwright Chromium + DOM parsing (方法二).

Launches Playwright's own Chromium browser (NOT Edge CDP), loads cookies
synced from the Edge login session, navigates to BOSS search pages, and
extracts job cards directly from the DOM.

Falls back to 方法一 (bookmarklet) if scraping fails.
"""

from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from app.services.platform_crawler_service import (
    BOSS_CITY_CODES,
    JobItem,
    _dict_to_job,
)

# ── Paths ───────────────────────────────────────────────────────────────────

_COOKIE_FILE = Path(".job_browser/boss_cookies.json")
_PROFILE_DIR = Path(".job_browser/chromium_profile")

# ── User-Agent pool ─────────────────────────────────────────────────────────

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

_VIEWPORT_WIDTHS = [1280, 1366, 1400, 1440, 1536]
_VIEWPORT_HEIGHTS = [700, 768, 800, 900]

# ── Bookmarklet (方法一 fallback) ───────────────────────────────────────────

_BOOKMARKLET_CODE = """javascript:(function(){
  let jobs=[];
  let cards=document.querySelectorAll('.job-card-wrapper');
  if(!cards.length)cards=document.querySelectorAll('[class*="job-card"]');
  cards.forEach(c=>{
    let j={};
    let getName=(sel)=>c.querySelector(sel)?.innerText?.trim()||'';
    j.title=getName('.job-name')||getName('[class*="job-name"]');
    j.company=getName('.company-name')||getName('[class*="company-name"]');
    j.salary=getName('.salary')||getName('[class*="salary"]');
    j.location=getName('.job-area')||getName('[class*="job-area"]');
    let tags=[];c.querySelectorAll('.job-limit .tag-item,[class*="tag-item"]').forEach(t=>tags.push(t.innerText.trim()));if(tags.length)j.tags=tags;
    let a=c.querySelector('a.job-card-left');if(a){let h=a.getAttribute('href');if(h)j.url=h.startsWith('/')?'https://www.zhipin.com'+h:h;}
    if(j.title)jobs.push(j);
  });
  if(!jobs.length){alert('没有找到岗位数据。请确认你在 BOSS 直聘的搜索结果页面上。');return;}
  let blob=new Blob([JSON.stringify(jobs,null,2)],{type:'application/json'});
  let url=URL.createObjectURL(blob);
  let a=document.createElement('a');a.href=url;a.download='bosszp_jobs_'+new Date().toISOString().slice(0,19).replace(/[:-]/g,'')+'.json';
  document.body.appendChild(a);a.click();document.body.removeChild(a);URL.revokeObjectURL(url);
  alert('已导出 '+jobs.length+' 条岗位数据！');
})();"""

_BOOKMARKLET_HELP = {
    "method": "bookmarklet",
    "title": "方法一：浏览器书签脚本（手动导出）",
    "steps": [
        "1. 在浏览器书签栏右键 → 添加页面",
        "2. 名称填：BOSS导出",
        "3. 网址粘贴下方代码",
        "4. 打开 zhipin.com 搜索岗位后，点击书签即可下载 JSON",
    ],
    "code": _BOOKMARKLET_CODE,
}

# ── Main crawl function ─────────────────────────────────────────────────────


async def crawl_boss_via_api(
    context: Any,
    keyword: str,
    city: str,
    max_pages: int = 1,
    fetch_detail: bool = False,
) -> list[JobItem]:
    """Crawl BOSS jobs using Playwright Chromium + DOM parsing."""

    city_code = BOSS_CITY_CODES.get(city, "101280600")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[boss-chromium] Playwright not installed")
        return _fallback_response(keyword)

    try:
        async with async_playwright() as p:
            # ── Launch Chromium with persistent profile ──
            _PROFILE_DIR.mkdir(parents=True, exist_ok=True)

            browser = await p.chromium.launch_persistent_context(
                user_data_dir=str(_PROFILE_DIR),
                headless=False,
                viewport={
                    "width": random.choice(_VIEWPORT_WIDTHS),
                    "height": random.choice(_VIEWPORT_HEIGHTS),
                },
                user_agent=random.choice(_USER_AGENTS),
                locale="zh-CN",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )

            # browser from launch_persistent_context is actually a BrowserContext
            bctx = browser
            page = bctx.pages[0] if bctx.pages else await bctx.new_page()

            # ── Load synced cookies from Edge login session ──
            if _COOKIE_FILE.exists():
                try:
                    with open(_COOKIE_FILE, "r", encoding="utf-8") as f:
                        cookies = json.load(f)
                    await bctx.add_cookies(cookies)
                    print(f"[boss-chromium] Loaded {len(cookies)} synced cookies")
                except Exception as exc:
                    print(f"[boss-chromium] Cookie load warning: {exc}")

            # ── Check login status ──
            await _safe_goto(page, "https://www.zhipin.com/web/geek/job")
            await page.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(1.5)

            current_url = page.url.lower()
            if "/web/geek/" not in current_url and "/web/chat" not in current_url:
                print(f"[boss-chromium] Not logged in, current URL: {current_url}")
                # Keep browser open so user can log in
                print("[boss-chromium] Browser is open — please log in to BOSS, then search again")
                await bctx.close()
                return _fallback_response(keyword)

            print("[boss-chromium] Login confirmed, starting search...")

            # ── Search & scrape ──
            all_jobs: list[JobItem] = []
            seen_urls: set[str] = set()

            for page_no in range(1, max_pages + 1):
                print(f"[boss-chromium] Page {page_no}/{max_pages}...")

                search_url = (
                    f"https://www.zhipin.com/web/geek/job"
                    f"?city={city_code}&query={quote(keyword)}"
                )
                if page_no > 1:
                    search_url += f"&page={page_no}"

                await _safe_goto(page, search_url)

                # Wait for job cards to render
                try:
                    await page.wait_for_selector(".job-card-wrapper", timeout=15000)
                except Exception:
                    # Try alternative selector
                    try:
                        await page.wait_for_selector("[class*='job-card']", timeout=8000)
                    except Exception:
                        print(f"[boss-chromium] No job cards found on page {page_no}")
                        break

                # Human-like behavior
                await _behave_like_human(page)

                # Parse job cards
                page_jobs, new_urls = await _parse_job_cards(page, keyword, city)
                for job in page_jobs:
                    job_url = getattr(job, "url", "") or job.encrypt_job_id
                    if job_url and job_url not in seen_urls:
                        seen_urls.add(job_url)
                        all_jobs.append(job)

                print(f"[boss-chromium] Page {page_no}: {len(page_jobs)} cards, {len(all_jobs)} total")

                # Next page
                if page_no >= max_pages:
                    break

                if not await _go_next_page(page):
                    print(f"[boss-chromium] No more pages")
                    break

                delay = random.uniform(2, 5)
                await asyncio.sleep(delay)

            # Save cookies for next session
            _save_cookies_sync(bctx)

            await bctx.close()
            print(f"[boss-chromium] Done: {len(all_jobs)} jobs from {min(page_no, max_pages)} pages")
            return all_jobs

    except Exception as e:
        print(f"[boss-chromium] Error: {e}")
        import traceback
        traceback.print_exc()
        return _fallback_response(keyword)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _fallback_response(keyword: str) -> list[JobItem]:
    """Return empty list — the caller will add bookmarklet info to errors."""
    return []


def get_bookmarklet_help() -> dict:
    """Return bookmarklet instructions for the frontend."""
    return _BOOKMARKLET_HELP


def _save_cookies_sync(context: Any) -> None:
    """Save browser cookies to JSON file for next session."""
    try:
        import asyncio as _asyncio

        async def _save():
            cookies = await context.cookies()
            _COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _COOKIE_FILE.write_text(json.dumps(cookies, ensure_ascii=False, indent=2))
            print(f"[boss-chromium] Saved {len(cookies)} cookies")

        # If we're in an event loop, use create_task; otherwise run sync
        try:
            loop = _asyncio.get_running_loop()
            loop.create_task(_save())
        except RuntimeError:
            pass  # No running loop, skip save
    except Exception as e:
        print(f"[boss-chromium] Cookie save error: {e}")


def sync_cookies_from_edge(context: Any) -> None:
    """Extract BOSS cookies from Edge context and save for Chromium use.

    Call this after the user logs in via Edge (save_state).
    """
    try:
        import asyncio as _asyncio

        async def _sync():
            cookies = await context.cookies(urls=["https://www.zhipin.com"])
            _COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _COOKIE_FILE.write_text(json.dumps(cookies, ensure_ascii=False, indent=2))
            print(f"[boss-chromium] Synced {len(cookies)} cookies from Edge")

        loop = _asyncio.get_running_loop()
        loop.create_task(_sync())
    except Exception as e:
        print(f"[boss-chromium] Cookie sync error: {e}")


async def _safe_goto(page: Any, url: str) -> None:
    """Navigate safely, ignoring timeouts."""
    try:
        await page.goto(url, wait_until="commit", timeout=30000)
    except Exception:
        pass


async def _behave_like_human(page: Any) -> None:
    """Simulate human scrolling behavior."""
    try:
        for _ in range(random.randint(1, 3)):
            scroll_y = random.randint(200, 600)
            await page.evaluate(f"window.scrollBy(0, {scroll_y})")
            await asyncio.sleep(random.uniform(0.3, 0.8))
        await page.evaluate(f"window.scrollTo(0, {random.randint(0, 200)})")
        await asyncio.sleep(random.uniform(0.2, 0.5))
    except Exception:
        pass


async def _parse_job_cards(page: Any, keyword: str, city: str) -> tuple[list[JobItem], set[str]]:
    """Extract job data from DOM cards."""
    jobs: list[JobItem] = []
    urls: set[str] = set()

    try:
        cards = await page.query_selector_all(".job-card-wrapper")
        if not cards:
            cards = await page.query_selector_all("[class*='job-card']")
    except Exception:
        cards = []

    for card in cards:
        try:
            # Title
            title_el = await card.query_selector(".job-name, [class*='job-name']")
            title = (await title_el.inner_text()).strip() if title_el else ""
            if not title:
                continue

            # Company
            company_el = await card.query_selector(".company-name, [class*='company-name']")
            company = (await company_el.inner_text()).strip() if company_el else ""

            # Salary
            salary_el = await card.query_selector(".salary, [class*='salary']")
            salary = (await salary_el.inner_text()).strip() if salary_el else ""

            # Location
            area_el = await card.query_selector(".job-area, [class*='job-area']")
            area = (await area_el.inner_text()).strip() if area_el else ""

            # Tags
            tags: list[str] = []
            try:
                tag_els = await card.query_selector_all(".job-limit .tag-item, [class*='tag-item']")
                for t in tag_els:
                    tag_text = (await t.inner_text()).strip()
                    if tag_text:
                        tags.append(tag_text)
            except Exception:
                pass

            # URL
            url = ""
            try:
                link_el = await card.query_selector("a.job-card-left, a[href*='job_detail']")
                if link_el:
                    href = (await link_el.get_attribute("href")) or ""
                    if href:
                        url = f"https://www.zhipin.com{href}" if href.startswith("/") else href
            except Exception:
                pass

            # Build raw text for enrichment
            raw_parts = [title, company, salary, area] + tags
            raw_text = " | ".join(p for p in raw_parts if p)

            # EncryptJobId from URL
            encrypt_id = ""
            if "/job_detail/" in url:
                encrypt_id = url.split("/job_detail/")[-1].split(".")[0].split("?")[0]

            job_dict = {
                "jobName": title,
                "brandName": company,
                "salaryDesc": salary,
                "cityName": city,
                "areaDistrict": area,
                "encryptJobId": encrypt_id or f"dom_{abs(hash(title + company)):08x}",
                "securityId": "",
                "skills": tags,
                "jobDegree": "",
                "jobExperience": "",
                "welfareList": [],
                "url": url,
            }

            item = _dict_to_job(job_dict, "boss", url or f"https://www.zhipin.com/web/geek/job?query={quote(keyword)}")
            if item is not None:
                item.raw_text = raw_text
                item.url = url
                jobs.append(item)
                if url:
                    urls.add(url)

        except Exception:
            continue

    return jobs, urls


async def _go_next_page(page: Any) -> bool:
    """Click next page button. Returns True if successful."""
    try:
        # Try .page-next first
        next_btn = await page.query_selector(".page-next")
        if not next_btn:
            next_btn = await page.query_selector("[class*='next']")
        if next_btn:
            is_enabled = await next_btn.is_enabled()
            if is_enabled:
                await next_btn.click()
                await asyncio.sleep(random.uniform(2, 4))
                return True
        return False
    except Exception:
        return False
