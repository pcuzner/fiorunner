#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import os
import sys
import argparse
import subprocess
import json
import threading
import signal
import tempfile
import socket
import time

stats_lock = threading.Lock()
interval_stats = dict()


class Metric(object):

    def __init__(self, vhelp, vtype):
        self.var_help = vhelp
        self.var_type = vtype
        self.data = []

    def add(self, labels=None, value=0):
        if not labels:
            labels = dict()
        _d = dict(labels=labels, value=value)
        self.data.append(_d)


class FIOState(object):
    active = False


class FIOStats(object):
    def __init__(self):
        self.metrics = dict()

    def collect():
        stats_lock.acquire()
        # use the interval_stats to build out self.metrics
        stats_lock.release()

    def formatted(self):
        # process self.metrics returning a byte stream
        pass


class FIOExporter(ThreadingMixIn, HTTPServer):
    daemon = True


class RequestHandler(BaseHTTPRequestHandler):
    fio_state = None
    quiet = False
    valid_routes = {
        "GET": [
            '/',
            '/metrics',
        ],
        "PUT": [
            '/job',
        ],
    }

    def root(self):
        """ webserver root, just shows a link to /metrics endpoint """

        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.wfile.write(b"""
<!DOCTYPE html>
<html>
  <head><title>FIO Slave/Exporter</title></head>
  <body>
    <h1>FIO Slave/Exporter</h1>
    <p><a href='/metrics'>Metrics</a></p>
  </body>
</html>""")

    def metrics(self):
        stats = FIOStats()
        stats.collect()
        # out = stats.formatted()

    def runjob(self, job):
        fio_thread = threading.Thread(target=execfio, args=(job,))
        fio_thread.daemon = True
        fio_thread.start()

    def do_GET(self):
        if self.path not in self.valid_routes['GET']:
            self.send_error(404, message="Undefined endpoint - {}".format(self.path))
            return
        if self.path == '/':
            self.root()
        elif self.path == '/metrics':
            self.metrics()

    def do_PUT(self):
        if self.path not in self.valid_routes['PUT']:
            self.send_error(404, message="Unsupported endpoint for a PUT operation - {}".format(self.path))
            return

        content_type = self.headers.get_content_type()
        if content_type != 'application/json':
            self.send_error(400, message="PUT request must be json")
            return

        c_json = dict()
        c_length = int(self.headers.get('content-length', 0))
        print(c_length)
        if c_length > 0:
            c_data = self.rfile.read(c_length)
            c_data = c_data.replace(b'\n', b'\\n')
            print(c_data)
            print(str(c_data, 'utf-8'))
            c_json = json.loads(str(c_data, 'utf-8'))
        print(c_json)
        if c_length == 0:
            self.send_error(400, message='Empty request - expecting json of the form {"job": "<parms>"}')
            return
        elif 'job' not in c_json:
            self.send_error(400, message='Invalid json - expecting json of the form {"job"": "<parms>"}')
        print(c_json)
        if self.fio_state.active:
            self.send_error(409, message="fio job already active")
            return
        else:
            ok, err = fio_syntax_ok(c_json['job'])
            if not ok:
                self.send_error(400, message="Job has syntax errors: {}".format(','.join(err)))
                return
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(bytes(json.dumps({"message": "job request received"}, ensure_ascii=False), 'utf-8'))
                self.runjob(c_json['job'])
                return


def execfio(job=None):
    state.active = True

    print("fio active {}".format(state.active))
    tf = tempfile.NamedTemporaryFile(mode="w+", delete=False)
    tf.write(job)
    tf.close()
    process = subprocess.Popen(['fio', tf.name, '--status-interval=1s', '--output-format=json'], stdout=subprocess.PIPE)
    json_str = ''
    print("fio running in pid {}".format(process.pid))
    while True:
        stdout = process.stdout.readline()
        output = stdout.decode('utf-8').rstrip()
        if output == '' and process.poll() is not None:
            break
        if output:
            if output[0] == '}':
                json_str += '}'
                stats_lock.acquire()
                interval_stats = json.loads(json_str)
                stats_lock.release()
                # print(json.dumps(interval_stats,indent=2))

                json_str = ''
            else:
                json_str += output
            # print("> {}".format(output.strip()))
        rc = process.poll()
    print("fio job finished")
    os.remove(tf.name)
    state.active = False
    print("fio active {}".format(state.active))


def fio_syntax_ok(job):
    # create a temp file containing the job deck
    # check the temp file
    print("checking syntax for job containing")
    print(job)
    tf = tempfile.NamedTemporaryFile(mode="w+", delete=False)
    tf.write(job)
    tf.close()
    print("job file is {}".format(tf.name))
    proc = subprocess.Popen(['fio', tf.name, '--parse-only'], stderr=subprocess.PIPE)
    stderr = str(proc.communicate()[1], 'utf-8').split('\n')[:-1]
    print("syntax check rc {}".format(proc.returncode))
    os.remove(tf.name)
    return proc.returncode == 0, stderr


def get_opts():
    parser = argparse.ArgumentParser(description="FIO slave with embedded API and metrics exporter")
    parser.add_argument(
        "--port",
        type=int,
        default=8081,
        help="tcp port for the FIO slave to listen on")
    return parser.parse_args()


def shutdown():
    print("Shutting down FIO runner")
    exporter.shutdown()


def main():

    exporter_thread = threading.Thread(target=exporter.serve_forever)
    print("Starting FIO runner")
    exporter_thread.start()

    while True:
        try:
            time.sleep(0.5)
        except KeyboardInterrupt:
            break
    exporter.shutdown()


if __name__ == "__main__":
    args = get_opts()

    # global state object, that the request handler can refer to
    state = FIOState()
    RequestHandler.fio_state = state

    try:
        exporter = FIOExporter(("0.0.0.0", args.port), RequestHandler)
    except socket.error:
        print("Unable to bind to {}".format(args.port))
        sys.exit(1)
    signal.signal(signal.SIGTERM, shutdown)
    main()
