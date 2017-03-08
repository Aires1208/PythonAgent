# -*- coding: utf-8 -*-
import sys
import json

from ssa.logistics.basic_wrapper import wrap_object, FunctionWrapper
from ssa.logistics.object_name import callable_name
from ssa.armoury.ammunition.function_tracker import FunctionTracker, function_trace_wrapper
from ssa.armoury.ammunition.tracker import current_tracker
from ssa.battlefield.tracer import Tracer
from ssa.battlefield.proxy import proxy_instance
from ssa.armoury.trigger.browser_rum import TingYunWSGIBrowserRumMiddleware
from ssa.armoury.trigger.cross_trace import process_header
from ssa.util import dumpstacks
from ssa.embattle.log_file import console

TARGET_WEB_APP = "web_app"
AGENT_REQUEST_SWITCH = "DISABLE_SSA_AGENT"


def wsgi_application_wrapper(module, object_path, *args):
    wrap_object(module, object_path, wsgi_wrapper_inline, *args)


def wsgi_wrapper_inline(wrapped, framework="Python", version=None, target=TARGET_WEB_APP):
    console.info("wrap the wsgi entrance with framework(%s), version(%s)", framework, version)

    def wrapper(wrapped, instance, args, kwargs):
        console.info("args===>")
        console.info(args)
        console.info("args<===")
        tracker = current_tracker()
        console.info("wsgi_wrapper_inline>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
        console.info("current_tracker:1: %s" % tracker)
        if tracker:
            console.info("current_tracker:2: None")
            console.info("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
            return wrapped(*args, **kwargs)

        environ, start_response = parse_wsgi_protocol(target, *args, **kwargs)
        disable_agent = environ.get(AGENT_REQUEST_SWITCH, None)
        if disable_agent:
            console.debug("Current trace is disabled with http request environment. %s", environ)
            return wrapped(*args, **kwargs)

        tracker = Tracer(proxy_instance(), environ, framework)
        tracker.generate_trace_id()
        tracker.start_work()

        def _start_response(status, response_headers, *args):
            # deal the response header/data
            process_header(tracker, response_headers)
            tracker.deal_response(status, response_headers, *args)
            _write = start_response(status, response_headers, *args)

            return _write

        result = []
        try:
            tracker.set_tracker_name(callable_name(wrapped), priority=1)
            application = function_trace_wrapper(wrapped)
            console.info("current_tracker:2: %s" % tracker)
            with FunctionTracker(tracker, name='Application', group='Python.WSGI'):
                result = TingYunWSGIBrowserRumMiddleware(tracker, application, _start_response, environ)()  # sunyan: 1
                # result = application(environ, start_response)
            console.info("wsgi_wrapper_inline<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
        except:
            console.exception("wsgi_entrance")
            tracker.finish_work(*sys.exc_info())
            raise

        return WSGIApplicationResponse(tracker, result)

    return FunctionWrapper(wrapped, wrapper)


class WSGIApplicationResponse(object):

    def __init__(self, tracer, generator):
        self.tracer = tracer
        self.generator = generator

    def __iter__(self):

        try:
            with FunctionTracker(self.tracer, name='Response', group='Python.WSGI'):
                for item in self.generator:  # sunyan: 2
                    yield item  # sunyan: 3
        except GeneratorExit:
            raise
        except:  # Catch all
            self.tracer.record_exception(*sys.exc_info())
            raise

    def close(self):
        """Server/gateway will call this close method to indicate that the task for tracing the request finished.
        :return:
        """
        # FIXME sunyan werkzeug/debug/__init__.py, line 288, if has close attribute, then invoke it.
        try:
            if hasattr(self.generator, 'close'):
                self.generator.close()
        except:  # Catch all
            self.tracer.finish_work(*sys.exc_info())
            raise
        else:
            self.tracer.finish_work(None, None, None)


def parse_wsgi_protocol(target, *args, **kwargs):
    if target == TARGET_WEB_APP:
        def wsgi_args(environ, start_response, *args, **kwargs):
            return environ, start_response

        return wsgi_args(*args, **kwargs)
    else:
        # FIXME
        return None


def wsgi_application_decorator(framework='xx', version='xx'):
    framework = 'xx' if framework is None else framework
    version = 'xx' if version is None else version

    def decorator(wrapped):
        return wsgi_wrapper_inline(wrapped, framework, version)

    return decorator


wsgi_app_wrapper_entrance = wsgi_wrapper_inline
