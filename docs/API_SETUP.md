# API Setup Guide

SIEV uses a clean **two-tier API architecture** for optimal model handling.

## 🏗️ Simplified Two-API Architecture

### 1. **General API** (`general_api.py`)  
**Purpose**: Standard chat models and local endpoints
- **Model Routing**: All models except specific reasoning models
- **Environment Variables**: `GENERAL_API_KEY`, `GENERAL_API_ENDPOINT`
- **Examples**: `gpt-4o`, `claude-3.5-sonnet`, `gpt-5-chat`, `llama-3.1-70b`, `deepseek-v3`

```bash
# Example usage  
./evaluate-gsm.sh "gpt-4o" "general-test" "env/.env"
./evaluate-gsm.sh "gpt-5-chat" "gpt5-chat-test" "env/.env"
./evaluate-gsm.sh "llama-3.1-70b" "llama-test" "env/.env"
```

### 2. **Reasoning API** (`reasoning_api.py`)
**Purpose**: Advanced reasoning models with specialized parameters
- **Model Routing**: Automatically detected for specific reasoning models
- **Environment Variables**: `REASONING_API_KEY`, `REASONING_API_ENDPOINT`
- **Examples**: `o1-preview`, `o1-mini`, `o3-mini`, `gpt-5-2025-08-07`

```bash
# Example usage
./evaluate-gsm.sh "o1-preview" "reasoning-test" "env/.env"
```

## 📋 Simplified Model Routing Logic

```python
def route_model(model_name):
    if is_reasoning_model(model_name):
        return "reasoning_api"      # -> reasoning_api.py  
    else:
        return "general_api"        # -> general_api.py (default for all others)

def is_reasoning_model(model_name):
    """
    Reasoning models (requiring specialized parameters):
    - O1 series: o1-preview, o1-mini, o1-pro
    - O3 series: o3-mini, o3-preview
    - Specific GPT-5 reasoning: gpt-5-2025-08-07, gpt-5-mini-shortco-2025-08-07
    
    Everything else goes to General API:
    - GPT-5 chat: gpt-5-chat, gpt-5-turbo
    - Standard models: gpt-4, claude-3, etc.
    - Local models: llama-3.1-70b, qwen-72b, etc.
    """
    model_lower = model_name.lower()
    
    # O1 and O3 series
    if model_lower.startswith(('o1-', 'o3-')):
        return True
        
    # Specific GPT-5 reasoning variants only
    reasoning_variants = [
        'gpt-5-2025-08-07',
        'gpt-5-mini-shortco-2025-08-07', 
        'gpt-5-nano-shortco-2025-08-07'
    ]
    
    return model_lower in reasoning_variants
```

## 🔧 Environment Configuration

Create your environment file in `env/.env`:

```bash
# General Models API (Standard Chat + Local Models)
GENERAL_API_KEY=your-general-models-api-key
GENERAL_API_ENDPOINT=https://your-general-endpoint.com/v1

# Reasoning Models API (O1, O3, specific GPT-5)
REASONING_API_KEY=your-reasoning-models-api-key
REASONING_API_ENDPOINT=https://your-reasoning-endpoint.com/v1
```

## 🎯 Model Examples by Category

### General Models (general_api.py)

```bash
./evaluate-gsm.sh "gpt-4o" "gpt4-test" "env/.env"
./evaluate-gsm.sh "gpt-5-chat" "gpt5-chat-test" "env/.env"
# ./evaluate-gsm.sh "claude-3.5-sonnet" "claude-test" "env/.env"
./evaluate-gsm.sh "llama-3.1-70b" "llama-test" "env/.env"
./evaluate-gsm.sh "qwen-72b-chat" "qwen-test" "env/.env"
```

### Reasoning Models (reasoning_api.py)

```bash
./evaluate-gsm.sh "o1-preview" "reasoning-test" "env/.env"
./evaluate-gsm.sh "o1-mini" "o1-mini-test" "env/.env"
./evaluate-gsm.sh "gpt-5-2025-08-07" "gpt5-reasoning-test" "env/.env"
```

## 🚀 Quick Start

### Setup Environment
```bash
cp .env.example env/.env
nano env/.env  # Configure your API credentials
```

### Configure API Endpoints

SIEV supports various endpoint types:

**OpenAI Direct**:
```bash
GENERAL_API_ENDPOINT=https://api.openai.com/v1
REASONING_API_ENDPOINT=https://api.openai.com/v1
```

**Azure OpenAI**:
```bash
GENERAL_API_ENDPOINT=https://your-resource.openai.azure.com/
REASONING_API_ENDPOINT=https://your-resource.openai.azure.com/
```

**Custom/Internal Endpoints**:
```bash
GENERAL_API_ENDPOINT=https://your-internal-api.company.com/v1
REASONING_API_ENDPOINT=https://your-reasoning-api.company.com/v1
```

**Local Models**:
```bash
GENERAL_API_ENDPOINT=http://localhost:8000/v1
REASONING_API_ENDPOINT=http://localhost:8001/v1
```

### Test Each API Tier
```bash
# Test general model  
./evaluate-gsm.sh "gpt-4o" "general-test" "env/.env"

# Test reasoning model
./evaluate-gsm.sh "o1-preview" "reasoning-test" "env/.env"
```

## 🔍 Troubleshooting

### Model Routing Issues

**Model routing**: All models go to General API except specific reasoning models

- **General**: `gpt-4o`, `gpt-5-chat`, `llama-3.1-70b`, etc.
- **Reasoning**: `o1-preview`, `gpt-5-2025-08-07`, etc.

**GPT-5 clarification**: 
- `gpt-5-chat` → General API (standard chat)
- `gpt-5-2025-08-07` → Reasoning API (specific reasoning variant)

**Environment variables**: Ensure correct variable names for each API tier

