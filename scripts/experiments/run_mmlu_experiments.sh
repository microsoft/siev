#!/bin/bash
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

#
# SIEV MMLU Experiments Runner
# ============================
#
# Professional script for running MMLU (Massive Multitask Language Understanding)
# dialectical reasoning experiments using the SIEV framework.
#
# This script orchestrates multiple experimental runs across MMLU reasoning tasks,
# applying thesis-antithesis-synthesis dialectical methodology.
#
# Author: Microsoft Research
# License: MIT

if [ $# -ne 7 ]; then
    echo "Usage: $0 <env file name> <output dir> <exam filenames> <number of attempts> <model> <model2: azure-gpt-4, gpt-4, ...> <redacted: 0, 1>"
    exit 1
fi
env_file="$1"
dir="$2"
exams="$3"
num_attempts="$4"
model="$5"
model2="$6"
redacted=$7

# Hardcoded internal dialectical parameters (simplified for user experience)
num_rounds=1
num_critics=1

if [[ "$model2" == "$model" ]]; then
    multimodel=0
else
    multimodel=1
fi

simple_thesis=0

# Determine the directory of the current script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source the configure-paths.sh file to set environment variables
source "$SCRIPT_DIR/../../configure-paths.sh"
source $VENV_DIR/bin/activate

for e in $exams;
do
    # SIEV dialectical reasoning configuration
    mode="hegel"
    num_thesis=1
    exam_filename=$(basename "$e")
    new_dir="${dir}"
    echo "env_file: $env_file"
    echo "exam: $e"
    bash "${CORE_SCRIPTS_DIR}/execute_mmlu_evaluation.sh" \
        "$env_file" "$new_dir" "$e" "$num_attempts" \
        "$model" "$num_thesis" "$mode" "$model2" "$redacted"

    echo "Completed exam: $e"
    sleep 1
done
echo "All experiments completed"
python3 ${ANALYSIS_SCRIPTS_DIR}/generate_summary.py --dirs="${new_dir}" --output="${new_dir}"
python3 ${ANALYSIS_SCRIPTS_DIR}/aggregate_experiments.py -i ${new_dir}/summary.json -o ${new_dir}/summary_aggregate.json

# Generate final results table
echo "Generating final results table..."
python3 ${ANALYSIS_SCRIPTS_DIR}/generate_final_table.py -i ${new_dir}/summary_aggregate.json -o ${new_dir}/final_results_table.csv -s mmlu