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
import meraki
import requests
import json
import urllib3
import sqlite3
import pprint
import time
import csv

urllib3.disable_warnings()

#set start_time to current time - this will be used to keep track of time range of the report
def setTime(start_time):
    start_time["start_time"] = time.time()


#generic API GET request
def getAPIRequest(url, headers):
    while True:
        try:
            response = requests.get(url, headers=headers, verify=False)
            resp_json = json.loads(response.text)

            return resp_json
        except ConnectionError as e:
            print(e)
            time.sleep(4)


#get organization IDs from Meraki Dashboard and return list of all organization IDs
def getOrgIDs(org_url, headers):
    orgs = getAPIRequest(org_url, headers)

    org_ids = []
    for org in orgs:
        org_id = org["id"]
        org_ids.append(org_id)

    return org_ids


#get networks from Meraki Dashboard and check if those networks have been added to the database and return set of all new networks
def checkNewNetworks(cur, base_url, headers, org_ids):
    all_networks = []
    for org_id in org_ids:
        network_endpoint = "/organizations/" + org_id + "/networks"
        networks = getAPIRequest(base_url+network_endpoint, headers)
        all_networks.extend(networks)

    filter_file = open("filter.json")
    filter_keywords = json.load(filter_file)
    filter_file.close()

    api_nets = set()
    net_dict = {}
    for network in all_networks:
        net_id = network["id"]
        net_name = network["name"]

        add_net = True
        for word in filter_keywords["key words"]:
            if word in net_name:
                add_net = False
                break

        if add_net:
            net_dict[net_id] = {"name": net_name}
            api_nets.add(net_id)

    net_query = '''SELECT id FROM site'''
    cur.execute(net_query)
    net_ids = cur.fetchall()

    db_nets = set()
    for net_id in net_ids:
        db_nets.add(net_id[0])

    new_net_set = api_nets - db_nets

    new_nets = {}
    for net in new_net_set:
        new_nets[net] = net_dict[net]["name"]

    return new_nets


#add new networks to the database
def addNewNetworks(cur, new_nets):
    for net_id, net_name in new_nets.items():
        insert_query = '''INSERT INTO site VALUES(?, ?);'''
        cur.execute(insert_query, (net_id, net_name))


#get network devices from Meraki Dashboard and check if those devices have been added to the database and return set of all new devices
def checkNewDevices(cur, base_url, headers, org_ids, device_dict):
    all_devices = []
    for org_id in org_ids:
        device_endpoint = "/organizations/" + org_id + "/devices"
        devices = getAPIRequest(base_url+device_endpoint, headers)
        all_devices.extend(devices)

    device_query = "SELECT mac FROM device"
    cur.execute(device_query)
    device_macs = cur.fetchall()

    site_query = "SELECT id from site"
    cur.execute(site_query)
    site_db = cur.fetchall()
    site_ids = []
    for site in site_db:
        site_ids.append(site[0])

    db_devices = set()
    for mac in device_macs:
        db_devices.add(mac[0])

    api_devices = set()
    for device in all_devices:
        mac = device["mac"]
        name = device["name"]
        model = device["model"]
        site_id = device["networkId"]

        if site_id in site_ids:
            api_devices.add(mac)
            device_dict[mac] = {
                "name": name,
                "model": model,
                "site_id": site_id
            }

    new_devices = api_devices - db_devices

    return new_devices


#add new device to the database
def addNewDevices(cur, new_devices, device_dict):
    for device in new_devices:
        mac = device
        name = device_dict[mac]["name"]
        model = device_dict[mac]["model"]
        site_id = device_dict[mac]["site_id"]

        insert_query = '''INSERT INTO device VALUES(?, ?, ?, ?);'''
        cur.execute(insert_query, (mac, name, model, site_id))


#check device statuses from Meraki Dashboard and return the statuses
def checkDeviceStatus(org_ids, base_url, headers):
    device_statuses = []
    for org_id in org_ids:
        device_status_endpoint = "/organizations/" + org_id + "/devices/statuses"

        while True:
            try:
                device_status = requests.get(base_url+device_status_endpoint, headers=headers, verify=False)
                device_status = json.loads(device_status.text)
                pprint.pprint(device_status)
                print()
                print()
                break
            except Exception as e:
                print(e)
                time.sleep(4)

            device_statuses.extend(device_status)

    return device_statuses


#if device was offline and is now online, add the start of downtime and end of downtime to the database
def addDeviceStatus(cur, device_statuses, down_devices):
    network_query = "SELECT id from site"
    cur.execute(network_query)
    site_db = cur.fetchall()
    site_ids = []
    for site in site_db:
        site_ids.append(site[0])

    for status in device_statuses:
        name = status["status"]
        mac = status["mac"]
        net_id = status["networkId"]

        if net_id in site_ids:
            if name == "online":
                if mac in down_devices.keys():
                 end_time = time.time()
                 start_time = down_devices[mac]["start_time"]

                 insert_query = "INSERT INTO status(start_time, end_time, device_mac) VALUES(?, ?, ?);"
                 cur.execute(insert_query, (start_time, end_time, mac))

                 del down_devices[mac]

            else:
                if mac not in down_devices.keys():
                    start_time = time.time()
                    down_devices[mac] = { "start_time": start_time }


#monitor the network devices - check if networks are in the database and add new networks to the database, check if devices are in the database and add new devices to the database, check if device statuses have changed and add new statuses to the database
def monitorDevices(down_devices):
    con = sqlite3.connect('meraki_sla.db')
    cur = con.cursor()

    base_url = meraki.base_url

    headers = {
        "X-Cisco-Meraki-API-Key": meraki.api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
        }

    org_endpoint = "/organizations"
    org_ids = getOrgIDs(base_url+org_endpoint, headers)

    new_nets = checkNewNetworks(cur, base_url, headers, org_ids)
    addNewNetworks(cur, new_nets)

    device_dict = {}
    new_devices = checkNewDevices(cur, base_url, headers, org_ids, device_dict)
    addNewDevices(cur, new_devices, device_dict)

    device_statuses = checkDeviceStatus(org_ids, base_url, headers)
    addDeviceStatus(cur, device_statuses, down_devices)

    con.commit()
    cur.close()
    con.close()


#write the SLA report - calculate the total downtime from the start of the program and find the percentage of uptime for MXs, MSs, and MRs in each network
def writeReport(down_devices, program_start):
    report_time = time.time()
    program_duration = report_time - program_start["start_time"]

    con = sqlite3.connect('meraki_sla.db')
    cur = con.cursor()

    device_query = "SELECT mac, model, site_id FROM device"
    cur.execute(device_query)
    devices = cur.fetchall()
    print("DEVICES: {}".format(devices))

    device_status = {}
    print("DOWN DEVICES: {}".format(down_devices))
    for device in devices:
        mac = device[0]
        model = device[1]
        site_id = device[2]

        status_query = "SELECT * FROM status WHERE device_mac = ?"
        cur.execute(status_query, (mac,))
        statuses = cur.fetchall()

        print("STATUSES: {}".format(statuses))

        total_downtime = 0
        for status in statuses:
            start_time = status[1]
            end_time = status[2]
            if end_time > program_start["start_time"]:
                downtime = end_time - start_time
                total_downtime += downtime

        if mac in down_devices.keys():
            downtime = time.time() - down_devices[mac]["start_time"]
            total_downtime += downtime

        device_status[mac] = {"downtime": total_downtime, "site": site_id, "model": model}


    site_health = {}
    print(device_status)
    for key, value in device_status.items():
        site_id = value["site"]
        model = value["model"]
        print(model)

        if site_id not in site_health.keys():
            site_query = "SELECT name FROM site WHERE id = ?"
            cur.execute(site_query, (site_id,))
            site = cur.fetchall()

            if site:
                site_name = site[0][0]

                site_health[site_id] = {
                    "name": site_name,
                    "mx_health": 0,
                    "ms_health": 0,
                    "mr_health": 0,
                    "mx_count": 0,
                    "ms_count": 0,
                    "mr_count": 0
                }

        if "MX" in model:
            site_health[site_id]["mx_health"] += value["downtime"]
            site_health[site_id]["mx_count"] += 1
        elif "MS" in model:
            site_health[site_id]["ms_health"] += value["downtime"]
            site_health[site_id]["ms_count"] += 1
        elif "MR" in model:
            site_health[site_id]["mr_health"] += value["downtime"]
            site_health[site_id]["mr_count"] += 1

    for site_id in site_health:
        if site_health[site_id]["mx_count"] != 0:
            mx_total_duration = program_duration * site_health[site_id]["mx_count"]
            mx_percent_down = site_health[site_id]["mx_health"] / mx_total_duration
        else:
            print("count = 0 for some reason")
            mx_percent_down = 1
        print(mx_percent_down)

        if site_health[site_id]["ms_count"] != 0:
            ms_total_duration = program_duration * site_health[site_id]["ms_count"]
            ms_percent_down = site_health[site_id]["ms_health"] / ms_total_duration
        else:
            print("count = 0 for some reason")
            ms_percent_down = 1
        print(ms_percent_down)

        if site_health[site_id]["mr_count"] != 0:
            mr_total_duration = program_duration * site_health[site_id]["mr_count"]
            mr_percent_down = site_health[site_id]["mr_health"] / mr_total_duration
        else:
            print("count = 0 for some reason")
            mr_percent_down = 1
        print(mr_percent_down)

        mx_percent_health = (1 - mx_percent_down) * 100
        ms_percent_health = (1 - ms_percent_down) * 100
        mr_percent_health = (1 - mr_percent_down) * 100

        site_health[site_id]["mx_health"] = mx_percent_health
        site_health[site_id]["ms_health"] = ms_percent_health
        site_health[site_id]["mr_health"] = mr_percent_health

    with open('sla_report.csv', 'w') as csvfile:
        reportwriter = csv.writer(csvfile)
        reportwriter.writerow(["Site Name", "MX Health", "MS Health", "MR Health"])
        for site in site_health:
            reportwriter.writerow([site_health[site]['name'], site_health[site]['mx_health'],
                site_health[site]['ms_health'], site_health[site]['mr_health']])

        csvfile.close()

    con.commit()
    cur.close()
    con.close()

    print("Report written!")
