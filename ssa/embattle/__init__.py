from ssa.embattle.inspection import take_control


def initialize(config_file=None):
    status = take_control(config_file).execute()
    return status
