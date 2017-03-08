# -*- coding: utf-8 -*-
from ssa.config.settings import global_settings


def defined_repertoire():
    hookers = {

        # mysql db

        "mysql": [
            {
                "target": "MySQLdb",
                'hook_func': 'detect',
                'hook_module': 'ssa.armoury.database_dbapi2'
            }
        ],

        "pymysql": [
            {
                'target': 'pymysql',
                'hook_func': 'detect',
                'hook_module': 'ssa.armoury.database_dbapi2'
            }
        ],

        # requests, 2.0.0-2.10.0
        "requests": [
            {
                "target": "requests.sessions",
                'hook_func': 'detect_requests_sessions',
                'hook_module': 'ssa.armoury.external_requests'
            },
        ],
        # flask, 0.6-1.0
        "flask": [
            {
                "target": "flask.app",
                'hook_func': 'detect_wsgi_entrance',
                'hook_module': 'ssa.armoury.framework_flask'
            },

            {
                "target": "flask.app",
                'hook_func': 'detect_app_entrance',
                'hook_module': 'ssa.armoury.framework_flask'
            },
        ],
        # bottle 0.10.x-0.12.x
        "bottle": [
            {
                "target": "bottle",
                'hook_func': 'detect_wsgi_entrance',
                'hook_module': 'ssa.armoury.framework_bottle'
            },
            {
                "target": "bottle",
                'hook_func': 'detect_templates',
                'hook_module': 'ssa.armoury.framework_bottle'
            },
            {
                "target": "bottle",
                'hook_func': 'detect_app_components',
                'hook_module': 'ssa.armoury.framework_bottle'
            },
        ],
        # rabbitmq
        # "rabbitmq": [
        #     {
        #         "target": "oslo_messaging.rpc.server",
        #         'hook_func': 'detect_rabbitmq_server_entrance',
        #         'hook_module': 'ssa.armoury.framework_rabbitmq'
        #     },
        #     {
        #         "target": "oslo_messaging.rpc.client",
        #         'hook_func': 'detect_rabbitmq_client_entrance',
        #         'hook_module': 'ssa.armoury.framework_rabbitmq'
        #     },
        # ]
        "oslo_messaging": [
            {
                "target": "oslo_messaging.rpc.server",
                'hook_func': 'detect_oslo_messaging_rpc_server_entrance',
                'hook_module': 'ssa.armoury.framework_oslo_messaging'
            },
            {
                "target": "oslo_messaging.rpc.client",
                'hook_func': 'detect_oslo_messaging_rpc_client_entrance',
                'hook_module': 'ssa.armoury.framework_oslo_messaging'
            },
        ],
        "pika": [
            {
                "target": "pika.channel",
                'hook_func': 'detect_pika_publish_entrance',
                'hook_module': 'ssa.armoury.framework_pika'
            },
            {
                "target": "pika.channel",
                'hook_func': 'detect_pika_consumer_entrance',
                'hook_module': 'ssa.armoury.framework_pika'
            },
        ],
    }

    return hookers
