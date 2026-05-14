#!/usr/bin/env python3
"""Standalone launcher for Step3.1 multi-method segmentation comparator."""

import os
import sys


def _bootstrap_paths():
    here = os.path.abspath(os.path.dirname(__file__))
    parent = os.path.abspath(os.path.join(here, ".."))
    if here not in sys.path:
        sys.path.insert(0, here)
    if parent not in sys.path:
        sys.path.insert(0, parent)


def main():
    _bootstrap_paths()
    from PyQt5.QtWidgets import QApplication
    from ui.step3_compare_page import Step31ComparePage

    app = QApplication(sys.argv)
    win = Step31ComparePage()
    win.resize(1500, 950)
    win.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
