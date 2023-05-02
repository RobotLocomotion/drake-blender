# SPDX-License-Identifier: BSD-2-Clause

import test.unittest_path_cleaner  # Disable Ubuntu packages.

from pathlib import Path
import signal
import socket
import subprocess
import time
import unittest

import numpy as np


class ServerTest(unittest.TestCase):

    def test_listen(self):
        """Checks that the server boots and starts listening."""
        # Find the server.
        server_path = Path("server").absolute().resolve()
        self.assertTrue(server_path.exists(), server_path)
        # Launch it in the background.
        server_proc = subprocess.Popen([server_path])
        # Wait for it to start accepting connections.
        start_time = time.time()
        while time.time() < start_time + 30.0:
            with socket.socket() as s:
                try:
                    s.connect(("127.0.0.1", 8000))
                    # Success!
                    break
                except ConnectionRefusedError as e:
                    time.sleep(0.1)
        else:
            self.fail("Could not connect after 30 seconds")
        server_proc.terminate()
        self.assertEqual(server_proc.wait(1.0), -signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
