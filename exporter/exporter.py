#!/usr/bin/env python

import urllib.request
import ssl
import json
import traceback
import argparse
import sys
import time
import logging
import yaml
import prometheus_client
import prometheus_client.core

# parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('--config', default=sys.argv[0] + '.yml', help='config file location')
parser.add_argument('--log_level', help='logging level')
parser.add_argument('--url', help='kubernetes web UI url')
parser.add_argument('--tasks', help='tasks to execute')
parser.add_argument('--ssl_public_key', help='ssl public key file for http connection')
parser.add_argument('--ssl_private_key', help='ssl private key file for http connection')
args = parser.parse_args()

# add prometheus decorators
REQUEST_TIME = prometheus_client.Summary('request_processing_seconds', 'Time spent processing request')

def get_config(args):
    '''Parse configuration file and merge with cmd args'''
    for key in vars(args):
        conf[key] = vars(args)[key]
    with open(conf['config']) as conf_file:
        conf_yaml = yaml.load(conf_file, Loader=yaml.FullLoader)
    for key in conf_yaml:
        if not conf.get(key):
            conf[key] = conf_yaml[key]

def configure_logging():
    '''Configure logging module'''
    log = logging.getLogger(__name__)
    log.setLevel(conf['log_level'])
    FORMAT = '%(asctime)s %(levelname)s %(message)s'
    logging.basicConfig(format=FORMAT)
    return log

# Decorate function with metric.
@REQUEST_TIME.time()
def get_data():
    '''Get data from target service'''
    for task_name in conf['tasks']:
        get_data_function = globals()['get_data_'+ task_name]
        get_data_function()
                
def get_data_external_metrics():
    '''Get data from "nodes" API'''
    #kubectl get --raw /apis/external.metrics.k8s.io/v1beta1 | python3 -c 'import json,sys,pprint;pprint.pprint(json.load(sys.stdin)["resources"][0])'
    url = conf['url'] + '/apis/external.metrics.k8s.io/v1beta1'
    req = urllib.request.Request(url)
    token = open(conf['token']).read()
    req.add_header('Authorization', 'Bearer {0}'.format(token))
    context = ssl.SSLContext()
    context.load_verify_locations(cafile=conf['ssl_ca_cert'])
    responce = urllib.request.urlopen(req, context=context)
    raw_data = responce.read().decode()
    json_data = json.loads(raw_data)
    parse_data_external_metrics(json_data)

def parse_data_external_metrics(json_data):
    '''Parse data from "nodes" API'''
    # get all resources
    for resource in json_data['resources']:
        labels = dict()
        labels['resource_name'] = resource['name']
        labels['resource_kind'] = resource['kind']
        metric_name = '{0}_resource_info'.format(conf['name'])
        description = "Information about resource"
        metric = {'metric_name': metric_name, 'labels': labels, 'description': description, 'value': 1}
        data.append(metric)
    # count all resources
    labels = dict()
    labels['resource_type'] = 'external metrics'
    metric_name = '{0}_resources_count'.format(conf['name'])
    description = "Resources count"
    value = len(json_data['resources'])
    metric = {'metric_name': metric_name, 'labels': labels, 'description': description, 'value': value}
    data.append(metric)

def label_clean(label):
    replace_map = {
        '\\': '',
        '"': '',
        '\n': '',
        '\t': '',
        '\r': '',
        '-': '_',
        ' ': '_'
    }
    for r in replace_map:
        label = label.replace(r, replace_map[r])
    return label

# run
conf = dict()
get_config(args)
log = configure_logging()
data = list()

kubernetes_external_metrics_exporter_up = prometheus_client.Gauge('kubernetes_external_metrics_exporter_up', 'kubernetes external metrics exporter scrape status')
kubernetes_external_metrics_exporter_errors_total = prometheus_client.Counter('kubernetes_external_metrics_exporter_errors_total', 'exporter scrape errors total counter')

class Collector(object):
    def collect(self):
        # add static metrics
        gauge = prometheus_client.core.GaugeMetricFamily
        counter = prometheus_client.core.CounterMetricFamily
        # get dinamic data
       #data = list()
        try:
            get_data()
            kubernetes_external_metrics_exporter_up.set(1)
        except:
            trace = traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
            for line in trace:
                print(line[:-1], flush=True)
            kubernetes_external_metrics_exporter_up.set(0)
            kubernetes_external_metrics_exporter_errors_total.inc()
        # add dinamic metrics
        to_yield = set()
        for _ in range(len(data)):
            metric = data.pop()
            labels = list(metric['labels'].keys())
            labels_values = [ metric['labels'][k] for k in labels ]
            if metric['metric_name'] not in to_yield:
                setattr(self, metric['metric_name'], gauge(metric['metric_name'], metric['description'], labels=labels))
            if labels:
                getattr(self, metric['metric_name']).add_metric(labels_values, metric['value'])
                to_yield.add(metric['metric_name'])
        for metric in to_yield:
            yield getattr(self, metric)

registry = prometheus_client.core.REGISTRY
registry.register(Collector())

prometheus_client.start_http_server(conf['listen_port'])

# endless loop
while True:
    try:
        while True:
            time.sleep(conf['check_interval'])
    except KeyboardInterrupt:
        break
    except:
        trace = traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
        for line in trace:
            print(line[:-1], flush=True)
