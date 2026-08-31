import json
import os
import pty
import select
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from tools.capture_episode import classify_input


class CaptureKeyboardInputTest(unittest.TestCase):
    def test_digit_is_annotation(self) -> None:
        self.assertEqual(classify_input(b"1"), "annotation")

    def test_enter_stops(self) -> None:
        self.assertEqual(classify_input(b"\r"), "stop")
        self.assertEqual(classify_input(b"\n"), "stop")

    def test_enter_without_annotation_stops(self) -> None:
        self.assertEqual(classify_input(b"\n"), "stop")

    def test_other_keys_do_nothing(self) -> None:
        self.assertEqual(classify_input(b"x"), "ignore")

    def test_rosbag_has_no_tty_and_digit_does_not_stop_episode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bin_dir = root / "bin"
            run_dir = root / "episode"
            bin_dir.mkdir()
            (run_dir / "logs").mkdir(parents=True)
            (run_dir / "run.json").write_text(json.dumps({"identity": {"label": "test"}}))
            ros2 = bin_dir / "ros2"
            ros2.write_text(
                "#!/usr/bin/env python3\n"
                "import os, signal, sys, time\n"
                "from pathlib import Path\n"
                "out = Path(sys.argv[sys.argv.index('--output') + 1])\n"
                "out.mkdir(parents=True)\n"
                "(out / 'rosbag2_0.db3').write_bytes(b'db')\n"
                "Path(os.environ['FAKE_STDIN_STATE']).write_text(str(os.isatty(0)))\n"
                "def stop(*_):\n"
                "    (out / 'metadata.yaml').write_text('rosbag2_bagfile_information: {}\\n')\n"
                "    raise SystemExit(0)\n"
                "signal.signal(signal.SIGINT, stop)\n"
                "while True: time.sleep(0.05)\n",
                encoding="utf-8",
            )
            publisher = bin_dir / "publisher-python"
            publisher.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "for _ in sys.stdin: pass\n",
                encoding="utf-8",
            )
            ros2.chmod(0o755)
            publisher.chmod(0o755)
            stdin_state = root / "rosbag_stdin.txt"
            harness = f"""
from argparse import Namespace
from pathlib import Path
from tools.capture_episode import record_one
args = Namespace(
    compression_mode='none', compression_format='zstd', source_domain='real',
    arms=['right'], cameras=['/camera/camera'], camera_profile='test', duration=30,
    experiment_id='e', condition_id='c', operator_id='o', auditor_id='a', task_id='t',
    robot_ns='/robot1', teleop_ns='/teleop', annotation_state=Path(r'{root / 'state.json'}'),
    event_publisher_python=r'{publisher}', max_duration=10,
)
print('RESULT', record_one(args, Path(r'{run_dir}'), ['/test/topic']), flush=True)
"""
            environment = os.environ.copy()
            environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
            environment["FAKE_STDIN_STATE"] = str(stdin_state)
            environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
            master, slave = pty.openpty()
            process = subprocess.Popen(
                [sys.executable, "-c", harness], stdin=slave, stdout=slave, stderr=slave,
                env=environment, close_fds=True,
            )
            os.close(slave)

            def read_until(needle: bytes, timeout: float = 5.0) -> bytes:
                output = bytearray()
                deadline = time.monotonic() + timeout
                while needle not in output and time.monotonic() < deadline:
                    ready, _, _ = select.select([master], [], [], 0.1)
                    if ready:
                        try:
                            output.extend(os.read(master, 4096))
                        except OSError:
                            break
                return bytes(output)

            try:
                self.assertIn(b"[REC 00:00]", read_until(b"[REC 00:00]"))
                os.write(master, b"1")
                self.assertIn(b"AUDIT #1", read_until(b"AUDIT #1"))
                time.sleep(0.2)
                self.assertIsNone(process.poll(), "annotation digit unexpectedly stopped recorder")
                os.write(master, b"\n")
                output = read_until(b"RESULT", timeout=8.0)
                process.wait(timeout=3)
                self.assertIn(b"RESULT (True", output)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=3)
                os.close(master)
            self.assertEqual(stdin_state.read_text(), "False")
            events = (run_dir / "artifacts/audit_events.jsonl").read_text().splitlines()
            self.assertEqual(len(events), 1)


if __name__ == "__main__":
    unittest.main()
