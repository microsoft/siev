# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
SIEV Custom Log Formatters - Specialized formatters for different output types.

Provides:
- ConsoleFormatter: Human-readable console output with colors
- JSONFormatter: Structured JSON output for machine processing
- ProgressFormatter: Specialized formatting for progress messages
"""

import logging
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any


class ConsoleFormatter(logging.Formatter):
    """
    Console formatter with color coding and progress-friendly output.
    
    Features:
    - Color coding by log level
    - Compact format for progress messages
    - Context information for errors
    - Timestamp formatting optimized for readability
    """
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green  
        'PROGRESS': '\033[34m',  # Blue
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def __init__(self, use_colors: bool = None):
        super().__init__()
        # Auto-detect color support
        self.use_colors = use_colors if use_colors is not None else self._supports_color()
    
    def _supports_color(self) -> bool:
        """Check if terminal supports colors."""
        return (
            hasattr(sys.stdout, 'isatty') and 
            sys.stdout.isatty() and 
            'TERM' in os.environ and 
            os.environ['TERM'] != 'dumb'
        )
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record for console output."""
        
        # Get color for log level
        color = self.COLORS.get(record.levelname, '') if self.use_colors else ''
        reset = self.COLORS['RESET'] if self.use_colors else ''
        
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        
        # Handle different log levels
        if record.levelname == 'PROGRESS':
            # Compact format for progress messages with experiment context
            message = record.getMessage()
            
            # Add experiment and attempt context if available
            if hasattr(record, 'experiment_name') and hasattr(record, 'try_index'):
                context_label = f"[{record.experiment_name} - Attempt {record.try_index}]"
                return f"{color}[PROGRESS]{reset} {context_label} {message}"
            elif hasattr(record, 'experiment_name'):
                context_label = f"[{record.experiment_name}]"
                return f"{color}[PROGRESS]{reset} {context_label} {message}"
            else:
                return f"{color}[PROGRESS]{reset} {message}"
        
        elif record.levelname in ['ERROR', 'CRITICAL']:
            # Detailed format for errors
            message = f"{color}[{record.levelname}]{reset} {timestamp} - {record.getMessage()}"
            
            # Add context if available
            if hasattr(record, 'context') and record.context:
                context_str = self._format_context(record.context)
                if context_str:
                    message += f"\n  Context: {context_str}"
            
            return message
        
        else:
            # Standard format for info, debug, warning
            return f"{color}[{record.levelname}]{reset} {timestamp} - {record.getMessage()}"
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context dictionary for display."""
        if not context:
            return ""
        
        # Extract key information
        key_items = []
        for key in ['experiment_name', 'model', 'question_num', 'attempt', 'phase']:
            if key in context:
                key_items.append(f"{key}={context[key]}")
        
        return ", ".join(key_items)


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging output.
    
    Features:
    - Complete log record as JSON
    - Context information preserved
    - Machine-readable format
    - Consistent field naming
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        
        # Base log data
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add context if available
        if hasattr(record, 'context') and record.context:
            log_data['context'] = record.context
        
        # Add exception info if available
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None
            }
        
        # Add any extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                          'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                          'thread', 'threadName', 'processName', 'process', 'context']:
                log_data[key] = value
        
        return json.dumps(log_data, default=str)


class ProgressFormatter(logging.Formatter):
    """
    Specialized formatter for progress tracking messages.
    
    Features:
    - Progress bar rendering
    - ETA calculations
    - Percentage completion
    - Rate information
    """
    
    def __init__(self, show_percentage: bool = True, show_eta: bool = True):
        super().__init__()
        self.show_percentage = show_percentage
        self.show_eta = show_eta
    
    def format(self, record: logging.LogRecord) -> str:
        """Format progress record with bar and statistics."""
        
        message = record.getMessage()
        
        # Check if this is a progress record with tracking data
        if hasattr(record, 'progress_data'):
            return self._format_progress(record.progress_data, message)
        
        # Fallback to regular message
        return f"[PROGRESS] {message}"
    
    def _format_progress(self, progress_data: Dict[str, Any], message: str) -> str:
        """Format progress data into a visual progress bar."""
        
        current = progress_data.get('current', 0)
        total = progress_data.get('total', 100)
        percentage = (current / total * 100) if total > 0 else 0
        
        # Build progress bar
        bar_width = 30
        filled = int(bar_width * current / total) if total > 0 else 0
        bar = '█' * filled + '░' * (bar_width - filled)
        
        # Build progress string
        progress_str = f"[{bar}] {current}/{total}"
        
        if self.show_percentage:
            progress_str += f" ({percentage:.1f}%)"
        
        if self.show_eta and 'eta_seconds' in progress_data:
            eta = progress_data['eta_seconds']
            if eta > 0:
                eta_str = self._format_duration(eta)
                progress_str += f" ETA: {eta_str}"
        
        if 'rate' in progress_data:
            rate = progress_data['rate']
            progress_str += f" ({rate:.1f}/min)"
        
        return f"{progress_str} - {message}"
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable string."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.0f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"


# Import os for color detection
import os