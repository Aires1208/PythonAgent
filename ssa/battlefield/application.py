# -*- coding:utf-8 -*-

"""This module implements data recording and reporting for an application

"""

import logging
import threading
import time
import sys

from ssa.logistics.transportation.engine import create_connection
from ssa.logistics.workshop.packager import Packager
from ssa.armoury.sampler.environment import env_config

from ssa.armoury.sampler.sampler import SamplerController
from ssa.logistics.exceptions import InvalidLicenseException, OutOfDateConfigException, InvalidDataTokenException
from ssa.logistics.exceptions import RetryDataForRequest, DiscardDataForRequest, ServerIsUnavailable
from ssa.config.settings import global_settings
from ssa.packages.wrapt.decorators import synchronized
from ssa.logistics.mapper import CONSTANCE_OUT_DATE_CONFIG, CONSTANCE_RETRY_DATA, CONSTANCE_SERVER_UNAVAILABLE
from ssa.logistics.mapper import CONSTANCE_DISCARD_DATA, CONSTANCE_HARVEST_ERROR, CONSTANCE_INVALID_DATA_TOKEN
from ssa.logistics.mapper import CONSTANCE_LICENSE_INVALID, CONSTANCE_SESSION_NOT_ACTIVED
from ssa.logistics.mapper import CONSTANCE_INVALID_LICENSE_KEY, MAX_RETRY_UPLOAD_FAILED_TIMES


console = logging.getLogger(__name__)


class Application(object):
    """Real web application property/action/dispatcher holder/controller
    """
    def __init__(self, app_name, linked_app=[]):
        console.info("Init Application with name %s, linked-name %s", app_name, linked_app)

        # if retry upload data failed. will not rollback the data and reset the session
        self.retry_upload_times = 0

        self._app_name = app_name
        self._linked_app = sorted(set(linked_app))
        self._active_session = None
        self.connect_thread = None
        self._is_license_valid = True

        self.sampler = []

        self.connect_retry_time = 60.0
        self._connect_event = threading.Event()
        self._packets_lock = threading.Lock()  # used to lock the core collect data
        self._packager = Packager()

        self._agent_commands_lock = threading.Lock()
        #self.profile_manager = get_profile_manger()
        #self.profile_status = False

        self.__max_tracker = 2000
        self._tracker_count = 0
        self._last_tracker = 0.0
        self.__data_sampler = []
        self.metric_name_ids = {"actions": {}, "apdex": {}, "components": {}, "general": {}, "errors": {}}

    @property
    def active(self):
        return self._active_session is not None

    @property
    def application_config(self):
        return self._active_session and self._active_session.config

    def stop_connecting(self):
        self._connect_event.set()

    def shutdown_internal_service(self):
        #self.profile_manager.shutdown()
        self.stop_sampler()

    def activate_session(self):
        """active a session(background thread) to register the application
        :return:
        """
        # TODO: do some check for agent status
        if self.connect_thread and self.connect_thread.is_alive():
            console.warning("Activate thread is active. maybe something wrong when dispatcher activate application.")
            return False

        self._connect_event.clear()

        self.connect_thread = threading.Thread(target=self.connect_to_headquarters, name="ssaSessionThread")
        self.connect_thread.setDaemon(True)
        self.connect_thread.start()

        return True

    def connect_to_headquarters(self):
        """Performs the actual registration of the application to server, get server config and set the current app settings.
        :return:
        """
        # ensure the main thread get to run first
        time.sleep(0.01)

        while not self._active_session:
            self.retry_upload_times = 0
            settings = global_settings()

            try:
                active_session = create_connection(None, self._app_name, self._linked_app, env_config(), settings)
            except InvalidLicenseException as _:
                console.warning("Invalid license in configuration, agent will stop to work please fix license and"
                                "restart agent again")

                self._is_license_valid = False
                self._connect_event.wait(self.connect_retry_time)
                continue
            except Exception:
                # use the harvest controller signal to control the connection
                console.exception("Connect to agent server failed, Connection will try again in 1 min.")
                self._connect_event.wait(self.connect_retry_time)
                continue
            finally:
                if self._connect_event.isSet():
                    console.info("Agent is shutting down, stop the connection to server now.")
                    return

            if active_session:
                self._is_license_valid = True
                self._connect_event.set()
                self.start_sampler()

                # set the application settings to data engine
                with self._packets_lock:
                    self._active_session = active_session
                    self._packager.reset_packets(self._active_session.config)

    def register_data_sampler(self, sampler, *args):
        # sunyan
        self.__data_sampler.append(SamplerController(sampler, args))

    @synchronized
    def start_sampler(self):
        for sampler in self.__data_sampler:
            try:
                console.debug("Starting data sampler in  %s", self._app_name)
                sampler.start()
            except Exception as err:
                console.exception("Exception occurred %s, when start sampler ", err, sampler.name)

    @synchronized
    def stop_sampler(self):
        for sampler in self.__data_sampler:
            try:
                sampler.stop()
            except Exception as err:
                console.exception("Exception occurred %s, when stop sampler ", err, sampler.name)

    def harvest(self, last_harvest, current_harvest, shutdown=False):
        ret_code = 0

        if not self._active_session:
            console.warning("Application not registered to server yet, skip harvest data.")
            return CONSTANCE_SESSION_NOT_ACTIVED, self._app_name, self._linked_app

        if not self._is_license_valid:
            console.debug("The license is invalid, skip harvest data.")
            return CONSTANCE_LICENSE_INVALID, self._app_name, self._linked_app

        with self._packets_lock:
            self._tracker_count = 0
            self._last_tracker = 0.0
            stat = self._packager.packets_snapshot()

        config = self.application_config

        for sampler in self.__data_sampler:
            if not config.enabled:
                break

            try:
                for metric_list in sampler.metrics(current_harvest - last_harvest):
                    stat.record_time_metrics(metric_list)
            except Exception as err:
                console.exception("Sample the data occurred errors. %s", err)

        try:
            # send metric data even if disabled by server
            performance_metric = self.get_performance_metric(stat, last_harvest, current_harvest, config.audit_mode)
            if config.audit_mode:
                console.info("Agent capture the performance data %s", performance_metric)

            print("sunyan=>send_performance_metric")
            result = self._active_session.send_performance_metric(performance_metric)

            # is application is disabled by server. send empty data and ignore all of other data. even if it is not
            # captured.
            if not config.enabled:
                stat.reset_metric_packets()
                return

            self.process_metric_id(result, config.daemon_debug)

            if config.error_collector.enabled:
                error_trace = self.get_error_trace_data(stat)
                print("sunyan=>send_error_trace")
                self._active_session.send_error_trace(error_trace)

                external_error_trace = self.get_external_error_trace(stat)
                print("sunyan=>send_external_error_trace")
                self._active_session.send_external_error_trace(external_error_trace)

                if config.audit_mode:
                    console.info("Agent capture the error trace data %s", error_trace)
                    console.info("Agent capture the external error trace data %s", external_error_trace)

            if config.action_tracer.enabled:
                slow_action_data = stat.action_trace_data()
                print("sunyan=>send_action_trace")
                self._active_session.send_action_trace(slow_action_data)

                if config.audit_mode:
                    console.info("Agent capture the slow action data %s", slow_action_data)

            if config.action_tracer.slow_sql:
                slow_sql_data = stat.slow_sql_data()
                print("sunyan=>send_sql_trace")
                self._active_session.send_sql_trace(slow_sql_data)

                if config.audit_mode:
                    console.info("Agent capture the slow sql data %s", slow_sql_data)

            stat.reset_metric_packets()

            # get the commands and execute it.
            self.process_headquarters_command()
            self.send_profile_data(config.audit_mode)

            if shutdown:
                self.shutdown_internal_service()
        except OutOfDateConfigException as _:
            # need to reset the connection
            self._active_session = None
            ret_code = CONSTANCE_OUT_DATE_CONFIG
            print("sunyan=>Config changed in server, reset the connect now.")
            console.info("Config changed in server, reset the connect now.")
        except InvalidDataTokenException as _:
            # if license key when upload the data ,then reset the session
            self._active_session = None
            ret_code = CONSTANCE_INVALID_DATA_TOKEN
            print("sunyan=>Data token is valid, register the application %s again now" % self._app_name)
            console.info("Data token is valid, register the application %s again now", self._app_name)
        except InvalidLicenseException as _:
            # if invalid license error occurred when upload data. current data will be lost. And dispatcher will reset
            # session.
            self._active_session = None
            ret_code = CONSTANCE_INVALID_LICENSE_KEY
            print("sunyan=>InvalidLicenseException")
        except RetryDataForRequest as _:
            print("sunyan=>RetryDataForRequest")
            console.warning("This exception indicates server service can not touched. if this error continues. please "
                            "report to us for further investigation. thank u")

            # if upload try times more than max, reset the session and raise invalid data token, thant will trigger
            # reconnection to data collector. This will avoid some issue for memory use because of data rollback.
            ret_code = CONSTANCE_RETRY_DATA
            if self.retry_upload_times >= MAX_RETRY_UPLOAD_FAILED_TIMES:
                self._active_session = None
                ret_code = CONSTANCE_INVALID_DATA_TOKEN

                print("sunyan=>Upload data to the dc failed with max retry %s" % self.retry_upload_times)
                console.warning("Upload data to the dc failed with max retry %s", self.retry_upload_times)
            else:
                self.retry_upload_times += 1
                with self._packets_lock:
                    try:
                        print("sunyan=>rollback")
                        self._packager.rollback(stat)
                    except Exception as err:
                        console.warning("rollback(%s) performance data failed. %s", self.retry_upload_times, err)

        except Exception as err:
            ret_code = CONSTANCE_HARVEST_ERROR

            console.exception("Some error occurred in agent code. if this error continues. "
                              "please report to us for further investigation. thank u.")
            console.exception("%s", err)

        return ret_code, self._app_name, self._linked_app

    def record_tracker(self, tracker):

        if not self._active_session or not self._packager.settings:
            console.debug("Agent server is disconnected, tracker data will be dropped.")
            return False

        try:
            stat = self._packager.create_data_zone()

            # sunyan
            print(str(tracker))
            stat.record_tracker(tracker)

            self._tracker_count += 1
            print("tracker_count:%s" % str(self._tracker_count))
            self._last_tracker = tracker.end_time

            with self._packets_lock:
                self._packager.merge_metric_packets(stat)
        except Exception as err:
            console.exception("Unexpected error occurred when record tracker data, that's maybe the agent code issue "
                              "if this continues, please report to us for further investigation. %s", err)

        return False

    def process_metric_id(self, metric_ids, debug_mode=False):
        """keep the metric id in the memory for replace the key
        :param metric_ids:the metric ids download from server.
        :return:
        """
        if not metric_ids or debug_mode:
            return self.metric_name_ids

        if "actions" in metric_ids:
            for item in metric_ids["actions"]:
                key = item[0]["name"].encode("utf8")
                self.metric_name_ids["actions"][key] = item[1]

        if "apdex" in metric_ids:
            for item in metric_ids["apdex"]:
                key = item[0]["name"].encode("utf8")
                self.metric_name_ids["apdex"][key] = item[1]

        if "general" in metric_ids:
            for item in metric_ids["general"]:
                key = item[0]["name"].encode("utf8")
                self.metric_name_ids["general"][key] = item[1]

        if "errors" in metric_ids:
            for item in metric_ids["errors"]:
                key = item[0]["name"].encode("utf8")
                self.metric_name_ids["errors"][key] = item[1]

        if "components" in metric_ids:
            for item in metric_ids["components"]:
                key = "%s:%s" % (item[0]["name"], item[0]["parent"])
                key = key.encode("utf8")
                self.metric_name_ids["components"][key] = item[1]

        return self.metric_name_ids

    def get_performance_metric(self, stat, last_harvest, current_harvest, audit_mode=False):
        """
        :param stat:
        :return:
        """
        # disable the id mechanism
        metric_name_ids = self.metric_name_ids
        if audit_mode:
            metric_name_ids = {"actions": {}, "apdex": {}, "components": {}, "general": {}, "errors": {}}

        # if application is disabled. should send some heartbit data.
        if not self.application_config.enabled:
            performance = {
                "type": "perfMetrics",
                "timeFrom": int(last_harvest),
                "timeTo": int(current_harvest),
                "interval": int(current_harvest - last_harvest),
                "actions": [],
                "apdex": [],
                "components": [],
                "general": [],
                "errors": stat.error_packets(metric_name_ids["errors"])
            }

            return performance

        performance = {
            "type": "perfMetrics",
            "timeFrom": int(last_harvest),
            "timeTo": int(current_harvest),
            "interval": int(current_harvest - last_harvest),
            "actions": stat.action_metrics(metric_name_ids["actions"]),
            "apdex": stat.apdex_data(metric_name_ids["apdex"]),
            "components": stat.component_metrics(metric_name_ids["components"]),
            "general": stat.general_trace_metric(metric_name_ids["general"]),
            "errors": stat.error_packets(metric_name_ids["errors"]),
        }

        return performance

    def get_error_trace_data(self, stat):
        """
        :return:
        """
        error_trace = {
            "type": "errorTraceData",
            "errors": stat.error_trace_data()
        }

        # no error data recorded return None as mark.
        if 0 == len(stat.error_trace_data()):
            error_trace = []

        return error_trace

    def get_external_error_trace(self, stat):
        """
        :param stat:
        :return:
        """
        error_data = stat.external_error_data()
        error_trace = {
            "type": "externalErrorTraceData",
            "errors": error_data
        }

        # no error data recorded return None as mark.
        if 0 == len(error_data):
            error_trace = None

        return error_trace

    def process_headquarters_command(self):
        """get the command from agent server, and start the command.
        :return:
        """

        # use the lock for only sure one processes on the agent command

        with self._agent_commands_lock:
            for cmd in self._active_session.request_agent_commands():
                console.info("Processing command %s", cmd)

                cmd_id = None
                if 'StopProfiler' not in cmd['name']:
                    cmd_id = cmd['id']

                cmd_name = cmd['name']
                cmd_args = cmd['args']

                cmd_handler = getattr(self, "cmd_%s" % cmd_name, None)
                if cmd_handler is None:
                    console.info("Agent dose not support command %s", cmd_name)
                    continue

                cmd_handler(cmd_id, cmd_args)

    """
    def cmd_StartProfiler(self, cid, args):
        # TODO
        pass

    def cmd_StopProfiler(self, cid, args):
        # TODO
        pass

    def send_profile_data(self, audit_mode=False):
        # TODO
        pass
    """
