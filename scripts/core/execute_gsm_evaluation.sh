#!/bin/bash
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

if [ $# -ne 9 ]; then
    echo "Usage: $0 <env file name> <output dir> <exam filename> <number of attempts>\
     <model: azure-gpt-4, gpt-4, ...> <number of thesis> <mode: hegel (dialectical reasoning)> <model2: azure-gpt-4, gpt-4, ...> <redact: 0, 1>"
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
model2="$8"
redacted=$9

if [[ "$model2" == "$model" ]]; then
    multimodel=0
else
    multimodel=1
fi

# Determine the directory of the current script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source the configure-paths.sh file to set environment variables
source "$SCRIPT_DIR/../../configure-paths.sh"
source $VENV_DIR/bin/activate   

echo "output dir: $dir"
echo "num_attempts: $num_attempts"

thesis="${TEMPLATES_DIR}/template.gsm.thesis"
thesis_name=$(basename "$thesis")

antithesis="${TEMPLATES_DIR}/template.gsm.antithesis"
antithesis_name=$(basename "$antithesis")

natural_antithesis="${TEMPLATES_DIR}/template.gsm.antithesis.natural"
natural_antithesis_name=$(basename "$natural_antithesis")

synthesis="${TEMPLATES_DIR}/template.gsm.synthesis"

synthesis_name=$(basename "$synthesis")
max_natural_samples=${MAX_NATURAL_SAMPLES:-3}
dir_name="${exam_filename}_${model}_${num_critics}_${num_thesis}_${mode}_${multimodel}"
dir_name=$(echo "$dir_name" | tr '/' '_')
new_dir="${dir}/${dir_name}"

if [ ! -f "$exam" ]; then
    echo "Error: Exam file '$exam' not found!"
    exit 1
fi
if [ ! -d "$new_dir" ]; then
    mkdir -p "$new_dir"
fi

write_settings_file() {
    local new_dir="$1"
    settings_file="${new_dir}/settings.txt"
    echo "env_file: $env_file" > "$settings_file"
    echo "dir: $dir" >> "$settings_file"
    echo "exam: $exam" >> "$settings_file"
    echo "exam_filename: $exam_filename" >> "$settings_file"
    echo "num_attempts: $num_attempts" >> "$settings_file"
    echo "num_critics: $num_critics" >> "$settings_file"
    echo "num_rounds: $num_rounds" >> "$settings_file"
    echo "model: $model" >> "$settings_file"
    echo "num_thesis: $num_thesis" >> "$settings_file"
    echo "mode: $mode" >> "$settings_file"
    echo "dir_name: $dir_name" >> "$settings_file"
    echo "thesis: $thesis_name" >> "$settings_file"
    echo "antithesis: $antithesis_name" >> "$settings_file"
    echo "natural_antithesis: $natural_antithesis_name" >> "$settings_file"
    echo "synthesis: $synthesis_name" >> "$settings_file"
    echo "multimodel: $multimodel" >> "$settings_file"
    echo "model2: $model2" >> "$settings_file"
    echo "redacted: $redacted" >> "$settings_file"
    echo "max_natural_samples: $max_natural_samples" >> "$settings_file"
}

write_settings_file "$new_dir"

for i in `seq 1 $num_attempts`; do
    bash ${CORE_SCRIPTS_DIR}/execute_gsm_iteration.sh "$env_file" "$new_dir" "$exam" "$num_attempts" $model $num_thesis "$mode" "$i" "$model2" $redacted
done

