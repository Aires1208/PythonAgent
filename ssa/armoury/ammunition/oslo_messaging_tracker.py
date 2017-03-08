
"""this module is implement the function detector for oslo_messaging

"""
import logging

from ssa.armoury.ammunition.function_tracker import FunctionTracker
from ssa.armoury.ammunition.tracker import current_tracker
from ssa.logistics.object_name import callable_name

console = logging.getLogger(__name__)


def rpc_client_prepare_call_wrapper(wrapped, instance, args, kwargs):
    try:
        console.info('rpc_client_prepare_call_wrapper before')
        console.info(args)
        console.info(kwargs)

        ctxt = args[0]
        method = args[1]

        tracker = current_tracker()
        if not tracker:
            return wrapped(*args, **kwargs)

        tracker.set_tracker_name(callable_name(wrapped), priority=4)
        with FunctionTracker(tracker, callable_name(wrapped), params=kwargs):
            ctxt['oslo_messaging_trace_id'] = tracker._trace_id
            console.info('rpc_client_prepare_call_wrapper after')
            console.info(args)
            console.info(kwargs)
            return wrapped(*args, **kwargs)
    except Exception as e:
        console.exception("rpc_client_prepare_call_wrapper error")


def rpc_client_prepare_cast_wrapper(wrapped, instance, args, kwargs):
    try:
        console.info('rpc_client_prepare_cast_wrapper before')
        console.info(args)
        console.info(kwargs)

        ctxt = args[0]
        method = args[1]

        tracker = current_tracker()
        if not tracker:
            return wrapped(*args, **kwargs)

        tracker.set_tracker_name(callable_name(wrapped), priority=4)
        with FunctionTracker(tracker, callable_name(wrapped), params=kwargs):
            ctxt['oslo_messaging_trace_id'] = tracker._trace_id
            console.info('rpc_client_prepare_cast_wrapper after')
            console.info(args)
            console.info(kwargs)
            return wrapped(*args, **kwargs)
    except Exception as e:
        console.exception("rpc_client_prepare_cast_wrapper error")
