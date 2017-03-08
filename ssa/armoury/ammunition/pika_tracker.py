
"""this module is implement the function detector for oslo_messaging

"""
import logging
import json

from ssa.armoury.ammunition.function_tracker import FunctionTracker
from ssa.armoury.ammunition.tracker import current_tracker
from ssa.logistics.object_name import callable_name

console = logging.getLogger(__name__)


def pika_channel_publish_wrapper(wrapped, instance, args, kwargs):
    try:
        console.info('pika_channel_publish_wrapper before')

        console.info(args)
        console.info(kwargs)

        tracker = current_tracker()
        if not tracker:
            return wrapped(*args, **kwargs)

        tracker.set_tracker_name(callable_name(wrapped), priority=4)
        with FunctionTracker(tracker, callable_name(wrapped), params=kwargs):
            kwargs['body'] = json.dumps({'pika_trace_id': tracker._trace_id, 'body': kwargs['body']})
            console.info('pika_channel_publish_wrapper after')
            console.info(args)
            console.info(kwargs)
            return wrapped(*args, **kwargs)
    except Exception as e:
        console.exception("pika_channel_publish_wrapper error")
