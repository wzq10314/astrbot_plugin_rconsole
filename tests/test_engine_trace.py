import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

spec=importlib.util.spec_from_file_location('engine_trace_under_test', Path(__file__).resolve().parents[1]/'services/engine_trace.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
EngineTrace, safe_packet=module.EngineTrace, module.safe_packet


class TraceTests(unittest.TestCase):
    def test_ignores_untrusted_bodies_and_credentials(self):
        row = safe_packet({'stage':'network','event':'error','host':'example.com',
                           'id':1,'elapsed_ms':125,'error':'ETIMEDOUT',
                           'url':'https://example.com/?token=secret',
                           'message':'cookie=secret','headers':{'Authorization':'secret'},
                           'name':'https://example.com/?token=secret'})
        self.assertEqual(row, {'stage':'network','event':'error','host':'example.com',
                               'id':1,'elapsed_ms':125,'error':'ETIMEDOUT'})
        self.assertEqual(safe_packet({'stage':'cookie=secret','event':'error'}), {})
        self.assertNotIn('host', safe_packet({'stage':'network','event':'begin','host':'user:pass@example.com'}))

    def test_timeout_retains_active_request_and_adapter_but_not_completed(self):
        log=Mock()
        with patch.object(module.time,'monotonic', return_value=10):
            trace=EngineTrace(log,'douyin',300)
            trace.record({'stage':'network','event':'begin','id':1,'host':'video.example.com'})
            trace.record({'stage':'network','event':'begin','id':2,'host':'api.example.com'})
            trace.record({'stage':'network','event':'end','id':2,'host':'api.example.com'})
            trace.rpc_begin('reply')
        with patch.object(module.time,'monotonic', return_value=310):
            trace.finish('timeout')
        result=log.warning.call_args.args[-1]
        self.assertIn('video.example.com', result)
        self.assertIn('"adapter": "reply"', result)
        self.assertIn('300000', result)
        self.assertEqual(len(trace.active), 1)

    def test_fetch_headers_finishes_fetch_observation(self):
        trace=EngineTrace(Mock(),'bili',300)
        trace.record({'stage':'fetch','event':'begin','id':1,'host':'api.example.com'})
        trace.record({'stage':'fetch','event':'headers','id':1,'status':200})
        self.assertFalse(trace.active)

    def test_active_diagnostics_are_bounded(self):
        trace=EngineTrace(Mock(),'bili',300)
        for i in range(300):trace.record({'stage':'network','event':'begin','id':i,'host':'example.com'})
        self.assertEqual(len(trace.active),128)

    def test_network_headers_and_timeout_do_not_hide_pending_body(self):
        trace=EngineTrace(Mock(),'douyin',300)
        trace.record({'stage':'network','event':'begin','id':1,'host':'cdn.example.com'})
        trace.record({'stage':'network','event':'headers','id':1,'status':200})
        trace.record({'stage':'network','event':'timeout','id':1,'error':'TimeoutError'})
        self.assertTrue(trace.active)
        trace.record({'stage':'network','event':'error','id':1,'error':'ECONNRESET'})
        self.assertFalse(trace.active)
