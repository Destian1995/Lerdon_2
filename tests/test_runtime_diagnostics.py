import unittest
from unittest.mock import patch

import runtime_diagnostics as diagnostics


class CaughtExceptionTests(unittest.TestCase):
    def test_records_original_traceback_without_console(self):
        try:
            raise RuntimeError('turn failed')
        except RuntimeError as error:
            with patch.object(diagnostics, '_crash_fd', 42), patch.object(diagnostics.os, 'write') as write:
                diagnostics.record_exception('Campaign turn failed', error)
        descriptor, content = write.call_args.args
        self.assertEqual(descriptor, 42)
        message = content.decode('utf-8')
        self.assertIn('Campaign turn failed', message)
        self.assertIn('test_runtime_diagnostics.py', message)
        self.assertIn('RuntimeError: turn failed', message)

    def test_full_disk_does_not_raise_another_exception(self):
        with patch.object(diagnostics, '_crash_fd', 42), patch.object(diagnostics.os, 'write', side_effect=OSError(28, 'full')):
            diagnostics.record_exception('Campaign turn failed', RuntimeError('original'))


if __name__ == '__main__':
    unittest.main()
