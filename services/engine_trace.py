"""Bounded engine diagnostics: never accept message bodies, URLs or credentials."""
import json
import re
import time
import uuid

STAGES = {'method', 'network', 'fetch', 'route', 'idle', 'shutdown', 'worker'}
EVENTS = {'begin', 'end', 'error', 'headers', 'timeout', 'pending', 'snapshot'}
NUMBERS = {'id', 'elapsed_ms', 'requests', 'children', 'background', 'intervals',
           'pending_methods', 'pending_network', 'pending_fetch', 'emitted', 'dropped', 'status'}
RPCS = {'which', 'state_get', 'state_set', 'state_del', 'config', 'summarize',
        'render_asset', 'render_status', 'render_text', 'reply', 'upload', 'get_reply', 'onebot'}


def safe_packet(data):
    if (not isinstance(data, dict) or not isinstance(data.get('stage'), str)
            or not isinstance(data.get('event'), str) or data['stage'] not in STAGES or data['event'] not in EVENTS):
        return {}
    out = {'stage': data['stage'], 'event': data['event']}
    for key in ('name', 'error'):
        value = data.get(key)
        if isinstance(value, str) and re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_.$]{0,79}', value):
            out[key] = value
    host = data.get('host')
    if isinstance(host, str) and len(host) <= 253 and re.fullmatch(r'[A-Za-z0-9.:-]+', host):
        out['host'] = host
    for key in NUMBERS:
        value = data.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 10**12:
            out[key] = int(value)
    return out


class EngineTrace:
    def __init__(self, logger, route, timeout):
        self.logger = logger
        self.id = uuid.uuid4().hex[:8]
        self.started = time.monotonic()
        self.active = {}
        self.last = {}
        self.rpc = None
        self.counters = {}
        route = route if isinstance(route, str) and re.fullmatch(r'[A-Za-z0-9_]{1,64}', route) else 'unknown'
        self.logger.info('RConsole trace=%s begin route=%s timeout=%ss', self.id, route, timeout)

    def record(self, data):
        row = safe_packet(data)
        if not row:
            return
        self.last = row
        key = (row['stage'], row.get('id'))
        if row['event'] in {'begin', 'pending'} and 'id' in row:
            if key in self.active or len(self.active) < 128:
                self.active[key] = (row, time.monotonic() - row.get('elapsed_ms', 0)/1000)
        elif row['event'] in {'end', 'error'} or (row['event']=='headers' and row['stage']=='fetch'):
            self.active.pop(key, None)
        if row['event'] == 'snapshot':
            self.counters = {k: v for k, v in row.items() if k in NUMBERS}
        level = self.logger.info if (row['event'] in {'error', 'timeout', 'pending', 'snapshot'}
                                    or row['stage'] in {'route', 'shutdown'}
                                    or row.get('elapsed_ms', 0) >= 1000) else self.logger.debug
        level('RConsole trace=%s diagnostic=%s', self.id, json.dumps(row, ensure_ascii=True))

    def rpc_begin(self, op):
        self.rpc = (op if op in RPCS else 'unknown', time.monotonic())

    def rpc_end(self):
        if self.rpc:
            elapsed = round((time.monotonic()-self.rpc[1])*1000)
            if elapsed >= 1000:
                self.logger.info('RConsole trace=%s adapter=%s elapsed_ms=%s', self.id, self.rpc[0], elapsed)
        self.rpc = None

    def finish(self, outcome):
        now = time.monotonic()
        pending = [dict(row, elapsed_ms=round((now-started)*1000))
                   for row, started in list(self.active.values())[:16]]
        summary = {'outcome': outcome if outcome in {'done','timeout','error','cancelled'} else 'error',
                   'elapsed_ms': round((now-self.started)*1000), 'pending': pending,
                   'counters': self.counters}
        if self.rpc:
            summary['adapter'] = self.rpc[0]
            summary['adapter_elapsed_ms'] = round((now-self.rpc[1])*1000)
        if self.last:
            summary['last'] = self.last
        log = self.logger.info if outcome == 'done' else self.logger.warning
        log('RConsole trace=%s finish=%s', self.id, json.dumps(summary, ensure_ascii=True))
