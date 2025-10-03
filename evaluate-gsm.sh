#!/bin/bash
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

#==============================================================================
# SIEV GSM-8K Dialectical Evaluation Script
#==============================================================================
#
# This script runs dialectical reasoning evaluation on the GSM-8K mathematical
# reasoning benchmark. It implements the Hegelian thesis-antithesis-synthesis
# methodology to assess model performance under critical challenge.
#
# USAGE:
#   ./evaluate-gsm.sh <model> <experiment_name> <environment_file>
#
# ARGUMENTS:
#   model            - Model identifier (auto-routed to appropriate API)
#   experiment_name  - Name for output directory and logs  
#   environment_file - Path to configuration file with API credentials
#
# MODEL ROUTING:
#   General API:   gpt-4o, gpt-5-chat, claude-3.5-sonnet, llama-3.1-70b
#   Reasoning API: o1-preview, gpt-5-2025-08-07, o3-mini
#
# OUTPUT:
#   - Experiment results: data/experiments/{experiment_name}/
#   - SIEV logs: logs/evaluations/gsm/{experiment_name}.log
#   - Dialectical responses: thesis, antithesis, synthesis JSON files
#
# EXAMPLES:
#   ./evaluate-gsm.sh "gpt-4o" "gsm-gpt4-baseline" "env/.env"  
#   ./evaluate-gsm.sh "o1-preview" "gsm-o1-reasoning" ".env.example"
#
#==============================================================================

# Validate command line arguments
if [ $# -ne 5 ]; then
    echo "❌ Error: Invalid number of arguments"
    echo ""
    echo "Usage: $0 <model> <exp_name> <env_file> <num_attempts> <exam_path>"
    echo ""
    echo "Arguments:"
    echo "  model         - Model identifier for evaluation"
    echo "  exp_name      - Experiment name for output directory"
    echo "  env_file      - Environment configuration file"
    echo "  num_attempts  - Number of evaluation attempts (required)"
    echo "  exam_path     - Path to exam JSON file (required)"
    echo ""
    echo "Model Examples:"
    echo "  General:   gpt-4o, gpt-5-chat, claude-3.5-sonnet, llama-3.1-70b" 
    echo "  Reasoning: o1-preview, gpt-5-2025-08-07, o3-mini"
    echo ""
    echo "Examples:"
    echo "  $0 'gpt-4o' 'gsm-gpt4-test' 'env/.env' 3 'data/input/gsm_data/sample_exam.json'"
    echo "  $0 'o1-preview' 'gsm-o1-test' 'env/.env' 5 'data/input/gsm_data/full_gsm.json'"
    exit 1
fi

#==============================================================================
# Configuration Variables
#==============================================================================

# Input dataset configuration
exams="$5"  # Exam path (required argument)

# Model configuration  
models="$1"      # Primary model for evaluation
model2="$1"      # Secondary model (same as primary for single-model eval)

# Dialectical evaluation parameters
attempts="$4"        # Number of evaluation attempts (required argument)
redact=1             # Whether to redact model responses in logs (1=yes, 0=no)

# Output configuration
test_name="$2"                              # Experiment name from user input
output_dir="data/experiments/${test_name}"  # Results directory
env="$3"                                    # Environment configuration file

for model in $models; do
    model2=$model
    echo "Running Thesis Model: $model, Antithesis Model: $model2"
    model_name=$(basename $model)
    bash scripts/experiments/run_gsm_experiments.sh \
        ${env} ${output_dir} "$exams" $attempts $model $model2 $redact
done

