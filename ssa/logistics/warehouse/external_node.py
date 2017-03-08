
"""

"""

from collections import namedtuple
from ssa.logistics.attribution import TimeMetric, node_start_time, node_end_time

_ExternalNode = namedtuple('_ExternalNode', ['library', 'url', 'children', 'start_time', 'end_time', 'protocol',
                                             'duration', 'exclusive'])


class ExternalNode(_ExternalNode):
    """

    """
    def time_metrics(self, root, parent):
        """
        :param root: the top node of the tracker
        :param parent: parent node.
        :return:
        """
        def extend_metric(metric_name):
            if not root.trace_data:
                return metric_name

            return "%s|%s|%s" % (metric_name, root.trace_data.get('id'), root.trace_data.get('action'))

        print("ExternalNode")

        name = 'GENERAL/External/NULL/All'
        yield TimeMetric(name=name, scope=root.path, duration=self.duration, exclusive=self.exclusive)

        name = "GENERAL/External/NULL/AllWeb"
        yield TimeMetric(name=name, scope=root.path, duration=self.duration, exclusive=self.exclusive)

        name = 'External/%s/%s' % (self.url.replace("/", "%2F"), root.name)
        yield TimeMetric(name=extend_metric(name), scope=root.path, duration=self.duration, exclusive=self.exclusive)

        if root.trace_data:
            # for cross trace.
            trace_data = root.trace_data
            name = 'ExternalTransaction/NULL/%s' % trace_data.get("id")
            yield TimeMetric(name=extend_metric(name), scope=root.path, duration=self.duration, exclusive=self.exclusive)

            name = 'ExternalTransaction/%s/%s' % (self.protocol, trace_data.get("id"))
            yield TimeMetric(name=extend_metric(name), scope=root.path, duration=self.duration, exclusive=self.exclusive)

            name = 'ExternalTransaction/%s:sync/%s' % (self.protocol, trace_data.get("id"))
            yield TimeMetric(name=extend_metric(name), scope=root.path, duration=self.duration, exclusive=self.exclusive)

        name = 'GENERAL/External/%s/%s' % (self.url.replace("/", "%2F"), root.name)
        yield TimeMetric(name=extend_metric(name), scope=root.path, duration=self.duration, exclusive=self.exclusive)

    def trace_node(self, root):
        """
        :param root: the root node of the tracker
        :return:
        """
        params = {}
        children = []
        call_count = 1
        class_name = ""
        method_name = root.name
        call_url = self.url
        root.trace_node_count += 1
        start_time = node_start_time(root, self)
        end_time = node_end_time(root, self)
        metric_name = 'External/%s/%s' % (self.url.replace("/", "%2F"), root.name)

        if root.trace_id and root.trace_data:
            params['txId'] = root.trace_id
            params['txData'] = root.trace_data

        return [start_time, end_time, metric_name, call_url, call_count, class_name, method_name, params, children]

    def __str__(self):
        library = self.library
        url = self.url
        children = self.children
        start_time = self.start_time
        end_time = self.end_time
        protocol = self.protocol
        duration = self.duration
        exclusive = self.exclusive
        lines = []
        lines.append("              >>>----------------------------------")
        lines.append("              :library:%s" % library)
        lines.append("              :url:%s" % url)
        lines.append("              :children:[%s]" % len(children))
        for child in children:
            for line in ["              %s" % x for x in str(child).split("\r\n")]:
                lines.append(line)
        lines.append("              :start_time:%s" % start_time)
        lines.append("              :end_time:%s" % end_time)
        lines.append("              :protocol:%s" % protocol)
        lines.append("              :duration:%s" % duration)
        lines.append("              :exclusive:%s" % exclusive)
        lines.append("              <<<----------------------------------")
        return '\r\n'.join(lines)
