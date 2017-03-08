# -*- coding: utf-8 -*-
import logging
import os
import sys
import threading
import traceback
import ConfigParser

from ssa.logistics.mapper import ENV_CONFIG_FILE
from ssa.logistics.exceptions import ConfigurationError
from ssa.logistics.mapper import map_log_level, map_key_words, map_app_name
from ssa.config.settings import global_settings
from ssa.embattle.log_file import initialize_logging
from ssa.packages.wrapt.importer import register_post_import_hook
from ssa.embattle.repertoire import defined_repertoire
from ssa.config.start_log import log_bootstrap

console = logging.getLogger(__name__)


class Embattle(object):
    _lock = threading.Lock()
    _instance = None

    def __init__(self, config_file):
        self.config_file = config_file
        self.is_embattled = False
        self.valid_embattle = True
        self._config_parser = ConfigParser.RawConfigParser()
        self._settings = global_settings()
        self._inspect_lock = threading.Lock()

        if not config_file:
            self.config_file = os.environ.get(ENV_CONFIG_FILE, None)

        if not self.config_file:
            log_bootstrap('Agent config file is not found, agent start failed.')
            self.valid_embattle = False

            log_bootstrap("get config file %s" % self.config_file)

    @staticmethod
    def singleton_instance(config_file):
        instance = Embattle._instance

        if not instance:
            with Embattle._lock:
                instance = Embattle._instance
                if not instance:
                    instance = Embattle(config_file)
                    Embattle._instance = instance

        return instance

    def inspect_prerequisites(self):
        log_bootstrap("Inspecting config file %s" % self.config_file, close=True)

        if not self._config_parser.read(self.config_file):
            raise ConfigurationError("Unable to access the config file. %s", self.config_file)

        self._settings.config_file = self.config_file
        self.load_settings()
        self.load_settings('tingyun:exclude', "plugins")
        self.load_settings('tingyun:private', "port")
        self.load_settings('tingyun:private', "host")
        self.load_settings('tingyun:proxy', "proxy_host")
        self.load_settings('tingyun:proxy', "proxy_port")
        self.load_settings('tingyun:proxy', "proxy_user")
        self.load_settings('tingyun:proxy', "proxy_pwd")
        self.load_settings('tingyun:proxy', "proxy_scheme")

        # we can not access the log file and log level from the config parser. it maybe empty.
        initialize_logging(self._settings.log_file, self._settings.log_level)

    def load_settings(self, section='tingyun', option=None, method='get'):
        self._settings.config_file = self.config_file

        if option is None:
            self._process_setting(section, 'log_file', method, None)
            self._process_setting(section, 'log_level', method, map_log_level)
            self._process_setting(section, 'license_key', method, None)
            self._process_setting(section, 'enabled', method, map_key_words)
            self._process_setting(section, 'app_name', method, map_app_name)
            # sunyan
            self._process_setting(section, 'app_framework', method, map_app_name)
            self._process_setting(section, 'audit_mode', method, map_key_words)
            self._process_setting(section, 'auto_action_naming', method, map_key_words)
            self._process_setting(section, 'ssl', method, map_key_words)
            self._process_setting(section, 'action_tracer.log_sql', method, map_key_words)
            self._process_setting(section, 'daemon_debug', method, map_key_words, True)
            self._process_setting(section, 'enable_profile', method, map_key_words)
            self._process_setting(section, 'urls_merge', method, map_key_words)
            self._process_setting(section, 'verify_certification', method, map_key_words)

            self._process_setting(section, 'tornado_wsgi_adapter_mode', method, map_key_words)
        else:
            self._process_setting(section, option, method, None, True)

    def _process_setting(self, section, option, method='get', mapper=None, hide=False):
        try:
            value = getattr(self._config_parser, method)(section, option)
            value = value if not mapper else mapper(value)

            # invalid value with mapper func mapping, used default instead
            if value is None:
                return

            target = self._settings
            fields = option.split('.', 1)

            while True:
                if len(fields) == 1:
                    setattr(target, fields[0], value)
                    break
                else:
                    target = getattr(target, fields[0])
                    fields = fields[1].split('.', 1)
        except ConfigParser.NoSectionError:
            if not hide:
                console.debug("No section[%s] in configure file", section)
        except ConfigParser.NoOptionError:
            if not hide:
                console.debug("No option[%s] in configure file", option)
        except Exception as err:
            console.warning("Process config error, section[%s]-option[%s] will use default value instead. %s", err)

    def detector(self, target_module, hook_module, function):

        def _detect(target_module):
            try:
                print("1.hook_module:%s" % hook_module)
                print("2.function:%s" % function)
                print("3.target_module:%s" % target_module)
                getattr(self.importer(hook_module), function)(target_module)
                console.info("Detect hooker %s for target module %s", hook_module, target_module)
            except Exception as _:
                console.warning("error occurred: %s" % traceback.format_exception(*sys.exc_info()))

        return _detect

    def importer(self, name):
        __import__(name)
        return sys.modules[name]

    def activate_weapons(self):
        exclude = self._settings.plugins
        for name, hooks in defined_repertoire().items():
            print("name:%s" % name)
            if name in exclude:
                console.debug("Ignore the plugin %s", name)
                continue
            for hook in hooks:
                print("|-hook:%s" % hook)
                target = hook.get('target', '')
                hook_func = hook.get('hook_func', '')
                hook_module = hook.get('hook_module', '')
                register_post_import_hook(self.detector(target, hook_module, hook_func), target)

    def execute(self):
        if not self.valid_embattle:
            return False

        # has been for some prerequisite check for corps operation
        if self.is_embattled:
            console.warning("Agent was initialized before.")
            return False

        with self._inspect_lock:

            if self.is_embattled:
                console.warning('agent was initialized before, skip it now.')
                return False

            log_bootstrap("Embattle:Stating init agent environment %s." % self._settings)
            self.is_embattled = True

            try:
                self.inspect_prerequisites()
                self.activate_weapons()
            except Exception as err:
                console.error("Errors. when initial the agent system. %s", err)
                return False

            return True


# This must the only entry for holding the corps's embattle
def take_control(config_file=None):
    return Embattle.singleton_instance(config_file)
