# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
Reasoning Models API Handler for SIEV: Structured dIalectical rEasoning eValuation
==================================================================================

This module provides specialized API interface for advanced reasoning models
that require different parameter handling compared to standard chat models.
It implements SIEV's two-tier architecture for intelligent model routing.

## Supported Model Families:

### OpenAI O1 Series:
- o1-preview, o1-mini, o1-pro

### OpenAI O3 Series:
- o3-mini (when available)

### GPT-5 Reasoning Models:
- gpt-5-2025-08-07, gpt-5-mini-shortco-2025-08-07, gpt-5-nano-shortco-2025-08-07

## Key Differences from Standard Models:
- ❌ No system prompt support (user messages only)
- ❌ No temperature/top_p/frequency_penalty parameters
- ✅ Uses max_completion_tokens instead of max_tokens
- ✅ Built-in reasoning/thinking process before responding

## Model Routing Logic:
Models are automatically routed to this API if they:
- Start with "o" or "O" (e.g., o1-preview, O1-pro)
- Match "gpt-5-" with specific date patterns (e.g., gpt-5-2025-08-07)
- Are explicitly configured for reasoning mode

## Parameter Adaptations:
- System prompts are merged into user messages
- Temperature is omitted (models use internal reasoning temperature)
- max_tokens → max_completion_tokens for proper token limit handling

## Usage Example:
    ```python
    from reasoning_api import ReasoningAPI
    
    assistant = ReasoningAPI(
        model="o1-preview",
        api_key_string="REASONING_API_KEY",
        api_endpoint_string="REASONING_API_ENDPOINT"
    )
    
    response = assistant.make_request_with_context(
        url=api_endpoint,
        key=api_key,
        question="Solve this complex mathematical proof..."
    )
    ```

Author: Soheil Abbasloo (Microsoft Research)
"""

from dotenv import load_dotenv
import json
import os
import requests
import sys
import time
import datetime
import argparse  
import datetime  
from openai import OpenAI, AzureOpenAI
from azure.identity import DefaultAzureCredential  # Azure authentication (currently unused)

from pprint import pprint
import re

# Import new logging system
from siev_logging.logger import SievLogger

class ReasoningAPI:
    """
    O1 reasoning model API handler with specialized parameter support.
    
    This class handles communication with O1-family reasoning models that
    require different API parameters compared to standard chat models.
    Automatically handles the parameter differences and conversation flow.
    
    Attributes:
        TIMEOUT_MAX (int): Maximum timeout for API calls in seconds
        GEN_SLEEP_TIME (int): Sleep time between API calls
        model (str): O1 model name to use for completions
        api_key_string (str): Environment variable name for API key
        api_endpoint_string (str): Environment variable name for API endpoint
    """
    TIMEOUT_MAX = 600
    GEN_SLEEP_TIME = 0  # seconds

    def __init__(self, iteration="1", use_history=True, env_file_path='.env', 
                 question_file_path='question', role_file_path='role',message_history_json_file='message_history',
                 response_file='response', output_dir='.', model="o1-preview",
                 world=None, check_response=0, full_response_filename='full_response',
                 world_method='parse_full_response', api_key_string="REASONING_API_KEY", api_endpoint_string="REASONING_API_ENDPOINT"):
        """
        Initialize the O1 API handler with configuration.
        
        Args:
            iteration (str): Iteration identifier for file naming
            use_history (bool): Whether to maintain conversation history
            env_file_path (str): Path to environment file with API credentials
            question_file_path (str): Path to question file
            role_file_path (str): Path to role/system prompt file
            message_history_json_file (str): Path to conversation history file
            response_file (str): Base name for response files
            output_dir (str): Output directory for generated files
            model (str): O1 model name for API calls (default: o1-preview)
            world: World object (unused, for compatibility)
            check_response (int): Whether to validate responses
            full_response_filename (str): Full response log filename
            world_method (str): World parsing method (unused)
            api_key_string (str): Environment variable name for API key
            api_endpoint_string (str): Environment variable name for endpoint
        """
        
        self.api_key_string = api_key_string
        self.api_endpoint_string = api_endpoint_string

        self.model = model

        self.iteration = iteration

        self.question_file_path = question_file_path
        self.question_file_path = os.path.join(output_dir, self.question_file_path)

        self.role_file_path = role_file_path
        self.role_file_path = os.path.join(output_dir, self.role_file_path)

        self.env_file_path = env_file_path
        self.env_file_path = os.path.join(output_dir, self.env_file_path)

        self.response_file = response_file+"_"+self.iteration+".md"
        self.response_file = os.path.join(output_dir, self.response_file)

        self.response_file_json = "all_"+response_file+"_"+self.iteration+".json"
        self.response_file_json = os.path.join(output_dir, self.response_file_json)

        self.data = self.load_environment_variables()
        self.message_history = []
        self.max_tokens = 2048 * 2 # 4096

        self.use_history = use_history
        self.output_dir = output_dir
        self.message_history_json = message_history_json_file+"_"+self.iteration+".json"
        self.message_history_json = os.path.join(self.output_dir, self.message_history_json)
        

        # World Related stuff
        self.world = world
        self.world_method = world_method
        self.check_response = check_response
        self.full_response_filename = full_response_filename
        self.full_response_filename = os.path.join(self.output_dir, self.full_response_filename)
        
        # Initialize logging system
        self.logger = SievLogger(
            name=f"ReasoningAPI_{model}",
            log_dir=output_dir
        )

    def call_world_function(self, message):
        if self.world is not None:
            return getattr(self.world, self.world_method)(message)
        return None
      
    def load_message_history(self, message_history_file):
        try:
            with open(message_history_file, 'r') as q_file:
                self.message_history = json.load(q_file)
        except FileNotFoundError:
            pass

    def try_request(self, url, key, question):
        """
        Make API request with O1-specific parameters.
        
        This method uses the exact parameter configuration required for O1 models.
        O1 models do not support standard chat completion parameters and require
        a simplified parameter set.
        
        Args:
            url (str): API URL (maintained for compatibility, uses self.client)
            key (str): API key (maintained for compatibility, uses self.client)
            question (str): User question/prompt to send to the model
            
        Returns:
            str: Model response content, or error message if failed
            
        Note:
            O1 models use minimal parameters (original implementation):
            - model: self.model (O1 model name)
            - messages: conversation messages (user role only)
            - stream: False (original setting)
            
            Explicitly excluded parameters that O1 models don't support:
            - temperature, top_p, frequency_penalty, presence_penalty
            - system role messages
            - max_tokens (may use max_completion_tokens in future)
        """
        # Log API call start at debug level
        self.logger.debug(f"Starting API request to {self.model}", extra={
            'model': self.model,
            'question_length': len(question),
            'history_length': len(self.message_history)
        })
        
        start_time = time.time()
        response = None  # Initialize response to None
        messages = self.message_history + [
            {"role": "user", "content": question}
        ]
        error = True
        
        backoff_in_seconds = 1
        valid = False
        extra_cnt = 0

        while (error or not valid):
            try:      
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    # max_tokens=self.max_tokens,
                    # temperature=0.7,
                    # top_p=0.95,
                    # frequency_penalty=0,
                    # presence_penalty=0,
                    # stop=None,
                    stream=False
                )
            except Exception as e:
                error_message = str(e)
                try:
                    match = re.search(r"'code':\s*'([^']*)'", error_message)
                    if match:
                        error_code = match.group(1)
                        if error_code == 'context_length_exceeded':
                            print(f"{self.at_now()} [Error] context_length_exceeded: {match.group(0)}", file=sys.stderr)
                            print("We stop the conversation as the context length is fully used.", file=sys.stderr)
                            self.logger.error("Context length exceeded", extra={
                                'error_code': error_code,
                                'model': self.model,
                                'message_count': len(messages),
                                'total_chars': sum(len(str(m)) for m in messages)
                            })
                            response_json = {"error": {"code": "context_length_exceeded", "message": "context length is fully used"}}                            
                            break
                        if error_code == 'Internal Server Error':
                            print(f"{self.at_now()} [Error] Internal Server Error: {match.group(0)}", file=sys.stderr)
                            self.logger.warning("Internal server error, retrying", extra={
                                'error_code': error_code,
                                'backoff_seconds': backoff_in_seconds,
                                'retry_attempt': True
                            })
                            # Let's try again
                            self.data = self.load_environment_variables()                            
                            time.sleep(backoff_in_seconds)
                            backoff_in_seconds = min(backoff_in_seconds * 2, 60)
                            continue

                except Exception as e2:
                    print(f"Failed to extract error code: {e2}",file=sys.stderr)
                                   
                error_message = f"{self.at_now()} [Error] {backoff_in_seconds} seconds backoff"
                if response:  # Check if response is not None
                    try:
                        error_message += f": {response.json()}"
                    except Exception as e_inner:  # Catch potential errors from .json() call
                        error_message += f". Additional error getting response JSON: {e_inner}"
                else:
                    error_message = error_message + "." + str(e)
               
                    match = re.search(r"Invalid prompt", error_message)
                    if match:
                        print(f"{self.at_now()} [Error] Invalid prompt: {match.group(0)}", file=sys.stderr)
                        print("We stop the conversation as the prompt is flagged, and we cannot go further!", file=sys.stderr)
                        response_json = {"error": {"code": "context_length_exceeded", "message": "context length is fully used"}}
                        break                  
                    match = re.search(r"The response was filtered", error_message)
                    if match:
                        print(f"{self.at_now()} [Error] The response was filtered: {match.group(0)}", file=sys.stderr)
                        print("We stop the conversation as the prompt is flagged, and we cannot go further!", file=sys.stderr)
                        response_json = {"error": {"code": "context_length_exceeded", "message": "context length is fully used"}}
                        break    
                    match = re.search(r"Your resource has been temporarily blocked", error_message)           
                    if match:
                        print(f"{self.at_now()} [Error] Your resource has been temporarily blocked: {match.group(0)}", file=sys.stderr)
                        print ("We stop the conversation as the prompt is flagged, and we cannot go further!", file=sys.stderr)
                        response_json = {"error": {"code": "context_length_exceeded", "message": "context length is fully used"}}
                        break     

                    match = re.search(r"expected a string, got null", error_message)         
                    if match:
                        print(f"{self.at_now()} [Error] expected a string, got null: {match.group(0)}", file=sys.stderr)
                        print ("We stop the conversation as the prompt is corrupted, and we cannot go further!", file=sys.stderr)
                        response_json = {"error": {"code": "context_length_exceeded", "message": "context length is fully used"}}
                        break
                       
                    error_message += f". Full Error string is: {e}"
                print(f"{self.at_now()} [ERROR] {error_message}", file=sys.stderr)
                print(f"More info: \nURL: {url}", file=sys.stderr)

                time.sleep(backoff_in_seconds)
                backoff_in_seconds = min(backoff_in_seconds * 2, 60)
                continue

            response_json = response.json()      
            response_json = json.loads(response_json)  # This converts the string to a dictionary


            if 'error' in response_json or 'statusCode' in response_json or "code" in response_json or "choices" not in response_json:
                print(f"{self.at_now()} [Error] {response_json}",file=sys.stderr)

                try:
                    if response_json['error']['code'] == '429':                                 
                        error_message = response_json['error']['message']
                        match = re.search(r'after (\d+) second', error_message)
                        if match:
                            backoff_in_seconds = int(match.group(1))/2 + 1
                            time.sleep(backoff_in_seconds)
                        else:
                            time.sleep(backoff_in_seconds)
                            backoff_in_seconds = min(backoff_in_seconds * 2, 60)
                        
                        print(f"{self.at_now()} ----- had a {backoff_in_seconds} seconds backoff!",file=sys.stderr)
                except Exception as e:
                    print(f"{self.at_now()} [Error] {e}",file=sys.stderr)
                
                try:
                    if response_json['error']['code'] == 'context_length_exceeded':
                        print(f"{self.at_now()} [Error] context_length_exceeded: {response_json['error']['message']}",file=sys.stderr)
                        print(f"We stop the conversation as the context length is fully used.",file=sys.stderr)
                        break

                except Exception as e:
                    print(f"{self.at_now()} [Error] {e}",file=sys.stderr)

                if response_json['error']['code'] == '40303':
                    pattern = re.compile(r"This model's maximum context length is (\d+) tokens. However, you requested (\d+) tokens \((\d+) in the messages, (\d+) in the")
                    error_msg = response_json['error']['message']
                    matches = pattern.findall(error_msg)
                    if len(matches) == 1:
                        match = matches[0]
                        max_context_length = int(match[0])
                        requested_length = int(match[1])
                        messages_length = int(match[2])
                        completion_length = int(match[3])
                        print(f"[Max_Token Error] max_context_length: {max_context_length}, requested_length: {requested_length}, messages_length: {messages_length}, prompt_length: {completion_length}",file=sys.stderr)
                        correct_max_token_length = max_context_length - messages_length
                        print(f"[Max_Token Error] correct_max_token_length: {correct_max_token_length}",file=sys.stderr)
                        self.max_tokens = correct_max_token_length               
                    
            else:
                error = False       
                valid = True
                time.sleep(self.GEN_SLEEP_TIME)

        if self.use_history and extra_cnt > 0:
            del messages[-2*extra_cnt:]

        # Log successful completion at debug level
        end_time = time.time()
        duration = end_time - start_time
        self.logger.debug(f"API request completed successfully", extra={
            'model': self.model,
            'duration_seconds': round(duration, 2),
            'response_length': len(str(response_json)) if response_json else 0,
            'final_message_count': len(messages)
        })

        return response_json, messages

    def make_request_with_context(self, url, key, question):
        response_json, messages = self.try_request(url, key, question)
        error_code = "No Error"
        try:
            error_code = response_json['error']['code']
        except:
            pass
        if 'error' in response_json and error_code == 'context_length_exceeded':
                new_message = "context_length_exceeded"
        else:
            new_message = response_json['choices'][0]['message']['content']


            self.message_history = messages
            self.message_history.append({"role": "assistant", "content": new_message})           
        
            filename = self.response_file
            res_json_file = self.response_file_json

            new_message = new_message if new_message is not None else "No response from the model"

            with open(filename, 'w') as f:
                f.write(new_message)

            with open(res_json_file, 'a') as outfile:
                json.dump(response_json, outfile)
                outfile.write('\n')
    
        return new_message
    
    def load_environment_variables(self):
        # Load environment variables from .env file
        dotenv_path = self.env_file_path  # The path to env file
        load_dotenv(dotenv_path)
        openai_key = os.getenv(self.api_key_string)
        gcr_url = os.getenv(self.api_endpoint_string)
        
        # Validate required environment variables
        if not openai_key:
            raise ValueError(f"Environment variable {self.api_key_string} not set. Please configure your API key in the environment file.")
        if not gcr_url:
            raise ValueError(f"Environment variable {self.api_endpoint_string} not set. Please configure your endpoint in the environment file.")

        with open(self.question_file_path, 'r') as file:
            question = file.read()

        with open(self.role_file_path, 'r') as file:
            role = file.read()

        # # Use AzureOpenAI for Azure endpoints
        # self.client = AzureOpenAI(
        #     api_key=openai_key,
        #     api_version="2024-09-01-preview",
        #     azure_endpoint=gcr_url
        # )

        # Choose OpenAI vs AzureOpenAI based on endpoint
        endpoint = (gcr_url or "").strip()

        is_openai = "api.openai.com" in endpoint
        is_azure = ("openai.azure.com" in endpoint) or ("azure.com" in endpoint)

        if is_openai:
            # OpenAI (and OpenAI-compatible servers via base_url)
            self.client = OpenAI(
                api_key=openai_key,
                base_url=endpoint  # e.g., https://api.openai.com/v1
            )
        elif is_azure:
            # Azure OpenAI
            self.client = AzureOpenAI(
                api_key=openai_key,
                api_version=os.getenv("REASONING_API_VERSION", "2024-09-01-preview"),
                azure_endpoint=endpoint
            )
        else:
            # Fallback: treat as OpenAI-compatible base_url (vLLM/TGI/etc.)
            self.client = OpenAI(
                api_key=openai_key,
                base_url=endpoint
            )
        
        return {
            'key': openai_key,
            'url': gcr_url,
            'role': role,
            'question': question
        }

    def at_now(self):
        current_ts = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
        ret = f"at [{current_ts}]"
        return ret

    def run(self):
        if self.use_history:
            self.load_message_history(self.message_history_json)
        else:
            pass

        result = self.make_request_with_context(
            self.data['url'],
            self.data['key'],
            self.data['question']
        )
        if result:
            with open(self.message_history_json, 'w') as f:
                json.dump(self.message_history, f)
        

        return result

    def run_with_given_question(self, question):
        if self.use_history:
            self.load_message_history(self.message_history_json)
        else:
            self.message_history = []

        result = self.make_request_with_context(
            self.data['url'],
            self.data['key'],
            question
        )
        if result:        
            with open(self.message_history_json, 'w') as f:
                json.dump(self.message_history, f)

        return result

