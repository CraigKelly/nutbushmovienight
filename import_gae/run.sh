#!/bin/bash

# Note that we assume that we are running from the directory that where
# everything is located.  If you want to move this script, set the $SCRIPT_DIR
# variable some other way

# Important: we pass along the command line to ./parse.py, so you should specify
# either --insert or --no-insert on the command line

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $SCRIPT_DIR

PARENT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "\033[32mStarting import setup in $(pwd)...\033[0m"

if [ -d venv ];
then
    source $SCRIPT_DIR/venv/bin/activate
    echo -e "\033[33mUpdating venv reqs in $SCRIPT_DIR/requirements.txt\033[0m"
    pip install --upgrade -r "$SCRIPT_DIR/requirements.txt"
else
    echo -e "\033[33mSetting up virtualenv in venv\033[0m"
    echo "IMPORTANT: Setting up for Python3.5!"
    virtualenv -p python3.5 venv

    PTHFILE="$SCRIPT_DIR/venv/lib/python3.5/site-packages/myparent.pth"
    echo -e "\033[33mAdding $PARENT_DIR to PYTHONPATH via $PTHFILE\033[0m"
    echo $PARENT_DIR > $PTHFILE

    source $SCRIPT_DIR/venv/bin/activate
    pip install --upgrade pip wheel setuptools
    echo -e "\033[33mInstalling reqs in $PARENT_DIR/requirements.txt\033[0m"
    pip install -r "$PARENT_DIR/requirements.txt"
    echo -e "\033[33mInstalling reqs in $SCRIPT_DIR/requirements.txt\033[0m"
    pip install --upgrade -r "$SCRIPT_DIR/requirements.txt"
fi

echo -e "\033[32mSetup Complete\033[0m"

if [ -f "gimme.json" ];
then
    echo -e "\033[33mSkipping retrieval - file already exists\033[0m"
else
    echo -e "\033[32mRunning retrieval process\033[0m"
    ./retrieve.py
fi

echo -e "\033[32mRunning parse process\033[0m"
./parse.py $*
