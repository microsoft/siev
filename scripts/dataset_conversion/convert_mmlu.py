#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
MMLU Dataset Converter for SIEV Framework

This script converts MMLU CSV files to SIEV-compatible JSON exam files.
Supports subject filtering, comprehensive validation, and progress tracking.

Author: SIEV Framework
Usage:
    python3 convert_mmlu.py --input_dir data/test --output_dir data/input/mmlu_dataset
    python3 convert_mmlu.py --input_dir data/test --output_dir data/input/mmlu_dataset --subjects "abstract_algebra,anatomy" --verbose
"""

import pandas as pd
import json
import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import logging
from glob import glob

def setup_logging(verbose: bool) -> logging.Logger:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)

def validate_mmlu_row(row: pd.Series, row_idx: int, logger: logging.Logger) -> bool:
    """
    Validate a single MMLU row for required fields and format.
    
    Args:
        row: Pandas series containing the row data
        row_idx: Row index for error reporting
        logger: Logger instance
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Check if we have at least 6 columns (question, A, B, C, D, answer)
        if len(row) < 6:
            logger.error(f"Row {row_idx}: Insufficient columns (expected 6, got {len(row)})")
            return False
            
        # Check for empty question
        if pd.isna(row.iloc[0]) or str(row.iloc[0]).strip() == '':
            logger.error(f"Row {row_idx}: Empty question")
            return False
            
        # Check for empty choices
        for i, choice_label in enumerate(['A', 'B', 'C', 'D'], 1):
            if pd.isna(row.iloc[i]) or str(row.iloc[i]).strip() == '':
                logger.warning(f"Row {row_idx}: Empty choice {choice_label}")
                
        # Check answer is valid (should be A, B, C, or D)
        answer = str(row.iloc[5]).strip().upper()
        if answer not in ['A', 'B', 'C', 'D']:
            logger.error(f"Row {row_idx}: Invalid answer '{answer}' (must be A, B, C, or D)")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Row {row_idx}: Validation error - {str(e)}")
        return False

def parse_mmlu_question(row: pd.Series, logger: logging.Logger) -> Tuple[str, str]:
    """
    Parse MMLU row to create formatted question and extract answer.
    
    Args:
        row: Pandas series containing question data
        logger: Logger instance
        
    Returns:
        Tuple of (formatted_question, answer)
    """
    try:
        question = str(row.iloc[0]).strip()
        choice_a = str(row.iloc[1]).strip()
        choice_b = str(row.iloc[2]).strip()
        choice_c = str(row.iloc[3]).strip()
        choice_d = str(row.iloc[4]).strip()
        answer = str(row.iloc[5]).strip().upper()
        
        # Format question with choices
        formatted_question = f"{question}: A) {choice_a}, B) {choice_b}, C) {choice_c}, D) {choice_d}"
        
        return formatted_question, answer
        
    except Exception as e:
        logger.error(f"Question parsing error: {str(e)}")
        return "", ""

def get_subject_from_filename(filename: str) -> str:
    """Extract subject name from CSV filename."""
    # Remove .csv extension and clean up
    subject = os.path.splitext(filename)[0]
    # Replace underscores with spaces and title case
    subject = subject.replace('_', ' ').title()
    return subject

def convert_mmlu_to_siev(
    input_dir: str,
    output_dir: str,
    test_id: str = "mmlu_exam",
    subjects: Optional[List[str]] = None,
    sample_size: Optional[int] = None,
    verbose: bool = False
) -> Tuple[bool, Dict[str, Any]]:
    """
    Convert MMLU CSV files to SIEV JSON format.
    
    Args:
        input_dir: Directory containing MMLU CSV files
        output_dir: Output directory for JSON files
        test_id: Test identifier for output files
        subjects: Optional list of specific subjects to convert
        sample_size: Optional limit on questions per subject
        verbose: Enable verbose logging
        
    Returns:
        Tuple of (success, stats_dict)
    """
    logger = setup_logging(verbose)
    
    # Validate input directory
    if not os.path.exists(input_dir):
        logger.error(f"Input directory not found: {input_dir}")
        return False, {}
        
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Find CSV files
    csv_files = glob(os.path.join(input_dir, "*.csv"))
    if not csv_files:
        logger.error(f"No CSV files found in: {input_dir}")
        return False, {}
        
    csv_files.sort()
    
    # Filter by subjects if specified
    if subjects:
        subjects_lower = [s.lower().replace(' ', '_') for s in subjects]
        filtered_files = []
        for csv_file in csv_files:
            filename = os.path.basename(csv_file)
            subject_name = os.path.splitext(filename)[0].lower()
            if subject_name in subjects_lower:
                filtered_files.append(csv_file)
        csv_files = filtered_files
        
        if not csv_files:
            logger.error(f"No CSV files found for subjects: {subjects}")
            return False, {}
    
    # Statistics tracking
    stats = {
        'total_files': len(csv_files),
        'processed_files': 0,
        'total_questions': 0,
        'valid_questions': 0,
        'invalid_questions': 0,
        'output_files': []
    }
    
    logger.info(f"Converting MMLU dataset from: {input_dir}")
    logger.info(f"Found {len(csv_files)} CSV files to process")
    logger.info(f"Output directory: {output_dir}")
    
    try:
        # Process each CSV file
        for csv_file in csv_files:
            filename = os.path.basename(csv_file)
            subject = get_subject_from_filename(filename)
            
            logger.info(f"Processing: {filename} ({subject})")
            
            try:
                # Read CSV file
                df = pd.read_csv(csv_file, header=None)
                
                if df.empty:
                    logger.warning(f"Empty CSV file: {filename}")
                    continue
                    
                # Initialize SIEV format dictionary for this subject
                siev_data = {
                    "info": {
                        "source": "MMLU Dataset",
                        "subject": subject,
                        "original_file": filename,
                        "converted_by": "SIEV Framework MMLU Converter",
                        "format": "SIEV JSON Exam Format",
                        "test_id": test_id,
                        "sample_size": sample_size,
                        "total_questions": 0  # Will be updated
                    }
                }
                
                question_index = 0
                file_valid_questions = 0
                file_invalid_questions = 0
                
                # Process each row
                for row_idx, row in df.iterrows():
                    stats['total_questions'] += 1
                    
                    # Validate row
                    if not validate_mmlu_row(row, row_idx, logger):
                        stats['invalid_questions'] += 1
                        file_invalid_questions += 1
                        continue
                        
                    # Check sample size limit
                    if sample_size and question_index >= sample_size:
                        logger.info(f"Reached sample size limit for {subject}: {sample_size}")
                        break
                        
                    # Parse question and answer
                    formatted_question, answer = parse_mmlu_question(row, logger)
                    
                    if not formatted_question or not answer:
                        stats['invalid_questions'] += 1
                        file_invalid_questions += 1
                        continue
                        
                    # Add to SIEV format
                    siev_data[question_index] = {
                        "question": formatted_question,
                        "answer": answer
                    }
                    
                    question_index += 1
                    stats['valid_questions'] += 1
                    file_valid_questions += 1
                
                # Update metadata
                siev_data["info"]["total_questions"] = file_valid_questions
                
                # Generate output filename
                output_filename = f"{filename}_{test_id}.json"
                output_path = os.path.join(output_dir, output_filename)
                
                # Write output file
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(siev_data, f, indent=4, ensure_ascii=False)
                    
                stats['output_files'].append(output_path)
                stats['processed_files'] += 1
                
                logger.info(f"  ✅ {subject}: {file_valid_questions} questions converted")
                if file_invalid_questions > 0:
                    logger.warning(f"  ⚠️  {subject}: {file_invalid_questions} invalid questions skipped")
                    
            except Exception as e:
                logger.error(f"Error processing {filename}: {str(e)}")
                continue
        
        # Print summary
        logger.info("=" * 60)
        logger.info("CONVERSION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total CSV files: {stats['total_files']}")
        logger.info(f"Processed files: {stats['processed_files']}")
        logger.info(f"Total questions: {stats['total_questions']}")
        logger.info(f"Valid questions: {stats['valid_questions']}")
        logger.info(f"Invalid questions: {stats['invalid_questions']}")
        logger.info(f"Output files: {len(stats['output_files'])}")
        logger.info("=" * 60)
        
        return True, stats
        
    except Exception as e:
        logger.error(f"Conversion failed: {str(e)}")
        return False, stats

def list_available_subjects(input_dir: str) -> List[str]:
    """List all available subjects in the input directory."""
    if not os.path.exists(input_dir):
        return []
        
    csv_files = glob(os.path.join(input_dir, "*.csv"))
    subjects = []
    
    for csv_file in csv_files:
        filename = os.path.basename(csv_file)
        subject = get_subject_from_filename(filename)
        subjects.append(subject)
        
    return sorted(subjects)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Convert MMLU CSV dataset to SIEV JSON exam format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert all subjects
  python3 convert_mmlu.py --input_dir data/test --output_dir data/input/mmlu_dataset
  
  # Convert specific subjects
  python3 convert_mmlu.py --input_dir data/test --output_dir data/input/mmlu_dataset --subjects "abstract_algebra,anatomy,astronomy"
  
  # Convert with custom test ID and sample size
  python3 convert_mmlu.py --input_dir data/test --output_dir data/input/mmlu_dataset --test_id my_test --sample_size 50
  
  # List available subjects
  python3 convert_mmlu.py --input_dir data/test --list_subjects
  
  # Verbose output for debugging
  python3 convert_mmlu.py --input_dir data/test --output_dir data/input/mmlu_dataset --verbose

Integration with SIEV evaluation:
  # After conversion, run evaluation with all 5 required arguments:
  ./evaluate-mmlu.sh "gpt-4o" "mmlu-experiment" "env/.env" 3 "data/input/mmlu_dataset/abstract_algebra_test_mmlu_exam.json"
  
  # Arguments: <model> <experiment_name> <env_file> <num_attempts> <exam_path>

Dataset Download:
  wget https://people.eecs.berkeley.edu/~hendrycks/data.tar
  tar -xf data.tar
        """
    )
    
    parser.add_argument(
        '--input_dir', 
        type=str, 
        required=True,
        help='Directory containing MMLU CSV files'
    )
    
    parser.add_argument(
        '--output_dir', 
        type=str,
        help='Output directory for converted JSON files'
    )
    
    parser.add_argument(
        '--test_id', 
        type=str, 
        default='mmlu_exam',
        help='Test identifier for output files (default: mmlu_exam)'
    )
    
    parser.add_argument(
        '--subjects', 
        type=str,
        help='Comma-separated list of subjects to convert (e.g., "abstract_algebra,anatomy")'
    )
    
    parser.add_argument(
        '--sample_size', 
        type=int,
        help='Limit number of questions per subject (useful for testing)'
    )
    
    parser.add_argument(
        '--list_subjects', 
        action='store_true',
        help='List available subjects and exit'
    )
    
    parser.add_argument(
        '--verbose', 
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    # List subjects mode
    if args.list_subjects:
        subjects = list_available_subjects(args.input_dir)
        if subjects:
            print("Available subjects:")
            for i, subject in enumerate(subjects, 1):
                print(f"  {i:2d}. {subject}")
        else:
            print("No CSV files found in the specified directory.")
        sys.exit(0)
    
    # Validate required arguments for conversion
    if not args.output_dir:
        parser.error("--output_dir is required for conversion")
    
    # Parse subjects
    subjects_list = None
    if args.subjects:
        subjects_list = [s.strip() for s in args.subjects.split(',')]
    
    # Convert dataset
    success, stats = convert_mmlu_to_siev(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        test_id=args.test_id,
        subjects=subjects_list,
        sample_size=args.sample_size,
        verbose=args.verbose
    )
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()