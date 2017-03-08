
"""Define this module for basic armory for oslo_messaging

"""

import logging

from ssa.armoury.ammunition.oslo_messaging_tracker import rpc_client_prepare_cast_wrapper, rpc_client_prepare_call_wrapper
from ssa.armoury.trigger.oslo_messaging_entrance import oslo_messaging_application_wrapper
from ssa.logistics.basic_wrapper import wrap_function_wrapper

console = logging.getLogger(__name__)


def detect_oslo_messaging_rpc_server_entrance(module):
    print "==>detect_oslo_messaging_rpc_server_entrance begin"
    oslo_messaging_application_wrapper(module.RPCServer, '_process_incoming', ('oslo_messaging', ))
    print "<==detect_oslo_messaging_rpc_server_entrance end"


def detect_oslo_messaging_rpc_client_entrance(module):
    print "==>detect_oslo_messaging_rpc_client_entrance begin"
    #wrap_function_wrapper(module.RPCClient, 'call', rpc_client_call_wrapper)
    #wrap_function_wrapper(module.RPCClient, 'cast', rpc_client_call_wrapper)
    wrap_function_wrapper(module._CallContext, 'call', rpc_client_prepare_call_wrapper)
    wrap_function_wrapper(module._CallContext, 'cast', rpc_client_prepare_cast_wrapper)
    print "<==detect_oslo_messaging_rpc_client_entrance end"
