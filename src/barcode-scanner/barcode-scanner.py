#
# Copyright (C) 2025 Intel Corporation.
#
# SPDX-License-Identifier: Apache-2.0
#

import usb.core
import usb.util
import paho.mqtt.client as mqtt
import time
import os

MQTT_BROKER_URL = os.getenv("MQTT_URL", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
VID = os.getenv("VID", 0x05e0)  # Vendor ID of the barcode scanner. Default value for Symbol LS2208 General Purpose Barcode Scanner
PID = os.getenv("PID", 0x1200)  # Product ID of the barcode scanner. Default value for Symbol LS2208 General Purpose Barcode Scanner

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


def main():        
    client = mqtt.Client(client_id="", clean_session=True, userdata=None, protocol=mqtt.MQTTv311, transport="tcp")
    client.connect(MQTT_BROKER_URL, MQTT_PORT, 60)
    print(f"Connected to MQTT")
    client.loop_start()

    dev, ep, needs_reattach = connect_barcode(VID, PID)
    # Loop through a series of 8-byte transactions and convert each to an
    # ASCII character. Print output after 0.25 seconds of no data.
    line = ''
    while True:
        try:
            # Wait up to 0.25 seconds for data. 250 = 0.25 second timeout.
            data = ep.read(1000, 250)

            # Split the input array into n sized arrays for parsing
            scanTime = time.time()
            arraySize = 8
            lst = [data[i:i + arraySize] for i in range(0, len(data), arraySize)]

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
                msg = '{"id": %s, "time": %s, "barcode": %s}' % (PID, str(scanTime), str(line))
                print(msg)
                client.publish("barcode", msg)
                line = ''

if __name__=="__main__":
    main()