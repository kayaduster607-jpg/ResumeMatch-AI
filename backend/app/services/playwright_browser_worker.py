"""Microsoft Edge CDP browser worker for recruitment-site crawling.

This version is built for Windows + Python 3.9:
- Uses the system Microsoft Edge, not Playwright Chromium.
- Starts Edge with a persistent profile and a local CDP debugging port.
- Uses Playwright Async API inside one dedicated background event loop.
- Keeps the Edge window open after search so BOSS verification pages do not flash and disappear.
"""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from urllib.parse import quote
from pathlib import Path
from typing import Any, Optional

# CDP script injected before every page load to defeat bot detection.
# BOSS checks navigator.deviceMemory (empty in CDP-controlled browsers) and
# navigator.webdriver (set by automation frameworks).
_ANTI_DETECTION_SCRIPT = """
// Override navigator properties that anti-bot systems check.
// BOSS specifically detects empty deviceMemory (CHR_MEMORY FAIL) and
// webdriver=true as automation signals.
Object.defineProperty(navigator, 'deviceMemory', {
    value: 8,
    writable: false,
    configurable: true,
    enumerable: false
});
Object.defineProperty(navigator, 'hardwareConcurrency', {
    value: 8,
    writable: false,
    configurable: true,
    enumerable: false
});
// Periodically remove Playwright/Puppeteer automation traces that get injected
// after page load (e.g. when Playwright attaches to a CDP page).
(function() {
    const propsToDelete = ['__playwright__', '__pw_manual__', '__PW_inspector__',
        '__playwright_testing__', '__PW_DEVTOOLS_METRICS__'];
    const cleanup = function() {
        for (var i = 0; i < propsToDelete.length; i++) {
            try { delete window[propsToDelete[i]]; } catch(e) {}
        }
    };
    cleanup();
    setInterval(cleanup, 2000);
})();
"""


class PlaywrightBrowserWorker:
    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._thread_lock = threading.Lock()

        self._playwright = None
        self._browser = None
        self._context = None
        self._edge_process: Optional[subprocess.Popen] = None

        self._base_dir = Path.cwd() / ".job_browser"
        self._profile_dir = self._base_dir / "edge_profile"
        self._state_path = self._base_dir / "storage_state.json"
        self._port = self._get_edge_port()

    # ── Public API ────────────────────────────────────

    def open_login_pages(self, platforms: list[str]) -> dict[str, Any]:
        return self._submit("open_login_pages", platforms, timeout=180)

    def save_state(self) -> dict[str, Any]:
        return self._submit("save_state", timeout=60)

    def get_cookies(self, urls: Optional[list[str]] = None) -> dict[str, Any]:
        """Return cookies from the managed browser context for direct API calls."""
        return self._submit("get_cookies", urls, timeout=30)

    def search_jobs(self, payload: dict[str, Any]) -> dict[str, Any]:
        timeout = max(180, int(payload.get("timeout_seconds", 360) or 360))
        return self._submit("search_jobs", payload, timeout=timeout)

    def collect_current_pages(self, payload: dict[str, Any]) -> dict[str, Any]:
        timeout = max(120, int(payload.get("timeout_seconds", 180) or 180))
        return self._submit("collect_current_pages", payload, timeout=timeout)

    def close(self) -> dict[str, Any]:
        return self._submit("close", timeout=30)

    # ── Thread / event loop ────────────────────────────

    def _ensure_thread(self) -> None:
        with self._thread_lock:
            if self._thread and self._thread.is_alive() and self._loop and self._loop.is_running():
                return
            self._ready.clear()
            self._thread = threading.Thread(
                target=self._thread_main,
                name="job-crawler-edge-cdp-worker",
                daemon=True,
            )
            self._thread.start()
        if not self._ready.wait(10):
            raise RuntimeError("浏览器后台线程启动超时。")

    def _thread_main(self) -> None:
        if sys.platform == "win32":
            policy = getattr(asyncio, "WindowsProactorEventLoopPolicy", None)
            if policy is not None:
                asyncio.set_event_loop_policy(policy())
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        loop.run_forever()

    def _submit(self, action: str, *args: Any, timeout: int = 120, **kwargs: Any) -> Any:
        self._ensure_thread()
        assert self._loop is not None
        future = asyncio.run_coroutine_threadsafe(self._dispatch(action, *args, **kwargs), self._loop)
        try:
            return future.result(timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            raise self._normalize_browser_error(exc) from exc

    async def _dispatch(self, action: str, *args: Any, **kwargs: Any) -> Any:
        handler = getattr(self, f"_do_{action}")
        return await handler(*args, **kwargs)

    # ── Browser lifecycle ──────────────────────────────

    async def _ensure_context(self):
        if self._context is not None:
            try:
                # Touch pages to verify the CDP connection is still alive.
                _ = self._context.pages
                return self._context
            except Exception:
                self._context = None
                self._browser = None

        self._profile_dir.mkdir(parents=True, exist_ok=True)
        self._state_path.parent.mkdir(parents=True, exist_ok=True)

        self._ensure_edge_process()

        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError("后端缺少 Playwright。请执行：python -m pip install -r requirements.txt") from exc

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        endpoint = f"http://127.0.0.1:{self._port}"
        try:
            self._browser = await self._playwright.chromium.connect_over_cdp(endpoint)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"连接 Edge CDP 失败：{exc}。请关闭所有由本项目打开的 Edge 后重试，或修改 EDGE_REMOTE_DEBUG_PORT。"
            ) from exc

        contexts = self._browser.contexts
        if not contexts:
            raise RuntimeError("Edge CDP 已连接，但没有可用浏览器上下文。")
        self._context = contexts[0]

        # Inject anti-detection scripts that run before every page's own JS.
        # This prevents BOSS from detecting CDP-controlled browsers by checking
        # navigator.deviceMemory / hardwareConcurrency / webdriver.
        try:
            await self._context.add_init_script(_ANTI_DETECTION_SCRIPT)
        except Exception:
            pass

        # Also apply to already-open pages via raw CDP so that reloads / future
        # navigations on those pages are protected.
        try:
            for page in list(getattr(self._context, "pages", []) or []):
                try:
                    cdp = await self._context.new_cdp_session(page)
                    await cdp.send("Page.addScriptToEvaluateOnNewDocument", {"source": _ANTI_DETECTION_SCRIPT})
                except Exception:
                    pass
        except Exception:
            pass

        # Do not keep a lonely about:blank tab.  It is the source of the
        # "blank Edge window stuck on screen" symptom after a search/login action.
        await self._cleanup_blank_pages(self._context, keep_one=False)
        return self._context

    async def _cleanup_blank_pages(self, context: Any, keep_one: bool = True) -> None:
        """Close useless about:blank/new-tab pages.

        Login pages are kept; only blank pages are closed. During search we call
        this with keep_one=False so a final empty about:blank window is also
        closed instead of staying on screen.
        """
        try:
            pages = list(getattr(context, "pages", []) or [])
        except Exception:
            return
        for page in pages:
            try:
                url = (getattr(page, "url", "") or "").strip().lower()
                if url in ("about:blank", "") or url.startswith("edge://newtab") or url.startswith("chrome://newtab"):
                    current_pages = list(getattr(context, "pages", []) or [])
                    if keep_one and len(current_pages) <= 1:
                        continue
                    await page.close()
            except Exception:
                pass


    def _ensure_edge_process(self) -> None:
        if self._is_port_open(self._port):
            return

        edge_path = self._find_edge_exe()
        if not edge_path:
            raise RuntimeError(
                "没有找到 Microsoft Edge。请确认已安装 Edge，或设置环境变量 EDGE_PATH 指向 msedge.exe。"
            )

        cmd = [
            edge_path,
            f"--remote-debugging-port={self._port}",
            f"--user-data-dir={str(self._profile_dir)}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-blink-features=AutomationControlled",
            "--window-size=1440,900",
            "--lang=zh-CN",
        ]
        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        self._edge_process = subprocess.Popen(  # noqa: S603
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )

        deadline = time.time() + 20
        while time.time() < deadline:
            if self._is_port_open(self._port) and self._cdp_ready():
                return
            time.sleep(0.25)
        raise RuntimeError(
            f"Edge 已启动但 CDP 端口 {self._port} 未就绪。请关闭 Edge 后重试，或检查端口是否被占用。"
        )

    def _cdp_ready(self) -> bool:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self._port}/json/version", timeout=1) as resp:
                return resp.status == 200
        except Exception:
            return False

    @staticmethod
    def _is_port_open(port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            return False

    @staticmethod
    def _get_edge_port() -> int:
        try:
            from app.core.config import get_settings
            return int(get_settings().EDGE_REMOTE_DEBUG_PORT or 9333)
        except Exception:
            return int(os.environ.get("EDGE_REMOTE_DEBUG_PORT", "9333"))

    @staticmethod
    def _find_edge_exe() -> str:
        env_path = os.environ.get("EDGE_PATH")
        try:
            from app.core.config import get_settings
            env_path = env_path or get_settings().EDGE_PATH
        except Exception:
            pass
        candidates = []
        if env_path:
            candidates.append(env_path)
        for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.environ.get(key)
            if base:
                candidates.append(str(Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"))
        candidates.extend([
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ])
        for path in candidates:
            if path and Path(path).exists():
                return path
        return ""

    # ── Operations ─────────────────────────────────────

    async def _do_open_login_pages(self, platforms: list[str]) -> dict[str, Any]:
        from app.services.platform_crawler_service import PLATFORM_LOGIN_URLS, normalize_platforms

        context = await self._ensure_context()
        opened: list[dict[str, str]] = []
        for platform in normalize_platforms(platforms):
            url = PLATFORM_LOGIN_URLS[platform]

            # BOSS 对自动化导航更敏感：登录页也优先通过 Edge 自身打开，
            # 再由 CDP 连接/读取，避免 page.goto 直接变空白。
            if platform == "boss":
                try:
                    open_url_in_managed_edge(url, prefer_system_command=True)
                    page = None
                    deadline = time.time() + 20
                    while time.time() < deadline:
                        for p in list(getattr(context, "pages", []) or []):
                            purl = getattr(p, "url", "") or ""
                            if "zhipin.com" in purl:
                                page = p
                        if page is not None:
                            try:
                                await page.bring_to_front()
                            except Exception:
                                pass
                            break
                        await asyncio.sleep(0.35)
                    opened.append({"platform": platform, "url": url})
                    continue
                except Exception:
                    # fallback below
                    pass

            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            except Exception:
                # Keep the tab open even when navigation times out.
                pass
            try:
                await page.bring_to_front()
            except Exception:
                pass
            opened.append({"platform": platform, "url": url})

        await self._cleanup_blank_pages(context, keep_one=False)

        return {
            "opened": opened,
            "message": "已用 Microsoft Edge 打开招聘网站。请完成登录/验证码后点击「保存登录状态」。",
            "profile_dir": str(self._profile_dir),
        }

    async def _do_save_state(self) -> dict[str, Any]:
        context = await self._ensure_context()
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            await context.storage_state(path=str(self._state_path))
        except Exception:
            # CDP persistent profile itself already saves cookies. storage_state is only a debug artifact.
            pass

        # Sync BOSS cookies from Edge so the Playwright Chromium crawler can reuse them.
        try:
            from app.services.boss_api_crawler import sync_cookies_from_edge
            sync_cookies_from_edge(context)
        except Exception:
            pass

        return {
            "state_path": str(self._state_path),
            "profile_dir": str(self._profile_dir),
            "message": "登录状态已保存在 Edge 独立用户目录。后续搜索会复用该目录。",
        }

    async def _do_get_cookies(self, urls: Optional[list[str]] = None) -> dict[str, Any]:
        """Return cookies from the browser context for use in direct API calls."""
        context = await self._ensure_context()
        try:
            cookies = await context.cookies(urls=urls or ["https://www.zhipin.com"])
            # Convert to simple dict format for httpx
            cookie_dict: dict[str, str] = {}
            for c in cookies:
                name = c.get("name", "")
                value = c.get("value", "")
                if name:
                    cookie_dict[name] = value
            return {"cookies": cookie_dict, "count": len(cookie_dict)}
        except Exception as e:
            return {"cookies": {}, "count": 0, "error": str(e)}

    async def _do_search_jobs(self, payload: dict[str, Any]) -> dict[str, Any]:
        from app.services.platform_crawler_service import crawl_jobs_with_context

        context = await self._ensure_context()
        result = await crawl_jobs_with_context(context, payload)
        await self._cleanup_blank_pages(context, keep_one=False)
        return result

    async def _do_collect_current_pages(self, payload: dict[str, Any]) -> dict[str, Any]:
        from app.services.platform_crawler_service import collect_current_edge_pages

        context = await self._ensure_context()
        result = await collect_current_edge_pages(context, payload)
        await self._cleanup_blank_pages(context, keep_one=False)
        return result

    async def _do_close(self) -> dict[str, Any]:
        # Close Playwright/CDP connection first. Then terminate the Edge process that this
        # worker started, if we still own that process. If the user opened another Edge
        # manually, we leave it alone.
        try:
            if self._context is not None:
                for page in list(getattr(self._context, "pages", []) or []):
                    try:
                        await page.close()
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            if self._browser is not None:
                await self._browser.close()
        except Exception:
            pass
        self._browser = None
        self._context = None
        try:
            if self._playwright is not None:
                await self._playwright.stop()
        except Exception:
            pass
        self._playwright = None
        try:
            if self._edge_process is not None and self._edge_process.poll() is None:
                self._edge_process.terminate()
        except Exception:
            pass
        self._edge_process = None
        return {"message": "项目专用 Edge 标签页已关闭；如果仍有 Edge 窗口残留，可以手动关闭。"}

    # ── Error handling ─────────────────────────────────

    @staticmethod
    def _normalize_browser_error(exc: BaseException) -> RuntimeError:
        text = str(exc).strip() or repr(exc)
        lower = text.lower()
        if "sync api inside the asyncio loop" in lower:
            return RuntimeError("浏览器启动失败：旧版 Playwright Sync API 仍在运行。请确认已覆盖新版文件并重启后端。")
        if "notimplementederror" in lower or isinstance(exc, NotImplementedError):
            return RuntimeError("浏览器启动失败：Windows 事件循环异常。当前版本使用 Edge CDP；请重启后端后重试。")
        return RuntimeError(text)


def _cdp_open_new_tab(port: int, url: str) -> None:
    encoded = quote(url, safe="")
    endpoint = f"http://127.0.0.1:{port}/json/new?{encoded}"
    last_exc = None
    for method in ("PUT", "GET"):
        try:
            req = urllib.request.Request(endpoint, method=method)
            with urllib.request.urlopen(req, timeout=3) as resp:
                if int(getattr(resp, "status", 0)) in (200, 201):
                    return
        except Exception as exc:
            last_exc = exc
    raise RuntimeError(f"DevTools 打开新标签失败：{last_exc}")


def open_url_in_managed_edge(url: str, prefer_system_command: bool = False) -> None:
    """Open URL in the managed Edge profile.

    For ordinary sites we can use CDP /json/new.  BOSS is more sensitive to
    DevTools-driven navigation and may render an empty page.  When
    ``prefer_system_command`` is True we ask the real Edge executable to open
    the URL in the already-running managed profile; this behaves closer to a
    user pressing Enter in Edge and avoids the BOSS blank-page regression.
    """
    try:
        from app.core.config import get_settings
        settings = get_settings()
        port = int(settings.EDGE_REMOTE_DEBUG_PORT or 9333)
    except Exception:
        port = int(os.environ.get("EDGE_REMOTE_DEBUG_PORT", "9333"))

    edge_path = PlaywrightBrowserWorker._find_edge_exe()
    if not edge_path:
        raise RuntimeError("没有找到 Microsoft Edge，无法打开招聘网站。")

    profile_dir = Path.cwd() / ".job_browser" / "edge_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    if PlaywrightBrowserWorker._is_port_open(port) and not prefer_system_command:
        try:
            _cdp_open_new_tab(port, url)
            return
        except Exception:
            pass

    if PlaywrightBrowserWorker._is_port_open(port) and prefer_system_command:
        # With the same user-data-dir already open, Edge routes this URL to the
        # existing browser process.  Do NOT pass --remote-debugging-port again;
        # repeatedly doing so caused context resets and orphan about:blank tabs.
        cmd_existing = [
            edge_path,
            f"--user-data-dir={str(profile_dir)}",
            "--no-first-run",
            "--no-default-browser-check",
            url,
        ]
        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            subprocess.Popen(cmd_existing, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)  # noqa: S603
            return
        except Exception:
            # Fall back to CDP if the OS-level route fails.
            try:
                _cdp_open_new_tab(port, url)
                return
            except Exception:
                pass

    cmd = [
        edge_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={str(profile_dir)}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
        "--window-size=1440,900",
        "--lang=zh-CN",
        url,
    ]
    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(  # noqa: S603
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


_worker: Optional[PlaywrightBrowserWorker] = None
_worker_lock = threading.Lock()


def get_browser_worker() -> PlaywrightBrowserWorker:
    global _worker
    with _worker_lock:
        if _worker is None:
            _worker = PlaywrightBrowserWorker()
        return _worker
