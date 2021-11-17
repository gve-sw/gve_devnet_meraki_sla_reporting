#!/usr/bin/env python3
"""Copyright (c) 2020 Cisco and/or its affiliates.

This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at

               https://developer.cisco.com/docs/licenses

All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied."""
import schedule
import time
from report import *

down_devices = {} #keep track of devices that go down
start_time = {"start_time": time.time()} #keep track of the start time of the program, this will update each time a report is written
monitorDevices(down_devices)
schedule.every(2).minutes.do(monitorDevices, down_devices) #monitor devices every 2 minutes
schedule.every(4).weeks.do(writeReport, down_devices, start_time) #write wireless health report every 4 weeks
schedule.every(4).weeks.do(setTime, start_time) #reset start_time

#program will run according to schedule until program errors out or is stopped with control-C
while True:
    schedule.run_pending()
    time.sleep(1)
