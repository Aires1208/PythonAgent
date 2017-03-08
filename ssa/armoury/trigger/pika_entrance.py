# -*- coding: utf-8 -*-
import sys
import json

from ssa.armoury.ammunition.function_tracker import FunctionTracker
from ssa.armoury.ammunition.tracker import current_tracker
from ssa.battlefield.proxy import proxy_instance
from ssa.battlefield.tracer import Tracer
from ssa.embattle.log_file import console
from ssa.logistics.basic_wrapper import wrap_object, FunctionWrapper
from ssa.logistics.object_name import callable_name


def pika_application_wrapper(module, object_path, *args):
    wrap_object(module, object_path, pika_wrapper_inline, *args)


def pika_wrapper_inline(wrapped, framework="Python", version=None):

    console.info("wrap the pika entrance with framework(%s), version(%s)", framework, version)

    def wrapper(wrapped, instance, args, kwargs):

        console.info('args:')
        console.info(args)
        console.info('kwargs:')
        console.info(kwargs)

        method = args[0]
        header = args[1]
        body = None
        pika_trace_id = None
        try:
            wrapped_message = json.loads(args[2])
            if 'pika_trace_id' in wrapped_message:
                pika_trace_id = wrapped_message['pika_trace_id']
                body = wrapped_message['body']
            else:
                body = args[2]
        except Exception:
            body = args[2]
        args = (method, header, body)
        params = {
            #'method': str(method),
            #'header': str(header),
            'body': body
        }

        tracker = current_tracker()
        console.info("pika_wrapper_inline>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
        console.info("current_tracker:1: %s" % tracker)
        if tracker:
            console.info("current_tracker:2: None")
            console.info("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
            return wrapped(*args, **kwargs)

        environ = {
            'k1': 'v1'
        }

        tracker = Tracer(proxy_instance(), environ, framework)

        if pika_trace_id is not None:
            tracker._trace_id = pika_trace_id
        tracker.generate_trace_id()
        tracker.start_work()

        result = None
        try:
            tracker.set_tracker_name(callable_name(wrapped), priority=1)
            with FunctionTracker(tracker, name='Application', group='Python.pika', params=params):
                result = wrapped(*args, **kwargs)
            console.info("pika_wrapper_inline<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
        except:
            console.exception("pika_wrapper_inline")
            tracker.finish_work(*sys.exc_info())
            raise
        else:
            tracker.finish_work(None, None, None)

        return result

    return FunctionWrapper(wrapped, wrapper)


pika_wrapper_entrance = pika_wrapper_inline
