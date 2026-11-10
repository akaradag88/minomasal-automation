"""Offline readiness suite: prohibit network and video rendering.

The older synthetic MP4 integration case is excluded deliberately: this command
must never produce any video, including a local synthetic fixture.
"""
from pathlib import Path
import socket
import subprocess
import unittest
from unittest.mock import patch

MODULES = (
    'test_minomasal_actions_runtime', 'test_minomasal_11_kasim', 'test_minomasal_10_8',
    'test_minomasal_gunluk_kilit', 'test_minomasal_v4',
    'test_minomasal_v4_47_revize', 'test_minomasal_v4_47_sureklilik',
    'test_minomasal_v4_mantik_kontrol',
)
EXCLUDED = ('test_successful_receipt_can_move_and_missing_image_blocks_publish',)


def cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from cases(item)
        else:
            yield item


def main():
    original_run = subprocess.run

    def guarded_run(args, *rest, **kwargs):
        executable = args[0] if not isinstance(args, str) else args.split()[0]
        if Path(str(executable)).name == 'ffmpeg':
            raise AssertionError('Readiness tests must not render video.')
        return original_run(args, *rest, **kwargs)

    suite = unittest.TestSuite(
        test for test in cases(unittest.defaultTestLoader.loadTestsFromNames(MODULES))
        if test.id().split('.')[-1] not in EXCLUDED
    )
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network disabled')), \
         patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('Network disabled')), \
         patch.object(subprocess, 'run', side_effect=guarded_run):
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__': main()
