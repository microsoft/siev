# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
SIEV Core Logger - Centralized logging with context injection and progress tracking.

Provides structured logging for the SIEV framework with:
- Multiple output handlers (console, file, error)
- Context injection for evaluation metadata  
- Performance tracking capabilities
- Log rotation and cleanup
- Custom log levels including PROGRESS
"""

import logging
import logging.handlers
import json
import sys
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union
from .formatters import ConsoleFormatter, JSONFormatter, ProgressFormatter


class SievLogger:
    """
    Core logger for SIEV framework with context injection and structured output.
    
    Features:
    - Custom PROGRESS log level (25) between INFO and WARNING
    - Context injection for all log messages
    - Multiple handlers: console, file, error-only, JSON
    - Performance tracking for API calls and operations
    - Automatic log rotation and cleanup
    """
    
    # Custom log levels
    PROGRESS = 25
    
    def __init__(self, 
                 name: str,
                 log_dir: str = "logs",
                 console_level: str = "PROGRESS",
                 file_level: str = "INFO",
                 error_level: str = "WARNING",
                 json_output: bool = False,
                 rotation_size: str = "10MB",
                 rotation_count: int = 5,
                 context: Optional[Dict[str, Any]] = None):
        """
        Initialize SIEV logger with configuration.
        
        Args:
            name: Logger name (usually module name)
            log_dir: Directory for log files
            console_level: Console output level
            file_level: File output level  
            error_level: Error file level
            json_output: Enable JSON structured logging
            rotation_size: Log rotation size
            rotation_count: Number of rotated files to keep
            context: Default context to inject in all messages
        """
        
        # Add custom PROGRESS level
        logging.addLevelName(self.PROGRESS, "PROGRESS")
        
        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)  # Set to lowest level, handlers will filter
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Set up log directory
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.log_dir / "evaluations").mkdir(exist_ok=True)
        (self.log_dir / "errors").mkdir(exist_ok=True) 
        (self.log_dir / "performance").mkdir(exist_ok=True)
        (self.log_dir / "debug").mkdir(exist_ok=True)
        
        # Store configuration - handle custom PROGRESS level
        if console_level.upper() == "PROGRESS":
            self.console_level = self.PROGRESS
        else:
            self.console_level = getattr(logging, console_level.upper())
        
        self.file_level = getattr(logging, file_level.upper())
        self.error_level = getattr(logging, error_level.upper())
        self.json_output = json_output
        self.context = context or {}
        
        # Performance tracking
        self.api_calls = []
        self.operation_times = {}
        self.start_time = time.time()
        
        # Set up handlers
        self._setup_handlers(rotation_size, rotation_count)
        
    def _setup_handlers(self, rotation_size: str, rotation_count: int):
        """Set up logging handlers for console, file, and error output."""
        
        # Console handler with progress formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.console_level)
        console_handler.setFormatter(ConsoleFormatter())
        self.logger.addHandler(console_handler)
        
        # Main log file handler with rotation
        main_log = self.log_dir / "evaluations" / "siev.log"
        file_handler = logging.handlers.RotatingFileHandler(
            main_log,
            maxBytes=self._parse_size(rotation_size),
            backupCount=rotation_count
        )
        file_handler.setLevel(self.file_level)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        self.logger.addHandler(file_handler)
        
        # Error-only file handler
        error_log = self.log_dir / "errors" / "errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log,
            maxBytes=self._parse_size("5MB"),
            backupCount=3
        )
        error_handler.setLevel(self.error_level)
        error_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s - Context: %(context)s'
        ))
        self.logger.addHandler(error_handler)
        
        # JSON handler if enabled
        if self.json_output:
            json_log = self.log_dir / "evaluations" / "siev.json"
            json_handler = logging.FileHandler(json_log)
            json_handler.setLevel(self.file_level)
            json_handler.setFormatter(JSONFormatter())
            self.logger.addHandler(json_handler)
    
    def _parse_size(self, size_str: str) -> int:
        """Parse size string like '10MB' to bytes."""
        size_str = size_str.upper()
        if size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)
    
    def _inject_context(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Inject context into log message extras."""
        context = self.context.copy()
        if extra:
            context.update(extra)
        return {"context": context}
    
    def progress(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log progress message with custom PROGRESS level and experiment context."""
        # Create log record manually to add experiment context attributes
        record_extra = self._inject_context(extra)
        
        # Extract experiment context for the formatter
        context = record_extra.get('context', {})
        
        # Create the log record
        record = self.logger.makeRecord(
            self.logger.name, self.PROGRESS, "", 0, message, (), None, extra=record_extra
        )
        
        # Add experiment context as direct attributes for the formatter
        if 'experiment_name' in context:
            record.experiment_name = context['experiment_name']
        if 'try_index' in context:
            record.try_index = context['try_index']
        
        # Log the record
        self.logger.handle(record)
    
    def info(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log info message with context."""
        self.logger.info(message, extra=self._inject_context(extra))
    
    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log debug message with context."""
        self.logger.debug(message, extra=self._inject_context(extra))
    
    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log warning message with context."""
        self.logger.warning(message, extra=self._inject_context(extra))
    
    def error(self, message: str, exception: Optional[Exception] = None, 
              extra: Optional[Dict[str, Any]] = None):
        """Log error message with context and optional exception."""
        context_extra = self._inject_context(extra)
        if exception:
            context_extra["context"]["exception"] = {
                "type": type(exception).__name__,
                "message": str(exception),
                "traceback": str(exception.__traceback__) if exception.__traceback__ else None
            }
        self.logger.error(message, extra=context_extra)
    
    def update_context(self, **kwargs):
        """Update the default context for this logger."""
        self.context.update(kwargs)
    
    def set_context(self, context: Dict[str, Any]):
        """Replace the entire context for this logger."""
        self.context = context
    
    def log_api_call(self, 
                     endpoint: str,
                     duration: float,
                     tokens_used: Optional[int] = None,
                     cost: Optional[float] = None,
                     success: bool = True,
                     retry_count: int = 0):
        """Log API call performance metrics."""
        call_data = {
            "endpoint": endpoint,
            "duration_ms": duration * 1000,
            "tokens_used": tokens_used,
            "cost": cost,
            "success": success,
            "retry_count": retry_count,
            "timestamp": time.time()
        }
        
        self.api_calls.append(call_data)
        
        # Use DEBUG level for performance logs to keep console clean
        level = "debug" if success else "warning"
        message = f"API call to {endpoint}: {duration:.0f}ms"
        if tokens_used:
            message += f", {tokens_used} tokens"
        if retry_count > 0:
            message += f", {retry_count} retries"
            
        getattr(self, level)(message, extra={"api_call": call_data})
    
    def start_operation(self, operation: str) -> str:
        """Start timing an operation."""
        operation_id = f"{operation}_{time.time()}"
        self.operation_times[operation_id] = {
            "operation": operation,
            "start_time": time.time()
        }
        self.debug(f"Started operation: {operation}", extra={"operation_id": operation_id})
        return operation_id
    
    def end_operation(self, operation_id: str, success: bool = True, 
                      extra: Optional[Dict[str, Any]] = None):
        """End timing an operation."""
        if operation_id not in self.operation_times:
            self.warning(f"Operation ID not found: {operation_id}")
            return
        
        op_data = self.operation_times[operation_id]
        duration = time.time() - op_data["start_time"]
        op_data.update({
            "end_time": time.time(),
            "duration": duration,
            "success": success
        })
        
        level = "info" if success else "error"
        message = f"Completed operation: {op_data['operation']} ({duration:.2f}s)"
        
        log_extra = {"operation": op_data}
        if extra:
            log_extra.update(extra)
            
        getattr(self, level)(message, extra=log_extra)
        del self.operation_times[operation_id]
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for this logger session."""
        total_runtime = time.time() - self.start_time
        
        # API call statistics
        successful_calls = [call for call in self.api_calls if call["success"]]
        failed_calls = [call for call in self.api_calls if not call["success"]]
        
        api_stats = {
            "total_calls": len(self.api_calls),
            "successful_calls": len(successful_calls),
            "failed_calls": len(failed_calls),
            "success_rate": len(successful_calls) / len(self.api_calls) if self.api_calls else 0,
            "avg_duration_ms": sum(call["duration_ms"] for call in self.api_calls) / len(self.api_calls) if self.api_calls else 0,
            "total_tokens": sum(call["tokens_used"] or 0 for call in self.api_calls),
            "total_cost": sum(call["cost"] or 0 for call in self.api_calls)
        }
        
        return {
            "session_duration": total_runtime,
            "api_statistics": api_stats,
            "context": self.context
        }