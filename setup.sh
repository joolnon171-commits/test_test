#!/bin/bash
apt-get update
apt-get install -y python3-dev build-essential libfreetype6-dev libpng-dev
pip install --upgrade pip
pip install -r requirements.txt