import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer
from profile_template_app import Worker


class WorkerTests(unittest.TestCase):
    def test_background_conversion_reports_completion(self):
        app = QApplication.instance() or QApplication([])
        worker = Worker(['input.xlsx'], 'template.xlsx', 'output')
        results = []
        loop = QEventLoop()
        worker.completed.connect(lambda count, errors: results.append((count, errors)))
        worker.finished.connect(loop.quit)
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        with patch('profile_template_app.convert_file', return_value=['output/report.xlsx']) as convert:
            worker.start()
            timer.start(5000)
            loop.exec()
            timer.stop()
            self.assertTrue(worker.wait(5000))
            app.processEvents()
            convert.assert_called_once()
        self.assertEqual(results, [(1, 0)])
