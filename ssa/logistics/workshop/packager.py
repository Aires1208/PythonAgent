# -*- coding: utf-8 -*-

import copy
import logging
import threading
from ssa.logistics.workshop.packets import TimePackets, ApdexPackets, SlowSqlPackets
from ssa.packages import six


console = logging.getLogger(__name__)


class Packager(object):

    def __init__(self):
        self.__max_error_count = 10
        self.__settings = None

        self.__time_packets = {}  # store time packets data key is name + scope
        self.__apdex_packets = {}
        self.__action_packets = {}
        self.__general_packets = {}
        # it's maybe include {name: {trackerType, count, $ERROR_ITEM}}
        # $ERROR_ITEM detail, check the documentation
        self.__traced_errors = {}

        # it's maybe include {name: {count, $ERROR_ITEM}}
        # $ERROR_ITEM detail, check the documentation
        self.__traced_external_errors = {}

        # format: {$"metric_name": [$slow_action_data, $duration]}
        self.__slow_action = {}
        self.__slow_sql_packets = {}

        self._packets_lock = threading.Lock()

    @property
    def settings(self):
        return self.__settings

    def create_data_zone(self):
        zone = Packager()
        zone.__settings = self.__settings
        return zone

    def reset_packets(self, application_settings):
        self.__settings = application_settings

        self.__time_packets = {}
        self.__apdex_packets = {}
        self.__action_packets = {}
        self.__general_packets = {}
        self.__traced_errors = {}
        self.__traced_external_errors = {}
        self.__slow_action = {}
        self.__slow_sql_packets = {}

    def record_tracker(self, tracker):
        if not self.__settings:
            console.error("The application settings is not merge into data engine.")
            return

        node_limit = self.__settings.action_tracer_nodes  # FIXME sunyan type mistakes: self.__settings.action_tracer_ndoes
        threshold = self.__settings.action_tracer.action_threshold

        print("tracker.time_metrics()   ===>")
        self.record_time_metrics(tracker.time_metrics())      # deal for component, include framework/db/other
        print("tracker.time_metrics()   <===")

        print("tracker.action_metrics() ===>")
        self.record_action_metrics(tracker.action_metrics())  # deal for user action
        print("tracker.action_metrics() <===")

        print("tracker.apdex_metrics()  ===>")
        self.record_apdex_metrics(tracker.apdex_metrics())    # for recording the apdex
        print("tracker.apdex_metrics()  <===")

        print("tracker.traced_error()   ===>")
        self.record_traced_errors(tracker.traced_error())     # for error trace detail
        print("tracker.traced_error()   <===")

        print("tracker.slow_action_trace()     ===>")
        self.record_slow_action(tracker.slow_action_trace(node_limit, threshold))
        print("tracker.slow_action_trace()     <===")

        print("tracker.slow_sql_nodes()        ===>")
        self.record_slow_sql(tracker.slow_sql_nodes())
        print("tracker.slow_sql_nodes()        <===")

        print("tracker.traced_external_error() ===>")
        self.record_traced_external_trace(tracker.traced_external_error())
        print("tracker.traced_external_error() <===")

    ####################################################################################################################

    def record_time_metrics(self, metrics):
        for metric in metrics:
            self.record_time_metric(metric)

    def record_time_metric(self, metric):
        # filter the general data from the metric, the metric node should be distinguish general and basic metric
        if metric.name.startswith("GENERAL"):
            self.record_general_metric(metric)
            return

        key = (metric.name, metric.scope or '')  # metric key for protocol
        packets = self.__time_packets.get(key)
        if packets is None:
            packets = TimePackets()

        packets.merge_time_metric(metric)
        print("k:{0},v:{1}".format(key, packets))
        self.__time_packets[key] = packets

        return key

    def record_general_metric(self, metric):
        key = (metric.name.split("/", 1)[1], '')
        packets = self.__general_packets.get(key)
        if packets is None:
            packets = TimePackets()

        packets.merge_time_metric(metric)
        self.__general_packets[key] = packets

        return key

    ####################################################################################################################

    def record_action_metrics(self, metrics):
        for metric in metrics:
            self.record_action_metric(metric)

    def record_action_metric(self, metric):
        key = (metric.name, metric.scope or '')  # metric key for protocol
        packets = self.__action_packets.get(key)
        if packets is None:  # FIXME sunyan type mistakes: if packets in None:
            packets = TimePackets()

        packets.merge_time_metric(metric)
        print("k:{0},v:{1}".format(key, packets))
        self.__action_packets[key] = packets

        return key

    ####################################################################################################################

    def record_apdex_metrics(self, metrics):
        for metric in metrics:
            self.record_apdex_metric(metric)

    def record_apdex_metric(self, metric):
        key = (metric.name, "")
        packets = self.__apdex_packets.get(key)

        if packets is None:
            packets = ApdexPackets(apdex_t=metric.apdex_t)

        packets.merge_apdex_metric(metric)
        print("k:{0},v:{1}".format(key, packets))
        self.__apdex_packets[key] = packets
        return key

    ####################################################################################################################

    def record_traced_errors(self, traced_errors):
        if not self.__settings.error_collector.enabled:
            return

        for error in traced_errors:
            if len(self.__traced_errors) > self.__max_error_count:
                console.debug("Error trace is reached maximum limitation")
                break

            if error.error_filter_key in self.__traced_errors:
                self.__traced_errors[error.error_filter_key]["count"] += 1
                self.__traced_errors[error.error_filter_key]["item"][-3] += 1
            else:
                self.__traced_errors[error.error_filter_key] = {
                    "count": 1,
                    "item": error.trace_data,
                    "tracker_type": error.tracker_type
                }

    ####################################################################################################################

    def record_slow_action(self, slow_action):
        if not self.__settings.action_tracer.enabled:
            return

        threshold = self.__settings.action_tracer.action_threshold
        if threshold > slow_action[1]:
            return

        top_n = self.__settings.action_tracer.top_n
        metric_name = slow_action[2]

        if metric_name not in self.__slow_action:
            self.__slow_action[metric_name] = [[slow_action, slow_action[1]]]
        else:
            # every request url/metric can save top_n action trace.
            if len(self.__slow_action[metric_name]) <= top_n:
                self.__slow_action[metric_name].append([slow_action, slow_action[1]])

    ####################################################################################################################

    def record_slow_sql(self, nodes):
        if not self.__settings.action_tracer.slow_sql:
            return

        for node in nodes:
            key = node.identifier
            packets = self.__slow_sql_packets.get(key)
            if not packets and len(self.__slow_sql_packets) < self.__settings.slow_sql_count:
                packets = SlowSqlPackets()
                self.__slow_sql_packets[key] = packets

            if packets:
                packets.merge_slow_sql_node(node)

    ####################################################################################################################

    def record_traced_external_trace(self, traced_errors):
        if not self.__settings.error_collector.enabled:
            return

        for error in traced_errors:
            if len(self.__traced_external_errors) > self.__max_error_count:
                console.debug("External error trace is reached maximum limitation.")
                break

            if error.error_filter_key in self.__traced_external_errors:
                self.__traced_external_errors[error.error_filter_key]["count"] += 1
                self.__traced_external_errors[error.error_filter_key]["item"][-3] += 1
            else:
                self.__traced_external_errors[error.error_filter_key] = {
                    "count": 1,
                    "status_code": error.status_code,
                    "item": error.trace_data,
                    "tracker_type": error.tracker_type
                }

    ####################################################################################################################

    def rollback(self, stat, merge_performance=True):
        if not merge_performance:
            return

        console.warning("Agent will rollback the data which is captured at last time. That indicates your network is broken.")

        for key, value in six.iteritems(stat.__time_packets):
            packets = self.__time_packets.get(key)
            if not packets:
                self.__time_packets[key] = copy.copy(value)
            else:
                packets.merge_packets(value)

        for key, value in six.iteritems(stat.__apdex_packets):
            packets = self.__apdex_packets.get(key)
            if not packets:
                self.__apdex_packets[key] = copy.copy(value)
            else:
                packets.merge_packets(value)

        for key, value in six.iteritems(stat.__action_packets):
            packets = self.__action_packets.get(key)
            if not packets:
                self.__action_packets[key] = copy.copy(value)
            else:
                packets.merge_packets(value)

        for key, value in six.iteritems(stat.__general_packets):
            packets = self.__general_packets.get(key)
            if not packets:
                self.__general_packets[key] = copy.copy(value)
            else:
                packets.merge_packets(value)

        for key, value in six.iteritems(stat.__traced_errors):
            packets = self.__traced_errors.get(key)
            if not packets:
                self.__traced_errors[key] = copy.copy(value)
            else:
                packets["count"] += value["count"]

        for key, value in six.iteritems(stat.__traced_external_errors):
            packets = self.__traced_external_errors.get(key)
            if not packets:
                self.__traced_external_errors[key] = copy.copy(value)
            else:
                packets["count"] += value["count"]

    def merge_metric_packets(self, snapshot):

        for key, value in six.iteritems(snapshot.__time_packets):
            packets = self.__time_packets.get(key)
            if not packets:
                self.__time_packets[key] = copy.copy(value)
            else:
                packets.merge_packets(value)

        for key, value in six.iteritems(snapshot.__apdex_packets):
            packets = self.__apdex_packets.get(key)
            if not packets:
                self.__apdex_packets[key] = copy.copy(value)
            else:
                packets.merge_packets(value)

        for key, value in six.iteritems(snapshot.__action_packets):
            packets = self.__action_packets.get(key)
            if not packets:
                self.__action_packets[key] = copy.copy(value)
            else:
                packets.merge_packets(value)

        # TODO: think more about the background task
        for key, value in six.iteritems(snapshot.__traced_errors):
            packets = self.__traced_errors.get(key)
            if not packets:
                self.__traced_errors[key] = copy.copy(value)
            else:
                packets["item"][-3] += value["count"]

        for key, value in six.iteritems(snapshot.__traced_external_errors):
            packets = self.__traced_external_errors.get(key)
            if not packets:
                self.__traced_external_errors[key] = copy.copy(value)
            else:
                packets["item"][-3] += value["count"]

        # generate general data
        for key, value in six.iteritems(snapshot.__general_packets):
            packets = self.__general_packets.get(key)
            if not packets:
                self.__general_packets[key] = copy.copy(value)
            else:
                packets.merge_packets(value)

        # for action trace
        top_n = self.__settings.action_tracer.top_n
        for key, value in six.iteritems(snapshot.__slow_action):
            if key not in self.__slow_action:
                self.__slow_action[key] = value
                break

            slow_actions = self.__slow_action.get(key)
            # although the target action trace value is `list`, but it only has 1 element in one metric.
            if len(slow_actions) > top_n:
                console.debug("The action trace is reach the top(%s), action(%s) is ignored.", top_n, key)
                break
            slow_actions.extend(value)

        # for slow sql
        max_sql = self.__settings.slow_sql_count
        for key, value in six.iteritems(snapshot.__slow_sql_packets):
            if len(self.__slow_sql_packets) > max_sql:
                console.debug("the slow sql trace count is reach the top.")

            slow_sql = self.__slow_sql_packets.get(key)
            if not slow_sql:
                self.__slow_sql_packets[key] = value
            else:
                if value.slow_sql_node.duration > slow_sql.slow_sql_node.duration:
                    self.__slow_sql_packets[key] = value

    def reset_metric_packets(self):
        self.__time_packets = {}
        self.__apdex_packets = {}
        self.__action_packets = {}
        self.__general_packets = {}

        self.__traced_errors = {}
        self.__traced_external_errors = {}
        self.__slow_action = {}
        self.__slow_sql_packets = {}

    def packets_snapshot(self):
        stat = copy.copy(self)

        self.__time_packets = {}
        self.__action_packets = {}
        self.__apdex_packets = {}
        self.__traced_errors = {}
        self.__traced_external_errors = {}
        self.__general_packets = {}
        self.__slow_action = {}
        self.__slow_sql_packets = {}

        return stat

    def component_metrics(self, metric_name_ids):
        result = []
        for key, value in six.iteritems(self.__time_packets):
            extend_metrics = key[0].split("|")
            if len(extend_metrics) == 1:
                upload_key = {
                    "name": key[0],
                    "parent": key[1]
                }
                upload_key_str = '%s:%s' % (key[0], key[1])
                upload_key = upload_key if upload_key_str not in metric_name_ids else metric_name_ids[upload_key_str]
                result.append([upload_key, value])
            elif len(extend_metrics) == 3:
                upload_key = {
                    "name": extend_metrics[0],
                    "parent": key[1],
                    "calleeId": extend_metrics[1],
                    "calleeName": extend_metrics[2]
                }
                result.append([upload_key, value])
        return result

    def apdex_data(self, metric_name_ids):
        result = []
        for key, value in six.iteritems(self.__apdex_packets):
            upload_key = {
                "name": key[0]
            }
            upload_key_str = '%s' % key[0]
            upload_key = upload_key if upload_key_str not in metric_name_ids else metric_name_ids[upload_key_str]
            result.append([upload_key, value])
        return result

    def action_metrics(self, metric_name_ids):
        result = []
        for key, value in six.iteritems(self.__action_packets):
            upload_key = {
                "name": key[0]
            }
            upload_key_str = '%s' % key[0]
            upload_key = upload_key if upload_key_str not in metric_name_ids else metric_name_ids[upload_key_str]
            result.append([upload_key, value])
        return result

    def error_packets(self, metric_name_ids):
        external_error, web_action_error = 'External', 'WebAction'
        error_types = [external_error, web_action_error]
        error_count = {
            "Errors/Count/All": 0,
            "Errors/Count/AllWeb": 0,
            "Errors/Count/AllBackground": 0
        }

        def parse_error_trace(traced_data):
            for error_filter_key, error in six.iteritems(traced_data):
                error_count["Errors/Count/All"] += error["count"]

                if error["tracker_type"] in error_types:
                    error_count["Errors/Count/AllWeb"] += error["count"]

                    action_key = "Errors/Count/%s" % error_filter_key.split("_|")[0]
                    if action_key not in error_count:
                        error_count[action_key] = error["count"]
                    else:
                        error_count[action_key] += error["count"]

                    if error["tracker_type"] == external_error:
                        action_key = "Errors/Type:%s/%s" % (error["status_code"], error_filter_key.split("_|")[0])
                        if action_key not in error_count:
                            error_count[action_key] = error["count"]
                        else:
                            error_count[action_key] += error["count"]
                else:
                    error_count["Errors/Count/AllBackground"] += 1

        parse_error_trace(self.__traced_errors)
        parse_error_trace(self.__traced_external_errors)

        stat_value = []
        for key, value in six.iteritems(error_count):
            upload_key = {"name": key}
            upload_key_str = '%s' % key
            upload_key = upload_key if upload_key_str not in metric_name_ids else metric_name_ids[upload_key_str]
            stat_value.append([upload_key, [value]])

        return stat_value

    # stat for error trace data
    # reply to the basic error trace data structure
    def error_trace_data(self):
        return [error["item"] for error in six.itervalues(self.__traced_errors)]

    def external_error_data(self):
        return [error["item"] for error in six.itervalues(self.__traced_external_errors)]

    def general_trace_metric(self, metric_name_ids):
        result = []
        for key, value in six.iteritems(self.__general_packets):
            extend_keys = key[0].split("|")
            if len(extend_keys) == 1:
                upload_key = {"name": key[0]}
                upload_key_str = '%s' % key[0]
                upload_key = upload_key if upload_key_str not in metric_name_ids else metric_name_ids[upload_key_str]
                result.append([upload_key, value])
            elif len(extend_keys) == 3:
                # do not replace the metric with id.
                upload_key = {"name": extend_keys[0], "calleeId": extend_keys[1], "calleeName": extend_keys[2]}
                result.append([upload_key, value])

        return result

    def action_trace_data(self):
        if not self.__slow_action:
            return []

        trace_data = []

        for traces in six.itervalues(self.__slow_action):
            for trace in traces:
                trace_data.append(trace[0])

        return {
            "type": "actionTraceData",
            "actionTraces": trace_data
        }

    def slow_sql_data(self):
        if not self.__slow_sql_packets:
            return []

        result = {
            "type": "sqlTraceData",
            "sqlTraces": []
        }
        maximum = self.__settings.slow_sql_count
        slow_sql_nodes = sorted(six.itervalues(self.__slow_sql_packets), key=lambda x: x.max_call_time)[-maximum:]

        for node in slow_sql_nodes:
            explain_plan = node.slow_sql_node.explain_plan
            params = {
                "explainPlan": explain_plan if explain_plan else {},
                "stacktrace": []
            }

            if node.slow_sql_node.stack_trace:
                for line in node.slow_sql_node.stack_trace:
                    if len(line) >= 4 and 'tingyun' not in line[0]:
                        params['stacktrace'].append("%s(%s:%s)" % (line[2], line[0], line[1]))

            result['sqlTraces'].append([
                node.slow_sql_node.start_time, node.slow_sql_node.path,
                node.slow_sql_node.metric, node.slow_sql_node.request_uri,
                node.slow_sql_node.formatted, node.call_count,
                node.total_call_time, node.max_call_time,
                node.min_call_time, str(params)
            ])

        return result
