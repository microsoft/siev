# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
SIEV Experiment Results Aggregator
==================================

Essential analysis script for aggregating results across multiple dialectical reasoning 
experiments. This script combines experimental results and generates unified summary 
statistics with proper statistical calculations.

** CRITICAL: This script is required by wrapper scripts and should NOT be deleted **

Key Features:
- Cross-experiment result aggregation
- Weighted statistical calculations with proper standard deviation handling
- Auto-detection of attempt counts for accurate statistics
- Summary statistics generation across multiple experimental runs
- Unified reporting across different reasoning benchmarks
- Integration with evaluation pipeline

Called by:
- run_gsm_experiments.sh
- run_mmlu_experiments.sh

Input/Output:
- Input: summary.json from individual experiments
- Output: summary_aggregate.json with combined statistics

Usage (automatic via wrappers):
    python3 gsm-mmlu-aggregate.py -i summary.json -o summary_aggregate.json
    python3 gsm-mmlu-aggregate.py -i summary.json -o summary_aggregate.json --attempts 3

Author: Soheil Abbasloo (Microsoft Research)
Status: Required for evaluation pipeline
"""

# Standard library imports
import argparse
import json
from collections import defaultdict

# Third-party imports
import numpy as np

def weighted_std(values, weights):
    """Calculate weighted standard deviation"""
    if len(values) == 0 or len(weights) == 0:
        return 0
    
    values = np.array(values)
    weights = np.array(weights)
    
    # Calculate weighted mean
    weighted_mean = np.average(values, weights=weights)
    
    # Calculate weighted variance
    weighted_variance = np.average((values - weighted_mean)**2, weights=weights)
    
    # Return weighted standard deviation
    return np.sqrt(weighted_variance)

def weighted_overall_std(scenario_averages, scenario_stds, weights, overall_average):
    """
    Calculate weighted overall standard deviation using scenario averages, scenario stds, and weights.
    
    Formula: Overall_Std = √[Σ(weight_i × (std_i² + (scenario_avg_i - overall_avg)²)) / Σ(weight_i)]
    
    Args:
        scenario_averages: List of scenario average values
        scenario_stds: List of scenario standard deviation values  
        weights: List of weights (number of questions per scenario)
        overall_average: The weighted overall average
    
    Returns:
        Weighted overall standard deviation
    """
    if len(scenario_averages) == 0 or len(weights) == 0:
        return 0
    
    scenario_averages = np.array(scenario_averages)
    scenario_stds = np.array(scenario_stds)
    weights = np.array(weights)
    
    # Calculate weighted overall variance using the pooled formula
    weighted_variance_sum = np.sum(weights * (scenario_stds**2 + (scenario_averages - overall_average)**2))
    total_weight = np.sum(weights)
    
    if total_weight == 0:
        return 0
    
    overall_variance = weighted_variance_sum / total_weight
    
    # Return weighted overall standard deviation
    return np.sqrt(overall_variance)

def detect_num_attempts(entries):
    """
    Auto-detect the number of attempts from the data structure.
    
    Args:
        entries: List of scenario entries for a model/design combination
    
    Returns:
        Number of attempts detected from the data
    """
    if not entries:
        return 1
    
    # Check the first entry to see how many values are in the arrays
    first_entry = entries[0]
    
    # Look for any array field to determine the number of attempts
    for key, value in first_entry.items():
        if isinstance(value, list) and key not in ['Scenario', 'Model', 'Design']:
            return len(value)
    
    # Default to 1 if no arrays found
    return 1

def calculate_raw_attempt_std(entries, num_attempts=None):
    """
    Calculate overall standard deviation directly from raw attempt data.
    For each attempt, calculate overall performance across all scenarios,
    then compute std of these overall performance values.
    
    Args:
        entries: List of scenario entries for a model/design combination
        num_attempts: Number of attempts (if None, will be auto-detected)
    
    Returns:
        Dictionary with raw attempt statistics for all metrics
    """
    if not entries:
        return {}
    
    # Initialize dictionaries to store per-attempt overall results
    attempt_results = {
        'thesis': [],
        'synthesis': [],
        'thesis_correct_synthesis_incorrect': [],
        'thesis_incorrect_synthesis_correct': [],
        'thesis_and_synthesis_correct': [],
        'antitheses_correct': [],
        'thesis_ant_correct_synth_incorrect': [],
        'ant_correct_thesis_synth_incorrect': [],
        'thesis_and_ant_correct': [],
        'thesis_ant_synth_all_correct': [],
        'thesis_synth_correct_ant_incorrect': [],
        'thesis_correct_ant_synth_incorrect': [],
        'ant_synth_correct_thesis_incorrect': [],
        'synth_correct_thesis_ant_incorrect': [],
        'all_incorrect': []
    }
    
    # Auto-detect or use provided number of attempts
    if num_attempts is None:
        num_attempts = detect_num_attempts(entries)
    
    for attempt_idx in range(num_attempts):
        # Calculate weighted overall for this specific attempt across all scenarios
        total_questions_attempt = 0
        weighted_sums_attempt = {key: 0 for key in attempt_results.keys()}
        
        for entry in entries:
            try:
                num_questions = entry["Num Questions"]
                if num_questions == 0:
                    continue
                    
                total_questions_attempt += num_questions
                
                # Extract attempt-specific values and calculate weighted contributions
                if attempt_idx < len(entry.get("Thesis Correct", [])):
                    thesis_val = entry["Thesis Correct"][attempt_idx] / num_questions
                    weighted_sums_attempt['thesis'] += thesis_val * num_questions
                
                synthesis_values = entry.get("Synthesis Correct", {}).get("0", [])
                if attempt_idx < len(synthesis_values):
                    synthesis_val = synthesis_values[attempt_idx] / num_questions
                    weighted_sums_attempt['synthesis'] += synthesis_val * num_questions
                
                # Handle other metrics similarly
                for field, key in [
                    ("Thesis Correct Synthesis Incorrect Count", 'thesis_correct_synthesis_incorrect'),
                    ("Thesis Incorrect Synthesis Correct Count", 'thesis_incorrect_synthesis_correct'),
                    ("Thesis and Synthesis Correct Count", 'thesis_and_synthesis_correct'),
                    ("Antitheses Correct", 'antitheses_correct'),
                    ("Thesis Ant Correct Synth Incorrect", 'thesis_ant_correct_synth_incorrect'),
                    ("Ant Correct Thesis Synth Incorrect", 'ant_correct_thesis_synth_incorrect'),
                    ("Thesis and Ant Correct", 'thesis_and_ant_correct'),
                    ("Thesis Ant Synth All Correct", 'thesis_ant_synth_all_correct'),
                    ("Thesis Synth Correct Ant Incorrect", 'thesis_synth_correct_ant_incorrect'),
                    ("Thesis Correct Ant Synth Incorrect", 'thesis_correct_ant_synth_incorrect'),
                    ("Ant Synth Correct Thesis Incorrect", 'ant_synth_correct_thesis_incorrect'),
                    ("Synth Correct Thesis Ant Incorrect", 'synth_correct_thesis_ant_incorrect'),
                    ("All Incorrect", 'all_incorrect')
                ]:
                    field_values = entry.get(field, [])
                    if attempt_idx < len(field_values):
                        field_val = field_values[attempt_idx] / num_questions
                        weighted_sums_attempt[key] += field_val * num_questions
                        
            except (KeyError, IndexError, ZeroDivisionError):
                continue
        
        # Calculate overall averages for this attempt
        if total_questions_attempt > 0:
            for key in attempt_results.keys():
                overall_avg = weighted_sums_attempt[key] / total_questions_attempt
                attempt_results[key].append(overall_avg)
    
    # Calculate mean and std across all attempts for each metric
    raw_attempt_stats = {}
    for key, values in attempt_results.items():
        if len(values) > 0:
            raw_attempt_stats[f'{key}_raw_avg'] = np.mean(values)
            raw_attempt_stats[f'{key}_raw_std'] = np.std(values) if len(values) > 1 else 0
        else:
            raw_attempt_stats[f'{key}_raw_avg'] = 0
            raw_attempt_stats[f'{key}_raw_std'] = 0
    
    return raw_attempt_stats

# Argument parser setup
parser = argparse.ArgumentParser(description="Calculate scenario averages and overall weighted averages per Model/Design.")
parser.add_argument("--input", "-i", required=True, help="Input JSON file name")
parser.add_argument("--output", "-o", required=True, help="Output JSON file name")
parser.add_argument("--precision", "-p", type=int, default=5, help="Number of decimal places for rounding (default: 5)")
parser.add_argument("--attempts", "-a", type=int, default=None, help="Number of attempts per scenario (default: auto-detect from data)")
args = parser.parse_args()

# Set precision parameter
pres = args.precision

# Load input JSON data
with open(args.input, 'r') as file:
    raw_data = json.load(file)

# Flatten the data structure if it's nested by scenario
data = []
if isinstance(raw_data, dict):
    # Handle nested structure: {"scenario": [entries]}
    for scenario, entries in raw_data.items():
        if isinstance(entries, list):
            data.extend(entries)
elif isinstance(raw_data, list):
    # Handle flat structure: [entries]
    data = raw_data
else:
    raise ValueError("Unexpected data structure in input JSON")

# Group data by Model and Design
grouped_data = defaultdict(list)
for entry in data:
    key = (entry["Model"], entry["Design"])
    grouped_data[key].append(entry)

results = []

# Process each group (Model/Design combination)
for (model, design), entries in grouped_data.items():
    # Initialize variables for overall weighted averages for this group
    total_questions_group = 0
    weighted_thesis_sum_group = 0
    weighted_synthesis_sum_group = 0
    weighed_thesis_correct_synthesis_incorrect_sum_group = 0
    weighted_thesis_incorrect_synthesis_correct_sum_group = 0
    weighted_thesis_and_synthesis_correct_sum_group = 0
    weighted_antitheses_correct_sum_group = 0
    weighted_thesis_ant_correct_synth_incorrect_sum_group = 0
    weighted_ant_correct_thesis_synth_incorrect_sum_group = 0
    weighted_thesis_and_ant_correct_sum_group = 0
    
    # Add weighted sums for the permutation fields
    weighted_thesis_ant_synth_all_correct_sum_group = 0
    weighted_thesis_synth_correct_ant_incorrect_sum_group = 0
    weighted_thesis_correct_ant_synth_incorrect_sum_group = 0
    weighted_ant_synth_correct_thesis_incorrect_sum_group = 0
    weighted_synth_correct_thesis_ant_incorrect_sum_group = 0
    weighted_all_incorrect_sum_group = 0
    
    # Initialize lists to store individual values for weighted std calculation
    thesis_values_group = []
    synthesis_values_group = []
    thesis_correct_synthesis_incorrect_values_group = []
    thesis_incorrect_synthesis_correct_values_group = []
    thesis_and_synthesis_correct_values_group = []
    antitheses_correct_values_group = []
    thesis_ant_correct_synth_incorrect_values_group = []
    ant_correct_thesis_synth_incorrect_values_group = []
    thesis_and_ant_correct_values_group = []
    thesis_ant_synth_all_correct_values_group = []
    thesis_synth_correct_ant_incorrect_values_group = []
    thesis_correct_ant_synth_incorrect_values_group = []
    ant_synth_correct_thesis_incorrect_values_group = []
    synth_correct_thesis_ant_incorrect_values_group = []
    all_incorrect_values_group = []
    weights_group = []
    
    # Initialize lists to store scenario standard deviations for reuse
    thesis_stds_group = []
    synthesis_stds_group = []
    thesis_correct_synthesis_incorrect_stds_group = []
    thesis_incorrect_synthesis_correct_stds_group = []
    thesis_and_synthesis_correct_stds_group = []
    antitheses_correct_stds_group = []
    thesis_ant_correct_synth_incorrect_stds_group = []
    ant_correct_thesis_synth_incorrect_stds_group = []
    thesis_and_ant_correct_stds_group = []
    thesis_ant_synth_all_correct_stds_group = []
    thesis_synth_correct_ant_incorrect_stds_group = []
    thesis_correct_ant_synth_incorrect_stds_group = []
    ant_synth_correct_thesis_incorrect_stds_group = []
    synth_correct_thesis_ant_incorrect_stds_group = []
    all_incorrect_stds_group = []

    # Calculate per-scenario results within the group
    for entry in entries:
        try:
            num_questions = entry["Num Questions"]
        except KeyError:
            print(f"Warning: 'Num Questions' key not found in entry: {entry}")
            continue

        # Calculate proportions first, then compute stats
        thesis_proportions = [x / num_questions for x in entry["Thesis Correct"]] if num_questions > 0 else [0] * len(entry["Thesis Correct"])
        thesis_avg = np.mean(thesis_proportions)
        thesis_std = np.std(thesis_proportions)

        # Handle potential missing or differently structured "Synthesis Correct"
        synthesis_values = entry.get("Synthesis Correct", {}).get("0", [])
        if synthesis_values and num_questions > 0:
            synthesis_proportions = [x / num_questions for x in synthesis_values]
            synthesis_avg = np.mean(synthesis_proportions)
            synthesis_std = np.std(synthesis_proportions)
        else:
            synthesis_avg = 0
            synthesis_std = 0
        
        # 'Thesis Correct Synthesis Incorrect Count': thesis_correct_synthesis_incorrect_count,
        # 'Thesis Incorrect Synthesis Correct Count': thesis_incorrect_synthesis_correct_count,
        # 'Thesis and Synthesis Correct Count': thesis_and_synthesis_correct_count
        
        # Calculate proportions for thesis/synthesis combination fields
        if entry.get("Thesis Correct Synthesis Incorrect Count") and num_questions > 0:
            thesis_correct_synthesis_incorrect_proportions = [x / num_questions for x in entry["Thesis Correct Synthesis Incorrect Count"]]
            thesis_correct_synthesis_incorrect_avg = np.mean(thesis_correct_synthesis_incorrect_proportions)
            thesis_correct_synthesis_incorrect_std = np.std(thesis_correct_synthesis_incorrect_proportions)
        else:
            thesis_correct_synthesis_incorrect_avg = 0
            thesis_correct_synthesis_incorrect_std = 0
    
        if entry.get("Thesis Incorrect Synthesis Correct Count") and num_questions > 0:
            thesis_incorrect_synthesis_correct_proportions = [x / num_questions for x in entry["Thesis Incorrect Synthesis Correct Count"]]
            thesis_incorrect_synthesis_correct_avg = np.mean(thesis_incorrect_synthesis_correct_proportions)
            thesis_incorrect_synthesis_correct_std = np.std(thesis_incorrect_synthesis_correct_proportions)
        else:
            thesis_incorrect_synthesis_correct_avg = 0
            thesis_incorrect_synthesis_correct_std = 0

        if entry.get("Thesis and Synthesis Correct Count") and num_questions > 0:
            thesis_and_synthesis_correct_proportions = [x / num_questions for x in entry["Thesis and Synthesis Correct Count"]]
            thesis_and_synthesis_correct_avg = np.mean(thesis_and_synthesis_correct_proportions)
            thesis_and_synthesis_correct_std = np.std(thesis_and_synthesis_correct_proportions)
        else:
            thesis_and_synthesis_correct_avg = 0
            thesis_and_synthesis_correct_std = 0

        # Handle antithesis-related fields
        if entry.get("Antitheses Correct") and num_questions > 0:
            antitheses_correct_proportions = [x / num_questions for x in entry["Antitheses Correct"]]
            antitheses_correct_avg = np.mean(antitheses_correct_proportions)
            antitheses_correct_std = np.std(antitheses_correct_proportions)
        else:
            antitheses_correct_avg = 0
            antitheses_correct_std = 0
        
        if entry.get("Thesis Ant Correct Synth Incorrect") and num_questions > 0:
            thesis_ant_correct_synth_incorrect_proportions = [x / num_questions for x in entry["Thesis Ant Correct Synth Incorrect"]]
            thesis_ant_correct_synth_incorrect_avg = np.mean(thesis_ant_correct_synth_incorrect_proportions)
            thesis_ant_correct_synth_incorrect_std = np.std(thesis_ant_correct_synth_incorrect_proportions)
        else:
            thesis_ant_correct_synth_incorrect_avg = 0
            thesis_ant_correct_synth_incorrect_std = 0
        
        if entry.get("Ant Correct Thesis Synth Incorrect") and num_questions > 0:
            ant_correct_thesis_synth_incorrect_proportions = [x / num_questions for x in entry["Ant Correct Thesis Synth Incorrect"]]
            ant_correct_thesis_synth_incorrect_avg = np.mean(ant_correct_thesis_synth_incorrect_proportions)
            ant_correct_thesis_synth_incorrect_std = np.std(ant_correct_thesis_synth_incorrect_proportions)
        else:
            ant_correct_thesis_synth_incorrect_avg = 0
            ant_correct_thesis_synth_incorrect_std = 0
        
        if entry.get("Thesis and Ant Correct") and num_questions > 0:
            thesis_and_ant_correct_proportions = [x / num_questions for x in entry["Thesis and Ant Correct"]]
            thesis_and_ant_correct_avg = np.mean(thesis_and_ant_correct_proportions)
            thesis_and_ant_correct_std = np.std(thesis_and_ant_correct_proportions)
        else:
            thesis_and_ant_correct_avg = 0
            thesis_and_ant_correct_std = 0
        
        # Handle 8-permutation fields
        if entry.get("Thesis Ant Synth All Correct") and num_questions > 0:
            thesis_ant_synth_all_correct_proportions = [x / num_questions for x in entry["Thesis Ant Synth All Correct"]]
            thesis_ant_synth_all_correct_avg = np.mean(thesis_ant_synth_all_correct_proportions)
            thesis_ant_synth_all_correct_std = np.std(thesis_ant_synth_all_correct_proportions)
        else:
            thesis_ant_synth_all_correct_avg = 0
            thesis_ant_synth_all_correct_std = 0
        
        if entry.get("Thesis Synth Correct Ant Incorrect") and num_questions > 0:
            thesis_synth_correct_ant_incorrect_proportions = [x / num_questions for x in entry["Thesis Synth Correct Ant Incorrect"]]
            thesis_synth_correct_ant_incorrect_avg = np.mean(thesis_synth_correct_ant_incorrect_proportions)
            thesis_synth_correct_ant_incorrect_std = np.std(thesis_synth_correct_ant_incorrect_proportions)
        else:
            thesis_synth_correct_ant_incorrect_avg = 0
            thesis_synth_correct_ant_incorrect_std = 0
        
        if entry.get("Thesis Correct Ant Synth Incorrect") and num_questions > 0:
            thesis_correct_ant_synth_incorrect_proportions = [x / num_questions for x in entry["Thesis Correct Ant Synth Incorrect"]]
            thesis_correct_ant_synth_incorrect_avg = np.mean(thesis_correct_ant_synth_incorrect_proportions)
            thesis_correct_ant_synth_incorrect_std = np.std(thesis_correct_ant_synth_incorrect_proportions)
        else:
            thesis_correct_ant_synth_incorrect_avg = 0
            thesis_correct_ant_synth_incorrect_std = 0
        
        if entry.get("Ant Synth Correct Thesis Incorrect") and num_questions > 0:
            ant_synth_correct_thesis_incorrect_proportions = [x / num_questions for x in entry["Ant Synth Correct Thesis Incorrect"]]
            ant_synth_correct_thesis_incorrect_avg = np.mean(ant_synth_correct_thesis_incorrect_proportions)
            ant_synth_correct_thesis_incorrect_std = np.std(ant_synth_correct_thesis_incorrect_proportions)
        else:
            ant_synth_correct_thesis_incorrect_avg = 0
            ant_synth_correct_thesis_incorrect_std = 0
        
        if entry.get("Synth Correct Thesis Ant Incorrect") and num_questions > 0:
            synth_correct_thesis_ant_incorrect_proportions = [x / num_questions for x in entry["Synth Correct Thesis Ant Incorrect"]]
            synth_correct_thesis_ant_incorrect_avg = np.mean(synth_correct_thesis_ant_incorrect_proportions)
            synth_correct_thesis_ant_incorrect_std = np.std(synth_correct_thesis_ant_incorrect_proportions)
        else:
            synth_correct_thesis_ant_incorrect_avg = 0
            synth_correct_thesis_ant_incorrect_std = 0
        
        if entry.get("All Incorrect") and num_questions > 0:
            all_incorrect_proportions = [x / num_questions for x in entry["All Incorrect"]]
            all_incorrect_avg = np.mean(all_incorrect_proportions)
            all_incorrect_std = np.std(all_incorrect_proportions)
        else:
            all_incorrect_avg = 0
            all_incorrect_std = 0
              
        difference = thesis_avg - synthesis_avg

        results.append({
            "Scenario": entry["Scenario"],
            "Model": entry["Model"],
            "Design": entry["Design"],
            "Num Questions": num_questions,
            "Thesis Average": thesis_avg,
            "Thesis Std": thesis_std,
            "Synthesis Average": synthesis_avg,
            "Synthesis Std": synthesis_std,
            "Thesis Average - Synthesis Average": difference,
            "Thesis Correct Synthesis Incorrect Average": thesis_correct_synthesis_incorrect_avg,
            "Thesis Correct Synthesis Incorrect Std": thesis_correct_synthesis_incorrect_std,
            "Thesis Incorrect Synthesis Correct Average": thesis_incorrect_synthesis_correct_avg,
            "Thesis Incorrect Synthesis Correct Std": thesis_incorrect_synthesis_correct_std,
            "Thesis and Synthesis Correct Average": thesis_and_synthesis_correct_avg,
            "Thesis and Synthesis Correct Std": thesis_and_synthesis_correct_std,
            "Thesis Incorrect Synthesis Correct Average - Thesis Correct Synthesis Incorrect Average": thesis_incorrect_synthesis_correct_avg - thesis_correct_synthesis_incorrect_avg,
            "Antitheses Correct Average": antitheses_correct_avg,
            "Antitheses Correct Std": antitheses_correct_std,
            "Thesis Ant Correct Synth Incorrect Average": thesis_ant_correct_synth_incorrect_avg,
            "Thesis Ant Correct Synth Incorrect Std": thesis_ant_correct_synth_incorrect_std,
            "Ant Correct Thesis Synth Incorrect Average": ant_correct_thesis_synth_incorrect_avg,
            "Ant Correct Thesis Synth Incorrect Std": ant_correct_thesis_synth_incorrect_std,
            "Thesis and Ant Correct Average": thesis_and_ant_correct_avg,
            "Thesis and Ant Correct Std": thesis_and_ant_correct_std,
            # Add 8-permutation fields
            "Thesis Ant Synth All Correct Average": thesis_ant_synth_all_correct_avg,
            "Thesis Ant Synth All Correct Std": thesis_ant_synth_all_correct_std,
            "Thesis Synth Correct Ant Incorrect Average": thesis_synth_correct_ant_incorrect_avg,
            "Thesis Synth Correct Ant Incorrect Std": thesis_synth_correct_ant_incorrect_std,
            "Thesis Correct Ant Synth Incorrect Average": thesis_correct_ant_synth_incorrect_avg,
            "Thesis Correct Ant Synth Incorrect Std": thesis_correct_ant_synth_incorrect_std,
            "Ant Synth Correct Thesis Incorrect Average": ant_synth_correct_thesis_incorrect_avg,
            "Ant Synth Correct Thesis Incorrect Std": ant_synth_correct_thesis_incorrect_std,
            "Synth Correct Thesis Ant Incorrect Average": synth_correct_thesis_ant_incorrect_avg,
            "Synth Correct Thesis Ant Incorrect Std": synth_correct_thesis_ant_incorrect_std,
            "All Incorrect Average": all_incorrect_avg,
            "All Incorrect Std": all_incorrect_std
        })

        # Update weighted sums for the group's overall average
        total_questions_group += num_questions
        weighted_thesis_sum_group += thesis_avg * num_questions
        weighted_synthesis_sum_group += synthesis_avg * num_questions
        weighed_thesis_correct_synthesis_incorrect_sum_group += thesis_correct_synthesis_incorrect_avg * num_questions
        weighted_thesis_incorrect_synthesis_correct_sum_group += thesis_incorrect_synthesis_correct_avg * num_questions
        weighted_thesis_and_synthesis_correct_sum_group += thesis_and_synthesis_correct_avg * num_questions
        weighted_antitheses_correct_sum_group += antitheses_correct_avg * num_questions
        weighted_thesis_ant_correct_synth_incorrect_sum_group += thesis_ant_correct_synth_incorrect_avg * num_questions
        weighted_ant_correct_thesis_synth_incorrect_sum_group += ant_correct_thesis_synth_incorrect_avg * num_questions
        weighted_thesis_and_ant_correct_sum_group += thesis_and_ant_correct_avg * num_questions
        
        # Add weighted sums for 8-permutation fields
        weighted_thesis_ant_synth_all_correct_sum_group += thesis_ant_synth_all_correct_avg * num_questions
        weighted_thesis_synth_correct_ant_incorrect_sum_group += thesis_synth_correct_ant_incorrect_avg * num_questions
        weighted_thesis_correct_ant_synth_incorrect_sum_group += thesis_correct_ant_synth_incorrect_avg * num_questions
        weighted_ant_synth_correct_thesis_incorrect_sum_group += ant_synth_correct_thesis_incorrect_avg * num_questions
        weighted_synth_correct_thesis_ant_incorrect_sum_group += synth_correct_thesis_ant_incorrect_avg * num_questions
        weighted_all_incorrect_sum_group += all_incorrect_avg * num_questions
        
        # Store values and weights for weighted std calculation
        thesis_values_group.append(thesis_avg)
        synthesis_values_group.append(synthesis_avg)
        thesis_correct_synthesis_incorrect_values_group.append(thesis_correct_synthesis_incorrect_avg)
        thesis_incorrect_synthesis_correct_values_group.append(thesis_incorrect_synthesis_correct_avg)
        thesis_and_synthesis_correct_values_group.append(thesis_and_synthesis_correct_avg)
        antitheses_correct_values_group.append(antitheses_correct_avg)
        thesis_ant_correct_synth_incorrect_values_group.append(thesis_ant_correct_synth_incorrect_avg)
        ant_correct_thesis_synth_incorrect_values_group.append(ant_correct_thesis_synth_incorrect_avg)
        thesis_and_ant_correct_values_group.append(thesis_and_ant_correct_avg)
        thesis_ant_synth_all_correct_values_group.append(thesis_ant_synth_all_correct_avg)
        thesis_synth_correct_ant_incorrect_values_group.append(thesis_synth_correct_ant_incorrect_avg)
        thesis_correct_ant_synth_incorrect_values_group.append(thesis_correct_ant_synth_incorrect_avg)
        ant_synth_correct_thesis_incorrect_values_group.append(ant_synth_correct_thesis_incorrect_avg)
        synth_correct_thesis_ant_incorrect_values_group.append(synth_correct_thesis_ant_incorrect_avg)
        all_incorrect_values_group.append(all_incorrect_avg)
        weights_group.append(num_questions)
        
        # Store scenario standard deviations for reuse in overall calculations
        thesis_stds_group.append(thesis_std)
        synthesis_stds_group.append(synthesis_std)
        thesis_correct_synthesis_incorrect_stds_group.append(thesis_correct_synthesis_incorrect_std)
        thesis_incorrect_synthesis_correct_stds_group.append(thesis_incorrect_synthesis_correct_std)
        thesis_and_synthesis_correct_stds_group.append(thesis_and_synthesis_correct_std)
        antitheses_correct_stds_group.append(antitheses_correct_std)
        thesis_ant_correct_synth_incorrect_stds_group.append(thesis_ant_correct_synth_incorrect_std)
        ant_correct_thesis_synth_incorrect_stds_group.append(ant_correct_thesis_synth_incorrect_std)
        thesis_and_ant_correct_stds_group.append(thesis_and_ant_correct_std)
        thesis_ant_synth_all_correct_stds_group.append(thesis_ant_synth_all_correct_std)
        thesis_synth_correct_ant_incorrect_stds_group.append(thesis_synth_correct_ant_incorrect_std)
        thesis_correct_ant_synth_incorrect_stds_group.append(thesis_correct_ant_synth_incorrect_std)
        ant_synth_correct_thesis_incorrect_stds_group.append(ant_synth_correct_thesis_incorrect_std)
        synth_correct_thesis_ant_incorrect_stds_group.append(synth_correct_thesis_ant_incorrect_std)
        all_incorrect_stds_group.append(all_incorrect_std)


    # Calculate overall weighted averages for this group
    if total_questions_group > 0: # Avoid division by zero if a group is empty or has 0 questions
        overall_thesis_avg_group = round(weighted_thesis_sum_group / total_questions_group, pres)
        overall_synthesis_avg_group = round(weighted_synthesis_sum_group / total_questions_group, pres)
        overall_difference_group = round(overall_thesis_avg_group - overall_synthesis_avg_group, pres)
        overall_thesis_correct_synthesis_incorrect_avg_group = round(weighed_thesis_correct_synthesis_incorrect_sum_group / total_questions_group, pres)
        overall_thesis_incorrect_synthesis_correct_avg_group = round(weighted_thesis_incorrect_synthesis_correct_sum_group / total_questions_group, pres)
        overall_thesis_and_synthesis_correct_avg_group = round(weighted_thesis_and_synthesis_correct_sum_group / total_questions_group, pres)
        overall_antitheses_correct_avg_group = round(weighted_antitheses_correct_sum_group / total_questions_group, pres)
        overall_thesis_ant_correct_synth_incorrect_avg_group = round(weighted_thesis_ant_correct_synth_incorrect_sum_group / total_questions_group, pres)
        overall_ant_correct_thesis_synth_incorrect_avg_group = round(weighted_ant_correct_thesis_synth_incorrect_sum_group / total_questions_group, pres)
        overall_thesis_and_ant_correct_avg_group = round(weighted_thesis_and_ant_correct_sum_group / total_questions_group, pres)
        
        # Calculate overall averages for 8-permutation fields
        overall_thesis_ant_synth_all_correct_avg_group = round(weighted_thesis_ant_synth_all_correct_sum_group / total_questions_group, pres)
        overall_thesis_synth_correct_ant_incorrect_avg_group = round(weighted_thesis_synth_correct_ant_incorrect_sum_group / total_questions_group, pres)
        overall_thesis_correct_ant_synth_incorrect_avg_group = round(weighted_thesis_correct_ant_synth_incorrect_sum_group / total_questions_group, pres)
        overall_ant_synth_correct_thesis_incorrect_avg_group = round(weighted_ant_synth_correct_thesis_incorrect_sum_group / total_questions_group, pres)
        overall_synth_correct_thesis_ant_incorrect_avg_group = round(weighted_synth_correct_thesis_ant_incorrect_sum_group / total_questions_group, pres)
        overall_all_incorrect_avg_group = round(weighted_all_incorrect_sum_group / total_questions_group, pres)
        
        # Calculate weighted overall standard deviations using scenario averages, scenario stds, and weights
        overall_thesis_std_group = round(weighted_overall_std(thesis_values_group, thesis_stds_group, weights_group, overall_thesis_avg_group), pres)
        overall_synthesis_std_group = round(weighted_overall_std(synthesis_values_group, synthesis_stds_group, weights_group, overall_synthesis_avg_group), pres)
        overall_thesis_correct_synthesis_incorrect_std_group = round(weighted_overall_std(thesis_correct_synthesis_incorrect_values_group, thesis_correct_synthesis_incorrect_stds_group, weights_group, overall_thesis_correct_synthesis_incorrect_avg_group), pres)
        overall_thesis_incorrect_synthesis_correct_std_group = round(weighted_overall_std(thesis_incorrect_synthesis_correct_values_group, thesis_incorrect_synthesis_correct_stds_group, weights_group, overall_thesis_incorrect_synthesis_correct_avg_group), pres)
        overall_thesis_and_synthesis_correct_std_group = round(weighted_overall_std(thesis_and_synthesis_correct_values_group, thesis_and_synthesis_correct_stds_group, weights_group, overall_thesis_and_synthesis_correct_avg_group), pres)
        overall_antitheses_correct_std_group = round(weighted_overall_std(antitheses_correct_values_group, antitheses_correct_stds_group, weights_group, overall_antitheses_correct_avg_group), pres)
        overall_thesis_ant_correct_synth_incorrect_std_group = round(weighted_overall_std(thesis_ant_correct_synth_incorrect_values_group, thesis_ant_correct_synth_incorrect_stds_group, weights_group, overall_thesis_ant_correct_synth_incorrect_avg_group), pres)
        overall_ant_correct_thesis_synth_incorrect_std_group = round(weighted_overall_std(ant_correct_thesis_synth_incorrect_values_group, ant_correct_thesis_synth_incorrect_stds_group, weights_group, overall_ant_correct_thesis_synth_incorrect_avg_group), pres)
        overall_thesis_and_ant_correct_std_group = round(weighted_overall_std(thesis_and_ant_correct_values_group, thesis_and_ant_correct_stds_group, weights_group, overall_thesis_and_ant_correct_avg_group), pres)
        overall_thesis_ant_synth_all_correct_std_group = round(weighted_overall_std(thesis_ant_synth_all_correct_values_group, thesis_ant_synth_all_correct_stds_group, weights_group, overall_thesis_ant_synth_all_correct_avg_group), pres)
        overall_thesis_synth_correct_ant_incorrect_std_group = round(weighted_overall_std(thesis_synth_correct_ant_incorrect_values_group, thesis_synth_correct_ant_incorrect_stds_group, weights_group, overall_thesis_synth_correct_ant_incorrect_avg_group), pres)
        overall_thesis_correct_ant_synth_incorrect_std_group = round(weighted_overall_std(thesis_correct_ant_synth_incorrect_values_group, thesis_correct_ant_synth_incorrect_stds_group, weights_group, overall_thesis_correct_ant_synth_incorrect_avg_group), pres)
        overall_ant_synth_correct_thesis_incorrect_std_group = round(weighted_overall_std(ant_synth_correct_thesis_incorrect_values_group, ant_synth_correct_thesis_incorrect_stds_group, weights_group, overall_ant_synth_correct_thesis_incorrect_avg_group), pres)
        overall_synth_correct_thesis_ant_incorrect_std_group = round(weighted_overall_std(synth_correct_thesis_ant_incorrect_values_group, synth_correct_thesis_ant_incorrect_stds_group, weights_group, overall_synth_correct_thesis_ant_incorrect_avg_group), pres)
        overall_all_incorrect_std_group = round(weighted_overall_std(all_incorrect_values_group, all_incorrect_stds_group, weights_group, overall_all_incorrect_avg_group), pres)

        # Calculate raw attempt-based standard deviations for comparison
        raw_attempt_stats = calculate_raw_attempt_std(entries, args.attempts)
        
        # Extract and round all raw attempt statistics
        raw_thesis_avg = round(raw_attempt_stats.get('thesis_raw_avg', 0), pres)
        raw_thesis_std = round(raw_attempt_stats.get('thesis_raw_std', 0), pres)
        raw_synthesis_avg = round(raw_attempt_stats.get('synthesis_raw_avg', 0), pres)
        raw_synthesis_std = round(raw_attempt_stats.get('synthesis_raw_std', 0), pres)
        raw_antitheses_avg = round(raw_attempt_stats.get('antitheses_correct_raw_avg', 0), pres)
        raw_antitheses_std = round(raw_attempt_stats.get('antitheses_correct_raw_std', 0), pres)
        raw_thesis_correct_synthesis_incorrect_std = round(raw_attempt_stats.get('thesis_correct_synthesis_incorrect_raw_std', 0), pres)
        raw_thesis_incorrect_synthesis_correct_std = round(raw_attempt_stats.get('thesis_incorrect_synthesis_correct_raw_std', 0), pres)
        raw_thesis_and_synthesis_correct_std = round(raw_attempt_stats.get('thesis_and_synthesis_correct_raw_std', 0), pres)
        raw_thesis_ant_correct_synth_incorrect_std = round(raw_attempt_stats.get('thesis_ant_correct_synth_incorrect_raw_std', 0), pres)
        raw_ant_correct_thesis_synth_incorrect_std = round(raw_attempt_stats.get('ant_correct_thesis_synth_incorrect_raw_std', 0), pres)
        raw_thesis_and_ant_correct_std = round(raw_attempt_stats.get('thesis_and_ant_correct_raw_std', 0), pres)
        raw_thesis_ant_synth_all_correct_std = round(raw_attempt_stats.get('thesis_ant_synth_all_correct_raw_std', 0), pres)
        raw_thesis_synth_correct_ant_incorrect_std = round(raw_attempt_stats.get('thesis_synth_correct_ant_incorrect_raw_std', 0), pres)
        raw_thesis_correct_ant_synth_incorrect_std = round(raw_attempt_stats.get('thesis_correct_ant_synth_incorrect_raw_std', 0), pres)
        raw_ant_synth_correct_thesis_incorrect_std = round(raw_attempt_stats.get('ant_synth_correct_thesis_incorrect_raw_std', 0), pres)
        raw_synth_correct_thesis_ant_incorrect_std = round(raw_attempt_stats.get('synth_correct_thesis_ant_incorrect_raw_std', 0), pres)
        raw_all_incorrect_std = round(raw_attempt_stats.get('all_incorrect_raw_std', 0), pres)

    
        # Add overall results for this group (using raw attempt stds)
        overall_results_group = {
            "Scenario": f"Overall - {model} - {design}", # Clarify which overall average this is
            "Model": model,
            "Design": design,
            "Num Questions": total_questions_group,
            "Thesis Average": overall_thesis_avg_group,
            "Thesis Std": raw_thesis_std,  # Use raw attempt std
            "Synthesis Average": overall_synthesis_avg_group,
            "Synthesis Std": raw_synthesis_std,  # Use raw attempt std
            "Thesis Average - Synthesis Average": overall_difference_group,
            "Thesis Correct Synthesis Incorrect Average": overall_thesis_correct_synthesis_incorrect_avg_group,
            "Thesis Correct Synthesis Incorrect Std": raw_thesis_correct_synthesis_incorrect_std,  # Use raw attempt std
            "Thesis Incorrect Synthesis Correct Average": overall_thesis_incorrect_synthesis_correct_avg_group,
            "Thesis Incorrect Synthesis Correct Std": raw_thesis_incorrect_synthesis_correct_std,  # Use raw attempt std
            "Thesis and Synthesis Correct Average": overall_thesis_and_synthesis_correct_avg_group,
            "Thesis and Synthesis Correct Std": raw_thesis_and_synthesis_correct_std,  # Use raw attempt std
            "Thesis Incorrect Synthesis Correct Average - Thesis Correct Synthesis Incorrect Average": round(overall_thesis_incorrect_synthesis_correct_avg_group - overall_thesis_correct_synthesis_incorrect_avg_group,pres),
            "Antitheses Correct Average": overall_antitheses_correct_avg_group,
            "Antitheses Correct Std": raw_antitheses_std,  # Use raw attempt std
            "Thesis Ant Correct Synth Incorrect Average": overall_thesis_ant_correct_synth_incorrect_avg_group,
            "Thesis Ant Correct Synth Incorrect Std": raw_thesis_ant_correct_synth_incorrect_std,  # Use raw attempt std
            "Ant Correct Thesis Synth Incorrect Average": overall_ant_correct_thesis_synth_incorrect_avg_group,
            "Ant Correct Thesis Synth Incorrect Std": raw_ant_correct_thesis_synth_incorrect_std,  # Use raw attempt std
            "Thesis and Ant Correct Average": overall_thesis_and_ant_correct_avg_group,
            "Thesis and Ant Correct Std": raw_thesis_and_ant_correct_std,  # Use raw attempt std
            # Add 8-permutation fields to overall results (using raw attempt stds)
            "Thesis Ant Synth All Correct Average": overall_thesis_ant_synth_all_correct_avg_group,
            "Thesis Ant Synth All Correct Std": raw_thesis_ant_synth_all_correct_std,  # Use raw attempt std
            "Thesis Synth Correct Ant Incorrect Average": overall_thesis_synth_correct_ant_incorrect_avg_group,
            "Thesis Synth Correct Ant Incorrect Std": raw_thesis_synth_correct_ant_incorrect_std,  # Use raw attempt std
            "Thesis Correct Ant Synth Incorrect Average": overall_thesis_correct_ant_synth_incorrect_avg_group,
            "Thesis Correct Ant Synth Incorrect Std": raw_thesis_correct_ant_synth_incorrect_std,  # Use raw attempt std
            "Ant Synth Correct Thesis Incorrect Average": overall_ant_synth_correct_thesis_incorrect_avg_group,
            "Ant Synth Correct Thesis Incorrect Std": raw_ant_synth_correct_thesis_incorrect_std,  # Use raw attempt std
            "Synth Correct Thesis Ant Incorrect Average": overall_synth_correct_thesis_ant_incorrect_avg_group,
            "Synth Correct Thesis Ant Incorrect Std": raw_synth_correct_thesis_ant_incorrect_std,  # Use raw attempt std
            "All Incorrect Average": overall_all_incorrect_avg_group,
            "All Incorrect Std": raw_all_incorrect_std,  # Use raw attempt std
            # Keep raw attempt statistics for reference
            "Raw Attempt Thesis Average": raw_thesis_avg,
            "Raw Attempt Thesis Std": raw_thesis_std,
            "Raw Attempt Synthesis Average": raw_synthesis_avg,
            "Raw Attempt Synthesis Std": raw_synthesis_std,
            "Raw Attempt Antitheses Average": raw_antitheses_avg,
            "Raw Attempt Antitheses Std": raw_antitheses_std,
            # Add weighted std for comparison (now as backup)
            "Weighted Overall Thesis Std": overall_thesis_std_group,
            "Weighted Overall Synthesis Std": overall_synthesis_std_group,
            "Weighted Overall Antitheses Std": overall_antitheses_correct_std_group,
            # Add comparison fields
            "Weighted vs Raw Thesis Avg Diff": round(overall_thesis_avg_group - raw_thesis_avg, pres),
            "Weighted vs Raw Thesis Std Diff": round(overall_thesis_std_group - raw_thesis_std, pres),
            "Weighted vs Raw Synthesis Avg Diff": round(overall_synthesis_avg_group - raw_synthesis_avg, pres),
            "Weighted vs Raw Synthesis Std Diff": round(overall_synthesis_std_group - raw_synthesis_std, pres)
        }
        results.append(overall_results_group)

# Save results to output JSON file
with open(args.output, 'w') as file:
    json.dump(results, file, indent=4)

print(f"Results saved to {args.output}")