# -*- coding: utf-8 -*-
import os
import sys
import imp
import logging

from ssa.config.start_log import log_bootstrap
from ssa.logistics.mapper import ENV_CONFIG_FILE


log_bootstrap('SSA Bootstrap = %s' % __file__)
log_bootstrap('working_directory = %r' % os.getcwd())

boot_directory = os.path.dirname(__file__)
root_directory = os.path.dirname(boot_directory)
log_bootstrap("root dir is: %s" % boot_directory)

path = list(sys.path)
if boot_directory in path:
    del path[path.index(boot_directory)]


try:
    (filename, pathname, description) = imp.find_module('sitecustomize', path)
except ImportError:
    pass
else:
    imp.load_module('sitecustomize', filename, pathname, description)

config_file = os.environ.get(ENV_CONFIG_FILE, None)
log_bootstrap("get config  %s" % config_file, close=True)


if config_file is None:
    from ssa.tingyun import TING_YUN_CONFIG_FILE
    #private_config = '/opt/tingyun.ini'
    private_config = TING_YUN_CONFIG_FILE
    if os.path.isfile(private_config):
        config_file = private_config
        log_bootstrap('used for specified config file[%s] in emergency!' % config_file, close=True)

if config_file is not None:
    if root_directory not in sys.path:
        sys.path.insert(0, root_directory)

    import ssa.startup
    ssa.startup.preheat_fight(config_file=config_file)
