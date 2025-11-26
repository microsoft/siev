#!/bin/bash
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

#==============================================================================
# SIEV Setup Validation Script
#==============================================================================
#
# Comprehensive validation tool for SIEV (Structured dIalectical rEasoning eValuation)
# installation and configuration. This script verifies all dependencies, file structure,
# and basic functionality before running evaluations.
#
# VALIDATION CHECKS:
#   ✓ Python version compatibility (3.8+)
#   ✓ Directory structure integrity
#   ✓ Core Python files presence and syntax
#   ✓ Shell script syntax validation  
#   ✓ Python import verification
#   ✓ Environment template availability
#   ✓ Environment configuration validation (API keys and endpoints)
#   ✓ Data directories setup
#
# USAGE:
#   ./validate.sh
#
# EXIT CODES:
#   0 - All validations passed
#   1 - One or more validations failed
#
# AUTHOR:
#   Soheil Abbasloo (Microsoft Research)
#
#==============================================================================

echo "🔍 SIEV: Structured dIalectical rEasoning eValuation - Validation"
echo "=============================="

# Determine the directory of the current script and source configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/configure-paths.sh"

# Activate virtual environment if it exists and not already activated
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d "$VENV_DIR" ]; then
        echo "🔧 Activating virtual environment..."
        source "$VENV_DIR/bin/activate"
        echo -e "${GREEN}✓${NC} Virtual environment activated: $VENV_DIR"
    else
        echo -e "${YELLOW}⚠${NC} Virtual environment not found at $VENV_DIR - using system Python"
    fi
else
    echo -e "${GREEN}✓${NC} Virtual environment already active: $VIRTUAL_ENV"
fi

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# Check Python version
echo -n "📋 Checking Python version... "
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
    echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION (OK)"
else
    echo -e "${RED}✗${NC} Python $PYTHON_VERSION (Need Python 3.8+)"
    ERRORS=$((ERRORS + 1))
fi

# Check required directories
echo -n "📁 Checking directory structure... "
REQUIRED_DIRS=("src" "data" "prompts/templates" "scripts/analysis" "docs" "env" "logs" "data/experiments")
MISSING_DIRS=()

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        MISSING_DIRS+=("$dir")
    fi
done

if [ ${#MISSING_DIRS[@]} -eq 0 ]; then
    echo -e "${GREEN}✓${NC} All required directories present"
else
    echo -e "${RED}✗${NC} Missing directories: ${MISSING_DIRS[*]}"
    ERRORS=$((ERRORS + 1))
fi

# Check core Python files
echo -n "🐍 Checking core Python files... "
CORE_FILES=("src/dialectical_evaluator.py" "src/general_api.py" "src/reasoning_api.py")
MISSING_FILES=()

for file in "${CORE_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -eq 0 ]; then
    echo -e "${GREEN}✓${NC} All core files present"
else
    echo -e "${RED}✗${NC} Missing files: ${MISSING_FILES[*]}"
    ERRORS=$((ERRORS + 1))
fi

# Check Python syntax
echo -n "🔧 Checking Python syntax... "
SYNTAX_ERRORS=()
for file in "${CORE_FILES[@]}"; do
    if [ -f "$file" ]; then
        if ! python3 -m py_compile "$file" 2>/dev/null; then
            SYNTAX_ERRORS+=("$file")
        fi
    fi
done

if [ ${#SYNTAX_ERRORS[@]} -eq 0 ]; then
    echo -e "${GREEN}✓${NC} All Python files have valid syntax"
else
    echo -e "${RED}✗${NC} Syntax errors in: ${SYNTAX_ERRORS[*]}"
    ERRORS=$((ERRORS + 1))
fi

# Check shell scripts
echo -n "📜 Checking shell scripts... "
SHELL_SCRIPTS=("evaluate-gsm.sh" "evaluate-mmlu.sh")
SHELL_ERRORS=()

for script in "${SHELL_SCRIPTS[@]}"; do
    if [ -f "$script" ]; then
        if ! bash -n "$script" 2>/dev/null; then
            SHELL_ERRORS+=("$script")
        fi
    else
        SHELL_ERRORS+=("$script (missing)")
    fi
done

if [ ${#SHELL_ERRORS[@]} -eq 0 ]; then
    echo -e "${GREEN}✓${NC} All shell scripts have valid syntax"
else
    echo -e "${RED}✗${NC} Shell script issues: ${SHELL_ERRORS[*]}"
    ERRORS=$((ERRORS + 1))
fi

# Check Python imports
echo -n "📦 Checking Python imports... "
if python3 -c "
import sys
sys.path.append('src')
try:
    from dialectical_evaluator import DialecticalEvaluator
    from general_api import GeneralAPI
    from reasoning_api import ReasoningAPI
    exit(0)
except Exception as e:
    print(f'Import error: {e}')
    exit(1)
" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} All imports successful"
else
    echo -e "${RED}✗${NC} Import errors detected"
    ERRORS=$((ERRORS + 1))
fi

# Check environment configuration files
echo -n "⚙️ Checking environment template... "
if [ ! -f ".env.example" ]; then
    echo -e "${RED}✗${NC} Missing .env.example template file"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✓${NC} Environment template present"
fi

# Check active environment configuration
echo -n "🔐 Checking environment configuration... "
ENV_WARNINGS=0
ENV_CONFIGURED=false

# Check if env/.env exists
if [ ! -f "env/.env" ]; then
    echo -e "${YELLOW}⚠${NC} No env/.env file found"
    echo "    Create env/.env from .env.example template for API configuration"
    ENV_WARNINGS=$((ENV_WARNINGS + 1))
else
    # Validate env/.env file contents
    ENV_VALIDATION_OUTPUT=$(python3 -c "
import sys
sys.path.append('src')
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv('env/.env')

# Check required variables
required_vars = ['GENERAL_API_KEY', 'GENERAL_API_ENDPOINT', 'REASONING_API_KEY', 'REASONING_API_ENDPOINT']
missing_vars = []
invalid_vars = []

for var in required_vars:
    value = os.getenv(var)
    if not value:
        missing_vars.append(var)
    elif value.startswith('your_') or value.startswith('https://your-'):
        invalid_vars.append(var)

# Check endpoint format
general_endpoint = os.getenv('GENERAL_API_ENDPOINT', '')
reasoning_endpoint = os.getenv('REASONING_API_ENDPOINT', '')

if general_endpoint and not (general_endpoint.startswith('http://') or general_endpoint.startswith('https://')):
    invalid_vars.append('GENERAL_API_ENDPOINT (invalid URL format)')

if reasoning_endpoint and not (reasoning_endpoint.startswith('http://') or reasoning_endpoint.startswith('https://')):
    invalid_vars.append('REASONING_API_ENDPOINT (invalid URL format)')

if missing_vars:
    print(f'MISSING: {missing_vars}')
    sys.exit(1)
elif invalid_vars:
    print(f'INVALID: {invalid_vars}')
    sys.exit(2)
else:
    print('VALID')
    sys.exit(0)
" 2>/dev/null)

    ENV_EXIT_CODE=$?
    
    if [ $ENV_EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}✓${NC} Environment configuration valid"
        ENV_CONFIGURED=true
    elif [ $ENV_EXIT_CODE -eq 1 ]; then
        echo -e "${RED}✗${NC} Missing required environment variables"
        echo "    Missing: $(echo $ENV_VALIDATION_OUTPUT | sed 's/MISSING: //')"
        echo "    Copy .env.example to env/.env and configure with your API credentials"
        ERRORS=$((ERRORS + 1))
    elif [ $ENV_EXIT_CODE -eq 2 ]; then
        echo -e "${RED}✗${NC} Invalid environment configuration"
        echo "    Invalid: $(echo $ENV_VALIDATION_OUTPUT | sed 's/INVALID: //')"
        echo "    Update env/.env with valid API endpoints and keys"
        ERRORS=$((ERRORS + 1))
    else
        echo -e "${YELLOW}⚠${NC} Could not validate environment configuration"
        ENV_WARNINGS=$((ENV_WARNINGS + 1))
    fi
fi

# Check data directories
echo -n "💾 Checking data directories... "
DATA_DIRS=("data/input" "data/output" "data/experiments")
MISSING_DATA_DIRS=()

for dir in "${DATA_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        MISSING_DATA_DIRS+=("$dir")
    fi
done

if [ ${#MISSING_DATA_DIRS[@]} -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Data directories present"
else
    echo -e "${YELLOW}⚠${NC} Will be created on first run: ${MISSING_DATA_DIRS[*]}"
fi

# Final summary
echo ""
echo "=============================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}🎉 Validation Complete: All checks passed!${NC}"
    echo ""
    if [ "$ENV_CONFIGURED" = "true" ]; then
        echo "✅ Your SIEV installation is fully configured and ready for evaluations."
        echo ""
        echo "🚀 Ready to run:"
        echo "   • GSM-8K Math Evaluation:"
        echo "     ./evaluate-gsm.sh 'gpt-4o' 'my-experiment' 'env/.env' 3 'data/input/gsm_data/sample_exam.json'"
        echo "   • MMLU Knowledge Evaluation:"
        echo "     ./evaluate-mmlu.sh 'gpt-4o' 'my-experiment' 'env/.env' 3 'data/input/mmlu_dataset/sample_exam.json'"
        echo ""
        echo "📁 Optional: Add custom datasets to data/input/ (GSM/MMLU format)"
    else
        echo "⚙️ Your SIEV installation is ready but needs API configuration."
        echo ""
        echo "🔧 Configuration steps:"
        echo "   1. Copy template: cp .env.example env/.env"
        echo "   2. Edit env/.env with your API endpoints and keys"
        echo "   3. Verify setup: ./validate.sh"
        echo ""
        echo "🚀 Then run evaluations:"
        echo "   • GSM-8K:"
        echo "     ./evaluate-gsm.sh 'gpt-4o' 'my-experiment' 'env/.env' 3 'data/input/gsm_data/sample_exam.json'"
        echo "   • MMLU:"
        echo "     ./evaluate-mmlu.sh 'gpt-4o' 'my-experiment' 'env/.env' 3 'data/input/mmlu_dataset/sample_exam.json'"
    fi
    exit 0
else
    echo -e "${RED}❌ Validation Failed: $ERRORS error(s) found${NC}"
    echo ""
    echo "🔧 Common fixes:"
    echo "   • Environment: Copy .env.example to env/.env and configure API credentials"
    echo "   • Dependencies: pip install -r requirements.txt"
    echo "   • Missing files: Ensure complete SIEV repository download"
    echo ""
    exit 1
fi
