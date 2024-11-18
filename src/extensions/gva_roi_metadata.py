'''
* Copyright (C) 2024 Intel Corporation.
*
* SPDX-License-Identifier: Apache-2.0
'''
import sys
import gi
import json
from copy import deepcopy
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject


class RoiMetadata:
    def __init__(self, disable=False, rois=""):
        
        self.roi_list = [str(i) for i in rois.split(',')]

    def process_frame(self, frame):

        if not self.roi_list:
            return True              

        for message in frame.messages():
            message_obj = json.loads(message)

            if "objects" in message_obj:
                frame.remove_message(message)
                message_objects_array = deepcopy(message_obj["objects"])

                roi_objects = []
                other_objects = []

                for obj in message_objects_array:
                    if "roi_type" in obj:
                        if obj["roi_type"] in self.roi_list:
                            roi_objects.append(obj)
                        else:
                            other_objects.append(obj)

                for obj in other_objects:
                    for roi_obj in roi_objects:
                        if (obj["x"] >= roi_obj["x"] and obj["x"] + obj["w"] <= roi_obj["x"] + roi_obj["w"] and
                                obj["y"] >= roi_obj["y"] and obj["y"] + obj["h"] <= roi_obj["y"] + roi_obj["h"]):
                            obj["roi_type"] = roi_obj["roi_type"]

                message_obj["objects"] = other_objects + roi_objects

                frame.add_message(json.dumps(
                    message_obj, separators=(',', ':')))
                break
        return True
