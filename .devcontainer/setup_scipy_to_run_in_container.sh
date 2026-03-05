#!/bin/bash

apt install -y gcc g++ gfortran libopenblas-dev liblapack-dev pkg-config

wget -O Miniforge3.sh "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash Miniforge3.sh -b -p "${HOME}/conda"
# tried the following to replace line 10-14 , it does not work, with error msg:
#   EnvironmentNameNotFound: Could not find conda environment: scipy-dev\nYou can list all discoverable environments with `conda info --envs`.\n\n\n
# source "${HOME}/conda/etc/profile.d/conda.sh && conda activate scipy-dev"
source "${HOME}/conda/etc/profile.d/conda.sh"
source "${HOME}/conda/etc/profile.d/mamba.sh"

mamba env create -f environment.yml
mamba activate scipy-dev

pip install -e . --no-build-isolation