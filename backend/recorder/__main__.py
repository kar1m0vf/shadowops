"""Run with: python -m recorder. Press Enter to stop and flush pending events."""

import argparse
import asyncio
import threading
from pathlib import Path

import httpx
from playwright.async_api import Error as PlaywrightError, async_playwright
from pydantic import ValidationError

from .browser import BrowserRecorder
from .config import RecorderConfig


async def record(config: RecorderConfig) -> int:
    recorder = BrowserRecorder(config)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context(service_workers='block', accept_downloads=False)
        try:
            await recorder.start(context)
            data = Path(__file__).resolve().parents[1] / 'data'
            data.mkdir(exist_ok=True)
            (data / 'last_session.txt').write_text(recorder.session_id, encoding='utf-8')
            print(f'Session ID: {recorder.session_id}', flush=True)
            print('Teach Mode is recording. Return to this terminal and press ENTER to stop.', flush=True)
            print('Field values are OFF unless explicitly allowlisted.', flush=True)
            loop = asyncio.get_running_loop()

            def terminal_stop():
                try:
                    input()
                except EOFError:
                    pass
                loop.call_soon_threadsafe(recorder.stopped.set)

            threading.Thread(target=terminal_stop, daemon=True).start()
            browser.on('disconnected', lambda _: recorder.stopped.set())
            context.on('page', lambda page: page.on('close', lambda _: (
                recorder.stopped.set() if not context.pages else None
            )))
            page = await context.new_page()
            await page.goto(config.start_url, wait_until='domcontentloaded')
            await recorder.stopped.wait()
        finally:
            await recorder.stop()
            await browser.close()
            print(f'Session ID: {recorder.session_id}', flush=True)
            print(f'Confirmed saved events: {recorder.saved_count}', flush=True)
        if recorder.failure:
            print(f'ERROR: {recorder.failure} {recorder.unsaved_count} event(s) not confirmed saved.')
            return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='ShadowOps Teach Mode: local browser recorder')
    parser.add_argument(
        '--config', type=Path,
        default=Path(__file__).resolve().parents[1] / 'recorder_config.json',
        help='Path to an explicit local-test configuration JSON file.',
    )
    args = parser.parse_args()
    try:
        config = RecorderConfig.load(args.config)
        return asyncio.run(record(config))
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, ValidationError, RuntimeError, httpx.HTTPError, PlaywrightError) as error:
        # Avoid printing request payloads, page contents, or secret-bearing URLs.
        print(f'Could not record ({type(error).__name__}). Check the backend, local site, configuration and Chromium installation.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
