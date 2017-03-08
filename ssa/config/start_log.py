# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import time

startup_debug = True
log_file = "/tmp/smartsight-agent-python-bootstrap.log"
log_file_handler = None


def log_message(text, *args):
    global startup_debug
    if startup_debug:
        text = text % args
        timestamp = time.strftime('%m-%d %T', time.localtime())
        print('SSA: %s (%d) - %s' % (timestamp, os.getpid(), text))

        return True

    return False


def log_bootstrap(msg, close=False):
    global log_file_handler

    if not startup_debug:
        return

    if close and log_file_handler is not None:
        log_data = "%s %s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S ", time.localtime()), os.getpid(), str(msg))
        log_file_handler.write(log_data)
        log_file_handler.write("close the log file....\n")
        log_file_handler.close()
        log_file_handler = None
        return

    if close and log_file_handler is None:
        log_file_handler = open(log_file, mode='a')
        log_data = "%s %s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S ", time.localtime()), os.getpid(), str(msg))
        log_file_handler.write(log_data)
        log_file_handler.write("close the log file....\n")
        log_file_handler.close()
        log_file_handler = None
        return

    if not close and log_file_handler is None:
        log_file_handler = open(log_file, mode='a')
        log_file_handler.write("open the log file....\n")

    log_data = "%s %s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S ", time.localtime()), os.getpid(), str(msg))
    log_file_handler.write(log_data)

