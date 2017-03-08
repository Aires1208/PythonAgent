import ConfigParser

config_file = ""
_config_parser = ConfigParser.RawConfigParser()
if not _config_parser.read(config_file):
    raise Exception("error")
value = getattr(_config_parser, "get")("license_key", option)