import os
from pathlib import Path
import subprocess
import tempfile
import unittest


HEALTHCHECK = Path(__file__).with_name("healthcheck.sh")


class HealthcheckTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.media = self.root / "media"
        self.media.mkdir()
        self.probe = self.root / "ffprobe"
        self.probe.write_text(
            '#!/bin/sh\n'
            'for arg do url=$arg; done\n'
            'printf "%s\\n" "$url" >> "$PROBE_LOG"\n'
            'case "$url" in\n'
            '  *unavailable) echo "Not Found (404)" >&2; exit 1 ;;\n'
            '  *audio-only) exit 0 ;;\n'
            '  *stalled) echo 0 ;;\n'
            '  *) echo 1 ;;\n'
            'esac\n',
            encoding="utf-8",
        )
        self.probe.chmod(0o755)
        self.log = self.root / "probes"

    def run_check(self, *names, port="8554"):
        for name in names:
            (self.media / name).touch()
        return subprocess.run(
            ["sh", str(HEALTHCHECK)],
            env={
                **os.environ,
                "MEDIA_DIR": str(self.media),
                "RTSP_PORT": port,
                "FFPROBE_BIN": str(self.probe),
                "PROBE_LOG": str(self.log),
            },
            text=True,
            capture_output=True,
            timeout=15,
        )

    def test_all_streams_must_deliver_packets(self):
        result = self.run_check("first.mp4", "last.mp4", "README.md")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(self.log.read_text().splitlines()), {
            "rtsp://127.0.0.1:8554/first",
            "rtsp://127.0.0.1:8554/last",
        })

    def test_one_unavailable_stream_blocks_readiness(self):
        result = self.run_check("ready.mp4", "unavailable.mp4")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unavailable is not ready", result.stderr)
        self.assertIn("Not Found (404)", result.stderr)
        self.assertEqual(len(self.log.read_text().splitlines()), 2)

    def test_audio_only_stream_is_not_ready(self):
        result = self.run_check("audio-only.mp4")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not delivering video packets", result.stderr)

    def test_zero_video_packets_is_not_ready(self):
        result = self.run_check("stalled.mp4")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not delivering video packets", result.stderr)

    def test_empty_media_directory_is_not_ready(self):
        result = self.run_check("README.md")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No .mp4 files found", result.stderr)

    def test_missing_media_directory_is_not_ready(self):
        self.media.rmdir()
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No .mp4 files found", result.stderr)

    def test_custom_port_and_filename(self):
        result = self.run_check("video sample.v1.mp4", port="9554")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.log.read_text().strip(),
            "rtsp://127.0.0.1:9554/video sample.v1",
        )


if __name__ == "__main__":
    unittest.main()
