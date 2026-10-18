from __future__ import annotations

import asyncio
import sys
from typing import Awaitable, TypeVar

T = TypeVar("T")


WINDOWS_PLAYWRIGHT_HELP = """打开浏览器失败：当前 Python/asyncio 环境不支持 Playwright 启动浏览器子进程。

常见原因：Windows 下事件循环被切成了 SelectorEventLoop，Playwright 启动 Chromium 时会抛 NotImplementedError()。

建议按顺序处理：
1. 重新打开 PowerShell / CMD，不要在 Jupyter、某些 IDE 内置控制台里运行。
2. 执行：python -m playwright install chromium
3. 再运行：python -m job_crawler login --platforms all
4. 如果仍失败，确认 Python 版本为 3.9+，并重新安装：pip install -U playwright
""".strip()


BROWSER_INSTALL_HELP = """打开浏览器失败：Playwright 浏览器运行环境不可用。

请先执行：
  pip install -r requirements-crawler.txt
  python -m playwright install chromium

然后再运行：
  python -m job_crawler login --platforms all
""".strip()


def ensure_windows_playwright_event_loop_policy() -> None:
    """Use the Windows event-loop policy that supports subprocesses.

    Playwright starts a Node driver process internally. On Windows, SelectorEventLoop
    does not implement subprocess APIs and raises NotImplementedError(). Some IDEs,
    notebooks, and libraries force that policy, so we reset it before asyncio.run().
    """
    if sys.platform != "win32":
        return
    proactor_policy = getattr(asyncio, "WindowsProactorEventLoopPolicy", None)
    if proactor_policy is None:
        return
    try:
        current = asyncio.get_event_loop_policy()
        if not isinstance(current, proactor_policy):
            asyncio.set_event_loop_policy(proactor_policy())
    except Exception:
        # Do not fail before the real browser launch; launch error handling will
        # print a clearer diagnostic if this did not work.
        pass


def run_async(coro: Awaitable[T]) -> T:
    ensure_windows_playwright_event_loop_policy()
    try:
        return asyncio.run(coro)
    except NotImplementedError as exc:
        raise RuntimeError(WINDOWS_PLAYWRIGHT_HELP) from exc
