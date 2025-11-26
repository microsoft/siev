#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
SIEV Final Results Table Generator
=================================

Generates the final results table with standardized metrics from summary_aggregate.json files.

Output Table Headers: Model | Scenario (gsm/mmlu) | p_T | p_S | Δ | OC | DS

Where:
- **p_T**: Conventional evaluation method (Thesis Accuracy)
- **p_S**: Synthesis accuracy  
- **Δ**: p_S - p_T (synthesis improvement over thesis)
- **OC**: Opposition Compliance (fraction where antithesis opposes thesis)
- **DS**: New Dialectical Reasoning Score = p_S × (λ + (1-λ) × OC^γ) with λ=0.7, γ=1.0

Usage:
- Use -s/--scenario parameter to explicitly specify scenario type (recommended)
- When called from experiment scripts, scenario type should be passed explicitly
- Auto-detection is available but explicit specification is more reliable

Author: SIEV Analysis Framework
Date: October 2025
"""

import argparse
import json
import pandas as pd
import numpy as np
from pathlib import Path
import logging
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FinalTableGenerator:
    """Generator for final SIEV results table with standardized metrics."""
    
    def __init__(self, lambda_param: float = 0.7, gamma_param: float = 1.0):
        """
        Initialize the final table generator.
        
        Args:
            lambda_param (float): Weight parameter λ ∈ [0,1] for dialectical score
            gamma_param (float): Curvature parameter γ ≥ 0 for dialectical score
        """
        self.lambda_param = lambda_param
        self.gamma_param = gamma_param
        
        logger.info(f"Initialized FinalTableGenerator with λ={lambda_param}, γ={gamma_param}")
    
    def clean_model_name(self, model_name: str) -> str:
        """
        Clean and standardize model names for consistent display.
        
        Args:
            model_name: Raw model name from data
            
        Returns:
            Cleaned model name
        """
        
        # Remove date patterns
        import re
        date_pattern = re.compile(r'(-\d{4}-\d{2}-\d{2})')
        match = date_pattern.search(model_name)
        if match:
            model_name = model_name.replace(match.group(1), '')
        
        # Model name standardization
        model_mapping = {
            'gpt-4o': 'GPT-4o',
            'gpt-4': 'GPT-4',
            'gpt-35': 'GPT-3.5',
            'gpt-41': 'GPT-4.1',
            'gpt-41-mini': 'GPT-4.1-mini',
            'phi-4': 'Phi-4',
            'o4-mini': 'O4-mini',
            'o3Mini': 'O3-mini',
            'o3': 'O3',
            'o1mini': 'O1-mini',
            'O1': 'O1',
            'DeepSeekV3': 'DeepSeek-V3',
            'kimi-k2': 'Kimi-K2',
            'qwen2-5': 'Qwen2.5',
            'llama-3-3': 'Llama-3.3',
            'gpt-5-mini': 'GPT-5-mini',
            'gpt-5-nano': 'GPT-5-nano',
            'gpt-5-chat': 'GPT-5-chat',
            'gpt-5': 'GPT-5',
        }
        
        for old_name, new_name in model_mapping.items():
            if old_name in model_name:
                model_name = model_name.replace(old_name, new_name)
                break
        
        return model_name
    
    def extract_scenario_name(self, scenario: str) -> str:
        """
        Extract scenario name without hardcoded detection logic.
        
        Since scenario labeling is handled by user input parameters,
        this function returns the raw scenario name for cases where
        no explicit scenario is provided (not recommended).
        
        Args:
            scenario: Raw scenario name from data
            
        Returns:
            Raw scenario name (no transformation)
        """
        # No hardcoded scenario detection - return raw scenario name
        # Users should provide explicit scenario type via -s parameter
        return scenario.lower().strip()
    
    def calculate_opposition_compliance(self, row: Dict[str, Any]) -> float:
        """
        Calculate Opposition Compliance (OC) from 8-permutation data.
        
        OC = fraction where antithesis opposes thesis (regardless of correctness)
        OC = (C3+C4) + (C5+C6) where:
        - C3: T✓ A✗ S✓ (Thesis Synth Correct Ant Incorrect)
        - C4: T✓ A✗ S✗ (Thesis Correct Ant Synth Incorrect)  
        - C5: T✗ A✓ S✓ (Ant Synth Correct Thesis Incorrect)
        - C6: T✗ A✓ S✗ (Ant Correct Thesis Synth Incorrect)
        
        Args:
            row: Data row with permutation averages
            
        Returns:
            Opposition compliance value [0,1]
        """
        try:
            # Extract the 8-permutation probabilities
            C3 = row.get('Thesis Synth Correct Ant Incorrect Average', 0.0)  # T✓ A✗ S✓
            C4 = row.get('Thesis Correct Ant Synth Incorrect Average', 0.0)   # T✓ A✗ S✗
            C5 = row.get('Ant Synth Correct Thesis Incorrect Average', 0.0)   # T✗ A✓ S✓
            C6 = row.get('Ant Correct Thesis Synth Incorrect Average', 0.0)   # T✗ A✓ S✗
            
            # Calculate Opposition Compliance
            OC = (C3 + C4) + (C5 + C6)  # T✓A✗ cases + T✗A✓ cases
            
            # Ensure OC is within [0,1] bounds
            return max(0.0, min(1.0, OC))
            
        except (KeyError, TypeError, ValueError) as e:
            logger.warning(f"Error calculating Opposition Compliance: {e}")
            return 0.0
    
    def calculate_dialectical_score(self, p_S: float, OC: float) -> float:
        """
        Calculate Dialectical Score (DS).
        
        DS = S_overall × (λ + (1-λ) × OC^γ)
        where S_overall = synthesis accuracy (p_S)
        
        Args:
            p_S: Synthesis accuracy
            OC: Opposition compliance
            
        Returns:
            Dialectical score
        """
        try:
            opposition_multiplier = self.lambda_param + (1 - self.lambda_param) * (OC ** self.gamma_param)
            DS = p_S * opposition_multiplier
            return DS
        except (TypeError, ValueError) as e:
            logger.warning(f"Error calculating Dialectical Score: {e}")
            return 0.0
    
    def process_summary_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Process a single summary_aggregate.json file.
        
        Note: Data processing logic is independent of user-provided scenario type.
        Scenario type override is applied only for final table labeling.
        
        Args:
            file_path: Path to summary_aggregate.json file
            
        Returns:
            List of processed data rows
        """
        logger.info(f"Processing file: {file_path}")
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return []
        
        processed_rows = []
        
        for row in data:
            # Only process overall summary rows (e.g., "Overall - gpt-4o - hegel"), 
            # skip individual scenarios (e.g., "sample_exam") to avoid double counting
            # and ensure we use properly aggregated statistics
            if 'Overall' not in row.get('Scenario', ''):
                continue
            
            # Extract basic information
            model = self.clean_model_name(row.get('Model', ''))
            
            # Always process data the same way regardless of user input
            # The scenario_type parameter is only used for final labeling
            scenario = self.extract_scenario_name(row.get('Scenario', ''))
            
            # Extract core metrics
            p_T = row.get('Thesis Average', 0.0)
            p_S = row.get('Synthesis Average', 0.0)
            
            # Calculate derived metrics
            delta = p_S - p_T
            OC = self.calculate_opposition_compliance(row)
            DS = self.calculate_dialectical_score(p_S, OC)
            
            processed_row = {
                'Model': model,
                'Scenario': scenario,  # This will be overridden later if scenario_type is provided
                'p_T': round(p_T, 3),
                'p_S': round(p_S, 3),
                'Δ': round(delta, 3),
                'OC': round(OC, 3),
                'DS': round(DS, 3)
            }
            
            processed_rows.append(processed_row)
            
        logger.info(f"Processed {len(processed_rows)} data rows from {file_path}")
        return processed_rows
    
    def generate_table(self, input_paths: List[Path], output_path: Path, scenario_type: str = None) -> None:
        """
        Generate the final results table from summary files.
        
        Args:
            input_paths: List of paths to summary_aggregate.json files
            output_path: Output path for final table CSV
            scenario_type: Explicit scenario type (gsm/mmlu), overrides auto-detection
        """
        logger.info(f"Generating final table from {len(input_paths)} input files")
        
        all_rows = []
        
        # Process all input files
        for input_path in input_paths:
            rows = self.process_summary_file(input_path)
            all_rows.extend(rows)
        
        if not all_rows:
            logger.error("No data found in input files")
            return
        
        # Create DataFrame
        df = pd.DataFrame(all_rows)
        
        # Apply scenario type override for labeling (if provided by user)
        # This doesn't affect processing logic, only final table labeling
        if scenario_type:
            df['Scenario'] = scenario_type
            logger.info(f"Applied scenario type override: all entries labeled as '{scenario_type}'")
        
        # Sort by scenario then by model performance (DS descending)
        df = df.sort_values(['Scenario', 'DS'], ascending=[True, False])
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save to CSV
        df.to_csv(output_path, index=False)
        
        logger.info(f"Final table saved to: {output_path}")
        logger.info(f"Table contains {len(df)} rows with {len(df['Model'].unique())} unique models")
        logger.info(f"Scenarios: {sorted(df['Scenario'].unique())}")
        
        # Display preview
        print("\n" + "="*80)
        print("FINAL RESULTS TABLE PREVIEW")
        print("="*80)
        print(df.to_string(index=False))
        print("="*80)


def main():
    """Main function to run the final table generator."""
    parser = argparse.ArgumentParser(
        description='Generate final SIEV results table from summary_aggregate.json files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Process single file with explicit scenario type
  python3 generate_final_table.py -i data/experiments/gsm-test/summary_aggregate.json -o final_results.csv -s gsm
  
  # Process multiple experiments with glob patterns
  python3 generate_final_table.py -i data/experiments/*/summary_aggregate.json -o consolidated_results.csv
  
  # Process specific scenario experiments only
  python3 generate_final_table.py -i data/experiments/gsm-*/summary_aggregate.json -o gsm_results.csv -s gsm
  
  # Use custom dialectical score parameters
  python3 generate_final_table.py -i data/experiments/*/summary_aggregate.json -o custom_results.csv --lambda 0.8 --gamma 1.5 -s mmlu
        '''
    )
    
    parser.add_argument('-i', '--input', required=True, nargs='+',
                       help='Path(s) to summary_aggregate.json file(s)')
    parser.add_argument('-o', '--output', required=True,
                       help='Output path for final results CSV')
    parser.add_argument('-s', '--scenario', choices=['gsm', 'mmlu'],
                       help='Explicit scenario type (gsm/mmlu) - overrides auto-detection')
    parser.add_argument('--lambda', type=float, default=0.7,
                       help='Lambda parameter for dialectical score (default: 0.7)')
    parser.add_argument('--gamma', type=float, default=1.0,
                       help='Gamma parameter for dialectical score (default: 1.0)')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Convert input paths to Path objects and expand globs
    input_paths = []
    for input_pattern in args.input:
        path = Path(input_pattern)
        if path.is_file():
            input_paths.append(path)
        else:
            # Try to expand as glob pattern
            expanded = list(path.parent.glob(path.name))
            if expanded:
                input_paths.extend(expanded)
            else:
                logger.error(f"No files found matching pattern: {input_pattern}")
    
    if not input_paths:
        logger.error("No valid input files found")
        return 1
    
    # Create generator and process files
    generator = FinalTableGenerator(
        lambda_param=getattr(args, 'lambda'),
        gamma_param=args.gamma
    )
    
    output_path = Path(args.output)
    generator.generate_table(input_paths, output_path, args.scenario)
    
    return 0


if __name__ == '__main__':
    exit(main())