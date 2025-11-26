#!/bin/bash
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

source "configure-paths.sh"
# sudo apt install -y python3-venv
python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to source the virtual environment. Exiting."
    exit
fi

pip install --upgrade pip
pip install -r requirements.txt

deactivate
echo "Virtual environment setup complete. To activate it, run:"
echo "source $VENV_DIR/bin/activate"

