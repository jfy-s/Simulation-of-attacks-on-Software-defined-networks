#!/bin/bash

CONTROLLER_IP="127.0.0.1"
CONTROLLER_PORT="6653"

ovs-vsctl set-controller s1 tcp:$CONTROLLER_IP:$CONTROLLER_PORT
ovs-vsctl set-controller s2 tcp:$CONTROLLER_IP:$CONTROLLER_PORT
ovs-vsctl set-controller s3 tcp:$CONTROLLER_IP:$CONTROLLER_PORT
ovs-vsctl set-controller s4 tcp:$CONTROLLER_IP:$CONTROLLER_PORT
ovs-vsctl set-controller s5 tcp:$CONTROLLER_IP:$CONTROLLER_PORT

echo "Controllers have been switched to $CONTROLLER_IP:$CONTROLLER_PORT"
ovs-vsctl show
