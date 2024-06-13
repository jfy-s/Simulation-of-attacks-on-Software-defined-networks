#!/bin/bash

echo "Starting iperf3 server on h1..."
mnexec -a 1 iperf3 -s &

sleep 2

echo "Starting iperf3 clients on h2..."
mnexec -a 2 iperf3 -c 10.0.0.1 -t 60 -b 10M -P 10 &

echo "Starting iperf3 clients on h3..."
mnexec -a 3 iperf3 -c 10.0.0.1 -t 60 -b 10M -P 10 &

echo "Starting iperf3 clients on h4..."
mnexec -a 4 iperf3 -c 10.0.0.1 -t 60 -b 10M -P 10 &

sleep 60

echo "DDoS attack simulation completed."
