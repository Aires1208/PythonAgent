# -*- coding: utf-8 -*-

import json
import logging

from collections import namedtuple
from ssa.logistics.attribution import TimeMetric, ApdexMetric, TracedError, node_start_time, node_end_time
from ssa.logistics.attribution import TracedExternalError


console = logging.getLogger(__name__)
_TrackerNode = namedtuple('_TrackerNode', ['type', 'group', 'name', 'start_time', 'end_time', 'request_uri',
                                           'duration', 'http_status', 'exclusive', 'children', 'path', "errors",
                                           "apdex_t", "request_params", "custom_params", "thread_name", "trace_data",
                                           "referer", "slow_sql", "queque_time", "trace_guid", 'trace_id',
                                           "external_error"])


class TrackerNode(_TrackerNode):

    def time_metrics(self):
        print("TrackerNode")
        yield TimeMetric(name=self.path, scope=self.path, duration=self.duration, exclusive=self.exclusive)

        queque_metric = 'GENERAL/WebFrontend/NULL/QueueTime'
        # FIMXE sunyan: ignore GENERAL right now.
        #print("TrackerNode:name:{0},scope:{1}".format(queque_metric, queque_metric))
        yield TimeMetric(name=queque_metric, scope=queque_metric, duration=self.queque_time, exclusive=self.queque_time)

        for child in self.children:
            for metric in child.time_metrics(self, self):
                yield metric

    def action_metrics(self):
        if self.type != "WebAction":
            return

        print("TrackerNode")
        yield TimeMetric(name=self.path, scope="", duration=self.duration, exclusive=self.exclusive)

    def apdex_metrics(self):
        if self.type != "WebAction":
            console.debug("get apdex with none webaction %s", self.type)
            return

        satisfying = 0
        tolerating = 0
        frustrating = 0

        if self.errors:
            frustrating = 1
        else:
            if self.duration <= self.apdex_t:
                satisfying = 1
            elif self.duration <= 4 * self.apdex_t:
                tolerating = 1
            else:
                frustrating = 1

        name = self.path.replace("WebAction", "Apdex")
        print("TrackerNode")
        yield ApdexMetric(name=name, satisfying=satisfying, tolerating=tolerating, frustrating=frustrating,
                          apdex_t=self.apdex_t)

    def traced_error(self):
        for error in self.errors:
            error_item = [error.error_time, self.path, error.http_status or 500, error.error_class_name, error.message,
                          1, self.request_uri.replace("%2F", "/")]
            stack_detail = []
            for line in error.stack_trace:
                if len(line) >= 4 and 'tingyun' not in line[0]:
                    stack_detail.append("%s(%s:%s)" % (line[2], line[0], line[1]))

            error_params = {"params": {"threadName": error.thread_name, "httpStatus": error.http_status,
                                       "referer": error.referer},
                            "requestParams": error.request_params,
                            "stacktrace": stack_detail
                            }

            error_item.append(json.dumps(error_params))

            error_filter_key = "%s_|%s_|%s_|%s" % (self.request_uri, error.http_status,
                                                   error.error_class_name, error.message)
            yield TracedError(error_filter_key=error_filter_key, tracker_type=error.tracker_type, trace_data=error_item)

    def trace_node(self, root):
        start_time = node_start_time(root, self)
        end_time = node_end_time(root, self)
        metric_name = self.path
        call_url = self.request_uri.replace("%2F", "/")
        call_count = 1
        class_name = ""
        method_name = self.name
        params = {}
        children = []

        root.trace_node_count += 1
        for child in self.children:
            if root.trace_node_count > root.trace_node_limit:
                break

            children.append(child.trace_node(root))

        return [start_time, end_time, metric_name, call_url, call_count, class_name, method_name, params, children]

    def slow_action_trace(self, limit, threshold):
        self.trace_node_limit = limit
        self.trace_node_count = 0
        start_time = int(self.start_time)
        duration = self.duration
        trace_id = self.trace_id if self.trace_id else ""
        # not a bug. the trace id indicate it is caller or called with cross trace, if this app is only called, this
        # should be empty
        trace_guid = self.trace_guid if self.trace_id else ""

        # if trace data has the tr attribute, the called has the slow action trace.
        action_trace_invoke = False
        if self.trace_data and self.trace_data.get("tr", False):
            action_trace_invoke = True

        # intercept the illegal data. before access the trace node(spend more sources)
        # now we return the original data with empty trace data. the next step will detect the duration value is less
        # than settings threshold.
        if duration < threshold and not action_trace_invoke:
            return [start_time, duration, self.path, self.request_uri, ""]

        trace_node = self.trace_node(self)
        slow_trace = [start_time, self.request_params, {"httpStatus": self.http_status, "threadName": self.thread_name,
                                                        "referer": self.referer}, trace_node]

        return [start_time, duration, self.path, self.request_uri.replace("%2F", "/"), json.dumps(slow_trace),
                trace_id, trace_guid]

    def slow_sql_nodes(self):
        for item in self.slow_sql:
            yield item.slow_sql_node(self)

    def traced_external_error(self):
        for error in self.external_error:
            metric_name = 'External/%s/%s' % (error.url.replace("/", "%2F"), self.request_uri)
            error_item = [error.error_time, metric_name, error.status_code,
                          error.error_class_name, 1, self.path]

            stack_detail = []
            for line in error.stack_trace:
                if len(line) >= 4 and 'tingyun' not in line[0]:
                    stack_detail.append("%s(%s:%s)" % (line[2], line[0], line[1]))

            error_params = {"params": {"threadName": error.thread_name, "httpStatus": error.http_status or 500},
                            "requestParams": error.request_params, "stacktrace": stack_detail}
            error_item.append(json.dumps(error_params))

            error_filter_key = "%s_|%s_|%s" % (metric_name, error.status_code, error.error_class_name)
            yield TracedExternalError(error_filter_key=error_filter_key, trace_data=error_item,
                                      tracker_type=error.tracker_type, status_code=error.status_code)

    def __str__(self):
        """
        m = {
            "type": self.type,
            "group": self.group,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "request_uri": self.request_uri,
            "duration": self.duration,
            "thread_name": self.thread_name,
            "http_status": self.http_status,
            "exclusive": self.exclusive,
            "children": self.children,
            "path": self.path,
            "errors": self.errors,
            "apdex_t": self.apdex_t,
            "queque_time": self.queque_time,
            "custom_params": self.custom_params,
            "request_params": self.request_params,
            "trace_id": self.trace_id,
            "referer": self.referer,
            "slow_sql": self.slow_sql,
            "trace_guid": self.trace_guid,
            "trace_data": self.trace_data,
            "external_error": self.external_error
        }
        return json.dumps(m, indent=4, sort_keys=False)
        """
        lines = []
        lines.append(">>>--------------------------------------------------------")
        lines.append("type          :%s" % self.type)
        lines.append("group         :%s" % self.group)
        lines.append("name          :%s" % self.name)
        lines.append("start_time    :%s" % self.start_time)
        lines.append("end_time      :%s" % self.end_time)
        lines.append("request_uri   :%s" % self.request_uri)
        lines.append("duration      :%s" % self.duration)
        lines.append("thread_name   :%s" % self.thread_name)
        lines.append("http_status   :%s" % self.http_status)
        lines.append("exclusive     :%s" % self.exclusive)
        lines.append("children      :[%s]" % len(self.children))
        for child in self.children:
            lines.append(str(child))
        lines.append("path          :%s" % self.path)
        lines.append("errors        :%s" % self.errors)
        lines.append("apdex_t       :%s" % self.apdex_t)
        lines.append("queque_time   :%s" % self.queque_time)
        lines.append("custome_params:%s" % self.custom_params)
        lines.append("request_params:%s" % self.request_params)
        lines.append("trace_id      :%s" % self.trace_id)
        lines.append("referer       :%s" % self.referer)
        lines.append("slow_sql      :%s" % self.slow_sql)
        lines.append("trace_guid    :%s" % self.trace_guid)
        lines.append("trace_data    :%s" % self.trace_data)
        lines.append("external_error:%s" % self.external_error)
        lines.append("<<<--------------------------------------------------------")
        return '\r\n'.join(lines)
