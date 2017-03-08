# -*- coding: utf-8 -*-

import logging
from collections import namedtuple
from ssa.logistics.warehouse.dbapi_tools import sql_parser
from ssa.logistics.attribution import node_start_time, node_end_time, TimeMetric
from ssa.config.settings import global_settings

_SlowSqlNode = namedtuple('_SlowSqlNode', ['duration', 'path', 'request_uri', 'sql', 'sql_format', 'metric', 'dbapi',
                                           'stack_trace', 'connect_params', 'cursor_params', 'execute_params',
                                           "start_time"])
_DatabaseNode = namedtuple('_DatabaseNode', ['dbapi',  'sql', 'children', 'start_time', 'end_time', 'duration',
                                             'exclusive', 'stack_trace', 'sql_format', 'connect_params',
                                             'cursor_params', 'execute_params', "dbtype"])
console = logging.getLogger(__name__)


class SlowSqlNode(_SlowSqlNode):
    """
    """
    def __new__(cls, *args, **kwargs):
        node = _SlowSqlNode.__new__(cls, *args, **kwargs)
        node.parser = sql_parser(node.sql, node.dbapi)
        return node

    @property
    def operation(self):
        return self.parser.operation

    @property
    def formatted(self):
        return self.parser.formatted(self.sql_format)

    @property
    def identifier(self):
        return self.parser.identifier

    @property
    def explain_plan(self):
        return self.parser.explain_plan(self.connect_params, self.cursor_params, self.execute_params)

    def __str__(self):
        lines = []
        lines.append("              >>>----------------------------------")
        lines.append("              :duration:%s" % self.duration)
        lines.append("              :request_uri:%s" % self.request_uri)
        lines.append("              :sql:%s" % self.sql)
        lines.append("              :sql_format:%s" % self.sql_format)
        lines.append("              :metric:%s" % self.metric)
        lines.append("              :dbapi:%s" % self.dbapi)
        lines.append("              :stack_trace:%s" % self.stack_trace)
        lines.append("              :connect_params:%s" % self.connect_params)
        lines.append("              :cursor_params:%s" % self.cursor_params)
        lines.append("              :execute_params:%s" % self.execute_params)
        lines.append("              :start_time:%s" % self.start_time)
        lines.append("              <<<----------------------------------")
        return '\r\n'.join(lines)


class DatabaseNode(_DatabaseNode):

    def __new__(cls, *args, **kwargs):
        node = _DatabaseNode.__new__(cls, *args, **kwargs)
        node.parser = sql_parser(node.sql, node.dbapi)

        return node

    @property
    def operation(self):
        return self.parser.operation

    @property
    def table(self):
        return self.parser.table

    @property
    def formatted(self):
        return self.parser.formatted(self.sql_format)

    @property
    def explain_plan(self):
        return self.parser.explain_plan(self.connect_params, self.cursor_params, self.execute_params)

    def time_metrics(self, root, parent):
        print("DatabaseNode")
        """
        :param root:
        :param parent:
        :return:
        """
        dbtype = r' %s' % self.dbtype
        name = 'GENERAL/Database%s/NULL/All' % dbtype
        yield TimeMetric(name=name, scope=root.path, duration=self.duration, exclusive=self.exclusive)

        if root.type == 'WebAction':
            name = "GENERAL/Database%s/NULL/AllWeb" % dbtype
            yield TimeMetric(name=name, scope=root.path, duration=self.duration, exclusive=self.exclusive)
        else:
            name = "GENERAL/Database%s/NULL/AllBackgound" % dbtype
            yield TimeMetric(name=name, scope=root.path, duration=self.duration, exclusive=self.exclusive)

        operation = str(self.operation).upper()

        if operation in ('SELECT', 'UPDATE', 'INSERT', 'DELETE'):
            if self.table:
                name = "GENERAL/Database%s/%s/%s" % (dbtype, self.table, operation)
                yield TimeMetric(name=name, scope=root.path, duration=self.duration, exclusive=self.exclusive)

                name = "Database%s/%s/%s" % (dbtype, self.table, operation)
                yield TimeMetric(name=name, scope=root.path, duration=self.duration, exclusive=self.exclusive)

            name = "GENERAL/Database%s/NULL/%s" % (dbtype, operation)
            yield TimeMetric(name=name, scope=root.path, duration=self.duration, exclusive=self.exclusive)
        else:
            name = "GENERAL/Database%s/operation/CALL" % dbtype
            yield TimeMetric(name=name, scope=root.path, duration=self.duration, exclusive=self.exclusive)

            name = "Database%s/operation/CALL" % dbtype
            yield TimeMetric(name=name, scope=root.path, duration=self.duration, exclusive=self.exclusive)

    def trace_node(self, root):
        """
        :param root: the root node of the tracker
        :return:
        """
        dbtype = r" %s" % self.dbtype
        params = {"sql": "", "explainPlan": {}, "stacktrace": []}
        children = []
        call_count = 1
        class_name = ""
        method_name = root.name
        root.trace_node_count += 1
        start_time = node_start_time(root, self)
        end_time = node_end_time(root, self)
        operation = str(self.operation).upper()
        metric_name = "Database%s/CALL/sql" % dbtype
        call_url = metric_name

        if operation in ('SELECT', 'UPDATE', 'INSERT', 'DELETE'):
            metric_name = 'Database/%s/%s' % (self.table, operation) if self.table else 'Database/NULL/%s' % operation

        if self.formatted:
            # Note, use local setting only.
            _settings = global_settings()
            params['sql'] = self.formatted

            if _settings.action_tracer.log_sql:
                console.info("Log sql is opened. sql upload is disabled, sql sentence is %s", self.formatted)
                params['sql'] = ""

            if self.explain_plan:
                params['explainPlan'] = self.explain_plan

            if self.stack_trace:
                for line in self.stack_trace:
                    if len(line) >= 4 and 'tingyun' not in line[0]:
                        params['stacktrace'].append("%s(%s:%s)" % (line[2], line[0], line[1]))

        return [start_time, end_time, metric_name, call_url, call_count, class_name, method_name, params, children]

    def slow_sql_node(self, root):
        """
        :return:
        """
        dbtype = r" %s" % self.dbtype
        request_uri = root.request_uri.replace("%2F", "/")
        metric_name = "Database%s/CALL/sql" % dbtype
        operation = str(self.operation).upper()

        if operation in ('SELECT', 'UPDATE', 'INSERT', 'DELETE'):
            metric_name = 'Database%s/NULL/%s' % (dbtype, operation)
            if self.table:
                metric_name = 'Database%s/%s/%s' % (dbtype, self.table, operation)

        return SlowSqlNode(duration=self.duration, path=root.path, request_uri=request_uri, metric=metric_name,
                           start_time=int(self.start_time), sql=self.sql, sql_format=self.sql_format, dbapi=self.dbapi,
                           stack_trace=self.stack_trace, connect_params=self.connect_params,
                           cursor_params=self.cursor_params, execute_params=self.execute_params)

    def __str__(self):
        lines = []
        lines.append("              >>>----------------------------------")
        lines.append("              :dbapi:%s" % self.dbapi)
        lines.append("              :sql:%s" % self.sql)
        lines.append("              :children:[%s]" % len(self.children))
        for child in self.children:
            for line in ["              %s" % x for x in str(child).split("\r\n")]:
                lines.append(line)
        lines.append("              :start_time:%s" % self.start_time)
        lines.append("              :end_time:%s" % self.end_time)
        lines.append("              :duration:%s" % self.duration)
        lines.append("              :exclusive:%s" % self.exclusive)
        lines.append("              :stack_trace:%s" % self.stack_trace)
        lines.append("              :sql_format:%s" % self.sql_format)
        lines.append("              :connect_params:%s" % str(self.connect_params))
        lines.append("              :cursor_params:%s" % str(self.cursor_params))
        lines.append("              :execute_params:%s" % str(self.execute_params))
        lines.append("              :dbtype:%s" % self.dbtype)
        lines.append("              <<<----------------------------------")
        return '\r\n'.join(lines)
