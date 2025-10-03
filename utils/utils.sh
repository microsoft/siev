#!/bin/bash
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

check_exit_code() {
    exit_code=$1  # Use the first parameter as the exit code
    
    if [ $exit_code -eq 0 ]; then
        :
    elif [ $exit_code -eq 2 ]; then
        echo "Termination condition met."
        exit 2
    elif [ $exit_code -eq 3 ]; then
        echo "Error: context_length_exceeded => Context length exceeded."
        exit 3
    elif [ $exit_code -eq 4 ]; then
        echo "Error: "
        exit 4
    else
        echo "Error: Unknown error ($exit_code). We skip this error since it is related to the code execution ..."
        # exit $exit_code
    fi
}


handle_long_output() {
    TIMESTAMP=$(date +%s)
    question_length=$(wc -m < $dir/question)
    if [ $question_length -gt $max_token_size ]; then
        cut -c 1-2000 $dir/question > $dir/question_cut
        mv $dir/question $dir/question_long_$TIMESTAMP
        echo "Your code generated a very long output ($question_length characters). Due to small token budget I cannot give you the full output. revise your code to reduce the output size. Here is the first 2000 characters of the stdout:" > $dir/question
        echo "" >> $dir/question
        cat question_cut >> $dir/question
    elif [ $question_length -gt $high_token_size ]; then
        echo "" >> $dir/question
        echo "Your code generated a long output ($question_length characters). Please consider revising your code to reduce the output size." >> $dir/question
    else
        echo ""
        echo "total token size of $question_length will be consumed by the response."
        echo ""
    fi
}


