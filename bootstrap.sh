#!/bin/bash
set -e
set -x

# Install Python
apt update
apt install --yes software-properties-common mosh
add-apt-repository --yes ppa:deadsnakes/ppa
apt-get --yes install python3.9 python3.9-venv python3.9-distuils build-essential

# Install Poetry
curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python3.9 -
source $HOME/.poetry/env

# Install Market Thingy
git clone https://github.com/linuxlefty/market-thingy
pushd market-thingy/
python3.9 $HOME/.poetry/bin/poetry install

# Create directory
mkdir -pv /home/pnaudus/Downloads

# Now start a shell
python3.9 $HOME/.poetry/bin/poetry shell
