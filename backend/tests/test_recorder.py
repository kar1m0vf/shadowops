"""Real Chromium -> real HTTP FastAPI -> isolated SQLite integration tests."""

import asyncio
import functools
import json
import os
import socket
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest
import uvicorn
from playwright.async_api import Error as PlaywrightError, async_playwright
from pydantic import ValidationError

from main import create_app
from recorder.browser import BrowserRecorder
from recorder.config import RecorderConfig, clean_url


class QuietHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/demo-view'):
            self.path = '/recorder.html'
        super().do_GET()

    def log_message(self, *args):
        pass


@pytest.fixture
def live_servers(tmp_path):
    handler = functools.partial(QuietHandler, directory=str(Path(__file__).parent / 'fixtures'))
    website = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    website_thread = threading.Thread(target=website.serve_forever, daemon=True)
    website_thread.start()
    api_socket = socket.socket()
    api_socket.bind(('127.0.0.1', 0))
    api_url = f'http://127.0.0.1:{api_socket.getsockname()[1]}'
    server = uvicorn.Server(uvicorn.Config(
        create_app(tmp_path / 'events.sqlite3'), host='127.0.0.1', log_level='error',
    ))
    api_thread = threading.Thread(target=server.run, kwargs={'sockets': [api_socket]}, daemon=True)
    api_thread.start()
    deadline = time.monotonic() + 10
    while not server.started and api_thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)
    if not server.started:
        pytest.fail('Test FastAPI server did not start.')
    origin = f'http://127.0.0.1:{website.server_port}'
    try:
        yield origin, api_url
    finally:
        server.should_exit = True
        api_thread.join(timeout=10)
        api_socket.close()
        website.shutdown()
        website.server_close()
        website_thread.join(timeout=5)


def config_for(servers, selectors=(), *, synthetic_identifier=False):
    origin, api_url = servers
    return RecorderConfig(
        start_url=origin + '/recorder.html', api_url=api_url,
        allowed_origins=[origin],
        value_allowlist=[{'origin': origin, 'selector': selector, 'synthetic_identifier': synthetic_identifier} for selector in selectors],
    )


async def browser_session(config, interactions):
    recorder = BrowserRecorder(config)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=os.getenv('SHADOWOPS_TEST_HEADED') != '1',
        )
        context = await browser.new_context(service_workers='block', accept_downloads=False)
        try:
            await recorder.start(context)
            page = await context.new_page()
            await page.goto(config.start_url)
            await interactions(page)
        finally:
            await recorder.stop()
            await browser.close()
    assert recorder.failure is None
    with httpx.Client(base_url=config.api_url, trust_env=False) as client:
        response = client.get(f'/api/events/{recorder.session_id}')
        assert response.status_code == 200
        events = response.json()
    assert len(events) == recorder.saved_count
    assert len(events) > 0
    assert [event['id'] for event in events] == sorted(event['id'] for event in events)
    assert all(event['session_id'] == recorder.session_id for event in events)
    return events


def test_real_browser_order_completed_edits_spa_navigation_and_stop(live_servers):
    config = config_for(live_servers, ['#demo-note', '#choice', '#dynamic-note'])

    async def interactions(page):
        await page.locator('#demo-note').press_sequentially('Synthetic demo note')
        await page.get_by_role('button', name='Save demo', exact=True).click()
        await page.locator('#choice').focus()
        await page.locator('#choice').press('ArrowDown')
        await page.locator('#choice').press('Enter')
        await page.get_by_role('button', name='Open demo view', exact=True).click()
        await page.get_by_label('Dynamic note').press_sequentially('Synthetic dynamic note')
        await page.get_by_role('button', name='Dynamic save', exact=True).click()
        await page.get_by_role('link', name='Next page').click()
        await page.get_by_role('button', name='Second save', exact=True).click()
        await page.go_back()
        # An unfinished edit must be committed by recorder.stop(), without a blur.
        await page.locator('#demo-note').press('Control+A')
        await page.locator('#demo-note').press_sequentially('Final synthetic note')

    events = asyncio.run(browser_session(config, interactions))
    assert [event['action'] for event in events] == [
        'navigation', 'input_change', 'click', 'select_change', 'click', 'navigation',
        'input_change', 'click', 'click', 'navigation', 'click', 'navigation', 'input_change',
    ]
    changes = [event for event in events if event['action'] == 'input_change']
    assert len(changes) == 3  # Not one event per keystroke, or duplicate blur/change.
    assert changes[0]['value'] == 'Synthetic demo note'
    assert changes[1]['value'] == 'Synthetic dynamic note'
    assert changes[2]['value'] == 'Final synthetic note'
    assert changes[0]['target']['label'] == 'Demo note'
    assert changes[0]['target']['placeholder'] == 'Write a demo note'
    assert any(candidate['strategy'] == 'css' and candidate['value'] == '#demo-note'
               and candidate['match_count'] == 1 for candidate in changes[0]['target']['locator_candidates'])
    assert next(event for event in events if event['action'] == 'select_change')['value'] == 'second'
    assert all('?' not in event['url'] and '#' not in event['url'] for event in events)


@pytest.mark.parametrize('synthetic_identifier', [False, True])
def test_sensitive_values_are_excluded_even_when_fields_are_allowlisted(live_servers, synthetic_identifier):
    config = config_for(live_servers, ['input', 'select'], synthetic_identifier=synthetic_identifier)

    async def interactions(page):
        for selector, value in [
            ('#password', 'PASSWORD_FIELD_SECRET'),
            ('#access-token', 'TOKEN_FIELD_SECRET'),
            ('#email', 'user@example.com'),
            ('#card-number', '4111111111111111'),
            ('#login-name', 'LOGIN_FIELD_SECRET'),
            ('#demo-note', 'Bearer VALUE_FIELD_SECRET'),
        ]:
            await page.locator(selector).fill(value)
            await page.get_by_role('button', name='Save demo', exact=True).click()
        await page.locator('#private-label').click()

    events = asyncio.run(browser_session(config, interactions))
    serialized = json.dumps(events)
    for secret in ['PASSWORD_FIELD_SECRET', 'TOKEN_FIELD_SECRET', 'user@example.com',
                   '4111111111111111', 'HIDDEN_FIELD_SECRET', 'LOGIN_FIELD_SECRET', 'VALUE_FIELD_SECRET']:
        assert secret not in serialized
    assert all('value' not in event for event in events)
    assert all(event['target']['selector'] not in ['#password', '#access-token', '#email', '#login-name'] for event in events)


def test_keyboard_submission_records_completed_edit_before_submit_click(live_servers):
    config = config_for(live_servers, ['#form-note'])

    async def interactions(page):
        await page.get_by_label('Demo form note').press_sequentially('Synthetic form note')
        await page.get_by_label('Demo form note').press('Enter')

    events = asyncio.run(browser_session(config, interactions))
    assert [event['action'] for event in events] == ['navigation', 'input_change', 'click']
    assert events[1]['value'] == 'Synthetic form note'
    assert events[2]['target']['label'] == 'Submit demo form'


def test_default_policy_no_values_and_nonconfigured_origin_blocked(live_servers):
    config = config_for(live_servers)

    async def interactions(page):
        await page.locator('#unapproved').press_sequentially('UNAPPROVED_FIELD_CONTENT')
        await page.get_by_role('button', name='Save demo', exact=True).click()
        await page.locator('#choice').focus()
        await page.locator('#choice').press('ArrowDown')
        await page.locator('#choice').press('Enter')
        await page.locator('#demo-check').check()
        # This local API origin is reachable but is NOT an allowed browser origin.
        with pytest.raises(PlaywrightError):
            await page.goto(config.api_url + '/health')

    events = asyncio.run(browser_session(config, interactions))
    assert any(event['action'] == 'input_change' for event in events)
    assert any(event['action'] == 'select_change' for event in events)
    assert all('value' not in event for event in events)
    assert 'UNAPPROVED_FIELD_CONTENT' not in json.dumps(events)
    assert all(event['url'].startswith(live_servers[0]) for event in events)


@pytest.mark.parametrize('origin', ['https://example.com', 'http://0.0.0.0:5173', 'http://127.0.0.1:5173/path', 'http://user:password@localhost:5173'])
def test_remote_or_nonexact_origins_are_rejected(origin):
    with pytest.raises(ValidationError):
        RecorderConfig(allowed_origins=[origin])


def test_url_queries_fragments_and_token_paths_are_redacted():
    assert clean_url('http://127.0.0.1:5173/demo?token=SECRET#SECRET') == 'http://127.0.0.1:5173/demo'
    assert clean_url('http://127.0.0.1:5173/token/SECRET') == 'http://127.0.0.1:5173/[redacted]'


@pytest.mark.parametrize('policy', ['allowed', 'no_synthetic_flag', 'not_allowlisted', 'other_origin'])
def test_synthetic_identifier_requires_exact_origin_and_explicit_rule(live_servers, policy):
    config = config_for(live_servers, ['#transaction-id'], synthetic_identifier=True)
    if policy == 'no_synthetic_flag':
        config.value_allowlist[0].synthetic_identifier = False
    elif policy == 'not_allowlisted':
        config.value_allowlist = []
    elif policy == 'other_origin':
        other_origin = live_servers[0].replace('127.0.0.1', 'localhost')
        config.allowed_origins.append(other_origin)
        config.value_allowlist[0].origin = other_origin

    async def interactions(page):
        await page.get_by_label('Transaction ID', exact=True).press_sequentially('TXN-81001')
        await page.get_by_role('button', name='Save demo', exact=True).click()
        await page.get_by_label('Transaction ID', exact=True).fill('')
        await page.get_by_role('button', name='Save demo', exact=True).click()

    events = asyncio.run(browser_session(config, interactions))
    assert [event['action'] for event in events] == ['navigation', 'input_change', 'click', 'input_change', 'click']
    assert events[1]['target']['selector'] == '#transaction-id'
    if policy == 'allowed':
        assert events[1]['value'] == 'TXN-81001'
        assert events[3]['value'] == ''
    else:
        assert 'value' not in events[1]
        assert 'value' not in events[3]


def test_secret_values_in_a_synthetic_identifier_field_are_still_blocked(live_servers):
    config = config_for(live_servers, ['#transaction-id'], synthetic_identifier=True)
    secrets = ['user@example.com', '4111111111111111', 'Bearer DEMO_TOKEN_SECRET', 'password-example']

    async def interactions(page):
        for secret in secrets:
            await page.locator('#transaction-id').fill(secret)
            await page.get_by_role('button', name='Save demo', exact=True).click()

    events = asyncio.run(browser_session(config, interactions))
    assert all('value' not in event for event in events)
    assert all(secret not in json.dumps(events) for secret in secrets)


def test_checkbox_and_radio_states_are_booleans_in_interaction_order(live_servers):
    config = config_for(live_servers, ['input'], synthetic_identifier=True)

    async def interactions(page):
        await page.get_by_label('Demo checkbox', exact=True).check()
        await page.get_by_label('Demo checkbox', exact=True).uncheck()
        await page.get_by_label('Choice A', exact=True).check()
        await page.get_by_label('Choice B', exact=True).check()
        await page.locator('#sensitive-toggle').check()

    events = asyncio.run(browser_session(config, interactions))
    changes = [event for event in events if event['action'] == 'input_change']
    assert [event['target']['selector'] for event in changes] == ['#demo-check', '#demo-check', '#radio-a', '#radio-b']
    assert [event['checked'] for event in changes] == [True, False, True, True]
    assert all(type(event['checked']) is bool for event in changes)
    assert all('value' not in event for event in changes)
    assert 'STATE_VALUE_SECRET' not in json.dumps(events)
    assert changes[-1]['target']['context']['label'] == 'Demo choice group'


def test_accessible_labels_exclude_decorations_and_preserve_unicode(live_servers):
    async def interactions(page):
        await page.get_by_role('button', name='Investigate transaction', exact=True).click()
        await page.get_by_role('button', name='Open café', exact=True).click()

    events = asyncio.run(browser_session(config_for(live_servers), interactions))
    clicks = [event for event in events if event['action'] == 'click']
    assert [event['target']['label'] for event in clicks] == ['Investigate transaction', 'Open café']
    role_candidate = next(candidate for candidate in clicks[0]['target']['locator_candidates'] if candidate['strategy'] == 'role')
    assert role_candidate['name'] == 'Investigate transaction'
    assert role_candidate['match_count'] == 1


def test_repeated_buttons_have_context_and_explicit_ambiguity(live_servers):
    async def interactions(page):
        await page.get_by_role('region', name='Alpha panel').get_by_role('button', name='Review demo').click()
        await page.get_by_role('region', name='Beta panel').get_by_role('button', name='Review demo').click()
        await page.get_by_role('button', name='Duplicate demo').nth(0).click()
        await page.get_by_role('button', name='Duplicate demo').nth(1).click()

    events = asyncio.run(browser_session(config_for(live_servers), interactions))
    targets = [event['target'] for event in events if event['action'] == 'click']
    assert [target['context']['label'] for target in targets[:2]] == ['Alpha panel', 'Beta panel']
    assert [target['selector'] for target in targets[:2]] == ['#panel-alpha button', '#panel-beta button']
    for target in targets:
        role_candidate = next(candidate for candidate in target['locator_candidates'] if candidate['strategy'] == 'role')
        assert role_candidate['match_count'] == 2
    # No invented positional locator: identical controls in identical context remain ambiguous.
    assert targets[2] == targets[3]
    assert targets[2]['selector'] is None
