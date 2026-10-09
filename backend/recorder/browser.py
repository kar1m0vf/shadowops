"""Playwright instrumentation and ordered delivery to the existing events API."""

import asyncio
from pathlib import Path
from uuid import uuid4

import httpx
from playwright.async_api import BrowserContext, Error as PlaywrightError
from pydantic import ValidationError

from main import BrowserEvent
from .config import RecorderConfig, clean_url, local_origin


class BrowserRecorder:
    def __init__(self, config: RecorderConfig):
        self.config = config
        self.session_id = f"teach-{uuid4()}"
        self.saved_count = 0
        self.unsaved_count = 0
        self.failure: str | None = None
        self.stopped = asyncio.Event()
        self._queue: asyncio.Queue = asyncio.Queue()
        self._accepting = False
        self._context: BrowserContext | None = None
        self._worker: asyncio.Task | None = None
        self._client: httpx.AsyncClient | None = None

    async def start(self, context: BrowserContext):
        self._context = context
        self._client = httpx.AsyncClient(
            base_url=self.config.api_url.rstrip('/'), timeout=5, trust_env=False,
            follow_redirects=False,
        )
        try:
            response = await self._client.get('/health')
            if response.status_code != 200 or response.json().get('service') != 'shadowops-backend':
                raise RuntimeError('The configured API is not a healthy ShadowOps backend.')
            await context.route('**/*', self._route)
            await context.route_web_socket('**/*', self._websocket)
            await context.expose_binding('__shadowops_record', self._receive)
            script = Path(__file__).with_name('observer.js').read_text(encoding='utf-8')
            script = script.replace('__SHADOWOPS_CONFIG__', self.config.model_dump_json())
            await context.add_init_script(script=script)
            self._accepting = True
            self._worker = asyncio.create_task(self._send_events())
        except Exception:
            await self._client.aclose()
            raise

    async def _route(self, route):
        if self.config.allows(route.request.url):
            await route.continue_()
        else:
            await route.abort('blockedbyclient')

    async def _websocket(self, route):
        url = route.url.replace('ws://', 'http://', 1).replace('wss://', 'https://', 1)
        if self.config.allows(url):
            route.connect_to_server()
        else:
            await route.close()

    def _receive(self, source, payload):
        if not self._accepting or self.failure or not isinstance(payload, dict):
            return
        frame = source['frame']
        if frame != source['page'].main_frame or not self.config.allows(frame.url):
            return
        payload = dict(payload)
        if not self.config.allows(payload.get('url', frame.url)):
            return
        allowed_selector = payload.pop('_allowed_selector', None)
        if 'value' in payload and not any(
            field.origin == local_origin(frame.url) and field.selector == allowed_selector
            for field in self.config.value_allowlist
        ):
            payload.pop('value')
        payload['session_id'] = self.session_id
        payload['url'] = clean_url(payload.get('url', frame.url))
        try:
            event = BrowserEvent.model_validate(payload)
        except (ValidationError, ValueError):
            self.failure = 'A captured event failed validation; recording stopped.'
            self.unsaved_count += 1
            self.stopped.set()
            return
        self._queue.put_nowait(event.model_dump(mode='json'))

    async def _send_events(self):
        while True:
            event = await self._queue.get()
            try:
                if event is None:
                    return
                if self.failure:
                    self.unsaved_count += 1
                    continue
                response = await self._client.post('/api/events', json=event)
                if response.status_code != 201:
                    raise RuntimeError(f'API returned HTTP {response.status_code}.')
                self.saved_count += 1
            except (httpx.HTTPError, RuntimeError) as error:
                self.unsaved_count += 1
                # No retries: this API has no idempotency key, so retries can duplicate events.
                self.failure = f'Event delivery failed ({type(error).__name__}); recording stopped.'
                self.stopped.set()
            finally:
                self._queue.task_done()

    async def stop(self):
        if self._worker is None:
            return
        for page in list(self._context.pages):
            if not page.is_closed():
                try:
                    await page.evaluate('() => window.__shadowopsObserver?.stop()')
                except PlaywrightError:
                    pass  # A closed/navigating document cannot flush its unfinished edit.
        self._accepting = False
        await self._queue.join()
        self._queue.put_nowait(None)
        await self._worker
        await self._client.aclose()
        self._worker = None
        self.stopped.set()
