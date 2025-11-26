# 📊 Dataset Conversion Tools

This directory contains conversion tools for preparing datasets in SIEV-compatible JSON format. SIEV is benchmark-agnostic and can work with any dataset - the tools here provide examples for popular benchmarks.

## 🚀 Quick Start

### Example Datasets

SIEV works with any dataset in the proper JSON format. For demonstration, we provide converters for popular benchmarks:

**Example Downloads**: [GSM-8K](https://github.com/openai/grade-school-math/raw/master/grade_school_math/data/test.jsonl) | [MMLU](https://people.eecs.berkeley.edu/~hendrycks/data.tar)

*Note: Extract the MMLU tar file after download: `tar -xf data.tar`*

### Convert to SIEV Format (Examples)

```bash
# Convert GSM dataset
python3 scripts/dataset_conversion/convert_gsm.py \
    --input_file test.jsonl \
    --output_dir data/input/gsm_data

# Convert MMLU dataset (all subjects)
python3 scripts/dataset_conversion/convert_mmlu.py \
    --input_dir data/test \
    --output_dir data/input/mmlu_dataset
```

## 📋 GSM Converter Example (`convert_gsm.py`)

Example converter that transforms GSM-8K JSONL format to SIEV JSON exam files. This demonstrates how to adapt any dataset for SIEV evaluation.

### Features
- ✅ Comprehensive input validation
- ✅ Progress tracking for large files
- ✅ Numerical answer extraction from GSM format
- ✅ Detailed error reporting and logging
- ✅ Robust handling of malformed entries

### Usage Examples

```bash
# Basic conversion
python3 convert_gsm.py --input_file test.jsonl --output_dir data/input/gsm_data

# Custom filename
python3 convert_gsm.py \
    --input_file test.jsonl \
    --output_dir data/input/gsm_data \
    --filename my_gsm_test.json

# Verbose output for debugging
python3 convert_gsm.py \
    --input_file test.jsonl \
    --output_dir data/input/gsm_data \
    --verbose
```

### Arguments

- `--input_file`: Path to GSM-8K test.jsonl file (required)
- `--output_dir`: Output directory for converted JSON file (required)  
- `--filename`: Output filename (default: gsm_exam.json)
- `--verbose`: Enable detailed logging

### Input Format (GSM JSONL)

```json
{"question": "Janet's ducks lay 16 eggs per day...", "answer": "Janet's ducks lay 16 eggs per day. She eats 3 for breakfast every morning and bakes 4 into muffins for her friends every day. She sells the remainder at the farmers' market daily for $2 per fresh duck egg. How much does she make every day at the farmers' market?\n\nJanet's ducks lay 16 eggs per day.\nShe eats 3 for breakfast.\nShe bakes 4 into muffins.\nSo she has 16 - 3 - 4 = 9 eggs left.\nShe sells these at $2 per egg.\nSo she makes 9 * $2 = $18 every day.\n#### 18"}
```

### Output Format (SIEV JSON)

```json
{
    "info": {
        "source": "GSM-8K Dataset",
        "original_file": "test.jsonl",
        "converted_by": "SIEV Framework GSM Converter",
        "format": "SIEV JSON Exam Format",
        "total_questions": 1319
    },
    "0": {
        "question": "Janet's ducks lay 16 eggs per day...",
        "answer": "18"
    }
}
```

**Note**: The `total_questions` field automatically reflects the complete dataset size (1,319 for GSM-8K test set).

## 📚 MMLU Converter Example (`convert_mmlu.py`)

Example converter that transforms MMLU CSV files to SIEV JSON exam files with subject organization. Shows how to handle multi-subject datasets for SIEV evaluation.

### Features

- ✅ Multi-subject processing
- ✅ Subject filtering capabilities
- ✅ CSV format validation
- ✅ Multiple choice formatting (A/B/C/D)
- ✅ Batch processing of multiple files
- ✅ Subject listing functionality

### Usage Examples

**Important**: Activate virtual environment first to ensure pandas and other dependencies are available:
```bash
source ../../SIEVenv/bin/activate  # From scripts/dataset_conversion directory
```

```bash
# Convert all subjects
python3 convert_mmlu.py \
    --input_dir data/test \
    --output_dir data/input/mmlu_dataset

# Convert specific subjects
python3 convert_mmlu.py \
    --input_dir data/test \
    --output_dir data/input/mmlu_dataset \
    --subjects "abstract_algebra,anatomy,astronomy"

# List available subjects
python3 convert_mmlu.py \
    --input_dir data/test \
    --list_subjects

# Convert with custom settings
python3 convert_mmlu.py \
    --input_dir data/test \
    --output_dir data/input/mmlu_dataset \
    --test_id my_mmlu_test \
    --sample_size 50 \
    --verbose
```

### Arguments

- `--input_dir`: Directory containing MMLU CSV files (required)
- `--output_dir`: Output directory for JSON files (required for conversion)
- `--test_id`: Test identifier for output files (default: mmlu_exam)
- `--subjects`: Comma-separated list of subjects to convert
- `--sample_size`: Limit questions per subject (useful for testing)
- `--list_subjects`: List available subjects and exit
- `--verbose`: Enable detailed logging

### Input Format (MMLU CSV)

```csv
The study of economics deals with,human behavior,natural phenomena,mathematical models,social structures,A
```

### Output Format (SIEV JSON)

```json
{
    "info": {
        "source": "MMLU Dataset",
        "subject": "Abstract Algebra",
        "original_file": "abstract_algebra_test.csv",
        "converted_by": "SIEV Framework MMLU Converter",
        "format": "SIEV JSON Exam Format",
        "total_questions": 100
    },
    "0": {
        "question": "The study of economics deals with: A) human behavior, B) natural phenomena, C) mathematical models, D) social structures",
        "answer": "A"
    }
}
```

## 🔧 Integration with SIEV Framework

After conversion, use the generated JSON files with SIEV evaluation scripts:

```bash
# Evaluate with GSM dataset
./evaluate-gsm.sh gpt-4o-mini my_experiment env/.env 3 data/input/gsm_data/gsm_exam.json

# Evaluate with MMLU dataset  
./evaluate-mmlu.sh gpt-4o-mini my_experiment env/.env 3 data/input/mmlu_dataset/abstract_algebra_test_mmlu_exam.json
```

## 📁 Output Structure

After conversion, your directory structure will look like:

```
data/input/
├── gsm_data/
│   └── gsm_exam.json                    # Converted GSM dataset
└── mmlu_dataset/
    ├── abstract_algebra_test_mmlu_exam.json
    ├── anatomy_test_mmlu_exam.json
    ├── astronomy_test_mmlu_exam.json
    └── ...                              # Other MMLU subjects
```

## 🛠️ Troubleshooting

### Common Issues

**GSM Conversion:**

- **Empty output**: Check input file format, ensure it's valid JSONL
- **Missing answers**: Verify GSM entries contain '####' delimiter
- **Encoding errors**: Ensure input file is UTF-8 encoded

**MMLU Conversion:**

- **No files found**: Verify CSV files exist in input directory
- **Invalid answers**: Check that answer column contains A/B/C/D values
- **Subject filtering**: Use `--list_subjects` to see available subjects

### Validation Commands

```bash
# Validate GSM conversion
python3 -c "
import json
with open('data/input/gsm_data/gsm_exam.json') as f:
    data = json.load(f)
    print(f'Questions: {data[\"info\"][\"total_questions\"]}')
    print(f'Sample: {data[\"0\"][\"question\"][:50]}...')
"

# Validate MMLU conversion
python3 -c "
import json, glob
files = glob.glob('data/input/mmlu_dataset/*.json')
print(f'MMLU files: {len(files)}')
for f in files[:3]:
    with open(f) as file:
        data = json.load(file)
        print(f'{data[\"info\"][\"subject\"]}: {data[\"info\"][\"total_questions\"]} questions')
"
```

## 🆘 Error Handling

Both converters include comprehensive error handling:

- **Input validation**: File existence, format checks
- **Data validation**: Required fields, format compliance
- **Progress tracking**: Large file processing indicators
- **Detailed logging**: Verbose mode for debugging
- **Graceful failures**: Continue processing despite individual errors

For detailed error information, always use the `--verbose` flag during conversion.

## 🔧 Extending to Other Datasets

SIEV is designed to work with any dataset. To create a converter for your dataset:

### Required JSON Format

```json
{
    "info": {
        "source": "Your Dataset Name",
        "total_questions": 100
    },
    "0": {
        "question": "Your question text",
        "answer": "Correct answer"
    },
    "1": {
        "question": "Another question",
        "answer": "Another answer"
    }
}
```

### Key Principles

- **Question-Answer Structure**: Each entry needs a `question` and `answer` field
- **Indexed Keys**: Questions indexed as "0", "1", "2", etc.
- **Metadata**: Include dataset information in the `info` section
- **Clean Answers**: Extract final answers from any reasoning steps

The GSM and MMLU converters serve as templates - adapt their structure for your specific dataset format!
