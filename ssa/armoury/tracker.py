# -*- coding: utf-8 -*-

import logging
import time
import random
import sys
import traceback

from ssa.armoury.ammunition.timer import Timer
from ssa.battlefield.knapsack import knapsack
from ssa.logistics.warehouse.database_node import DatabaseNode
from ssa.logistics.warehouse.tracker_node import TrackerNode
from ssa.logistics.warehouse.error_node import ErrorNode, ExternalErrorNode
from ssa.packages import six

console = logging.getLogger(__name__)


class Tracker(object):

    def __init__(self, proxy, enabled=None, framework="Python"):
        self.framework = framework
        self.proxy = proxy
        self.enabled = False
        self._settings = None

        self.thread_id = knapsack().current_thread_id()

        self.background_task = False
        self.start_time = 0
        self.end_time = 0
        # FIXME
        self.queque_start = 0
        self._queue_time = 0
        self.trace_node = []
        self.async_func_trace_time = 0 # millisecond

        self._errors = []
        self.external_error = []
        self._custom_params = {}
        self._slow_sql_nodes = []

        self.http_method = "GET"
        self.request_uri = None
        self.http_status = 500
        self.request_params = {}
        self.header_params = {}
        self.cookie_params = {}
        self._priority = 0
        self._group = None
        self._name = None
        self.apdex = 0
        self._frozen_path = None

        self.stack_trace_count = 0
        self.explain_plan_count = 0

        self.thread_name = "Unknow"
        self.referer = ""

        self._trace_guid = ""
        self._trace_id = ""
        self._ssa_id = ""

        self._called_traced_data = ""
        self.call_ssa_id = ""
        self.call_req_id = ""

        self.db_time = -1
        self.external_time = -1
        self.redis_time = -1
        self.memcache_time = -1
        self.mongo_time = -1

        global_settings = proxy.global_settings
        if global_settings.enabled:
            if enabled or (enabled is None and proxy.enabled):
                self._settings = proxy.settings
                if not self._settings:
                    self.proxy.activate()
                    self._settings = proxy.settings

                if self._settings:
                    self.enabled = True

        if self.enabled:
            self._ssa_id = self._settings.tingyunIdSecret

    def __enter__(self):
        if not self.enabled:
            return self

        try:
            self.save_tracker()
        except Exception as _:
            console.fatal("Fatal error when save tracker, if this continues, please contact us for further investigation")
            raise

        self.start_time = time.time()
        self.trace_node.append(Timer(None))

    def __exit__(self, exc_type, exc_val, exc_tb, async=False):
        if not self.enabled:
            return

        if not async:
            try:
                self.drop_tracker()
            except Exception as err:
                console.exception("error detail %s", err)
                raise

        if not self.is_uri_captured(self.request_uri):
            console.debug("ignore the uri %s", self.request_uri)
            return

        if exc_type is not None and exc_val is not None and exc_tb is not None:
            self.record_exception(exc_type, exc_val, exc_tb)

        self.end_time = time.time()
        # FIXME
        duration = self.duration

        root_node = self.trace_node.pop()
        children = root_node.children
        exclusive = duration + root_node.exclusive

        tracker_type = "WebAction" if not self.background_task else "BackgroundAction"
        group = self._group or ("Python" if self.background_task else "Uri")
        request_params = self.filter_params(self.request_params)
        uri = self.url_encode(self.request_uri)

        # replace the sepcified matric apdex_t
        apdex_t = self._settings.apdex_t
        path = self.path
        if path in self._settings.action_apdex:
            apdex_t = self._settings.action_apdex.get(path)

        node = TrackerNode(type=tracker_type,
                           group=group,
                           name=self._name,
                           start_time=self.start_time,
                           end_time=self.end_time,
                           request_uri=uri,
                           duration=duration,
                           thread_name=self.thread_name,
                           http_status=self.http_status,
                           exclusive=exclusive,
                           children=tuple(children),
                           path=self.path,
                           errors=self._errors,
                           apdex_t=apdex_t,
                           queque_time=self.queque_time,
                           custom_params=self._custom_params,
                           request_params=request_params,
                           trace_id=self._trace_id,
                           referer=self.referer,
                           slow_sql=self._slow_sql_nodes,
                           trace_guid=self.generate_trace_guid(),
                           trace_data=self._called_traced_data,
                           external_error=self.external_error)

        self.proxy.record_tracker(node)

    def record_exception(self, exc=None, value=None, tb=None, params=None, tracker_type="WebAction", ignore_errors=[]):
        if not self._settings or not self._settings.error_collector.enabled:
            return

        if exc is None and value is None and tb is None:
            exc, value, tb = sys.exc_info()

        if exc is None or value is None or tb is None:
            console.warning("None exception is got. skip it now. %s, %s, %s", exc, value, tb)
            return

        if self.http_status in self._settings.error_collector.ignored_status_codes:
            console.debug("ignore the status code %s", self.http_status)
            return

        # 'True' - ignore the error.
        # 'False'- record the error.
        # ignore status code and maximum error number filter will be done in data engine because of voiding repeat count
        # method ignore_errors() is used to detect the the status code which is can not captured
        if callable(ignore_errors):
            should_ignore = ignore_errors(exc, value, tb, self._settings.error_collector.ignored_status_codes)
            if should_ignore:
                return

        # think more about error occurred before deal the status code.
        if self.http_status in self._settings.error_collector.ignored_status_codes:
            console.debug("record_exception: ignore  error collector status code")
            return

        module = value.__class__.__module__
        name = value.__class__.__name__
        fullname = '%s:%s' % (module, name) if module else name

        request_params = self.filter_params(self.request_params)
        if params:
            custom_params = dict(request_params)
            custom_params.update(params)
        else:
            custom_params = dict(request_params)

        try:
            message = str(value)
        except Exception as _:
            try:
                # Assume JSON encoding can handle unicode.
                message = six.text_type(value)
            except Exception as _:
                message = '<unprintable %s object>' % type(value).__name__

        stack_trace = traceback.extract_tb(tb)
        node = ErrorNode(error_time=int(time.time()), http_status=self.http_status, error_class_name=fullname,
                         uri=self.url_encode(self.request_uri), thread_name=self.thread_name, message=message,
                         stack_trace=stack_trace, request_params=custom_params, tracker_type=tracker_type,
                         referer=self.referer)

        self._errors.append(node)

    def record_external_error(self, url, error_code, http_status=0, _exception=None, request_params=None, tracker_type="External"):
        ignored_status = [401, ]
        if http_status in ignored_status or int(http_status) < 400:
            console.info("Agent caught http status code %s, ignore it now.", http_status)
            return

        status_code = error_code or http_status
        error_class_name = ""
        stack_trace = ""

        if _exception:
            exc, value, tb = _exception
            module = value.__class__.__module__
            name = value.__class__.__name__
            error_class_name = '%s:%s' % (module, name) if module else name
            stack_trace = traceback.extract_tb(tb)

        node = ExternalErrorNode(error_time=int(time.time()),
                                 status_code=status_code,
                                 thread_name=self.thread_name,
                                 url=url,
                                 error_class_name=error_class_name,
                                 http_status=http_status,
                                 stack_trace=stack_trace,
                                 request_params=request_params,
                                 tracker_type=tracker_type)

        self.external_error.append(node)

    @property
    def path(self):
        if self._frozen_path:
            return self._frozen_path

        tracker_type = "WebAction" if not self.background_task else "BackgroundAction"
        name = self._name or "Undefined"

        try:
            named_metric = self.settings.naming.naming_web_action(self.http_method, self.request_uri,
                                                                  self.request_params,
                                                                  self.header_params, self.cookie_params)
        except Exception as err:
            console.error("Error occurred when parsing naming rules. %s", err)
            named_metric = None

        if named_metric:
            path = '%s/%s' % (tracker_type, self.url_encode(named_metric))
            return path

        uri_params_captured = self._settings.web_action_uri_params_captured.get(self.request_uri, '')
        if self.request_uri in self._settings.web_action_uri_params_captured:
            match_param = ''
            for actual_param in self.request_params:
                if actual_param in uri_params_captured:
                    match_param += "&%s=%s" % (actual_param, self.request_params[actual_param])
            match_param = match_param.replace("&", "?", 1)
            self.request_uri = "%s%s" % (self.request_uri, match_param)

        if not self._settings.auto_action_naming:
            path = "%s/%s%s" % (tracker_type, self.framework, self.url_encode(self.request_uri))
        else:
            path = '%s/%s/%s' % (tracker_type, self.framework, name)

        return path

    def url_encode(self, uri):
        encoded_url = "/index"
        if not uri or uri == "/":
            return encoded_url

        # drop the uri first /
        encoded_url = uri.replace("/", "%2F")

        return encoded_url

    def merge_urls(self, url):
        if not self.settings.urls_merge or self.settings.auto_action_naming:
            return url

        def is_digit(world):
            if str(world).isdigit():
                return '*'

            return world

        url_re = '/'.join([is_digit(s) for s in url.split('/')])
        url_segments = []
        pre_is_digit = False
        is_param = False

        for s in str(url_re):
            # skip the query parameters
            if s == "?":
                is_param = True

            if is_param:
                url_segments.append(s)
                continue

            # current and the last is digit. replace it.
            if str(s).isdigit() and pre_is_digit:
                url_segments[-1] = '*'

            elif str(s).isdigit() and not pre_is_digit:
                pre_is_digit = True
                url_segments.append(s)

            else:
                url_segments.append(s)
                pre_is_digit = False

        return ''.join(url_segments)

    def set_tracker_name(self, name, group="Function", priority=None):
        if priority is None:
            return

        if priority is not None and priority < self._priority:
            return

        if isinstance(name, bytes):
            name = name.decode('Latin-1')

        self._priority = priority
        self._group = group
        self._name = name

    def save_tracker(self):
        knapsack().save_tracker(self)

    def drop_tracker(self):
        if not self.enabled:
            return self

        knapsack().drop_tracker(self)

    def process_database_node(self, node):
        if type(node) is not DatabaseNode:
            return

        if not self._settings.action_tracer.enabled:
            return

        if not self._settings.action_tracer.slow_sql:
            return

        if self._settings.action_tracer.record_sql == 'off':
            return

        if node.duration < self._settings.action_tracer.slow_sql_threshold:
            return

        self._slow_sql_nodes.append(node)

    def push_node(self, node):
        self.trace_node.append(node)

    def pop_node(self, node):
        last = self.trace_node.pop()
        assert last == node
        parent = self.trace_node[-1]

        return parent

    def current_node(self):
        if self.trace_node:
            return self.trace_node[-1]

    def is_uri_captured(self, uri):
        # capture all url
        if not self._settings.urls_captured:
            return True

        for p in self._settings.urls_captured:
            if p and p.match(uri):
                return True

        return False

    def filter_params(self, params):
        result = {}

        if not params:
            return result

        if not self._settings.action_tracer.enabled or not self._settings.capture_params:
            return result

        for key in params:
            if key not in self._settings.ignored_params:
                result[key] = params[key]

        return result

    @property
    def name(self):
        return self._name

    @property
    def group(self):
        return self._group

    @property
    def settings(self):
        return self._settings

    @property
    def duration(self):
        if not self.end_time:
            self.end_time = time.time()

        return int((self.end_time - self.start_time) * 1000)

    def generate_trace_guid(self):
        duration = self.duration
        if duration < self.settings.action_tracer.stack_trace_threshold:
            return ""

        if self._trace_guid:
            return self._trace_guid

        guid = '%s%s' % (time.time(), random.random())
        guid = guid.replace('.', '')
        self._trace_guid = guid[:30]
        return self._trace_guid

    def generate_trace_id(self):
        if self._trace_id:
            return self._trace_id

        trace_id = '%s%s' % (time.time(), random.random())
        trace_id = trace_id.replace('.', '')
        self._trace_id = trace_id[:16]
        return self._trace_id

    @property
    def queque_time(self):
        if not self._queque_time:
            _queque_time = int(self.start_time * 1000.0 - self.queque_start)
            self._queque_time = _queque_time if _queque_time > 0 and self.queque_start != 0 else 0

        return self._queque_time


def current_tracker():
    return knapsack().current_tracker()
