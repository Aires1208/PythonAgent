rm -rf build && mkdir -p build
tar -zcvf smartsight-agent-python.tar.gz flask_zipkin.py ply py_zipkin/ ssa/ thriftpy/ requests/ urllib3/ sitecustomize.py chardet/
mv smartsight-agent-python.tar.gz build
