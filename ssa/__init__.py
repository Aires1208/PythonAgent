VERSION = (1, 1, 2, 'final', 0)


def get_version():
    from ssa.version import get_version
    return get_version(VERSION)
