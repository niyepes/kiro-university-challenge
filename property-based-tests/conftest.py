# Copyright AnyCompany
"""Pytest configuration for the property-based test suite.

Ensures this directory is importable so ``customer_logic`` and ``strategies``
resolve regardless of the directory pytest is launched from.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
