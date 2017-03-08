# -*- coding: utf-8 -*-
import sys

from ssa.armoury.ammunition.function_tracker import FunctionTracker
from ssa.armoury.ammunition.tracker import current_tracker
from ssa.battlefield.proxy import proxy_instance
from ssa.battlefield.tracer import Tracer
from ssa.embattle.log_file import console
from ssa.logistics.basic_wrapper import wrap_object, FunctionWrapper
from ssa.logistics.object_name import callable_name


def oslo_messaging_application_wrapper(module, object_path, *args):
    wrap_object(module, object_path, oslo_messaging_wrapper_inline, *args)


def oslo_messaging_wrapper_inline(wrapped, framework="Python", version=None):

    console.info("wrap the oslo_messaging entrance with framework(%s), version(%s)", framework, version)

    def wrapper(wrapped, instance, args, kwargs):

        incoming_message = args[0][0]
        msg = incoming_message.message
        console.info("msg:")
        console.info(msg)
        ctxt = incoming_message.ctxt
        console.info("ctxt:")
        console.info(ctxt)

        oslo_messaging_trace_id = ctxt['oslo_messaging_trace_id'] if 'oslo_messaging_trace_id' in ctxt else None

        tracker = current_tracker()
        console.info("oslo_messaging_wrapper_inline>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
        console.info("current_tracker:1: %s" % tracker)
        if tracker:
            console.info("current_tracker:2: None")
            console.info("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
            return wrapped(*args, **kwargs)

        environ = {
            'k1': 'v1'
        }

        tracker = Tracer(proxy_instance(), environ, framework)
        if oslo_messaging_trace_id is not None:
            tracker._trace_id = oslo_messaging_trace_id
        tracker.generate_trace_id()
        tracker.start_work()

        result = None
        try:
            tracker.set_tracker_name(callable_name(wrapped), priority=1)
            with FunctionTracker(tracker, name='Application', group='Python.oslo_messaging', params=msg['args']):
                result = wrapped(*args, **kwargs)
            console.info("oslo_messaging_wrapper_inline<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
        except:
            console.exception("oslo_messaging_entrance")
            tracker.finish_work(*sys.exc_info())
            raise
        else:
            tracker.finish_work(None, None, None)

        return result

    return FunctionWrapper(wrapped, wrapper)


oslo_messaging_rpc_wrapper_entrance = oslo_messaging_wrapper_inline
