# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
General Models API Handler for SIEV: Structured dIalectical rEasoning eValuation
================================================================================

This module provides the standard OpenAI-compatible API interface for general-purpose
language models. It handles all non-reasoning models in SIEV's two-tier architecture,
providing consistent access to standard chat completion models from various providers.

## Supported Model Families:

### OpenAI GPT Series:
- gpt-4, gpt-4o, gpt-4-turbo, gpt-3.5-turbo, gpt-5-chat, gpt-5-turbo

### Anthropic Claude:
- claude-3-opus, claude-3-sonnet, claude-3-haiku, claude-3.5-sonnet

### Google Gemini:
- gemini-pro, gemini-1.5-pro, gemini-2.0-flash

### Meta Llama:
- llama-3.3-72b, llama-3.1-405b, llama-3.1-70b, llama-3.1-8b

### Other Models:
- Mistral: mistral-large, mistral-medium, mixtral-8x7b
- DeepSeek: R1, V3
- Qwen: qwen-2.5-72b
- Any OpenAI-compatible endpoint

## Model Routing Logic:
This API handles all models EXCEPT:
- O1/O3 reasoning models (handled by ReasoningAPI)
- GPT-5 reasoning variants with specific date patterns (handled by ReasoningAPI)

## Key Features:
- Automatic retry logic with exponential backoff
- Comprehensive error handling and logging
- Support for system prompts and conversation history
- Token usage tracking and cost estimation
- Multiple authentication methods (API key, Azure credentials)

## Environment Configuration:
- GENERAL_API_KEY: API key for authentication
- GENERAL_API_ENDPOINT: Base URL for the API service
- GENERAL_API_VERSION: API version (optional, defaults to latest)

## Usage Example:
    api = GeneralAPI()
    response = api.call_openai_api(
        model="gpt-4o",
        prompt="Solve this math problem: 2+2=?",
        system_prompt="You are a helpful math tutor."
    )

Author: Soheil Abbasloo (Microsoft Research)
"""

# Standard library imports
import json
import os
import sys
import time
import datetime
import argparse
import re
from pprint import pprint

# Third-party imports
import requests                              # HTTP requests for API calls
from dotenv import load_dotenv              # Environment variable loading
from openai import OpenAI, AzureOpenAI        # OpenAI and Azure OpenAI API clients
from azure.identity import DefaultAzureCredential  # Azure authentication (currently unused)

# SIEV imports
# Import new logging system
from siev_logging.logger import SievLogger
from siev_logging.settings import setup_experiment_context

class GeneralAPI:
    """
    Standard OpenAI-compatible API handler for chat models.
    
    This class handles communication with OpenAI-compatible APIs that support
    standard chat completion parameters. It automatically manages conversation
    history, handles errors, and provides response parsing.
    
    Attributes:
        TIMEOUT_MAX (int): Maximum timeout for API calls in seconds
        GEN_SLEEP_TIME (int): Sleep time between API calls
        model (str): Model name to use for completions
        api_key_string (str): Environment variable name for API key
        api_endpoint_string (str): Environment variable name for API endpoint
    """
    TIMEOUT_MAX = 600
    GEN_SLEEP_TIME = 0  # seconds

    def __init__(self, iteration="1", use_history=True, env_file_path='.env', 
                 question_file_path='question', role_file_path='role',message_history_json_file='message_history',
                 response_file='response', output_dir='.', model="deepseek",
                 world=None, check_response=0, full_response_filename='full_response',
                 world_method='parse_full_response', api_key_string="GENERAL_API_KEY", api_endpoint_string="GENERAL_API_ENDPOINT",
                 experiment_name="general_api_eval"):
        """
        Initialize the API handler with configuration.
        
        Args:
            iteration (str): Iteration identifier for file naming
            use_history (bool): Whether to maintain conversation history
            env_file_path (str): Path to environment file with API credentials
            question_file_path (str): Path to question file
            role_file_path (str): Path to role/system prompt file
            message_history_json_file (str): Path to conversation history file
            response_file (str): Base name for response files
            output_dir (str): Output directory for generated files
            model (str): Model name for API calls
            world: World object (unused, for compatibility)
            check_response (int): Whether to validate responses
            full_response_filename (str): Full response log filename
            world_method (str): World parsing method (unused)
            api_key_string (str): Environment variable name for API key
            api_endpoint_string (str): Environment variable name for endpoint
            experiment_name (str): Name of the experiment for logging context
        """
        
        # Initialize logger with context
        context = setup_experiment_context(
            experiment_name=experiment_name,
            model=model,
            iteration=iteration,
            api_type="general"
        )
        self.logger = SievLogger(
            name=f"general_api.{model}",
            log_dir=os.path.join(output_dir, "logs"),
            context=context
        )
        
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

        # Log initialization at DEBUG level to keep console clean
        self.logger.debug(f"Initialized GeneralAPI for model {model}", extra={
            "iteration": iteration,
            "max_tokens": self.max_tokens,
            "use_history": use_history
        })

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



    def call_world_function(self, message):
        if self.world is not None:
            return getattr(self.world, self.world_method)(message)
        return None
      
    def load_message_history(self, message_history_file):
        try:
            with open(message_history_file, 'r') as q_file:
                self.message_history = json.load(q_file)
        except FileNotFoundError:
            self.message_history = [{"role": "system", "content": self.data['role']}]
            pass

    def try_request(self, url, key, question):
        """
        Make API request with exact original parameters.
        
        This method preserves the exact parameter configuration from the original
        implementation to ensure compatibility and consistent behavior.
        
        Args:
            url (str): API URL (maintained for compatibility, uses self.client)
            key (str): API key (maintained for compatibility, uses self.client)
            question (str): User question/prompt to send to the model
            
        Returns:
            str: Model response content, or error message if failed
            
        Note:
            Uses standard OpenAI chat completion parameters:
            - temperature: 0.7 (original setting)
            - top_p: 0.95 (original setting)  
            - max_tokens: self.max_tokens (configurable)
            - frequency_penalty: 0 (original setting)
            - presence_penalty: 0 (original setting)
        """
        response = None  # Initialize response to None
        messages = self.message_history + [
            {"role": "user", "content": question}
        ]
        error = True
        
        backoff_in_seconds = 1
        valid = False
        extra_cnt = 0

        while (error or not valid):
            # Start timing the API call
            call_start_time = time.time()
            
            try:      
                # Use OpenAI client for API requests
                # The o1-preview model does not support some of the parameters including stop, 'system' as role etc. 
                # We need to change things in that regard maybe.
                # a simple version like this works though: 
                ## response = client.chat.completions.create(
                ### model="o1-preview",
                ## model="o1-mini",
                ## messages=[
                ##    {"role": "user", "content": "How many 'r' in strawberry?"},
                ## ])
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=0.7,
                    top_p=0.95,
                    frequency_penalty=0,
                    presence_penalty=0,
                    stop=None,
                    stream=False
                )
            except Exception as e:
                error_message = str(e)
                try:
                    match = re.search(r"'code':\s*'([^']*)'", error_message)
                    if match:
                        error_code = match.group(1)
                        if error_code == 'context_length_exceeded':
                            self.logger.error("Context length exceeded", extra={
                                "error_code": error_code,
                                "error_match": match.group(0)
                            })
                            print("We stop the conversation as the context length is fully used.", file=sys.stderr)
                            response_json = {"error": {"code": "context_length_exceeded", "message": "context length is fully used"}}                            
                            break
                        if error_code == 'Internal Server Error':
                            self.logger.warning("Internal server error, retrying", extra={
                                "error_code": error_code,
                                "backoff_seconds": backoff_in_seconds
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
                    # We may have {e} = Error code: 400 - {'error': {'message': 'Invalid prompt: your prompt was flagged as potentially violating our usage policy.\
                    # Please try again with a different prompt: https://platform.openai.com/docs/guides/reasoning#advice-on-prompting', 'type': 'invalid_request_error', 'param': None, 'code': 'invalid_prompt'}}
                    # So, let's check if str(e) contains 'message'
                    match = re.search(r"Invalid prompt", error_message)
                    if match:
                        self.logger.error("Invalid prompt flagged", extra={
                            "error_match": match.group(0)
                        })
                        # Stop conversation when prompt is invalid                           
                        print("We stop the conversation as the prompt is flagged, and we cannot go further!", file=sys.stderr)
                        response_json = {"error": {"code": "context_length_exceeded", "message": "context length is fully used"}}
                        break                  
                    match = re.search(r"The response was filtered", error_message)
                    if match:
                        print(f"{self.at_now()} [Error] The response was filtered: {match.group(0)}", file=sys.stderr)
                        # Stop conversation when response is filtered                           
                        print("We stop the conversation as the prompt is flagged, and we cannot go further!", file=sys.stderr)
                        response_json = {"error": {"code": "context_length_exceeded", "message": "context length is fully used"}}
                        break   
                    match = re.search(r"Your resource has been temporarily blocked", error_message)           
                    if match:
                        print(f"{self.at_now()} [Error] Your resource has been temporarily blocked: {match.group(0)}", file=sys.stderr)
                        print ("We stop the conversation as the prompt is flagged, and we cannot go further!", file=sys.stderr)
                        response_json = {"error": {"code": "context_length_exceeded", "message": "context length is fully used"}}
                        break      

                    # Error code: 400 - {'error': {'message': "Invalid value for 'content': expected a string, got null.", 'type': 'invalid_request_error', 'param': 'messages.[1].content', 'code': None}}. Full Error string is: Error code: 400 - {'error': {'message': "Invalid value for 'content': expected a string, got null.", 'type': 'invalid_request_error', 'param': 'messages.[1].content', 'code': None}}
                    match = re.search(r"expected a string, got null", error_message)         
                    if match:
                        print(f"{self.at_now()} [Error] expected a string, got null: {match.group(0)}", file=sys.stderr)
                        print ("We stop the conversation as the prompt is corrupted, and we cannot go further!", file=sys.stderr)
                        response_json = {"error": {"code": "context_length_exceeded", "message": "context length is fully used"}}
                        break

                    match = re.search(r"Bearer token has expired", error_message)
                    if match:
                        print(f"{self.at_now()} [Error] Bearer token has expired: {match.group(0)}.\n So, we refresh the token: self.load_environment_variables()", file=sys.stderr)
                        print(f" => Full error string: {e}", file=sys.stderr)
                        # we need to refresh the token
                        self.data = self.load_environment_variables()
                        time.sleep(backoff_in_seconds)
                        continue
                    
                    match = re.search(r"Bearer token not valid", error_message)
                    if match:
                        print(f"{self.at_now()} [Error] Bearer token not valid: {match.group(0)}.\n So, we refresh the token: self.load_environment_variables()", file=sys.stderr)
                        print(f" => Full error string: {e}", file=sys.stderr)
                        # we need to refresh the token
                        self.data = self.load_environment_variables()
                        time.sleep(backoff_in_seconds)
                        backoff_in_seconds = min(backoff_in_seconds * 2, 60)
                        continue
                       
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
                        # time.sleep(backoff_in_seconds)
                        # backoff_in_seconds = min(backoff_in_seconds * 2, self.TIMEOUT_MAX)
                except Exception as e:
                    print(f"{self.at_now()} [Error] {e}",file=sys.stderr)
                
                try:
                    if response_json['error']['code'] == 'context_length_exceeded':
                        print(f"{self.at_now()} [Error] context_length_exceeded: {response_json['error']['message']}",file=sys.stderr)
                        # Stop conversation when context length is fully used
                        print(f"We stop the conversation as the context length is fully used.",file=sys.stderr)
                        break

                except Exception as e:
                    print(f"{self.at_now()} [Error] {e}",file=sys.stderr)

                #for max tokens error handling
                # if int(response_json['error']['code']) == 40303:
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
                # Calculate API call duration
                call_duration = time.time() - call_start_time
                
                # Log successful API call
                self.logger.log_api_call(
                    endpoint=self.model,
                    duration=call_duration,
                    success=True,
                    retry_count=backoff_in_seconds - 1 if backoff_in_seconds > 1 else 0
                )
                
                error = False
        
                # Consult with the world to check if the response is valid
                if self.check_response == 1 and self.world is not None:            # parse the input:
                    # valid, error_message, strategy, code, x, y = world.parse_full_response(response)
                    new_message = response_json['choices'][0]['message']['content']
                    # valid, error_message, strategy, code, parsed_coordinates = self.world.parse_full_response(new_message)
                    valid, error_message, strategy, code, parsed_coordinates = self.call_world_function(new_message)
                    if valid == False:
                        print(f"{time.strftime('%H:%M:%S')} - {error_message}\n response:\n{new_message}", file=sys.stderr)
                        filename = self.full_response_filename +'_'+str(extra_cnt)
                        if new_message is not None:
                            with open(filename, 'a') as f:
                                f.write(new_message + '\n')
                        else:
                            with open(filename, 'a') as f:
                                f.write('-------------------------------------------------------------\n')
                                f.write('We got an empty response, why?!\n')
                                f.write('-------------------------------------------------------------\n')
                        # Check if the new message is not simialar to the previsous one
                        if len(messages) >= 2:
                            if new_message == messages[-2]['content']:
                                error_message = f"Your new response is exactly similar to your invalid previous response. You have to provide a different response that follows the rules discussed before. As before, " + error_message
                                print(f"{time.strftime('%H:%M:%S')} - Duplicate reposnse detected => response:\n{new_message}", file=sys.stderr)

                            if new_message != messages[-2]['content'] or error_message != messages[-1]['content']:
                                extra_cnt+=1          
                                # Prepare the next question due to the error detected by the World
                                messages.append({"role": "assistant", "content": new_message})
                                messages.append({"role": "user", "content": error_message})
                        else:
                            extra_cnt+=1          
                            # Prepare the next question due to the error detected by the World
                            messages.append({"role": "assistant", "content": new_message})
                            messages.append({"role": "user", "content": error_message})
                else:
                    valid = True
                
                time.sleep(self.GEN_SLEEP_TIME)

        if self.use_history and extra_cnt > 0:
            del messages[-2*extra_cnt:]

        return response_json, messages

    def make_request_with_context(self, url, key, question):
        """
        Execute API request with conversation context and error handling.
        
        This is the main entry point for making API calls with proper context management,
        error handling, and response processing. It manages the complete request lifecycle
        from preparation to response storage.
        
        Args:
            url (str): API endpoint URL for requests
            key (str): API key for authentication
            question (str): The question/prompt to send to the model
            
        Returns:
            str: The model's response content, or error message if failed
            
        Side Effects:
            - Updates conversation history
            - Saves response to output files
            - Logs API interactions and errors
            - Handles context length exceeded scenarios
            
        Error Handling:
            - Retries on rate limiting with exponential backoff
            - Graceful handling of context length exceeded
            - Comprehensive logging of all error conditions
        """

        # response = requests.post(url, json=data, headers=headers)
        # response_json = response.json()

        response_json, messages = self.try_request(url, key, question)
        # Need to make sure that we did not stop due to exceeding the context length ...
        # Check if 'error' key exists in response_json
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

            # filename = "response_"+self.iteration+".md"
            
        
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

        # Use AzureOpenAI for Azure endpoints
        self.client = AzureOpenAI(
            api_key=openai_key,
            api_version="2024-09-01-preview",
            azure_endpoint=gcr_url
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
            self.message_history = [{"role": "system", "content": self.data['role']}]

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
            self.message_history = [{"role": "system", "content": self.data['role']}]

        result = self.make_request_with_context(
            self.data['url'],
            self.data['key'],
            question
        )
        if result:        
            with open(self.message_history_json, 'w') as f:
                json.dump(self.message_history, f)

        return result

