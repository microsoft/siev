# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
SIEV Progress Tracker - Real-time progress tracking with ETA calculations.

Provides:
- Question-level progress tracking
- Dialectical phase tracking (Thesis → Antithesis → Synthesis)
- ETA calculations based on historical performance
- Rate calculations (questions/minute)
- Success/failure tracking
"""

import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta


class ProgressTracker:
    """
    Real-time progress tracker for SIEV evaluations.
    
    Features:
    - Multi-level progress tracking (questions, attempts, phases)
    - ETA calculations based on moving averages
    - Success/failure rate tracking
    - Phase timing for dialectical cycles
    - Export capabilities for analysis
    """
    
    PHASES = ["thesis", "antithesis", "synthesis"]
    
    def __init__(self, 
                 total_questions: int,
                 total_attempts: int = 1,
                 experiment_name: str = "evaluation",
                 logger = None):
        """
        Initialize progress tracker.
        
        Args:
            total_questions: Total number of questions to process
            total_attempts: Number of attempts per question
            experiment_name: Name of the experiment for context
            logger: Optional logger for progress updates
        """
        
        self.total_questions = total_questions
        self.total_attempts = total_attempts
        self.experiment_name = experiment_name
        self.logger = logger
        
        # Progress state
        self.current_question = 0
        self.current_attempt = 0
        self.current_phase = None
        self.start_time = time.time()
        
        # Timing data
        self.question_times = []  # List of question completion times
        self.phase_times = {}     # Phase timing within current question
        self.phase_start_time = None
        
        # Success tracking
        self.successful_questions = 0
        self.failed_questions = 0
        self.phase_success_rates = {phase: [] for phase in self.PHASES}
        
        # History for ETA calculations
        self.completion_history = []
        self.rate_window = 10  # Number of recent completions to use for rate
        
    def start_evaluation(self):
        """Start the evaluation tracking."""
        self.start_time = time.time()
        if self.logger:
            self.logger.progress(
                f"Starting {self.experiment_name} evaluation ({self.total_questions} questions)"
            )
    
    def start_question(self, question_num: int):
        """Start processing a new question."""
        self.current_question = question_num
        self.current_attempt = 1
        self.current_phase = None
        self.question_start_time = time.time()
        
        if self.logger:
            progress_data = self._get_progress_data()
            self.logger.progress(
                f"Question {question_num}/{self.total_questions}",
                extra={"progress_data": progress_data}
            )
    
    def start_attempt(self, attempt_num: int):
        """Start a new attempt for the current question."""
        self.current_attempt = attempt_num
        self.attempt_start_time = time.time()
        
        if self.logger:
            self.logger.progress(
                f"Question {self.current_question}/{self.total_questions} - Attempt {attempt_num}/{self.total_attempts}"
            )
    
    def enter_phase(self, phase: str):
        """Enter a new dialectical phase."""
        if phase not in self.PHASES:
            raise ValueError(f"Invalid phase: {phase}. Must be one of {self.PHASES}")
        
        self.current_phase = phase
        self.phase_start_time = time.time()
        
        if self.logger:
            self.logger.progress(
                f"Question {self.current_question}/{self.total_questions} - Phase: {phase.title()}"
            )
    
    def complete_phase(self, phase: str, success: bool = True, **kwargs):
        """Complete a dialectical phase."""
        if self.phase_start_time is None:
            return
        
        phase_duration = time.time() - self.phase_start_time
        
        # Record phase timing
        if self.current_question not in self.phase_times:
            self.phase_times[self.current_question] = {}
        
        self.phase_times[self.current_question][phase] = {
            "duration": phase_duration,
            "success": success,
            "timestamp": time.time(),
            **kwargs
        }
        
        # Track success rates
        self.phase_success_rates[phase].append(success)
        
        if self.logger:
            status = "✓" if success else "✗"
            self.logger.progress(
                f"Phase {phase.title()} completed {status} ({phase_duration:.1f}s)"
            )
        
        self.phase_start_time = None
    
    def complete_question(self, success: bool = True):
        """Complete the current question."""
        if hasattr(self, 'question_start_time'):
            question_duration = time.time() - self.question_start_time
            self.question_times.append(question_duration)
            
            # Add to completion history for ETA calculation
            self.completion_history.append({
                "question": self.current_question,
                "duration": question_duration,
                "timestamp": time.time(),
                "success": success
            })
        
        # Update success counters
        if success:
            self.successful_questions += 1
        else:
            self.failed_questions += 1
        
        if self.logger:
            status = "✓" if success else "✗"
            elapsed = self._format_duration(time.time() - self.start_time)
            eta = self._calculate_eta()
            eta_str = self._format_duration(eta) if eta > 0 else "unknown"
            
            self.logger.progress(
                f"Question {self.current_question}/{self.total_questions} completed {status} | "
                f"Elapsed: {elapsed} | ETA: {eta_str}"
            )
    
    def complete_evaluation(self):
        """Complete the entire evaluation."""
        total_duration = time.time() - self.start_time
        success_rate = self.successful_questions / max(1, self.successful_questions + self.failed_questions)
        
        if self.logger:
            self.logger.progress(
                f"Evaluation completed! {self.successful_questions}/{self.total_questions} successful "
                f"({success_rate:.1%}) in {self._format_duration(total_duration)}"
            )
    
    def _get_progress_data(self) -> Dict[str, Any]:
        """Get current progress data for formatting."""
        return {
            "current": self.current_question,
            "total": self.total_questions,
            "eta_seconds": self._calculate_eta(),
            "rate": self._calculate_rate(),
            "success_rate": self._calculate_success_rate()
        }
    
    def _calculate_eta(self) -> float:
        """Calculate estimated time to completion."""
        if len(self.completion_history) < 2:
            return 0
        
        # Use recent completions for rate calculation
        recent_completions = self.completion_history[-self.rate_window:]
        if len(recent_completions) < 2:
            return 0
        
        # Calculate average time per question
        durations = [c["duration"] for c in recent_completions]
        avg_duration = sum(durations) / len(durations)
        
        # Remaining questions
        remaining = self.total_questions - self.current_question
        
        return remaining * avg_duration
    
    def _calculate_rate(self) -> float:
        """Calculate questions per minute."""
        if not self.completion_history:
            return 0
        
        elapsed = time.time() - self.start_time
        return (len(self.completion_history) / elapsed) * 60 if elapsed > 0 else 0
    
    def _calculate_success_rate(self) -> float:
        """Calculate current success rate."""
        total = self.successful_questions + self.failed_questions
        return self.successful_questions / total if total > 0 else 0
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable string."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.0f}m{seconds % 60:.0f}s"
        else:
            hours = seconds / 3600
            minutes = (seconds % 3600) / 60
            return f"{hours:.0f}h{minutes:.0f}m"
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive progress statistics."""
        total_elapsed = time.time() - self.start_time
        
        # Question statistics
        question_stats = {
            "completed": len(self.question_times),
            "successful": self.successful_questions,
            "failed": self.failed_questions,
            "success_rate": self._calculate_success_rate(),
            "avg_time": sum(self.question_times) / len(self.question_times) if self.question_times else 0,
            "questions_per_minute": self._calculate_rate()
        }
        
        # Phase statistics
        phase_stats = {}
        for phase in self.PHASES:
            successes = sum(1 for success in self.phase_success_rates[phase] if success)
            total = len(self.phase_success_rates[phase])
            phase_stats[phase] = {
                "attempts": total,
                "successes": successes,
                "success_rate": successes / total if total > 0 else 0
            }
        
        # Overall statistics
        return {
            "experiment": self.experiment_name,
            "total_elapsed": total_elapsed,
            "questions": question_stats,
            "phases": phase_stats,
            "eta": self._calculate_eta(),
            "progress_percentage": (self.current_question / self.total_questions) * 100
        }
    
    def export_data(self) -> Dict[str, Any]:
        """Export all tracking data for analysis."""
        return {
            "config": {
                "total_questions": self.total_questions,
                "total_attempts": self.total_attempts,
                "experiment_name": self.experiment_name
            },
            "timing": {
                "start_time": self.start_time,
                "question_times": self.question_times,
                "phase_times": self.phase_times,
                "completion_history": self.completion_history
            },
            "results": {
                "successful_questions": self.successful_questions,
                "failed_questions": self.failed_questions,
                "phase_success_rates": self.phase_success_rates
            },
            "statistics": self.get_statistics()
        }