#!/bin/bash
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

#!/bin/bash
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

if [ $# -ne 10 ]; then
    echo "Usage: $0 <env file name> <output dir> <exam filename> <number of attempts> <model: azure-gpt-4, gpt-4, ...> <redact: 0, 1>\
    <number of thesis> <mode: hegel (dialectical reasoning)> <attemptid> <model2: azure-gpt-4, gpt-4, ...> "
    exit 1
fi
env_file="$1"
dir="$2"
exam="$3"
exam_filename=$(basename "$exam")
exam_filename="${exam_filename%.json}"
num_attempts="$4"
num_critics=1
num_rounds=1
model="$5"
num_thesis=$6
mode="$7"
attemptid=$8
model2="$9"
redacted=${10}

if [[ "$model2" == "$model" ]]; then
    multimodel=0
else
    multimodel=1
fi

i=$attemptid

# Determine the directory of the current script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source the configure-paths.sh file to set environment variables
source "$SCRIPT_DIR/../../configure-paths.sh"
source $VENV_DIR/bin/activate   

thesis="${TEMPLATES_DIR}/template.mmlu.thesis"
thesis_name=$(basename "$thesis")

antithesis="${TEMPLATES_DIR}/template.mmlu.antithesis"
antithesis_name=$(basename "$antithesis")

synthesis="${TEMPLATES_DIR}/template.mmlu.synthesis"

synthesis_name=$(basename "$synthesis")
new_dir="${dir}"

copy_files_to_new_dir() {
    local new_dir="$1"
    mkdir -p $new_dir
    cp "$exam" "$new_dir"/
    cp "$thesis" "$new_dir"/
    cp "$antithesis" "$new_dir"/
    cp "$synthesis" "$new_dir"/
    cp "$env_file" "$new_dir"/.env
    cp ${TEMPLATES_DIR}/question.mmlu "$new_dir"/
    cp ${ROLES_DIR}/role.mmlu "$new_dir"/
}

new_dir_attempt="${dir}/attempt_${i}"
copy_files_to_new_dir "$new_dir_attempt"

python3 ${SRC_DIR}/dialectical_evaluator.py \
    --output_dir="$new_dir_attempt" --exam="$exam" --try_index=$i \
        --env=".env" \
        --antithesis_base_prompt="$antithesis_name" \
        --thesis_base_prompt="$thesis_name" \
        --synthesis_base_prompt="$synthesis_name" \
        --num_rounds=$num_rounds \
        --model=$model \
        --question_filename_base="question.mmlu" \
        --role_filename="role.mmlu" \
        --test_type="mmlu" \
        --multi-model=$multimodel \
        --model2="$model2" \
        --redacted=$redacted

python3 ${ANALYSIS_SCRIPTS_DIR}/evaluate_reasoning.py --dir="$new_dir_attempt" --try_index=$i --num_rounds=$num_rounds
