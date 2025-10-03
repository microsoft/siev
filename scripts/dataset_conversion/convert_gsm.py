#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
GSM-8K Dataset Converter for SIEV Framework

This script converts GSM-8K test.jsonl format to SIEV-compatible JSON exam files.
Provides comprehensive error handling, validation, and progress tracking.

Author: SIEV Framework
Usage:
    python3 convert_gsm.py --input_file test.jsonl --output_dir data/input/gsm_data
    python3 convert_gsm.py --input_file test.jsonl --output_dir data/input/gsm_data --verbose
"""

import json
import argparse
import os
import sys
from pathlib import Path
import re
from typing import Dict, Any, Optional, Tuple
import logging

def setup_logging(verbose: bool) -> logging.Logger:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)

def validate_gsm_entry(entry: Dict[str, Any], line_num: int, logger: logging.Logger) -> bool:
    """
    Validate a single GSM entry for required fields and format.
    
    Args:
        entry: Dictionary containing question and answer
        line_num: Line number for error reporting
        logger: Logger instance
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Check required fields
        if 'question' not in entry:
            logger.error(f"Line {line_num}: Missing 'question' field")
            return False
            
        if 'answer' not in entry:
            logger.error(f"Line {line_num}: Missing 'answer' field")
            return False
            
        question = entry['question'].strip()
        answer = entry['answer'].strip()
        
        # Validate question is not empty
        if not question:
            logger.error(f"Line {line_num}: Empty question")
            return False
            
        # Validate answer format (should contain ####)
        if '####' not in answer:
            logger.warning(f"Line {line_num}: Answer doesn't contain '####' delimiter - may not be standard GSM format")
            
        return True
        
    except Exception as e:
        logger.error(f"Line {line_num}: Validation error - {str(e)}")
        return False

def parse_gsm_answer(answer: str, logger: logging.Logger) -> str:
    """
    Parse GSM answer to extract the final numerical answer.
    
    Args:
        answer: Raw answer string from GSM dataset
        logger: Logger instance
        
    Returns:
        Extracted numerical answer or original answer if parsing fails
    """
    try:
        # Look for #### delimiter
        if '####' in answer:
            # Extract everything after ####
            parts = answer.split('####')
            if len(parts) >= 2:
                numerical_answer = parts[-1].strip()
                
                # Clean up common formatting
                numerical_answer = re.sub(r'[^\d\-\.\,]', '', numerical_answer)
                
                if numerical_answer:
                    return numerical_answer
                    
        # If no #### found or parsing failed, return original
        logger.debug(f"Could not parse numerical answer from: {answer[:50]}...")
        return answer.strip()
        
    except Exception as e:
        logger.warning(f"Answer parsing error: {str(e)}")
        return answer.strip()

def convert_gsm_to_siev(
    input_file: str, 
    output_dir: str, 
    filename: Optional[str] = None,
    verbose: bool = False
) -> Tuple[bool, Dict[str, Any]]:
    """
    Convert GSM JSONL file to SIEV JSON format.
    
    Args:
        input_file: Path to input JSONL file
        output_dir: Output directory for JSON file
        filename: Optional custom filename (default: gsm_exam.json)
        verbose: Enable verbose logging
        
    Returns:
        Tuple of (success, stats_dict)
    """
    logger = setup_logging(verbose)
    
    # Validate input file
    if not os.path.exists(input_file):
        logger.error(f"Input file not found: {input_file}")
        return False, {}
        
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Determine output filename
    if filename is None:
        filename = "gsm_exam.json"
    if not filename.endswith('.json'):
        filename += '.json'
        
    output_path = os.path.join(output_dir, filename)
    
    # Statistics tracking
    stats = {
        'total_lines': 0,
        'valid_entries': 0,
        'invalid_entries': 0,
        'processed_entries': 0,
        'output_file': output_path
    }
    
    # Initialize SIEV format dictionary
    siev_data = {
        "info": {
            "source": "GSM-8K Dataset",
            "original_file": os.path.basename(input_file),
            "converted_by": "SIEV Framework GSM Converter",
            "format": "SIEV JSON Exam Format",
            "total_questions": 0  # Will be updated
        }
    }
    
    try:
        logger.info(f"Converting GSM dataset: {input_file}")
        logger.info(f"Output directory: {output_dir}")
        
        with open(input_file, 'r', encoding='utf-8') as f:
            question_index = 0
            
            for line_num, line in enumerate(f, 1):
                stats['total_lines'] = line_num
                
                # Show progress for large files
                if line_num % 100 == 0:
                    logger.info(f"Processing line {line_num}...")
                
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    # Parse JSON line
                    entry = json.loads(line)
                    
                    # Validate entry
                    if not validate_gsm_entry(entry, line_num, logger):
                        stats['invalid_entries'] += 1
                        continue
                        
                    stats['valid_entries'] += 1
                    
                    # Extract and process question/answer
                    question = entry['question'].strip()
                    raw_answer = entry['answer'].strip()
                    processed_answer = parse_gsm_answer(raw_answer, logger)
                    
                    # Add to SIEV format
                    siev_data[question_index] = {
                        "question": question,
                        "answer": processed_answer
                    }
                    
                    question_index += 1
                    stats['processed_entries'] += 1
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Line {line_num}: JSON decode error - {str(e)}")
                    stats['invalid_entries'] += 1
                    continue
                except Exception as e:
                    logger.error(f"Line {line_num}: Processing error - {str(e)}")
                    stats['invalid_entries'] += 1
                    continue
        
        # Update metadata
        siev_data["info"]["total_questions"] = stats['processed_entries']
        
        # Write output file
        logger.info(f"Writing output to: {output_path}")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(siev_data, f, indent=4, ensure_ascii=False)
            
        # Print summary
        logger.info("=" * 60)
        logger.info("CONVERSION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total lines processed: {stats['total_lines']}")
        logger.info(f"Valid entries: {stats['valid_entries']}")
        logger.info(f"Invalid entries: {stats['invalid_entries']}")
        logger.info(f"Questions converted: {stats['processed_entries']}")
        logger.info(f"Output file: {output_path}")
        logger.info("=" * 60)
        
        return True, stats
        
    except Exception as e:
        logger.error(f"Conversion failed: {str(e)}")
        return False, stats

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Convert GSM-8K JSONL dataset to SIEV JSON exam format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic conversion
  python3 convert_gsm.py --input_file test.jsonl --output_dir data/input/gsm_data
  
  # Convert with custom filename
  python3 convert_gsm.py --input_file test.jsonl --output_dir data/input/gsm_data --filename my_gsm_test.json
  
  # Verbose output for debugging
  python3 convert_gsm.py --input_file test.jsonl --output_dir data/input/gsm_data --verbose

Integration with SIEV evaluation:
  # After conversion, run evaluation with all 5 required arguments:
  ./evaluate-gsm.sh "gpt-4o" "gsm-experiment" "env/.env" 3 "data/input/gsm_data/gsm_exam.json"
  
  # Arguments: <model> <experiment_name> <env_file> <num_attempts> <exam_path>

Dataset Download:
  wget https://github.com/openai/grade-school-math/raw/master/grade_school_math/data/test.jsonl
        """
    )
    
    parser.add_argument(
        '--input_file', 
        type=str, 
        required=True,
        help='Path to GSM-8K test.jsonl file'
    )
    
    parser.add_argument(
        '--output_dir', 
        type=str, 
        required=True,
        help='Output directory for converted JSON file'
    )
    
    parser.add_argument(
        '--filename', 
        type=str, 
        default=None,
        help='Output filename (default: gsm_exam.json)'
    )
    
    parser.add_argument(
        '--verbose', 
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    # Convert dataset
    success, stats = convert_gsm_to_siev(
        input_file=args.input_file,
        output_dir=args.output_dir,
        filename=args.filename,
        verbose=args.verbose
    )
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()