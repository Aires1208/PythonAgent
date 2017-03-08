
"""Define this module for basic armory for pika

"""

import logging

from ssa.armoury.ammunition.pika_tracker import pika_channel_publish_wrapper
from ssa.armoury.trigger.pika_entrance import pika_application_wrapper
from ssa.logistics.basic_wrapper import wrap_function_wrapper

console = logging.getLogger(__name__)


def detect_pika_consumer_entrance(module):
    print "==>detect_oslo_messaging_pika_consumer_entrance begin"
    pika_application_wrapper(module.Channel, '_on_deliver', ('pika', ))
    print "<==detect_oslo_messaging_pika_consumer_entrance end"


def detect_pika_publish_entrance(module):
    print "==>detect_pika_publish_entrance begin"
    wrap_function_wrapper(module.Channel, 'basic_publish', pika_channel_publish_wrapper)
    print "<==detect_pika_publish_entrance end"
