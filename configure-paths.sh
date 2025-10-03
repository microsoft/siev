#!/bin/bash
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# Set the path to the main folder of the project
export PROJECT_ROOT="$(pwd)"

# Set environment variables for different paths
export VENV_DIR="$PROJECT_ROOT/../SIEVenv"
export TEMPLATES_DIR="$PROJECT_ROOT/prompts/templates"
export ROLES_DIR="$PROJECT_ROOT/prompts/roles"
export DATA_DIR="$PROJECT_ROOT/data"
export INPUT_DIR="$PROJECT_ROOT/data/input"
export EXP_DIR="$PROJECT_ROOT/data/experiments"
export DATASET_DIR="$PROJECT_ROOT/data/datasets"
export UTILS_DIR="$PROJECT_ROOT/utils"
export ENV_DIR="$PROJECT_ROOT/env"
export ACTIVE_LEARNING_SCRIPTS_DIR="$PROJECT_ROOT/active_learning"
export SCRIPTS_DIR="$PROJECT_ROOT/scripts"
export CORE_SCRIPTS_DIR="$SCRIPTS_DIR/core"
export EXPERIMENT_SCRIPTS_DIR="$SCRIPTS_DIR/experiments"
export ANALYSIS_SCRIPTS_DIR="$SCRIPTS_DIR/analysis"

# Backward compatibility (deprecated - use new names above)
export RUN_SCRIPTS_DIR="$CORE_SCRIPTS_DIR"
export WRAPPER_SCRIPTS_DIR="$EXPERIMENT_SCRIPTS_DIR"


export SRC_DIR="$PROJECT_ROOT/src"
# export ANALYSIS_SRC_DIR="$SRC_DIR/analysis"
export LOGS_DIR="$PROJECT_ROOT/logs"

# Ensure PYTHONPATH is always set, even if it's not defined
export PYTHONPATH="${PYTHONPATH:-}"

# Add the src directory to PYTHONPATH
export PYTHONPATH="$UTILS_DIR:$SRC_DIR:$PYTHONPATH"

# Create directories if they do not exist
mkdir -p "$TEMPLATES_DIR"
mkdir -p "$ROLES_DIR"
mkdir -p "$DATA_DIR"
mkdir -p "$INPUT_DIR"
mkdir -p "$ENV_DIR"
mkdir -p "$EXP_DIR"
mkdir -p "$DATASET_DIR"
mkdir -p "$UTILS_DIR"
mkdir -p "$SCRIPTS_DIR"
mkdir -p "$RUN_SCRIPTS_DIR"
mkdir -p "$WRAPPER_SCRIPTS_DIR"
mkdir -p "$ANALYSIS_SCRIPTS_DIR"
mkdir -p "$SRC_DIR"
# mkdir -p "$ANALYSIS_SRC_DIR"
mkdir -p "$LOGS_DIR"
mkdir -p "$VENV_DIR"

if [ ! -f env/.env ]; then
    echo " " > env/.env
fi
if ! grep -q 'R1_URL=' env/.env; then
    echo 'R1_URL="http://0.0.0.0:11434/api/chat"' >> env/.env
    echo 'R1_KEY=" "' >> env/.env
    echo " " >> env/.env
fi

if ! grep -q 'LOCAL_ENDPOINT=' env/.env; then
    echo 'LOCAL_ENDPOINT="http://localhost:30000/v1/"' >> env/.env
    echo 'LOCAL_KEY="None"' >> env/.env
    echo " " >> env/.env
fi
