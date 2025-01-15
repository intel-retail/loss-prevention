#
# Copyright (C) 2024-25 Intel Corporation.
#
# SPDX-License-Identifier: Apache-2.0
#

import serial
import time
import os
import paho.mqtt.client as mqtt

# need to update code based on device used
port_name = '/dev/ttyUSB0' 
baud_rate = 9600
timeout = 1  # 1 second timeout
parity = serial.PARITY_EVEN
byte_size = serial.SEVENBITS
stop_bits = serial.STOPBITS_ONE

MQTT_BROKER_URL = os.getenv("MQTT_URL", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "event/scale")


# Reading class object to hold data from the scale
class Reading:
    def __init__(self, status="", value="", unit=""):
        self.status = status
        self.value = value
        self.unit = unit

    def print_weight(self):
        return (f"Weight: {self.value} {self.unit}")

    def to_string(self):
        if self.status == "OK" or self.status == "Motion":
            return (f"Status: {self.status}, {self.print_weight()}")
        else:
            return (f"Status: {self.status}")

def read_scale(dev:serial.Serial):
    # build buffer
    buffer_bytes = bytearray()

    # Try reading a small chunk of data to verify communication - need to update code based on device used
    weight_request = bytes([0x57, 0x0D])
    dev.write(weight_request)

    time.sleep(0.128)

    # print output request
    weight_bytes = dev.read(16)  # Read 16 bytes to check if the scale is responsive
    buffer_bytes.extend(weight_bytes)
    buffer_str = buffer_bytes.hex().upper()
    print(f"Received data (hex): {buffer_str}")
    return buffer_str

def process_scale_hex(buf:str):
    # Need to update code based on device used
    status_ending = b"0D03"  # Status ending in response
    weight_ending = b"0D0A"  # Weight reading ending in response
    weight_value_start = b"0A3"  # Start of weight data
    period_byte = b"2E"  # Byte that signifies period
    expected_period_index = 6  # Expected index for period byte in weight data

    # Map for known status codes
    status_tbl = {
        b"00": "OK",
        b"10": "Motion",
        b"20": "Scale at Zero",
        b"01": "Under Capacity",
        b"02": "Over Capacity",
    }

    # Find the start index for the weight value
    start_index = buf.find(weight_value_start.decode("utf-8"))
    print(f"Start index: {start_index}")

    # Check for valid data structure
    if start_index != 0 or len(buf) > 30:
        print("Invalid start index or data too long")


    # Look for status and weight data in the response
    if status_ending.decode("utf-8") in buf:
        reading = Reading(status="", value="", unit="")

        status_len = 4
        weight_len = 16
        status_index = buf.find(status_ending.decode("utf-8"))
        weight_index = buf.find(weight_ending.decode("utf-8"))
        period_index = buf.find(period_byte.decode("utf-8"))

        if status_index >= 0 and len(buf) > status_index:
            status = buf[status_index - status_len:status_index]
            status_def = status_tbl.get(bytes.fromhex(status), "N/A")
            reading.status = status_def
            # print(f"Status found: {reading.status}")

        if weight_index >= 0 and len(buf) > weight_index and period_index == expected_period_index:
            weight_str = buf[weight_index - weight_len:weight_index]
            weight = bytes.fromhex(weight_str)

            unit_len = 2
            unit_index = len(weight) - unit_len
            reading.value = weight[:unit_index].decode("utf-8")
            reading.unit = weight[unit_index:].decode("utf-8")

        return reading

def main():
    while True:
        try:
            with serial.Serial(port_name, baud_rate, byte_size, parity, stop_bits, timeout ) as ser:
                print(f"Connected to {port_name}")

                buffer_str = read_scale(ser)

                result = process_scale_hex(buffer_str)

                print(result.to_string())
                client.publish(topic=MQTT_TOPIC, payload=result.print_weight())

        except serial.SerialException as e:
            print(f"Error connecting to the port: {e}")

if __name__=="__main__":
    client = mqtt.Client(client_id="", clean_session=True, userdata=None, protocol=mqtt.MQTTv311, transport="tcp")
    client.connect(MQTT_BROKER_URL, MQTT_PORT, 60)
    print(f"Connected to MQTT")
    client.loop_start() 
    main()
