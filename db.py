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
import sqlite3

con = sqlite3.connect('meraki_sla.db')
cur = con.cursor()

cur.execute('''CREATE TABLE site
    (id TEXT PRIMARY KEY,
    name TEXT);''')

cur.execute('''CREATE TABLE device
    (mac TEXT PRIMARY KEY,
    name TEXT,
    model TEXT,
    site_id TEXT,
    FOREIGN KEY(site_id) REFERENCES site(id));''')

cur.execute('''CREATE TABLE status
    (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    device_mac TEXT,
    FOREIGN KEY(device_mac) REFERENCES device(mac));''')

con.commit()
cur.close()
con.close()
