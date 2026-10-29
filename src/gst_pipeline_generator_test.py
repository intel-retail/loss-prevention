'''
* Copyright (C) 2026 Intel Corporation.
*
* SPDX-License-Identifier: Apache-2.0
'''

import contextlib
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

GENERATOR_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'gst-pipeline-generator.py')


def load_generator():
    try:
        import dotenv  # noqa: F401
    except ImportError:
        # Device .env files only exist in the container, so an empty stub is enough here
        sys.modules['dotenv'] = types.SimpleNamespace(dotenv_values=lambda path: {})
    spec = importlib.util.spec_from_file_location('gst_pipeline_generator', GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WORKLOADS = {
    'workload_pipeline_map': {
        'detect_a': [{'type': 'gvadetect', 'model': 'yolo11n',
                      'precision': 'INT8', 'device': 'CPU'}],
        'detect_b': [{'type': 'gvadetect', 'model': 'yolov8',
                      'precision': 'INT8', 'device': 'CPU'}],
    }
}


class GeneratorStreamManifestTest(unittest.TestCase):
    def setUp(self):
        self.generator = load_generator()

    def generate(self, cameras, lanes):
        with tempfile.TemporaryDirectory() as tmpdir:
            camera_path = os.path.join(tmpdir, 'cameras.json')
            workload_path = os.path.join(tmpdir, 'workloads.json')
            manifest_path = os.path.join(tmpdir, 'pipeline_streams.json')
            with open(camera_path, 'w') as f:
                json.dump({'lane_config': {'cameras': cameras}}, f)
            with open(workload_path, 'w') as f:
                json.dump(WORKLOADS, f)
            self.generator.CONFIG_CAMERA_TO_WORKLOAD = camera_path
            self.generator.CONFIG_WORKLOAD_TO_PIPELINE = workload_path
            stdout = io.StringIO()
            with patch.dict(os.environ, {'STREAM_MANIFEST_PATH': manifest_path}), \
                    contextlib.redirect_stdout(stdout), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.generator.main(lanes)
            with open(manifest_path) as f:
                manifest = json.load(f)['streams']
        pipeline = stdout.getvalue()
        counters = re.findall(r'gvafpscounter name=(\S+)', pipeline)
        sources = re.findall(r'\b(?:rtspsrc|filesrc) name=', pipeline)
        return counters, sources, manifest

    @staticmethod
    def camera(index, workloads):
        return {'camera_id': f'cam{index + 1}', 'fps': 15,
                'fileSrc': f'video{index + 1}.mp4', 'workloads': workloads}

    def test_counter_names_sort_in_lane_order_with_ten_or_more_cameras_and_lanes(self):
        cameras = [self.camera(i, ['detect_a']) for i in range(12)]
        counters, sources, manifest = self.generate(cameras, lanes=11)

        # gvafpscounter reports per-stream FPS in byte-sorted name order
        self.assertEqual(counters, sorted(counters, key=str.encode))
        self.assertEqual(len(counters), 12 * 11)
        self.assertEqual(len(sources), len(manifest))
        self.assertEqual([entry['fpscounter'] for entry in manifest], counters)
        self.assertEqual([entry['log_index'] for entry in manifest],
                         list(range(len(manifest))))
        self.assertEqual([(entry['lane'], entry['camera_index']) for entry in manifest],
                         [(lane, cam) for lane in range(11) for cam in range(12)])

    def test_manifest_handles_skipped_and_multi_branch_cameras(self):
        cameras = [
            self.camera(0, ['detect_a']),
            self.camera(1, ['lp_vlm']),
            self.camera(2, ['detect_a', 'detect_b']),
        ]
        counters, sources, manifest = self.generate(cameras, lanes=2)

        self.assertEqual(len(sources), 6)
        self.assertEqual(len(manifest), 6)
        self.assertEqual([entry['fpscounter'] for entry in manifest], counters)
        # camera_index refers to the original config, so the skipped cam2 leaves a gap
        self.assertEqual(
            [(e['lane'], e['camera_index'], e['camera_id'], e['branch'], e['workloads'])
             for e in manifest],
            [(0, 0, 'cam1', 0, ['detect_a']),
             (0, 2, 'cam3', 0, ['detect_a']),
             (0, 2, 'cam3', 1, ['detect_b']),
             (1, 0, 'cam1', 0, ['detect_a']),
             (1, 2, 'cam3', 0, ['detect_a']),
             (1, 2, 'cam3', 1, ['detect_b'])])


if __name__ == '__main__':
    unittest.main()
