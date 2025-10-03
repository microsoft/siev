#!/bin/bash
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

#==============================================================================
# SIEV MMLU Dialectical Evaluation Script
#==============================================================================
#
# This script runs dialectical reasoning evaluation on the MMLU (Massive
# Multitask Language Understanding) benchmark. It implements the Hegelian
# thesis-antithesis-synthesis methodology to assess model performance across
# multiple academic domains under critical challenge.
#
# USAGE:
#   ./evaluate-mmlu.sh <model> <experiment_name> <environment_file> <num_attempts> <exam_path>
#
# ARGUMENTS:
#   model            - Model identifier (auto-routed to appropriate API)
#   experiment_name  - Name for output directory and logs
#   environment_file - Path to configuration file with API credentials
#   num_attempts     - Number of evaluation attempts for statistical analysis
#   exam_path        - Path to MMLU exam JSON file
#
# MODEL ROUTING:
#   General API:   gpt-4o, gpt-5-chat, claude-3.5-sonnet, llama-3.1-70b
#   Reasoning API: o1-preview, gpt-5-2025-08-07, o3-mini
#
# OUTPUT:
#   - Experiment results: data/experiments/{experiment_name}/
#   - SIEV logs: logs/evaluations/mmlu/{experiment_name}.log
#   - Domain-specific accuracy metrics and dialectical response analysis
#
# EXAMPLES:
#   ./evaluate-mmlu.sh "gpt-4o" "mmlu-gpt4-baseline" "env/.env" 3 "data/input/mmlu_dataset/sample_exam.json"
#   ./evaluate-mmlu.sh "o1-preview" "mmlu-o1-reasoning" ".env.example" 5 "data/input/mmlu_dataset/custom_exam.json"
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
    echo "  env_file      - Environment configuration file (required)"
    echo "  num_attempts  - Number of evaluation attempts (required)"
    echo "  exam_path     - Path to exam JSON file (required)"
    echo ""
    echo "Examples:"
    echo "  $0 'gpt-4o' 'mmlu-gpt4-test' 'env/.env' 3 'data/input/mmlu_dataset/sample_exam.json'"
    echo "  $0 'o1' 'mmlu-o1-test' 'env/.env' 5 'data/input/mmlu_dataset/custom_exam.json'"
    exit 1
fi
    
models="$1"
model2="$1"

exams="$5"        # Exam path (required argument)

attempts="$4"     # Number of evaluation attempts (required argument)
redact=1
test_name="$2"
output_dir="data/experiments/${test_name}"
env="$3"          # Environment file (required argument)

for model in $models; do
    model2=$model
    echo "Running Thesis Model: $model, Antithesis Model: $model2"
    model_name=$(basename "$model")
    bash scripts/experiments/run_mmlu_experiments.sh \
        "$env" "$output_dir" "$exams" "$attempts" "$model" "$model2" "$redact"
done

echo "Done!"