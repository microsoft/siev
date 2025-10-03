# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
SIEV Dialectical Reasoning Evaluator
====================================

Essential evaluation script for scoring dialectical reasoning experiments across 
any reasoning benchmark (GSM, MMLU, etc.). This script processes thesis-antithesis-synthesis
responses and calculates comprehensive performance metrics.

** CRITICAL: This script is required by run scripts and should NOT be deleted **

Key Features:
- Generic dialectical reasoning evaluation (works with any dataset)
- Thesis vs Antithesis vs Synthesis scoring
- Comprehensive accuracy calculations across all dialectical components
- Support for multiple reasoning benchmarks
- Integration with experimental run pipeline

Called by:
- execute_gsm_iteration.sh
- execute_mmlu_iteration.sh

Author: Soheil Abbasloo (Microsoft Research)
Status: Required for evaluation pipeline
"""

from glob import glob
import pandas as pd
import json
import time
import random
import openai
import argparse
import os

def normalize_number(value):
    """
    Normalize a number by converting it to a float.
    This handles numbers with commas, scientific notation, and different decimal formats.
    If the value is not a number, return the original string.
    """
    # Remove commas
    value = value.replace(',', '')
    # remove dollar sign
    value = value.replace('$', '')
    try:
        # Convert to float
        return float(value)
    except ValueError:
        # If conversion fails, return the original value
        return value


def parse_arguments():
    parser = argparse.ArgumentParser(description="Evaluate dialectical reasoning accuracy using SIEV methodology.")
    parser.add_argument('--input', type=str, default="all_responses.json", help="filename containing all the responses from the agents")
    parser.add_argument('--dir', type=str, required=True, help="directory including the file to evaluate")
    parser.add_argument('--try_index', type=int, required=True, help="index of the attempt")
    parser.add_argument('--num_rounds', type=int, required=True, help="number of dialectical rounds")
    parser.add_argument('--precision', type=int, default=5, help="number of decimal places for rounding (default: 5)")
    args = parser.parse_args()
    return args

def main(args):
    """
    Main SIEV dialectical reasoning evaluation function.
    
    This function implements the core SIEV methodology:
    1. Thesis evaluation
    2. Antithesis evaluation  
    3. Synthesis evaluation
    4. Comprehensive dialectical analysis
    """
    
    # Set precision parameter
    pres = args.precision
    
    # input_parent = os.path.join(args.dir, f"attempt_{args.try_index}")
    input_parent = args.dir
    input = os.path.join(input_parent, args.input)
    num_rounds = args.num_rounds - 1

    try:
        with open(input, 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        print(f"Error: The file {input} does not exist.")
        return
    except json.JSONDecodeError:
        print(f"Error: The file {input} is not a valid JSON file.")
        return

    thesis_correct = 0
    synthesis_correct = 0
    num_questions = 0
    synth_correct = {}
    antitheses_correct = {}
    thesis_correct_synthesis_incorrect = 0
    thesis_incorrect_synthesis_correct = 0
    thesis_and_synthesis_correct = 0
    thesis_and_ant_correct_synth_incorrect = 0
    thesis_and_ant_correct = 0
    ant_correct_thesis_synth_incorrect = 0
    
    # All 8 permutations of (Thesis, Antithesis, Synthesis) correctness
    thesis_ant_synth_all_correct = 0          # T=1, A=1, S=1
    thesis_ant_correct_synth_incorrect = 0    # T=1, A=1, S=0 (already tracked above)
    thesis_synth_correct_ant_incorrect = 0    # T=1, A=0, S=1  
    thesis_correct_ant_synth_incorrect = 0    # T=1, A=0, S=0
    ant_synth_correct_thesis_incorrect = 0    # T=0, A=1, S=1
    ant_correct_thesis_synth_incorrect = 0    # T=0, A=1, S=0 (already tracked above)
    synth_correct_thesis_ant_incorrect = 0    # T=0, A=0, S=1
    all_incorrect = 0                         # T=0, A=0, S=0

    for rounds in range(num_rounds+1):
        synth_correct[f'{rounds}'] = 0
        antitheses_correct[f'{rounds}'] = 0

    for key, value in data.items():
        # Add type checking to ensure value is a dictionary
        if not isinstance(value, dict):
            print(f"Error: Entry {key} is not a dictionary. Type: {type(value)}, Value: {str(value)[:100]}...")
            # Count invalid entries as failed questions
            num_questions += 1
            continue
            
        synth_all = ""
        antith_all = ""
        for rounds in range(num_rounds+1):
            synth_key = f"synthesis_answer_{rounds}"
            antith_key = f"antithesis_answer_{rounds}"
            
            # Check if synthesis key exists before accessing
            if synth_key not in value:
                print(f"Warning: Key '{synth_key}' not found in entry {key}. Available keys: {list(value.keys())}")
                continue
                
            try:
                synth_all = synth_all + str(value[synth_key]) + " "
            except Exception as e:
                print(f"Error processing entry {key}, key {synth_key}: {e}")
                continue
            
            # Check if required keys exist for accuracy calculation
            if 'answer' not in value:
                print(f"Warning: 'answer' key not found in entry {key}")
                continue
                
            if synth_key not in value:
                print(f"Warning: '{synth_key}' key not found in entry {key}")
                continue
                
            try:
                answer_norm = normalize_number(value['answer'])
                synth_norm = normalize_number(value[synth_key])
                # if value['answer'] == value[f"synthesis_answer_{rounds}"]:
                if answer_norm == synth_norm:
                    synth_correct[f'{rounds}'] += 1
            except Exception as e:
                print(f"Error processing answer comparison for entry {key}, round {rounds}: {e}")
                continue
                
            # Check antithesis answer for this round - try different possible key formats
            antith_value = None
            possible_keys = [f"antitheses_answers_{rounds}"]
            
            for possible_key in possible_keys:
                if possible_key in value:
                    antith_value = str(value[possible_key]).strip().lstrip(',').strip()
                    break
            
            if antith_value:
                antith_all = antith_all + antith_value + " "
                antith_norm = normalize_number(antith_value)
                if answer_norm == antith_norm:
                    antitheses_correct[f'{rounds}'] += 1
            else:
                # Debug: print available keys for first few items
                if int(key) < 3:
                    print(f"Debug - Available keys for {key}: {list(value.keys())}")
                    antith_keys = [k for k in value.keys() if 'anti' in k.lower()]
                    print(f"Debug - Antithesis-related keys: {antith_keys}")

        # Check if required keys exist for final calculations
        final_synth_key = f"synthesis_answer_{num_rounds}"
        if final_synth_key not in value:
            print(f"Warning: Final synthesis key '{final_synth_key}' not found in entry {key}")
            # Count missing key entries as failed questions
            num_questions += 1
            continue
            
        if 'thesis_answer' not in value:
            print(f"Warning: 'thesis_answer' key not found in entry {key}")
            # Count missing key entries as failed questions
            num_questions += 1
            continue
            
        if 'answer' not in value:
            print(f"Warning: 'answer' key not found in entry {key}")
            # Count missing key entries as failed questions
            num_questions += 1
            continue

        try:
            synth_value = value[final_synth_key]
            answer_norm = normalize_number(value['answer'])
            thesis_norm = normalize_number(value['thesis_answer'])
            synth_norm = normalize_number(synth_value)
        except Exception as e:
            print(f"Error processing final values for entry {key}: {e}")
            # Count processing errors as failed questions
            num_questions += 1
            continue
        
        # Check if final antithesis_answer exists - try different possible key formats
        antithesis_answer = ''
        antithesis_norm = ''
        possible_final_keys = [f"antitheses_answers_{num_rounds}"]
        
        for possible_key in possible_final_keys:
            if possible_key in value:
                antithesis_answer = str(value[possible_key]).strip().lstrip(',').strip()
                antithesis_norm = normalize_number(antithesis_answer)
                break
        
        # Determine correctness for each component
        thesis_is_correct = answer_norm == thesis_norm
        antithesis_is_correct = antithesis_answer and answer_norm == antithesis_norm
        synthesis_is_correct = answer_norm == synth_norm
        
        # Count individual correctness (for backward compatibility)
        if thesis_is_correct:
            thesis_correct += 1
            
        # Count all 8 permutations systematically
        if thesis_is_correct and antithesis_is_correct and synthesis_is_correct:
            thesis_ant_synth_all_correct += 1
        elif thesis_is_correct and antithesis_is_correct and not synthesis_is_correct:
            thesis_and_ant_correct_synth_incorrect += 1
        elif thesis_is_correct and not antithesis_is_correct and synthesis_is_correct:
            thesis_synth_correct_ant_incorrect += 1
        elif thesis_is_correct and not antithesis_is_correct and not synthesis_is_correct:
            thesis_correct_ant_synth_incorrect += 1
        elif not thesis_is_correct and antithesis_is_correct and synthesis_is_correct:
            ant_synth_correct_thesis_incorrect += 1
        elif not thesis_is_correct and antithesis_is_correct and not synthesis_is_correct:
            ant_correct_thesis_synth_incorrect += 1
        elif not thesis_is_correct and not antithesis_is_correct and synthesis_is_correct:
            synth_correct_thesis_ant_incorrect += 1
        elif not thesis_is_correct and not antithesis_is_correct and not synthesis_is_correct:
            all_incorrect += 1
            
        # Maintain backward compatibility counters
        if thesis_is_correct and not synthesis_is_correct:
            thesis_correct_synthesis_incorrect += 1
        if not thesis_is_correct and synthesis_is_correct:
            thesis_incorrect_synthesis_correct += 1
        if thesis_is_correct and synthesis_is_correct:
            thesis_and_synthesis_correct += 1
        if antithesis_answer and antithesis_is_correct and thesis_is_correct:
            thesis_and_ant_correct += 1
        

        num_questions += 1

    # Handle case where no valid questions were processed
    if num_questions == 0:
        print("Warning: No valid questions were processed. All entries may have errors.")
        output = {
            "num_questions": 0,
            "thesis_correct": 0,
            "thesis_accuracy": 0.0,
            "thesis_correct_synthesis_incorrect_count": 0,
            "thesis_incorrect_synthesis_correct_count": 0,
            "thesis_and_synthesis_correct_count": 0,
            "antitheses_correct": 0,
            "thesis_ant_correct_synth_incorrect": 0,
            "ant_correct_thesis_synth_incorrect": 0,
            "thesis_and_ant_correct": 0,
            # All 8 permutations
            "thesis_ant_synth_all_correct": 0,
            "thesis_ant_synth_all_correct_accuracy": 0.0,
            "thesis_ant_correct_synth_incorrect": 0,
            "thesis_ant_correct_synth_incorrect_accuracy": 0.0,
            "thesis_synth_correct_ant_incorrect": 0,
            "thesis_synth_correct_ant_incorrect_accuracy": 0.0,
            "thesis_correct_ant_synth_incorrect": 0,
            "thesis_correct_ant_synth_incorrect_accuracy": 0.0,
            "ant_synth_correct_thesis_incorrect": 0,
            "ant_synth_correct_thesis_incorrect_accuracy": 0.0,
            "ant_correct_thesis_synth_incorrect": 0,
            "ant_correct_thesis_synth_incorrect_accuracy": 0.0,
            "synth_correct_thesis_ant_incorrect": 0,
            "synth_correct_thesis_ant_incorrect_accuracy": 0.0,
            "all_incorrect": 0,
            "all_incorrect_accuracy": 0.0,
            "permutation_validation_status": "OK"
        }
        for rounds in range(num_rounds+1):
            output[f"synthesis_{rounds}"] = 0
            output[f"synthesis_{rounds}_accuracy"] = 0.0
            output[f"antithesis_{rounds}"] = 0
            output[f"antithesis_{rounds}_accuracy"] = 0.0
    else:
        output = {
            "num_questions": num_questions,
            "thesis_correct": thesis_correct,
            "thesis_accuracy": round(thesis_correct/num_questions,pres),
            "thesis_correct_synthesis_incorrect_count": thesis_correct_synthesis_incorrect,
            "thesis_incorrect_synthesis_correct_count": thesis_incorrect_synthesis_correct,
            "thesis_and_synthesis_correct_count": thesis_and_synthesis_correct,
            "antitheses_correct": antitheses_correct[f'{num_rounds}'],
            "thesis_ant_correct_synth_incorrect": thesis_and_ant_correct_synth_incorrect,
            "ant_correct_thesis_synth_incorrect": ant_correct_thesis_synth_incorrect,
            "thesis_and_ant_correct": thesis_and_ant_correct,
            # All 8 permutations with counts and accuracies
            "thesis_ant_synth_all_correct": thesis_ant_synth_all_correct,
            "thesis_ant_synth_all_correct_accuracy": round(thesis_ant_synth_all_correct/num_questions, pres),
            "thesis_ant_correct_synth_incorrect": thesis_and_ant_correct_synth_incorrect,
            "thesis_ant_correct_synth_incorrect_accuracy": round(thesis_and_ant_correct_synth_incorrect/num_questions, pres),
            "thesis_synth_correct_ant_incorrect": thesis_synth_correct_ant_incorrect,
            "thesis_synth_correct_ant_incorrect_accuracy": round(thesis_synth_correct_ant_incorrect/num_questions, pres),
            "thesis_correct_ant_synth_incorrect": thesis_correct_ant_synth_incorrect,
            "thesis_correct_ant_synth_incorrect_accuracy": round(thesis_correct_ant_synth_incorrect/num_questions, pres),
            "ant_synth_correct_thesis_incorrect": ant_synth_correct_thesis_incorrect,
            "ant_synth_correct_thesis_incorrect_accuracy": round(ant_synth_correct_thesis_incorrect/num_questions, pres),
            "ant_correct_thesis_synth_incorrect": ant_correct_thesis_synth_incorrect,
            "ant_correct_thesis_synth_incorrect_accuracy": round(ant_correct_thesis_synth_incorrect/num_questions, pres),
            "synth_correct_thesis_ant_incorrect": synth_correct_thesis_ant_incorrect,
            "synth_correct_thesis_ant_incorrect_accuracy": round(synth_correct_thesis_ant_incorrect/num_questions, pres),
            "all_incorrect": all_incorrect,
            "all_incorrect_accuracy": round(all_incorrect/num_questions, pres)
        }
        for rounds in range(num_rounds+1):
            output[f"synthesis_{rounds}"] = synth_correct[f'{rounds}']
            output[f"synthesis_{rounds}_accuracy"] = round(synth_correct[f'{rounds}']/num_questions, pres)
            output[f"antithesis_{rounds}"] = antitheses_correct[f'{rounds}']
            output[f"antithesis_{rounds}_accuracy"] = round(antitheses_correct[f'{rounds}']/num_questions, pres)

    # Validation: Check that all permutations sum to total questions
    total_permutations = (thesis_ant_synth_all_correct + thesis_and_ant_correct_synth_incorrect + 
                         thesis_synth_correct_ant_incorrect + thesis_correct_ant_synth_incorrect +
                         ant_synth_correct_thesis_incorrect + ant_correct_thesis_synth_incorrect + 
                         synth_correct_thesis_ant_incorrect + all_incorrect)
    
    if total_permutations != num_questions and num_questions > 0:
        print(f"Warning: Permutation sum ({total_permutations}) does not match total questions ({num_questions})")
        print(f"This may indicate missing antithesis data or logic errors.")
        output["permutation_validation_warning"] = f"Sum mismatch: {total_permutations} vs {num_questions}"
    else:
        output["permutation_validation_status"] = "OK"

    output_path = os.path.join(args.dir, "../", f"evaluation_results_attempt_{args.try_index}.json")
    with open(output_path, 'w') as outfile:
        json.dump(output, outfile, indent=4)
    
    return 


if __name__ == "__main__":
    args = parse_arguments()
    main(args)