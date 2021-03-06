from collections import namedtuple

from ssa.logistics.attribution import TimeMetric, node_start_time, node_end_time


_FunctionNode = namedtuple('_FunctionNode', ['group', 'name', 'children', 'start_time', 'end_time', 'duration',
                                             'exclusive', 'params', 'stack_trace'])


class FunctionNode(_FunctionNode):
    """
    """
    def time_metrics(self, root, parent):
        """
        :param root:
        :param parent:
        :return:
        """
        name = 'Python/%s/%s' % (self.group, self.name)

        print("FunctionNode")
        yield TimeMetric(name=name, scope=root.path, duration=self.duration, exclusive=self.exclusive)

        for child in self.children:
            for metric in child.time_metrics(root, self):
                yield metric

    def trace_node(self, root):
        """
        :param root: the root node of the trakcer
        :return: traced node
        """
        start_time = node_start_time(root, self)
        end_time = node_end_time(root, self)
        metric_name = 'Python/%s/%s' % (self.group, self.name)
        call_url = root.request_uri
        call_count = 1
        class_name = ""
        method_name = self.name
        params = {"sql": "", "explainPlan": {}, "stacktrace": []}
        children = []

        root.trace_node_count += 1
        for child in self.children:
            if root.trace_node_count > root.trace_node_limit:
                break

            children.append(child.trace_node(root))

        if self.stack_trace:
            for line in self.stack_trace:
                if len(line) >= 4 and 'tingyun' not in line[0]:
                    params['stacktrace'].append("%s(%s:%s)" % (line[2], line[0], line[1]))

        return [start_time, end_time, metric_name, call_url, call_count, class_name, method_name, params, children]

    def __str__(self):
        group = self.group
        name = self.name
        children = self.children
        start_time = self.start_time
        end_time = self.end_time
        duration = self.duration
        exclusive = self.exclusive
        params = self.params
        stack_trace = self.stack_trace
        lines = []
        lines.append("              >>>----------------------------------")
        lines.append("              :group:%s" % group)
        lines.append("              :name:%s" % name)
        lines.append("              :children:[%s]" % len(children))
        for child in children:
            for line in ["              %s" % x for x in str(child).split("\r\n")]:
                lines.append(line)
        lines.append("              :start_time:%s" % start_time)
        lines.append("              :end_time:%s" % end_time)
        lines.append("              :duration:%s" % duration)
        lines.append("              :exclusive:%s" % exclusive)
        lines.append("              :params:%s" % params)
        lines.append("              :stack_trace:%s" % stack_trace)
        lines.append("              <<<----------------------------------")
        return '\r\n'.join(lines)

