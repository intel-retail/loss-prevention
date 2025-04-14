#
# Copyright (C) 2024-25 Intel Corporation.
#
# SPDX-License-Identifier: Apache-2.0
#

# This script is used to parse the sensor data and publish it to the MQTT broker.
# The script reads the sensor data from the sensorData.json file and publishes it to the MQTT broker.

import argparse
import os
import paho.mqtt.client as mqtt

MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USERNAME = os.getenv('MQTT_USERNAME', None)
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', None)
ROOT_CA = os.getenv('ROOT_CA', None)

class SimulateSensorData:
    def __init__(self, file):
        self.file = file
        self.client = mqtt.Client(client_id="", clean_session=True, userdata=None, protocol=mqtt.MQTTv311, transport="tcp")
        if MQTT_USERNAME:
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        if ROOT_CA:
            self.client.tls_set(ROOT_CA)
        self.client.on_connect = self.on_connect
        self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
        self.client.loop_start()
        return

    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code "+str(rc))
        return

    def publish_file(self):
        with open(self.file) as f:
            for line in f:
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    topic, message = parts
                    message = message.strip().lstrip("b'").rstrip("'")
                    self.client.publish(topic=topic, payload=message)
        return

def build_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', required=True, type=str, help='Path to the sensor data file')
    return parser.parse_args()

def main():
    args = build_argparser()
    if not os.path.exists(args.file):
        print("Need a file to simulate sensor data")
        return
    sensor_simulator = SimulateSensorData(args.file)
    while True:
        sensor_simulator.publish_file()
    return

if __name__ == "__main__":
    main()
