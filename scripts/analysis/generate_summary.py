# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
SIEV Experiment Results Summarizer
=================================

Essential analysis script for processing dialectical reasoning experimental results
and creating statistical summaries and performance analyses.

** CRITICAL: This script is required by wrapper scripts and should NOT be deleted **

Key Features:
- Statistical summary generation across experiments
- Model performance comparison analysis
- Cross-scenario result aggregation
- CSV export with detailed metrics
- Integration with SIEV evaluation pipeline

Usage (automatic via experiment scripts):
    python3 generate_summary.py --dirs=<experiment_dir> --output=<output_dir>

Author: Soheil Abbasloo (Microsoft Research)
Status: Required for evaluation pipeline
"""

# Standard library imports
import argparse
import json
import os
import sys
from collections import defaultdict
import glob
from concurrent.futures import ThreadPoolExecutor
import csv

# Third-party imports
import pandas as pd
import numpy as np

def dbgprint(debug_flag, message):
    if debug_flag:
        print(message)

DBG = False

def extract_model_from_directory_name(dir_name):
    """
    Extract model name from standardized SIEV directory format:
    {exam_filename}_{model}_{num_critics}_{num_thesis}_{mode}_{multimodel}
    
    Args:
        dir_name (str): Directory name following SIEV naming convention
        
    Returns:
        str or None: Extracted model name, or None if parsing fails
        
    Examples:
        "sample_exam_gpt-4o_1_1_hegel_0" -> "gpt-4o"
        "sample_exam_o1_1_1_hegel_0" -> "o1"
    """
    parts = dir_name.split('_')
    if len(parts) < 6:
        return None
    
    # Validate and remove the known suffix: {critics}_{thesis}_{mode}_{multimodel}
    try:
        multimodel = int(parts[-1])  # Should be 0 or 1
        mode = parts[-2]             # Should be "hegel"
        thesis = int(parts[-3])      # Should be number  
        critics = int(parts[-4])     # Should be number
    except (ValueError, IndexError):
        return None
    
    # Remove the suffix, leaving parts before the last 4
    remaining_parts = parts[:-4]
    
    if len(remaining_parts) < 2:
        return None
    
    # For "sample_exam_gpt-4o", we want "gpt-4o" (last part)
    # For "sample_exam_azure-gpt-4o", we want "azure-gpt-4o" (last part)
    # The model is always the last part after removing the suffix
    return remaining_parts[-1]


def extract_scenario_from_directory_name(dir_name):
    """
    Extract scenario name from standardized SIEV directory format.
    
    Args:
        dir_name (str): Directory name following SIEV naming convention
        
    Returns:
        str or None: Extracted scenario name, or None if parsing fails
        
    Examples:
        "sample_exam_gpt-4o_1_1_hegel_0" -> "sample_exam"
        "gsm_test_o1_1_1_hegel_0" -> "gsm_test"
    """
    parts = dir_name.split('_')
    if len(parts) < 6:
        return None
    
    # Validate and remove the known suffix: {critics}_{thesis}_{mode}_{multimodel}
    try:
        multimodel = int(parts[-1])  # Should be 0 or 1
        mode = parts[-2]             # Should be "hegel"
        thesis = int(parts[-3])      # Should be number  
        critics = int(parts[-4])     # Should be number
    except (ValueError, IndexError):
        return None
    
    # Remove the suffix, leaving parts before the last 4
    remaining_parts = parts[:-4]
    
    if len(remaining_parts) < 2:
        return None
    
    # For "sample_exam_gpt-4o", we want "sample_exam" (all parts except the last)
    # The scenario is everything except the last part (which is the model)
    return '_'.join(remaining_parts[:-1])


def load_results(dirs):
    summary = []
    for dir_path in dirs:
        dbgprint(DBG, f"Processing directory: {dir_path}")
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            if os.path.isdir(item_path):
                model = extract_model_from_directory_name(item)
                scenario = extract_scenario_from_directory_name(item)
                
                if model and scenario:
                    dbgprint(DBG, f"Found experiment: {item} -> Model: {model}, Scenario: {scenario}")
                    
                    # Find all evaluation_results_attempt_*.json files for this experiment
                    results_files = glob.glob(os.path.join(item_path, 'evaluation_results_attempt_*.json'))
                    
                    if not results_files:
                        dbgprint(DBG, f"No evaluation results files found in {item_path}")
                        continue
                    
                    # Initialize arrays to collect values from multiple attempts
                    thesis_corrects = []
                    synthesis_corrects = {}
                    antitheses_corrects = {}
                    num_questions = None
                    thesis_correct_synthesis_incorrect_count = []
                    thesis_incorrect_synthesis_correct_count = []
                    thesis_and_synthesis_correct_count = []
                    antitheses_correct = []
                    thesis_ant_correct_synth_incorrect = []
                    ant_correct_thesis_synth_incorrect = []
                    thesis_and_ant_correct = []
                    
                    # All 8 permutations of (Thesis, Antithesis, Synthesis) correctness
                    thesis_ant_synth_all_correct = []
                    thesis_synth_correct_ant_incorrect = []
                    thesis_correct_ant_synth_incorrect = []
                    ant_synth_correct_thesis_incorrect = []
                    synth_correct_thesis_ant_incorrect = []
                    all_incorrect = []
                    
                    # Process each attempt file to build arrays (like old script)
                    for results_file in results_files:
                        try:
                            with open(results_file, 'r') as f:
                                data = json.load(f)
                                
                                if num_questions is None:
                                    num_questions = data.get('num_questions', 1)
                                
                                # Collect thesis values
                                thesis_corrects.append(data.get('thesis_correct', 0))
                                thesis_correct_synthesis_incorrect_count.append(data.get('thesis_correct_synthesis_incorrect_count', 0))
                                thesis_incorrect_synthesis_correct_count.append(data.get('thesis_incorrect_synthesis_correct_count', 0))
                                thesis_and_synthesis_correct_count.append(data.get('thesis_and_synthesis_correct_count', 0))
                                
                                # Handle antithesis fields
                                if 'antitheses_correct' in data:
                                    antitheses_correct.append(data['antitheses_correct'])
                                if 'thesis_ant_correct_synth_incorrect' in data:
                                    thesis_ant_correct_synth_incorrect.append(data['thesis_ant_correct_synth_incorrect'])
                                if 'ant_correct_thesis_synth_incorrect' in data:
                                    ant_correct_thesis_synth_incorrect.append(data['ant_correct_thesis_synth_incorrect'])
                                if 'thesis_and_ant_correct' in data:
                                    thesis_and_ant_correct.append(data['thesis_and_ant_correct'])
                                    
                                # Handle all 8 permutations
                                if 'thesis_ant_synth_all_correct' in data:
                                    thesis_ant_synth_all_correct.append(data['thesis_ant_synth_all_correct'])
                                if 'thesis_synth_correct_ant_incorrect' in data:
                                    thesis_synth_correct_ant_incorrect.append(data['thesis_synth_correct_ant_incorrect'])
                                if 'thesis_correct_ant_synth_incorrect' in data:
                                    thesis_correct_ant_synth_incorrect.append(data['thesis_correct_ant_synth_incorrect'])
                                if 'ant_synth_correct_thesis_incorrect' in data:
                                    ant_synth_correct_thesis_incorrect.append(data['ant_synth_correct_thesis_incorrect'])
                                if 'synth_correct_thesis_ant_incorrect' in data:
                                    synth_correct_thesis_ant_incorrect.append(data['synth_correct_thesis_ant_incorrect'])
                                if 'all_incorrect' in data:
                                    all_incorrect.append(data['all_incorrect'])
                                
                                # Collect synthesis and antithesis values by iteration number
                                for key, value in data.items():
                                    if ((key.startswith('synthesis_') or key.startswith('thesis_') or key.startswith('max_first_')) and key.split('_')[-1].isdigit()):
                                        synthesis_key = key.split('_')[-1]
                                        if synthesis_key not in synthesis_corrects:
                                            synthesis_corrects[synthesis_key] = []
                                        synthesis_corrects[synthesis_key].append(value)
                                    elif key.startswith('antithesis_') and key.split('_')[-1].isdigit():
                                        antithesis_key = key.split('_')[-1]
                                        if antithesis_key not in antitheses_corrects:
                                            antitheses_corrects[antithesis_key] = []
                                        antitheses_corrects[antithesis_key].append(value)
                                        
                        except (FileNotFoundError, json.JSONDecodeError) as e:
                            dbgprint(DBG, f"Error reading file: {results_file} - {e}")
                            continue
                    
                    # Create summary entry with arrays (matching old script format)
                    if synthesis_corrects == {} and antitheses_corrects == {}:
                        summary.append({
                            'Scenario': scenario,
                            'Model': model,
                            'Design': 'hegel',
                            'Num Questions': num_questions,
                            'Thesis Correct': thesis_corrects,
                        })
                    else:
                        summary.append({
                            'Scenario': scenario,
                            'Model': model,
                            'Design': 'hegel',
                            'Num Questions': num_questions,
                            'Thesis Correct': thesis_corrects,
                            'Synthesis Correct': synthesis_corrects,
                            'Antitheses Correct Dict': antitheses_corrects,
                            'Thesis Correct Synthesis Incorrect Count': thesis_correct_synthesis_incorrect_count,
                            'Thesis Incorrect Synthesis Correct Count': thesis_incorrect_synthesis_correct_count,
                            'Thesis and Synthesis Correct Count': thesis_and_synthesis_correct_count,
                            'Antitheses Correct': antitheses_correct,
                            'Thesis Ant Correct Synth Incorrect': thesis_ant_correct_synth_incorrect,
                            'Ant Correct Thesis Synth Incorrect': ant_correct_thesis_synth_incorrect,
                            'Thesis and Ant Correct': thesis_and_ant_correct,
                            # All 8 permutations
                            'Thesis Ant Synth All Correct': thesis_ant_synth_all_correct,
                            'Thesis Synth Correct Ant Incorrect': thesis_synth_correct_ant_incorrect,
                            'Thesis Correct Ant Synth Incorrect': thesis_correct_ant_synth_incorrect,
                            'Ant Synth Correct Thesis Incorrect': ant_synth_correct_thesis_incorrect,
                            'Synth Correct Thesis Ant Incorrect': synth_correct_thesis_ant_incorrect,
                            'All Incorrect': all_incorrect
                        })
                else:
                    dbgprint(DBG, f"Could not extract model/scenario from directory name: {item}")
    
    return summary


def convert_to_csv(summary, output_dir):
    """Convert summary data to CSV format matching the old script structure"""
    rows = []
    for item in summary:
        scenario = item.get('Scenario', '')
        model = item.get('Model', '')
        design = item.get('Design', 'hegel')
        num_questions = item.get('Num Questions', 0)
        
        # Get array data
        thesis_corrects = item.get('Thesis Correct', [])
        synthesis_corrects = item.get('Synthesis Correct', {})
        
        # Create one row per attempt
        max_attempts = len(thesis_corrects) if thesis_corrects else 1
        for attempt_idx in range(max_attempts):
            thesis_correct = thesis_corrects[attempt_idx] if attempt_idx < len(thesis_corrects) else 0
            
            # Get synthesis value for attempt (use synthesis_0 if available)
            synthesis_correct = 0
            if '0' in synthesis_corrects and attempt_idx < len(synthesis_corrects['0']):
                synthesis_correct = synthesis_corrects['0'][attempt_idx]
            
            # Get other metrics if available
            thesis_correct_synthesis_incorrect_count = 0
            if 'Thesis Correct Synthesis Incorrect Count' in item:
                tcsi_list = item['Thesis Correct Synthesis Incorrect Count']
                if attempt_idx < len(tcsi_list):
                    thesis_correct_synthesis_incorrect_count = tcsi_list[attempt_idx]
            
            rows.append([
                scenario, model, design, num_questions, attempt_idx + 1, thesis_correct,
                thesis_correct_synthesis_incorrect_count, 0, 0, 'NA', synthesis_correct,
                0, 0, 0, 0, 'NA', 0, 0, 0, 0, 0, 0, 0
            ])

    df = pd.DataFrame(rows, columns=[
        'Scenario', 'Model', 'Design', 'Num Questions', 'Attempt', 'Thesis Correct', 
        'Thesis Correct Synthesis Incorrect Count', 'Thesis Incorrect Synthesis Correct Count', 
        'Thesis and Synthesis Correct Count', 'Synthesis Iteration', 'Synthesis Correct',
        'Antitheses Correct', 'Thesis Ant Correct Synth Incorrect', 'Ant Correct Thesis Synth Incorrect',
        'Thesis and Ant Correct', 'Antithesis Iteration', 'Antithesis Correct',
        'Thesis Ant Synth All Correct', 'Thesis Synth Correct Ant Incorrect', 'Thesis Correct Ant Synth Incorrect',
        'Ant Synth Correct Thesis Incorrect', 'Synth Correct Thesis Ant Incorrect', 'All Incorrect'
    ])
    df.to_csv(os.path.join(output_dir, 'summary.csv'), index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=str, required=True, help='Path to the output directory')
    parser.add_argument('--dirs', type=str, required=True, help='Comma-separated list of directories to summarize')
    parser.add_argument('--precision', type=int, default=5, help='Number of decimal places for rounding (default: 5)')
    args = parser.parse_args()
    output_dir = args.output
    dirs = args.dirs.split(',')
    pres = args.precision
    dbgprint(DBG, f"input dirs: {dirs}")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    summary = load_results(dirs)
    with open(os.path.join(output_dir, 'summary.json'), 'w') as f:
        json.dump(summary, f, indent=4)
    convert_to_csv(summary, output_dir)