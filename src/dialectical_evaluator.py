# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
SIEV: Structured dIalectical rEasoning eValuation
==================================================

Main evaluation engine for dialectical reasoning assessment of Large Language Models.

This module implements the core Hegelian dialectical evaluation methodology:
1. **Thesis**: Generate initial response to a given problem
2. **Antithesis**: Create critical analysis/alternative view challenging the thesis  
3. **Synthesis**: Refine response by incorporating insights from the critique

## Key Features:
- Support for GSM-8K (mathematical reasoning) and MMLU (general knowledge) benchmarks
- Intelligent model routing between General API and Reasoning API backends
- Comprehensive error handling and retry mechanisms
- Detailed logging and progress tracking
- Flexible prompt template system
- Result validation and answer extraction

## Architecture:
The evaluator uses a two-tier API system:
- General API: Standard models (GPT-4, GPT-5-chat, local models)
- Reasoning API: Advanced reasoning models (O1, O3, GPT-5-reasoning)

## Usage:
    python dialectical_evaluator.py --model gpt-4o --exp_name test --env_path env/.env
    
Author: Soheil Abbasloo (Microsoft Research)
"""

# Standard library imports
import argparse
import sys
import time
import os
import json
import re
import shutil

# SIEV API imports - Intelligent model routing system
from general_api import GeneralAPI as General      # Standard & local models
from reasoning_api import ReasoningAPI as Reasoning # O1, O3, GPT-5 reasoning models

# SIEV Logging imports
from siev_logging import SievLogger, ProgressTracker, setup_experiment_context

# ============================================================================
# Global Configuration Variables
# ============================================================================

# Debug flag for verbose output and error tracing
debug_flag = False

# Maximum consecutive errors before aborting evaluation
# Prevents infinite retry loops on persistent API failures
max_num_consq_errors = 5

class Thesis:
    """
    Container class for dialectical reasoning responses (thesis/antithesis/synthesis).
    
    This class encapsulates all information about a single step in the dialectical
    reasoning process, including the generated text, extracted answers, error states,
    and retry tracking for robust API interaction.
    
    Attributes:
        error (bool): Whether an error occurred during API call or processing
        error_message (str): Detailed error description for debugging
        thesis (str): The complete response text from the model
        final_answer (str): Extracted final answer (e.g., A/B/C/D for MMLU, number for GSM)
        num_consq_errors (int): Counter for consecutive errors (used for retry logic)
        
    Usage:
        # Create thesis response
        thesis_obj = Thesis(thesis="The answer is 42", final_answer="42")
        
        # Create error response  
        error_obj = Thesis(error=True, error_message="API timeout")
    """
    
    def __init__(self, error=False, error_message="", thesis=None, final_answer=None):
        """
        Initialize a new Thesis object.
        
        Args:
            error (bool): True if an error occurred during generation
            error_message (str): Description of the error (empty if no error)
            thesis (str): The model's response text (None if error occurred)
            final_answer (str): Extracted answer from response (None if not extractable)
        """
        self.error = error
        self.error_message = error_message
        self.thesis = str(thesis) if thesis is not None else ""
        self.final_answer = final_answer
        self.num_consq_errors = 0  # Reset counter for new instances
        
    def reset(self):
        """
        Reset all attributes to default values.
        
        Used when reusing the same Thesis object for multiple attempts
        or when clearing error states for retry logic.
        """
        self.error = False
        self.error_message = ""
        self.thesis = ""
        self.final_answer = None
        self.num_consq_errors = 0

class Exam:
    """
    Container class for exam/benchmark data and associated metadata.
    
    This class encapsulates all information about a benchmark dataset (GSM-8K or MMLU),
    including the questions, answers, metadata, and experimental configuration. It serves
    as the primary data structure for organizing evaluation sessions.
    
    Attributes:
        data (dict): Complete exam data including questions, answers, and choices
        info (dict): Metadata about the exam (size, filename, benchmark type, etc.)
        filename (str): Source exam filename (e.g., "gsm8k_test.json")
        size (int): Total number of questions in the exam/dataset
        id (str): Unique identifier for this exam instance
        output_dir (str): Directory path where results will be saved
        org_data_dir (str): Original data directory path (for reference)
        seed (int): Random seed for reproducible question sampling/ordering
        
    The exam data structure typically contains:
    - For GSM-8K: {"question": str, "answer": str}
    - For MMLU: {"question": str, "choices": [str], "answer": str, "subject": str}
    
    Usage:
        # Load exam from data
        exam = Exam(exam_data)
        print(f"Loaded {exam.size} questions from {exam.filename}")
    """
    
    def __init__(self, exam_data=None):
        """
        Initialize an Exam object from loaded data.
        
        Args:
            exam_data (dict, optional): Dictionary containing exam questions and metadata.
                                       If None, creates an empty exam structure.
        """
        if exam_data is None:
            exam_data = {}
            
        self.data = exam_data
        self.info = exam_data.get("info", {})
        self.filename = self.info.get("filename", "unknown_exam.json")
        self.size = self.info.get("size", 0)
        self.id = self.info.get("id", "")
        self.output_dir = self.info.get("output_dir", "")
        self.org_data_dir = self.info.get("data_dir", "")
        self.seed = self.info.get("seed", 0)

class DialecticalEvaluator:
    """
    Main evaluation engine for dialectical reasoning assessment.
    
    Implements Hegelian dialectical methodology with support for:
    - Multiple benchmark types (GSM, MMLU)
    - Various API backends (OpenAI, Azure, custom endpoints)
    - Configurable evaluation modes (same-model, cross-model)
    - Comprehensive error handling and logging
    
    Attributes:
        thesis_obj (Thesis): Container for thesis response
        antithesis_obj (Thesis): Container for antithesis response  
        synthesis_obj (Thesis): Container for synthesis response
        exam (Exam): Exam data and metadata
        assistant (object): Primary model API interface
        assistant2 (object): Secondary model API interface (for cross-model)
    """
    def __init__(self):
        self.thesis_obj = Thesis()
        self.antithesis_obj = Thesis()
        self.synthesis_obj = Thesis()
        self.exam  = Exam()
        self.seperation_symbol = "="
        self.seperation_symbol_cnt = 20
        self.current_question_idx = 0
        self.parse_function = None
        self.assistant = None
        self.assistant2 = None
        
        # Logging will be initialized in bootstrap() when we have args
        self.logger = None
        self.progress = None
    
    def debug_print(self, message):
        """
        Print debug message if debug mode is enabled.
        
        Args:
            message (str): Message to log for debugging
        """
        if debug_flag:
            self.log_assist(message, f" ")

    def parse_arguments(self):
        """
        Parse command line arguments for evaluation configuration.
        
        Returns:
            argparse.Namespace: Parsed command line arguments
            
        Key Arguments:
            --model: Model name (e.g., 'gpt-4o', 'azure-gpt-4')
            --exam: Path to exam JSON file
            --mode: Evaluation mode ('hegel' for dialectical)
            --test_type: Benchmark type ('mmlu' or 'gsm')
            --multi_model: Use different models for thesis/antithesis
            --num_rounds: Number of dialectical rounds
            --output_dir: Directory for output files
        """ 
        parser = argparse.ArgumentParser(description="Make a request to OpenAI with or without message history.")

        parser.add_argument('--multi-model', type=int, choices=[0, 1], default=0, help="multi-model or not? For backward compatibility, the default is 0\
            when 1, thesis and antithesis generators will use different models. Need to provide --model2")
        parser.add_argument('--model2', type=str, default="gpt-4o", help="model name for antithesis generator")

        parser.add_argument('--exam', type=str,  required=True, help="exam file name")

        parser.add_argument('--max_repeat', type=str, default="10", help="maximum number of repeats")      
        parser.add_argument('--env', type=str, default=".env", help="environment file name")

        parser.add_argument('--output_dir', type=str, default=".", help="output directory")
        parser.add_argument('--try_index', type=int, required=True, help="The index showing we're in which try")
        parser.add_argument('--model', type=str, default="gpt", help="model name: gpt, llama3")
        
        parser.add_argument('--thesis_base_prompt', type=str, default="template.thesis.gen", help="thesis base prompt")
        parser.add_argument('--antithesis_base_prompt', type=str, default="template.antithesis.gen", help="antithesis base prompt")
        parser.add_argument('--synthesis_base_prompt', type=str, default="template.synthesis.gen", help="synthesis base prompt")

        parser.add_argument('--role_filename', type=str, default="role.mmlu", help="role filename")
        parser.add_argument('--question_filename_base', type=str, default="question.mmlu", help="question filename base")
        parser.add_argument('--message_history_json_file_base', type=str, default="message_history_mmlu", help="message history json file base")
        parser.add_argument('--response_file_base', type=str, default="response_mmlu", help="response file base")
        parser.add_argument('--use_response', type=int, choices=[0, 1], default=0, help="use response file")
        parser.add_argument('--full_response_filename', type=str, default="full_response", help="full response filename")
        parser.add_argument('--check_response', type=int, choices=[0, 1], default=0, help="Check response")        
        parser.add_argument('--use_db', type=int, choices=[0, 1], default=0, help="Using db or not? For backward compatibility, the default is 0")

        parser.add_argument('--num_rounds', type=int, default=2, help="number of rounds of synthesis to run for each question")

        parser.add_argument('--test_type', type=str, default="mmlu", help="test type: gsm, mmlu")
        
        parser.add_argument('--redacted', type=int, choices=[0, 1], default=0, help="redacted or not (r1 <think>..</think> part)? For backward compatibility, the default is 0")
        
        args = parser.parse_args()
        return args
    
    def thesis_prompt_preparation(self, args, question):
        """
        Prepare the initial thesis prompt from template.
        
        Args:
            args: Command line arguments containing prompt template path
            question (str): The question to be answered
            
        Returns:
            str: Formatted thesis prompt with question inserted
        """
        thesis_base_prompt_path = os.path.join(args.output_dir, args.thesis_base_prompt)
        with open(thesis_base_prompt_path, 'r') as file:
            thesis_prompt = file.read()
        thesis_prompt = thesis_prompt.replace("--PROBLEM STATEMENT--", "\n" + question)
        self.debug_print(thesis_prompt)
        return thesis_prompt
    
    def antithesis_prompt_preparation(self, args, question, thesis):
        """
        Prepare the antithesis (critique) prompt from template.
        
        Args:
            args: Command line arguments containing redaction settings
            question (str): Original question
            thesis (str): The thesis response to critique
            
        Returns:
            str: Formatted antithesis prompt with question and thesis
        """
        antithesis_prompt_path = os.path.join(args.output_dir, args.antithesis_base_prompt)
        with open(antithesis_prompt_path, 'r') as file:
            antithesis_prompt = file.read()
        antithesis_prompt = antithesis_prompt.replace("--PROBLEM STATEMENT--", "\n" + question)

        if args.redacted == 1:
            # Remove reasoning chains for R1 models if redacted mode enabled
            thesis_redacted = re.sub(r'<think>(.*?)</think>', '', thesis, flags=re.DOTALL)
            antithesis_prompt = antithesis_prompt.replace("--THESIS STATEMENT--", "\n" + thesis_redacted)    
        else:
            antithesis_prompt = antithesis_prompt.replace("--THESIS STATEMENT--", "\n" + thesis)

        self.debug_print(antithesis_prompt)
        return antithesis_prompt

    def synthesis_prompt_preparation_v2(self, args, question, thesis, antithesis):
        # with open(args.synthesis_base_prompt, 'r') as file:
        #     synthesis_prompt = file.read()
        synthesis_prompt = f"To help you on your task, I provide you with the responses of {self.num_antithesis} other agent(s) who are observing your answers:"
        if args.redacted == 1:
            antithesis_redacted = re.sub(r'<think>(.*?)</think>', '', antithesis, flags=re.DOTALL)
            synthesis_prompt = synthesis_prompt + "\n\nThesis: " + antithesis_redacted
            synthesis_prompt = synthesis_prompt + antithesis
        else:
            synthesis_prompt = synthesis_prompt + antithesis

        synthesis_prompt = synthesis_prompt + "\n\nNow, Given the arguments and comments provided, update your answer. \
                btw, keep the same format as before when you are responding.\n\n"
        self.debug_print(synthesis_prompt)
        return synthesis_prompt

    def parse_mmlu_response(self, response):
        error = False
        error_message = None
        strategy = None
        llm_final_answer = None
        self.debug_print(response)

        llm_final_answer = re.search(r'_final_answer_:\s*\((.*?)\)\s*', response, re.DOTALL)
        llm_final_answer = llm_final_answer.group(1) if llm_final_answer else None

        if llm_final_answer is None:
            llm_final_answer = re.search(r'_final_answer_:\s*(.*?)\s*$', response, re.DOTALL)
            llm_final_answer = llm_final_answer.group(1) if llm_final_answer else None
    
        strategy = re.search(r'_reasoning_:\s*(.*?)\s*_final_answer_', response, re.DOTALL)
        strategy = strategy.group(1) if strategy else None
        

        if llm_final_answer is None:
            error = True
            error_message = "Either no answers is found or you didn't follow the instructions. In addition to the part started by \"_reasoning_:\" \
                            you need to give your final answer starting with \"_final_answer_:\" and followed by (X), where X must be either A, B, C, D, or None. \
                            Please try again."
            
            self.log_assist(f"{time.strftime('%H:%M:%S')} - {error_message}\n stratgey: {strategy}\n answer:{llm_final_answer}\n","")
        
        if llm_final_answer == "None":           
            error = True
            error_message = "Your conclusion that the answers is (None) is wrong. \
                            Please think again and revise your answer, as one of the answers among A, B, C, or D is the correct answer. Please try again."
            
            self.log_assist(f"{time.strftime('%H:%M:%S')} - {error_message}\n stratgey: {strategy}\n answer: {llm_final_answer}\n", "")

        thesis_obj = Thesis(error, error_message, response, llm_final_answer)

        return thesis_obj

    def parse_gsm_response(self, response):
        error = False
        error_message = None
        strategy = None
        llm_final_answer = None
        self.debug_print(response)

        llm_final_answer = re.search(r'_final_answer_:\s*\((.*?)\)\s*', response, re.DOTALL)
        llm_final_answer = llm_final_answer.group(1) if llm_final_answer else None

        if llm_final_answer is None:
            llm_final_answer = re.search(r'_final_answer_:\s*(.*?)\s*$', response, re.DOTALL)
            llm_final_answer = llm_final_answer.group(1) if llm_final_answer else None
    
        strategy = re.search(r'_reasoning_:\s*(.*?)\s*_final_answer_', response, re.DOTALL)
        strategy = strategy.group(1) if strategy else None
        
        if llm_final_answer is None:
            error = True
            error_message = "Either no answers is found or you didn't follow the instructions. In addition to the part started by \"_reasoning_:\" \
                            you need to give your final answer starting with \"_final_answer_:\" and followed by (X), where X must be a number. \
                            Please try again."
            
            self.log_assist(f"{time.strftime('%H:%M:%S')} - {error_message}\n stratgey: {strategy}\n answer:{llm_final_answer}\n","")
        
        if llm_final_answer == "None":           
            error = True
            error_message = "Your conclusion that the answers is (None) is wrong. \
                            Please think again and revise your answer."
            
            self.log_assist(f"{time.strftime('%H:%M:%S')} - {error_message}\n stratgey: {strategy}\n answer: {llm_final_answer}\n", "")

        thesis_obj = Thesis(error, error_message, response, llm_final_answer)

        return thesis_obj
    
    def handling_error(self, obj, assistant=None):
        if assistant is None:
            assistant = self.assistant
       
        cnt=0
        num_consq_errors=0
        while obj.error == True:
            cnt+=1
            if obj.final_answer is None or obj.final_answer == "None":
                num_consq_errors+=1
                self.log_assist(f"{time.strftime('%H:%M:%S')} - obj.num_consq_errors: {obj.num_consq_errors}\n max_num_consq_errors:{max_num_consq_errors}\n", "")
                if num_consq_errors >= max_num_consq_errors:
                    if obj.thesis is None:
                        obj.thesis = "None"
                    if obj.final_answer is None:
                        obj.final_answer = "None"
                    return obj.thesis, obj

            self.log_assist(f"{time.strftime('%H:%M:%S')} - context.num_consq_errors: {obj.num_consq_errors}\n=============================\n", "")

            self.log_assist(f"{time.strftime('%H:%M:%S')} - {obj.error_message}\n stratgey\n{obj.thesis}\n", "")

            filename = args.full_response_filename +'_'+str(self.current_question_idx) + '_' + str(cnt)
            filename = os.path.join(self.output_dir, filename)
            if obj.thesis is not None:
                with open(filename, 'a') as f:
                    f.write(obj.thesis + '\n')
            else:
                with open(filename, 'a') as f:
                    f.write('')
            # Llama3 model returns empty string likely when all tokens are consumed!
            if obj.thesis == "":
                return "", obj
            obj.thesis = assistant.run_with_given_question(obj.error_message)         
            obj = self.parse_function(obj.thesis)
            if obj.thesis == "context_length_exceeded":
                return obj.thesis, obj
            if obj.thesis == "No response from the model":
                return obj.thesis, obj
        return obj.thesis, obj
    
    def bootstrap(self, args):
        """
        Initialize the evaluator with command line arguments and setup evaluation context.
        
        This method configures the evaluation environment, loads exam data, initializes
        logging systems, and prepares API interfaces for dialectical evaluation.
        
        Args:
            args (argparse.Namespace): Parsed command line arguments containing:
                - exam: Path to exam JSON file
                - model: Primary model name
                - model2: Secondary model name (for multi-model mode)
                - output_dir: Directory for output files
                - env: Environment file path
                - num_rounds: Number of dialectical rounds
                - multi_model: Whether to use different models for thesis/antithesis
        
        Side Effects:
            - Loads exam data from JSON file
            - Initializes SIEV logging system
            - Sets up progress tracking
            - Configures API interfaces (General or Reasoning)
            - Creates output directory structure
        """
        self.exam = args.exam
        self.num_antithesis = 1
        self.max_repeat = args.max_repeat
        self.response = None
        self.use_history = 1
        self.env = args.env
        self.role_filename = args.role_filename
        self.question_filename = args.question_filename_base
        self.message_history_json_file = args.message_history_json_file_base
        self.response_file_base = args.response_file_base 
        self.use_response = args.use_response
        self.full_response_filename = args.full_response_filename 
        self.check_response = args.check_response
        self.use_db = args.use_db
        self.use_history_flag = bool(self.use_history)
        self.iteration = "1"
        self.world = None
        self.try_index = args.try_index
        self.num_rounds = args.num_rounds
        # Read the exam JSON file
        with open(self.exam, 'r') as f:
            exam_data = json.load(f)
        # Parse the exam data
        exam = Exam(exam_data)
        self.exam = exam

        self.parent_output_dir = args.output_dir
        self.output_dir = args.output_dir

        # Extract experiment name from output directory path
        # Format: data/experiments/{experiment_name}/... or similar
        output_path_parts = os.path.normpath(args.output_dir).split(os.sep)
        if 'experiments' in output_path_parts:
            exp_idx = output_path_parts.index('experiments')
            if exp_idx + 1 < len(output_path_parts):
                experiment_name = output_path_parts[exp_idx + 1]
            else:
                experiment_name = "unknown_experiment"
        else:
            # Fallback: use the last directory name
            experiment_name = os.path.basename(args.output_dir) or "evaluation"

        # Initialize logging system with experiment and attempt context
        context = setup_experiment_context(
            experiment_name=experiment_name,
            model=args.model,
            dataset=os.path.basename(args.exam),
            num_rounds=args.num_rounds,
            max_repeat=args.max_repeat
        )
        
        # Add try_index to context for attempt identification
        context['try_index'] = args.try_index
        
        self.logger = SievLogger(
            name="dialectical_evaluator",
            log_dir=os.path.join(self.output_dir, "logs"),
            context=context
        )
        
        # Initialize progress tracker with experiment and attempt identification
        self.progress = ProgressTracker(
            total_questions=exam.size,
            total_attempts=args.max_repeat,
            experiment_name=experiment_name,
            logger=self.logger
        )
        
        # Add attempt identification to experiment context for parallel run clarity
        attempt_info = f"Attempt {args.try_index}"
        experiment_label = f"{experiment_name} ({attempt_info})"
        
        self.logger.debug("Evaluation initialized", extra={
            "total_questions": exam.size,
            "max_attempts": args.max_repeat,
            "model": args.model,
            "exam_file": args.exam,
            "try_index": args.try_index,
            "experiment_label": experiment_label
        })

        self.log_file = os.path.join(self.output_dir, "whiteboard")       
        with open(self.log_file, 'w') as f:
            f.write("\n" + self.seperation_symbol*self.seperation_symbol_cnt + "\n" + "Log initialized" + "\n" + self.seperation_symbol*self.seperation_symbol_cnt + "\n")

    def set_assistant(self, args):
        # Bringing up the model with simplified two-tier routing
        if self.is_reasoning_model(args.model):
            self.assistant = Reasoning(use_history=self.use_history_flag,iteration=self.iteration,
                                env_file_path=self.env, question_file_path=self.question_filename, role_file_path=self.role_filename,
                                message_history_json_file=self.message_history_json_file,response_file=self.response_file_base,output_dir=self.output_dir, model=args.model,
                                world = self.world, check_response = self.check_response , full_response_filename = self.full_response_filename)
        else:
            # General models: gpt-4, claude-3, gpt-5-chat, local models, etc.
            self.assistant = General(
                                use_history=self.use_history_flag,iteration=self.iteration,
                                env_file_path=self.env, question_file_path=self.question_filename, role_file_path=self.role_filename,
                                message_history_json_file=self.message_history_json_file,response_file=self.response_file_base,output_dir=self.output_dir, model = args.model,
                                world = self.world, check_response = self.check_response , full_response_filename = self.full_response_filename)

    def is_reasoning_model(self, model_name):
        """
        Determine if a model is a reasoning model requiring specialized parameters.
        
        Reasoning models:
        - O1 series: o1-preview, o1-mini, o1-pro
        - O3 series: o3-mini, o3-preview  
        - Specific GPT-5 reasoning variants: gpt-5, gpt-5-mini, gpt-5-nano
        
        NOT reasoning models:
        - GPT-5 chat: gpt-5-chat
        - Standard models: gpt-4, claude-3, etc.
        """
        model_lower = model_name.lower()
        
        # Ox series are reasoning models
        if model_lower.startswith(('o')):
            return True
        
        if model_lower.startswith('gpt-5-') and not model_lower.startswith('gpt-5-chat'):
            return True

        return False
    
    def set_assistant_2(self, args):
        # Bringing up the model with simplified two-tier routing
        if self.is_reasoning_model(args.model2):
            self.assistant2 = Reasoning(use_history=self.use_history_flag,iteration=self.iteration,
                                env_file_path=self.env, question_file_path=self.question_filename, role_file_path=self.role_filename,
                                message_history_json_file=self.message_history_json_file,response_file=self.response_file_base,output_dir=self.output_dir, model=args.model2,
                                world = self.world, check_response = self.check_response , full_response_filename = self.full_response_filename)
        else:
            # General models: gpt-4, claude-3, gpt-5-chat, etc.
            self.assistant2 = General(
                                use_history=self.use_history_flag,iteration=self.iteration,
                                env_file_path=self.env, question_file_path=self.question_filename, role_file_path=self.role_filename,
                                message_history_json_file=self.message_history_json_file,response_file=self.response_file_base,output_dir=self.output_dir, model = args.model2,
                                world = self.world, check_response = self.check_response , full_response_filename = self.full_response_filename)

    def log_assist(self, prompt, response):
        with open(self.log_file, 'a') as log:
            log.write(f"{prompt}\n")
            log.write(f"{response}\n")
            log.write(self.seperation_symbol*self.seperation_symbol_cnt + "\n")

    def main(self, args):
        """
        Main evaluation entry point for dialectical reasoning assessment.
        
        Orchestrates the complete evaluation process:
        1. Initializes evaluation environment via bootstrap()
        2. Loads questions and answers from exam data
        3. Executes dialectical methodology for each question
        4. Tracks progress and handles errors
        5. Saves comprehensive results to JSON
        
        Args:
            args (argparse.Namespace): Command line arguments with evaluation configuration
            
        Process Flow:
            - Extract questions/answers from exam data
            - For each question: run thesis → antithesis → synthesis
            - Log progress and capture detailed responses
            - Save final results with accuracy metrics
            
        Output Files:
            - response_data_{try_index}.json: Complete evaluation results
            - Individual message history files per dialectical step
            - Progress logs and error tracking
        """
        self.bootstrap(args)

        questions_and_answers = []
        all_responses = {}
        multi_model = args.multi_model

        for i in range(self.exam.size):
            question_data = self.exam.data.get(str(i), {})
            if not question_data:
                continue
            question = question_data.get("question")
            answer = question_data.get("answer")
            questions_and_answers.append({i: {"question": question,"answer": answer}})

        current_try_inx = self.try_index
        response_data = {}
        mode_function_map = {
            "hegel": self.hegel,
        }

        mode = "hegel"
        if mode in mode_function_map:
            mode_function = mode_function_map[mode]
        else:
            raise ValueError("Unsupported evaluation mode")
            return

        parse_function_map = {
            "gsm": self.parse_gsm_response,
            "mmlu": self.parse_mmlu_response
        }

        if args.test_type in parse_function_map:
            self.parse_function = parse_function_map[args.test_type]
        else:
            raise ValueError("test_type should be either gsm or mmlu")

        # Starting the Exam ...
        self.logger.progress(f"🚀 Starting evaluation of {len(questions_and_answers)} questions")
        
        # Start progress tracking
        if self.progress:
            self.progress.start_evaluation()
        
        for idx, qa in enumerate(questions_and_answers):
            question = qa[idx]["question"]
            answer = qa[idx]["answer"]
            self.current_question_idx = idx
            
            # Update progress tracker
            if self.progress:
                self.progress.start_question(idx + 1)

            next_resp = os.path.join(self.output_dir, f"response_{idx+1}.json")
            current_resp = os.path.join(self.output_dir, f"response_{idx}.json")
          
            evaluation_results = os.path.join(self.output_dir, "..", f"evaluation_results_attempt_{current_try_inx}.json")

            if os.path.exists(current_resp) and os.path.getsize(current_resp) > 0:
                # If the next response file exists and is not empty, we can skip this question, or if current answered question is the last question
                if (os.path.exists(next_resp) and os.path.getsize(next_resp) > 0) or ((idx == len(questions_and_answers) - 1) and os.path.exists(evaluation_results) and os.path.getsize(evaluation_results) > 0):
                    # read from the response file and load the data
                    with open(current_resp, 'r') as response_file:
                        response_data = json.load(response_file)
                    try:
                        # Check if we have a valid response or if it contains context_length_exceeded
                        if re.search("context_length_exceeded", str(response_data), re.DOTALL):
                            print(f"Found context length exceeded error in question #{idx}, will re-attempt this question.")
                            if self.logger:
                                self.logger.warning(f"Context length exceeded for question {idx + 1}, retrying")
                        else:
                            all_responses[idx] = response_data
                            print(f"Previous response for idx {idx} found and loaded.")
                            self.log_assist(f"Skipping question #{idx}, as we have already answered this question number {idx}!\n", "")
                            if self.logger:
                                self.logger.debug(f"Skipped question {idx + 1} (already completed)")
                            continue
                    except Exception as e:
                        print(f"Error processing response data for question #{idx}: {e}")
                        if self.logger:
                            self.logger.error(f"Failed to process response for question {idx + 1}", extra={
                                'error': str(e),
                                'question_idx': idx,
                                'response_file': current_resp
                            })
                    
            # Call the mode function            
            response_data = mode_function(question, answer, current_try_inx, idx, args)

            # Save the responses            
            current_resp = os.path.join(self.output_dir, f"response_{idx}.json")
            with open(current_resp, 'w') as response_file:
                json.dump(response_data, response_file, indent=4)
            
            all_responses[idx] = response_data
            self.log_assist(f"{time.strftime('%H:%M:%S')} - question number {idx} is finished!", f"{time.strftime('%H:%M:%S')} - question number {idx} is finished!")
            
            # Log completion with new logging system
            if self.logger:
                self.logger.debug(f"Completed question {idx + 1}/{len(questions_and_answers)}")
                
            # Update progress for completion
            if self.progress:
                self.progress.complete_question(success=True)
           
        # Save all responses to a JSON file
        all_responses_filename = os.path.join(self.output_dir, "all_responses.json")
        with open(all_responses_filename, 'w') as all_responses_file:
            json.dump(all_responses, all_responses_file, indent=4)
            
        # Final completion logging
        if self.logger:
            self.logger.progress(f"✅ Evaluation completed successfully! Results saved to {all_responses_filename}")
        if self.progress:
            self.progress.complete_evaluation()

    def hegel(self, question, answer, current_try_inx, idx, args):
        
        # Prepare thesis prompt            
        self.thesis_obj = Thesis()
        self.iteration = str(current_try_inx) + '_' + str(idx)
        self.iteration = "thesis_" + self.iteration
        self.set_assistant(args)
        thesis_prompt = self.thesis_prompt_preparation(args, question)
        thesis_response = self.assistant.run_with_given_question(thesis_prompt)
        self.log_assist(f"Thesis Prompt: {thesis_prompt}\n", f"Thesis Response: {thesis_response}\n")           
        self.thesis_obj = self.parse_function(thesis_response)
        response, self.thesis_obj = self.handling_error(self.thesis_obj)
        if response == "context_length_exceeded":
            self.log_assist(f"context_length_exceeded", f"\n")
            return response
            
        self.log_assist(f"\n", f"\n")
        self.debug_print("="*20)
        response_data = {
            "question": question,
            "answer": answer,
            "thesis": self.thesis_obj.thesis,
            "thesis_answer": self.thesis_obj.final_answer
        }

        for synth_round in range(self.num_rounds):
            
            # Loop for multiple antithesis
            combined_antitheses = ""
            combined_antitheses_final_answers = ""
            current_assistant = None

            for antithesis_try in range(self.num_antithesis):
                self.antithesis_obj = Thesis()
                self.iteration = str(synth_round) + '_' + str(current_try_inx) + '_' + str(idx) 
                self.iteration = f"antithesis_{antithesis_try}_" + self.iteration
                if args.multi_model == 0:
                    self.set_assistant(args)
                    current_assistant = self.assistant
                else:
                    self.set_assistant_2(args)
                    current_assistant = self.assistant2

                antithesis_prompt = self.antithesis_prompt_preparation(args, question, self.thesis_obj.thesis)
                antithesis_response = current_assistant.run_with_given_question(antithesis_prompt)
                self.log_assist(f"Antithesis Prompt: {antithesis_prompt}\n", f"Antithesis Response: {antithesis_response}\n")
                self.antithesis_obj = self.parse_function(antithesis_response)
                response, self.antithesis_obj = self.handling_error(self.antithesis_obj, current_assistant)
                if response == "context_length_exceeded":
                    return response
                self.log_assist(f"\n", f" ")
                combined_antitheses = combined_antitheses + "\n\nReviewer " + str(antithesis_try+1) + ":\n" + str(self.antithesis_obj.thesis)
                combined_antitheses_final_answers = combined_antitheses_final_answers + ", " + str(self.antithesis_obj.final_answer)
                self.debug_print("-"*10)
            
            self.debug_print("="*20)
            response_data = response_data | {
                f"antitheses_{synth_round}": combined_antitheses,
                f"antitheses_answers_{synth_round}": combined_antitheses_final_answers
            }

            # Prepare synthesis prompt with all antitheses
            self.synthesis_obj = Thesis()
            self.iteration = str(current_try_inx) + '_' + str(idx)
            self.iteration = "thesis_" + self.iteration
            self.set_assistant(args)
            synthesis_prompt = self.synthesis_prompt_preparation_v2(args, question, self.thesis_obj.thesis, combined_antitheses)
            synthesis_response = self.assistant.run_with_given_question(synthesis_prompt)
            self.log_assist(f"Synthesis Prompt: {synthesis_prompt}\n", f"Synthesis Response: {synthesis_response}\n")
            self.synthesis_obj = self.parse_function(synthesis_response)
            response, self.synthesis_obj = self.handling_error(self.synthesis_obj)
            if response == "context_length_exceeded":
                return response
            self.log_assist(f"\n", f" ")
            self.debug_print("="*20)
            response_data = response_data | {
                f"synthesis_{synth_round}": self.synthesis_obj.thesis,
                f"synthesis_answer_{synth_round}": self.synthesis_obj.final_answer
            }

            # Now, we feed in the synthesis response as a thesis and repeat the process
            self.thesis_obj = self.synthesis_obj
        
        return response_data    


if __name__ == '__main__':
    evaluator = DialecticalEvaluator()
    args = evaluator.parse_arguments()
    evaluator.main(args)
    
