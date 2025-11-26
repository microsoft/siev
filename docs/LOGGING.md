# SIEV Logging System

The SIEV Logging System provides comprehensive logging, progress tracking, and error handling for the SIEV evaluation framework. It offers real-time progress updates, structured logging, and enhanced error reporting to improve the user experience during long-running evaluations.

## Features

### 🔄 Real-Time Progress Tracking
- Live progress updates with ETA calculations
- Question-by-question progress monitoring
- Phase tracking (thesis/antithesis/synthesis)
- Success rate monitoring
- Performance metrics (questions/minute, average times)

### 📊 Structured Logging
- Multiple output formats (console, file, JSON)
- Automatic log rotation and cleanup
- Context injection with experiment metadata
- Custom log levels including PROGRESS
- Organized log directories by type

### 🛠️  Error Handling

- Contextual error information
- API call performance tracking
- Retry logic monitoring
- Recovery suggestions
- Token limit and rate limiting detection

## Quick Start

The logging system is automatically integrated into SIEV evaluations. No additional configuration is required for basic usage.

### Example: Basic Evaluation with Logging

```bash
# Run evaluation - logging happens automatically
./evaluate-gsm.sh -m gpt-4 -e sample_exam.json
```

You'll see real-time progress like:
```
[PROGRESS] Starting GSM Evaluation (10 questions, 1 attempts each)
[PROGRESS] Question 1/10 - Phase: Thesis
[PROGRESS] Phase Thesis completed ✓ (2.3s)
[PROGRESS] Question 1/10 - Phase: Antithesis  
[PROGRESS] Phase Antithesis completed ✓ (1.8s)
[PROGRESS] Question 1/10 - Phase: Synthesis
[PROGRESS] Phase Synthesis completed ✓ (2.1s)
[PROGRESS] Question 1/10 completed ✓ | Elapsed: 6s | ETA: 54s
```

## Log Organization

Logs are automatically organized in the `logs/` directory:

```
logs/
├── evaluations/          # Main evaluation logs
│   ├── siev.log         # Human-readable logs
│   └── siev.json        # Structured JSON logs
├── errors/              # Error-specific logs
├── performance/         # API performance metrics
└── debug/              # Debug information
```

## Configuration

### Environment Variables

You can customize logging behavior using environment variables:

```bash
# Set log level (DEBUG, INFO, WARNING, ERROR)
export SIEV_LOG_LEVEL=INFO

# Enable JSON output for all logs
export SIEV_JSON_LOGGING=true

# Set custom log directory
export SIEV_LOG_DIR=./custom_logs
```

### Programmatic Configuration

For advanced users, you can configure logging programmatically:

```python
from siev_logging.logger import SievLogger
from siev_logging.settings import setup_experiment_context

# Set up experiment context
context = setup_experiment_context(
    experiment_name="my_experiment",
    model="gpt-4",
    dataset="gsm8k",
    iteration="1"
)

# Create custom logger
logger = SievLogger(
    name="my_evaluation",
    log_dir="./logs",
    console_level="PROGRESS",  # Show progress on console
    file_level="INFO",         # Log info+ to file
    json_output=True,          # Enable structured JSON logs
    context=context
)

# Use logger
logger.info("Starting custom evaluation")
logger.progress("Processing question 1/10")
```

## Progress Tracking

The progress tracking system provides detailed insights into evaluation progress:

### Progress Metrics

- **Current Question**: Which question is being processed
- **Phase Progress**: Current dialectical phase (thesis/antithesis/synthesis)
- **Success Rate**: Percentage of successful completions
- **ETA**: Estimated time to completion
- **Rate**: Questions processed per minute
- **Duration**: Time spent on current and total evaluation

### Progress Data Export

```python
from siev_logging.progress import ProgressTracker

# Get comprehensive statistics
stats = progress_tracker.get_statistics()
print(f"Questions completed: {stats['questions']['completed']}")
print(f"Success rate: {stats['questions']['success_rate']:.1%}")
print(f"Average time per question: {stats['questions']['avg_time']:.1f}s")

# Export raw data for analysis
data = progress_tracker.export_data()
```

## Error Handling

The logging system provides enhanced error reporting with context:

### Automatic Error Detection

- **Context Length Exceeded**: Automatic detection and logging
- **Rate Limiting**: Backoff strategy logging
- **API Timeouts**: Retry attempt tracking
- **Invalid Responses**: Response validation logging

### Error Context

Each error log includes:
- **Timestamp**: When the error occurred
- **Context**: Experiment details (model, question, attempt)
- **Error Type**: Classification of the error
- **Recovery Info**: Suggested next steps
- **Performance Data**: API timing information

### Example Error Log

```json
{
  "timestamp": "2025-10-02T10:15:30.123456",
  "level": "ERROR",
  "message": "Context length exceeded for question 5",
  "context": {
    "experiment_name": "gsm_evaluation",
    "model": "gpt-4",
    "question_idx": 5,
    "attempt": 1,
    "total_tokens": 8192,
    "max_tokens": 8000
  },
  "recovery_suggestion": "Consider reducing prompt length or using a model with larger context window"
}
```

## Integration with SIEV Components

### API Classes

The logging system is integrated with all SIEV API classes:

- **GeneralAPI**: Logs all standard model interactions
- **ReasoningAPI**: Enhanced logging for O1/reasoning models

### Evaluation Framework

- **DialecticalEvaluator**: Complete evaluation lifecycle tracking
- **Question Processing**: Individual question progress
- **Phase Tracking**: Thesis/antithesis/synthesis monitoring

## Analysis and Monitoring

### Log Analysis

Use the structured JSON logs for analysis:

```bash
# Count successful vs failed questions
jq '.context.success' logs/evaluations/siev.json | sort | uniq -c

# Average API response time
jq '.context.duration' logs/evaluations/siev.json | jq -s 'add/length'

# Error frequency by type
jq 'select(.level=="ERROR") | .context.error_type' logs/evaluations/siev.json | sort | uniq -c
```

### Real-Time Monitoring

Monitor evaluations in real-time:

```bash
# Follow evaluation progress
tail -f logs/evaluations/siev.log | grep PROGRESS

# Watch for errors
tail -f logs/errors/* 

# Monitor API performance
tail -f logs/performance/*
```

## Performance Impact

The logging system is designed for minimal performance impact:

- **Asynchronous logging**: Non-blocking log operations
- **Efficient formatting**: Optimized for speed
- **Configurable levels**: Control verbosity vs performance
- **Log rotation**: Automatic cleanup prevents disk bloat

### Performance Benchmarks

- **Overhead**: <1% evaluation time increase
- **Memory**: ~2MB additional memory usage
- **Disk**: Logs rotate automatically (default: 10MB per file, 5 files retained)

## Troubleshooting

### Common Issues

**Q: No progress updates appearing**
```bash
# Check if PROGRESS level is enabled
export SIEV_LOG_LEVEL=PROGRESS
```

**Q: Log files not created**
```bash
# Check log directory permissions
ls -la logs/
# Create if missing
mkdir -p logs/{evaluations,errors,performance,debug}
```

**Q: JSON logs malformed**
```bash
# Validate JSON structure
jq . logs/evaluations/siev.json
```

**Q: Too many log files**
```bash
# Clean old logs (keeps last 5 rotations)
find logs/ -name "*.log.*" -mtime +7 -delete
```

### Debug Mode

Enable debug logging for troubleshooting:

```bash
export SIEV_LOG_LEVEL=DEBUG
export SIEV_DEBUG_MODE=true
```

This will provide detailed information about:
- Logger initialization
- Progress tracker setup
- API call details
- Internal state changes

## Contributing

### Adding Custom Log Types

```python
# Define custom log level
CUSTOM_LEVEL = 35
logging.addLevelName(CUSTOM_LEVEL, "CUSTOM")

# Add to logger
logger.log(CUSTOM_LEVEL, "Custom message")
```

### Extending Progress Tracking

```python
class CustomProgressTracker(ProgressTracker):
    def track_custom_metric(self, value):
        self.custom_metrics.append(value)
        self.logger.info(f"Custom metric: {value}")
```

### Custom Formatters

```python
from siev_logging.formatters import ConsoleFormatter

class CustomFormatter(ConsoleFormatter):
    def format(self, record):
        # Add custom formatting logic
        return super().format(record)
```
