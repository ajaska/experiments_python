#!/bin/bash

pm2 start --interpreter 'poetry' --interpreter-args 'run python3.8' lightswitch.py
