#
# Copyright (C) 2025 Intel Corporation.
#
# SPDX-License-Identifier: Apache-2.0
#

import argparse
import datetime
import json
import os
import paho.mqtt.client as mqtt
from pytz import timezone
import time
import usb.core
import usb.util

SSCAPE_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"
MQTT_BROKER_URL = os.getenv("MQTT_URL", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", None)
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", None)
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "barcode")
SSCAPE_AUTH_FILE = os.getenv("SSCAPE_AUTH_FILE", None)
SSCAPE_ROOTCA = os.getenv("SSCAPE_ROOTCA", None)

def hid2ascii(lst):
    """The USB HID device sends an 8-byte code for every character. This
    routine converts the HID code to an ASCII character.

    See https://www.usb.org/sites/default/files/documents/hut1_12v2.pdf
    for a complete code table. Only relevant codes are used here."""

    # Example input from scanner representing the string "http:":
    #   array('B', [0, 0, 11, 0, 0, 0, 0, 0])   # h
    #   array('B', [0, 0, 23, 0, 0, 0, 0, 0])   # t
    #   array('B', [0, 0, 0, 0, 0, 0, 0, 0])    # nothing, ignore
    #   array('B', [0, 0, 23, 0, 0, 0, 0, 0])   # t
    #   array('B', [0, 0, 19, 0, 0, 0, 0, 0])   # p
    #   array('B', [2, 0, 51, 0, 0, 0, 0, 0])   # :


    if len(lst) > 8:
        lst = lst[0:8]

    if len(lst) != 8:
        raise ValueError("Invalid data length (needs 8 bytes)")
    conv_table = {
        0:['', ''],
        4:['a', 'A'],
        5:['b', 'B'],
        6:['c', 'C'],
        7:['d', 'D'],
        8:['e', 'E'],
        9:['f', 'F'],
        10:['g', 'G'],
        11:['h', 'H'],
        12:['i', 'I'],
        13:['j', 'J'],
        14:['k', 'K'],
        15:['l', 'L'],
        16:['m', 'M'],
        17:['n', 'N'],
        18:['o', 'O'],
        19:['p', 'P'],
        20:['q', 'Q'],
        21:['r', 'R'],
        22:['s', 'S'],
        23:['t', 'T'],
        24:['u', 'U'],
        25:['v', 'V'],
        26:['w', 'W'],
        27:['x', 'X'],
        28:['y', 'Y'],
        29:['z', 'Z'],
        30:['1', '!'],
        31:['2', '@'],
        32:['3', '#'],
        33:['4', '$'],
        34:['5', '%'],
        35:['6', '^'],
        36:['7' ,'&'],
        37:['8', '*'],
        38:['9', '('],
        39:['0', ')'],
        40:['\n', '\n'],
        41:['\x1b', '\x1b'],
        42:['\b', '\b'],
        43:['\t', '\t'],
        44:[' ', ' '],
        45:['_', '_'],
        46:['=', '+'],
        47:['[', '{'],
        48:[']', '}'],
        49:['\\', '|'],
        50:['#', '~'],
        51:[';', ':'],
        52:["'", '"'],
        53:['`', '~'],
        54:[',', '<'],
        55:['.', '>'],
        56:['/', '?'],
        100:['\\', '|'],
        103:['=', '='],
        }

    # A 2 in first byte seems to indicate to shift the key. For example
    # a code for ';' but with 2 in first byte really means ':'.
    if lst[0] == 2:
        shift = 1
    else:
        shift = 0

    # The character to convert is in the third byte
    ch = lst[2]
    if ch not in conv_table:
        print("Warning: data not in conversion table")
        return ''
    return conv_table[ch][shift]

def connect_barcode(vid, pid):
    # Find our device using the VID (Vendor ID) and PID (Product ID)
    dev = usb.core.find(idVendor=vid, idProduct=pid)
    if dev is None:
        raise IOError('USB device not found')

    # Disconnect it from kernel
    needs_reattach = False
    if dev.is_kernel_driver_active(0):
        needs_reattach = True
        dev.detach_kernel_driver(0)
        print("Detached USB device from kernel driver")

    # set the active configuration. With no arguments, the first
    # configuration will be the active one
    dev.set_configuration()

    # get an endpoint instance
    cfg = dev.get_active_configuration()
    intf = cfg[(0,0)]

    ep = usb.util.find_descriptor(
        intf,
        # match the first IN endpoint
        custom_match = \
        lambda e: \
            usb.util.endpoint_direction(e.bEndpointAddress) == \
            usb.util.ENDPOINT_IN)

    if ep is None:
        raise ValueError("Endpoint for USB device not found.")
    return dev, ep, needs_reattach

def parse_args():
    parser = argparse.ArgumentParser(description='Sends requests via KServe gRPC API using images in format supported by OpenCV. It displays performance statistics and optionally the model accuracy')
    parser.add_argument('--vid', required=False, default=0x05e0, help='Vendor ID of the barcode scanner') # Default value for Symbol LS2208 General Purpose Barcode Scanner
    parser.add_argument('--pid', required=False, default=0x1200, help='Product ID of the barcode scanner') # Default value for Symbol LS2208 General Purpose Barcode Scanner
    return parser.parse_args()


def main():
    args = parse_args()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, transport="tcp", userdata=None)

    certs = None
    if SSCAPE_ROOTCA is not None and os.path.exists(SSCAPE_ROOTCA):
        if certs is None:
            certs = {}
        certs['ca_certs'] = SSCAPE_ROOTCA
    if certs is not None:
        client.tls_set(**certs)
        client.tls_insecure_set(False)
    
    if SSCAPE_AUTH_FILE is not None:
        if os.path.exists(SSCAPE_AUTH_FILE):
            with open(SSCAPE_AUTH_FILE) as json_file:
                data = json.load(json_file)
            user = data['user']
            pw = data['password']
            client.username_pw_set(user, pw)
    elif MQTT_USERNAME is not None and MQTT_PASSWORD is not None:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    print("connecting to MQTT at %s:%d" % (MQTT_BROKER_URL, MQTT_PORT))
    client.connect(MQTT_BROKER_URL, MQTT_PORT, 60)
    print(f"Connected to MQTT and publishing to %s" % MQTT_TOPIC)
    client.loop_start()

    dev, ep, needs_reattach = connect_barcode(args.vid, args.pid)
    # Loop through a series of 8-byte transactions and convert each to an
    # ASCII character. Print output after 0.25 seconds of no data.
    line = ''
    while True:
        try:
            # Wait up to 0.25 seconds for data. 250 = 0.25 second timeout.
            data = ep.read(1000, 250)

            scan_time = time.time()
            utc_time = datetime.datetime.fromtimestamp(scan_time, tz=timezone("UTC")).strftime(SSCAPE_DATETIME_FORMAT)[:-3]

            # Split the input array into n sized arrays for parsing
            array_size = 8
            lst = [data[i:i + array_size] for i in range(0, len(data), array_size)]

            # Loop through 8 bit arrays and convert each to ascii for human readability
            for inchar in lst:
                ch = hid2ascii(inchar)
                line += ch
        except KeyboardInterrupt:
            print("Stopping program")
            dev.reset()
            if needs_reattach:
                dev.attach_kernel_driver(0)
                print("Reattached USB device to kernel driver")
            break
        except usb.core.USBError:
            # Timed out. End of the data stream. Print the scan line.
            if len(line) > 0:
                msg = '{"id": %s, "product_id": %d, "timestamp": %s, "value": %s}' % (MQTT_TOPIC.split("/")[-1], args.pid, utc_time, str(line))
                print(msg)
                client.publish(MQTT_TOPIC, json.dumps(msg))
                line = ''

if __name__=="__main__":
    main()