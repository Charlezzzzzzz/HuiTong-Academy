import pathlib
import sys
import unittest
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from server import _auth_attempt_key, _auth_throttle_status, _clear_auth_failures, _record_auth_failure


class TestAuthThrottle(unittest.TestCase):
    def test_five_failures_enter_temporary_lockout(self):
        handler = SimpleNamespace(client_address=("127.0.0.1", 1234))
        key = _auth_attempt_key(handler, "admin")
        _clear_auth_failures(key)
        for _ in range(5):
            _record_auth_failure(key)
        self.assertGreater(_auth_throttle_status(key), 0)
        _clear_auth_failures(key)
        self.assertEqual(_auth_throttle_status(key), 0)


if __name__ == "__main__":
    unittest.main()
