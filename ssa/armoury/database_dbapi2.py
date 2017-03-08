
"""The detect module follow the protocol: https://www.python.org/dev/peps/pep-0249/

"""

import logging
import time

from ssa.armoury.ammunition.tracker import current_tracker
from ssa.armoury.ammunition.database_tracker import DatabaseTracker
from ssa.armoury.ammunition.function_tracker import FunctionTracker, wrap_function_trace


# module_name: standard db name for data exchange protocol.
db_name_module = {
    "MySQLdb": "MySQL", "pymysql": "MySQL", "oursql": "MySQL",
    "cx_Oracle": "Oracle",
    "psycopg2": "PostgreSQL", "psycopg2ct": "PostgreSQL", "psycopg2cffi": "PostgreSQL",
    "pyodbc": "ODBC"
    }
console = logging.getLogger(__name__)


def detect(module):
    """ more interface description about dbapi2 in: https://www.python.org/dev/peps/pep-0249/
    :param module:
    :return:
    """
    dbtype = db_name_module.get(module.__name__, "dbapi2")

    class TingYunCursor(object):

        def __init__(self, cursor, cursor_params=None, connect_params=None):
            """
            :param cursor:
            :param cursor_params:
            :param connect_params:
            :return:
            """
            object.__setattr__(self, 'cursor', cursor)
            object.__setattr__(self, 'cursor_params', cursor_params)
            object.__setattr__(self, 'connect_params', connect_params)

        def __setattr__(self, name, value):
            setattr(self.cursor, name, value)

        def __getattr__(self, name):
            return getattr(self.cursor, name)

        def __iter__(self):
            return iter(self.cursor)

        def fetchone(self, *args, **kwargs):
            """we do not capture the metric of execute result. this is small time used
            :args:
            :kwargs:
            :return:
            """
            return self.cursor.fetchone(*args, **kwargs)

        def fetchmany(self, *args, **kwargs):
            """we do not capture the metric of execute result. this is small time used
            :args:
            :kwargs:
            :return:
            """
            return self.cursor.fetchmany(*args, **kwargs)

        def fetchall(self, *args, **kwargs):
            """this operation maybe spend more time. this is small time used
            and the sql was executed. we can not take it
            :args:
            :kwargs:
            :return:
            """
            return self.cursor.fetchall(*args, **kwargs)

        def execute(self, sql, *args, **kwargs):
            """
            :param sql:
            :param args:
            :param kwargs:
            :return:
            """
            tracker = current_tracker()
            if not tracker:
                return self.cursor.execute(sql, *args, **kwargs)

            with DatabaseTracker(tracker, sql, dbtype, module, self.connect_params, self.cursor_params,
                                 (args, kwargs)):
                return self.cursor.execute(sql, *args, **kwargs)

        def executemany(self, sql, *args, **kwargs):
            """
            :param sql:
            :param args:
            :param kwargs:
            :return:
            """
            tracker = current_tracker()
            if not tracker:
                return self.cursor.executemany(sql, *args, **kwargs)

            with DatabaseTracker(tracker, sql, dbtype, module):
                return self.cursor.executemany(sql, *args, **kwargs)

        def callproc(self, procname, *args, **kwargs):
            """
            :param procname:
            :param args:
            :param kwargs:
            :return:
            """
            tracker = current_tracker()
            if not tracker:
                return self.cursor.callproc(procname, *args, **kwargs)

            with DatabaseTracker(tracker, 'CALL %s' % procname, dbtype, module):
                return self.cursor.callproc(procname, *args, **kwargs)

        # sunyan: polish

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            del exc_info
            self.cursor.close()

    class TingYunConnection(object):

        def __init__(self, connection, params=None):
            """
            :param connection:
            :param params:
            :return:
            """
            object.__setattr__(self, 'connection', connection)
            object.__setattr__(self, 'params', params)

        def __setattr__(self, name, value):
            setattr(self.connection, name, value)

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def close(self, *args, **kwargs):
            """
            :param args:
            :param kwargs:
            :return:
            """
            return self.connection.close(*args, **kwargs)

        def cursor(self, *args, **kwargs):
            """
            :param args:
            :param kwargs:
            :return:
            """
            return TingYunCursor(self.connection.cursor(*args, **kwargs), (args, kwargs), self.params)

        def commit(self):
            """
            :return:
            """
            tracker = current_tracker()
            if not tracker:
                return self.connection.commit()

            with DatabaseTracker(tracker, 'COMMIT', dbtype, module):
                return self.connection.commit()

        def rollback(self):
            """
            :return:
            """
            tracker = current_tracker()
            if not tracker:
                return self.connection.rollback()

            with DatabaseTracker(tracker, 'ROLLBACK', dbtype, module):
                return self.connection.rollback()

    class DatabaseWrapper(object):

        def __init__(self, connect):
            self.connect = connect
            self.connect_instance = None

        def __call__(self, *args, **kwargs):
            """when module call the connect method. the wrapper will callback __call__ instead.
            :param args:
            :param kwargs:
            :return:
            """
            self.connect_instance = self.connect(*args, **kwargs)

            return TingYunConnection(self.connect_instance, (args, kwargs))

    # Check if module is already wrapped
    if hasattr(module, '_self_dbapi2_wrapped'):
        return

    wrap_function_trace(module, 'connect', name='%s.connect' % dbtype, group='Database')
    module.connect = DatabaseWrapper(module.connect)
    module._self_dbapi2_wrapped = True
