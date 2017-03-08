import os
import random
import string
import requests
import json

from py_zipkin import zipkin
from ssa.embattle.log_file import console
from ssa.logistics.warehouse.external_node import ExternalNode
from ssa.logistics.warehouse.function_node import FunctionNode
from ssa.logistics.warehouse.database_node import DatabaseNode


class Zipkin(object):

    def _gen_random_id(self):
        return ''.join(
            random.choice(
                string.digits) for i in range(16))

    def __init__(self, environ=None, sample_rate=100, framework=''):
        console.info("===================================================")
        console.info("os.environ before")
        console.info(os.environ)
        console.info("===================================================")

        MSB_IP = os.environ.get('OPENPALETTE_MSB_IP', '')
        console.info("MSB_IP:[" + MSB_IP + "]")
        APP_NAME = os.environ.get('APP_NAME', '')
        console.info("APP_NAME:[" + APP_NAME + "]")

        # FIXME sunyan
        self.app_name = "app1" if APP_NAME is None or APP_NAME is '' else APP_NAME
        #self.app_name = "VNPM_RabbitMQ_PYTHON" if APP_NAME is None or APP_NAME is '' else APP_NAME
        self.environ = environ
        self.framework = framework
        self._sample_rate = sample_rate
        self._transport_handler = None
        self._transport_exception_handler = None
        if MSB_IP is None or MSB_IP is '':
            os.environ['no_proxy'] = '10.62.100.151'
            self.zipkin_dsn = 'http://10.62.100.151:8085/zipkin/api/v1/spans'
            #self.zipkin_dsn = 'http://localhost:9411/api/v1/spans'
            console.info("ZIPKIN_DSN is none, change it to:" + self.zipkin_dsn)
        else:
            os.environ['no_proxy'] = MSB_IP
            ZIPKIN_DSN = 'http://' + MSB_IP + ':80/api/smartsight-collector-python/v1/spans'
            console.info("ZIPKIN_DSN:[" + ZIPKIN_DSN + "]")
            self.zipkin_dsn = ZIPKIN_DSN

        console.info("no_proxy:" + os.environ['no_proxy'])
        console.info("===================================================")
        console.info("os.environ after")
        console.info(os.environ)
        console.info("===================================================")

    def default_exception_handler(self, ex):
        pass

    def default_handler(self, encoded_span):
        if self.app_name is None:
            console.info("APP_NAME is none, error!")
            return

        try:
            body = str.encode('\x0c\x00\x00\x00\x01') + encoded_span
            console.info("url:{0}".format(self.zipkin_dsn))
            rec = requests.post(
                self.zipkin_dsn,
                data=body,
                headers={'Content-Type': 'application/x-thrift'},
                timeout=1,
            )
            console.info("rec:{0}".format(rec))
            return rec
        except Exception as e:
            console.exception("flask_zipkin")
            if self._transport_exception_handler:
                self._transport_exception_handler(e)
            else:
                self.default_exception_handler(e)

    def transport_handler(self, callback):
        self._transport_handler = callback
        return callback

    def transport_exception_handler(self, callback):
        self._transport_exception_handler = callback
        return callback

    def handle(self, node):
        try:
            if self.framework == 'flask' or self.framework == 'bottle':
                console.info("handle flask")
                self.handle_flask(node)
            elif self.framework == 'oslo_messaging':
                console.info("handle oslo_messaging")
                self.handle_rabbitmq(node)
            elif self.framework == 'pika':
                console.info("handle pika")
                self.handle_pika(node)
            else:
                pass
        except Exception as e:
            console.exception("handle error")

    # FIXME much same as handle_rabbitmq, consider refactor this method!
    def handle_pika(self, node):
        try:
            console.info("environ>>>>>>")
            print(self.environ)
            console.info("environ<<<<<<")

            if node.type == 'WebAction':
                for child in node.children:
                    if 'pika' in child.group:
                        transport_handler = self._transport_handler or self.default_handler

                        trace_id = node.trace_id
                        span_name = json.dumps(child.params)
                        start_time = child.start_time
                        end_time = child.end_time
                        parent_span_id = None
                        is_sampled = True
                        flags = '0'

                        zipkin_attrs = self.generate_zipkin_attrs(trace_id=trace_id,
                                                                  span_id=self._gen_random_id(),
                                                                  parent_span_id=parent_span_id,
                                                                  flags=flags,
                                                                  is_sampled=is_sampled)
                        span2 = self.generate_span_2(service_name=self.app_name,
                                                     span_name=span_name,
                                                     zipkin_attrs=zipkin_attrs,
                                                     transport_handler=transport_handler)
                        span2.start(start_time)
                        span2.stop(start_timestamp=start_time, end_timestamp=end_time)

        except Exception as e:
            console.exception("handle_pika error")

    def handle_rabbitmq(self, node):
        try:
            console.info("environ>>>>>>")
            print(self.environ)
            console.info("environ<<<<<<")

            if node.type == 'WebAction':
                for child in node.children:
                    if 'oslo_messaging' in child.group:
                        transport_handler = self._transport_handler or self.default_handler

                        trace_id = node.trace_id
                        span_name = json.dumps(child.params)
                        start_time = child.start_time
                        end_time = child.end_time
                        parent_span_id = None
                        is_sampled = True
                        flags = '0'

                        zipkin_attrs = self.generate_zipkin_attrs(trace_id=trace_id,
                                                                  span_id=self._gen_random_id(),
                                                                  parent_span_id=parent_span_id,
                                                                  flags=flags,
                                                                  is_sampled=is_sampled)
                        span2 = self.generate_span_2(service_name=self.app_name,
                                                     span_name=span_name,
                                                     zipkin_attrs=zipkin_attrs,
                                                     transport_handler=transport_handler)
                        span2.start(start_time)
                        span2.stop(start_timestamp=start_time, end_timestamp=end_time)

        except Exception as e:
            console.exception("handle_rabbitmq error")

    def handle_flask(self, node):
        try:
            console.info("environ>>>>>>")
            print(self.environ)
            console.info("environ<<<<<<")

            """
            headers = self.environ['werkzeug.request'].headers
            url = self.environ['werkzeug.request'].url
            trace_id = headers.get('X-B3-TraceId') or self._gen_random_id()
            parent_span_id = headers.get('X-B3-Parentspanid')
            is_sampled = str(headers.get('X-B3-Sampled') or '0') == '1'
            flags = headers.get('X-B3-Flags')
            """

            trace_id = node.trace_id
            #trace_id = self.environ.get('HTTP_X_B3_TRACEID') or self._gen_random_id()
            start_time = node.start_time
            end_time = node.end_time
            url = "http://{0}{1}".format(self.environ.get('HTTP_HOST'), self.environ.get('PATH_INFO'))
            parent_span_id = self.environ.get('HTTP_X_B3_PARENTSPANID')
            #is_sampled = str(self.environ.get('HTTP_X_B3_SAMPLED') or '0') == '1'
            is_sampled = True
            #flags = self.environ.get('HTTP_X_B3_FLAGS')
            flags = '0'

            # parent span
            transport_handler = self._transport_handler or self.default_handler
            zipkin_attrs = self.generate_zipkin_attrs(trace_id=trace_id, span_id=self._gen_random_id(), parent_span_id=parent_span_id, flags=flags, is_sampled=is_sampled)
            span2 = self.generate_span_2(service_name=self.app_name, span_name=url, zipkin_attrs=zipkin_attrs, transport_handler=transport_handler)
            span2.start(start_time)

            if node.type == 'WebAction':
                for child in node.children:
                    # flask
                    if child.name == 'Response':
                        for child2 in child.children:
                            # flask or bottle
                            if 'flask' in child2.name or 'bottle' in child2.name:
                                for child3 in child2.children:
                                    if child3.group == 'Function':
                                        for child4 in child3.children:
                                            # mysql
                                            if type(child4) == DatabaseNode and child4.sql != 'COMMIT':
                                                sql = child4.sql
                                                span_name = ''
                                                execute_params = child4.execute_params
                                                if sql.strip().upper().startswith("SELECT"):
                                                    sql = sql % execute_params[0]
                                                    span_name = "SELECT"
                                                elif sql.strip().upper().startswith("INSERT"):
                                                    sql = sql % execute_params[0]
                                                    span_name = "INSERT"
                                                elif sql.strip().upper().startswith("DELETE"):
                                                    sql = sql % execute_params[0]
                                                    span_name = "DELETE"
                                                elif sql.strip().upper().startswith("UPDATE"):
                                                    sql = sql % execute_params[0][0]
                                                    span_name = "UPDATE"
                                                else:
                                                    pass

                                                # child span
                                                span3 = self.generate_span_3(service_name=self.app_name,
                                                                             span_name=span_name,
                                                                             binary_annotations={'jdbc.query': sql})
                                                span3.start(child4.start_time)
                                                span3.stop(start_timestamp=child4.start_time, end_timestamp=child4.end_time)
                                            # requests
                                            elif type(child4) == ExternalNode:
                                                # TODO ?
                                                pass
                                            # rabbitmq, FIXME sunyan: right now, we don't need this branch, but may be useful in the future!
                                            #elif type(child4) == FunctionNode and 'oslo_messaging' in child4.name:
                                            #    span3 = self.generate_span_3(service_name=self.app_name,
                                            #                                 span_name=json.dumps(child4.params),
                                            #                                 binary_annotations=child4.params)
                                            #    span3.start(child4.start_time)
                                            #    span3.stop(start_timestamp=child4.start_time,
                                            #               end_timestamp=child4.end_time)
                                            else:
                                                pass
                                    else:
                                        pass
                            # not flask and bottle
                            else:
                                pass
                    # others
                    else:
                        pass

            span2.stop(start_timestamp=start_time, end_timestamp=end_time)

        except Exception as e:
            console.exception("handle_flask error")

    def generate_zipkin_attrs(self, trace_id=None, span_id=None, parent_span_id=None, flags=None, is_sampled=None):
        zipkin_attrs = zipkin.ZipkinAttrs(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            flags=flags,
            is_sampled=is_sampled,
        )
        console.info("zipkin_attrs...begin")
        console.info(zipkin_attrs)
        console.info("zipkin_attrs...end")
        return zipkin_attrs

    def generate_span_2(self, service_name=None, span_name=None, zipkin_attrs=None, transport_handler=None):
        span = zipkin.zipkin_span(
            service_name=service_name,
            span_name=span_name,
            zipkin_attrs=zipkin_attrs,
            transport_handler=transport_handler
        )
        return span

    def generate_span_3(self, service_name=None, span_name=None, binary_annotations=None):
        return zipkin.zipkin_span(service_name=service_name, span_name=span_name, binary_annotations=binary_annotations)

    # not used right now.
    def generate_span_4(self, service_name=None, span_name=None, zipkin_attrs=None, transport_handler=None, binary_annotations=None):
        span = zipkin.zipkin_span(
            service_name=service_name,
            span_name=span_name,
            zipkin_attrs=zipkin_attrs,
            transport_handler=transport_handler,
            binary_annotations=binary_annotations
        )
        return span
