# kubernetes-external-metrics-exporter
Exporter for kubernetes external metrics

## build

~~~~
docker login
docker-compose -f docker-compose-build.yml build
docker-compose -f docker-compose-build.yml push
~~~~

## configuration

customize your configuration via config file kubernetes-external-metrics-exporter/exporter/exporter.py.yml

## run

Use docker-compose.yml to run container with mounted config kubernetes-external-metrics-exporter/exporter/exporter.py.yml
~~~~
docker-compose up
~~~~

## dependencies if want to run without container

pip3 install --user pyaml prometheus_client

