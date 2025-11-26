# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
SIEV Logging Package - Centralized logging infrastructure for SIEV framework.

This package provides:
- SievLogger: Core logging class with structured output
- ProgressTracker: Real-time progress tracking with ETA
- Custom formatters for console and file output
- Context injection for evaluation metadata
"""

from .logger import SievLogger
from .progress import ProgressTracker
from .formatters import ConsoleFormatter, JSONFormatter, ProgressFormatter
from .settings import load_config, setup_experiment_context, get_experiment_config

__all__ = [
    'SievLogger',
    'ProgressTracker', 
    'ConsoleFormatter',
    'JSONFormatter',
    'ProgressFormatter',
    'load_config',
    'setup_experiment_context',
    'get_experiment_config'
]

__version__ = '1.0.0'