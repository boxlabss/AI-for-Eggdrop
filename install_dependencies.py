#!/usr/bin/env python3
# Script to install dependencies for the Grok Flask API.
# Run this manually after creating a virtualenv: python3 -m venv env; source env/bin/activate; python3 install_dependencies.py
import subprocess
import sys
def install_dependencies():
    # List of required packages with pinned versions for stability
    packages = [
        'flask>=3.0.0',
        'openai>=1.0.0',
        'gunicorn>=22.0.0',
        'requests>=2.31.0',
        'bleach>=6.1.0',
        'geopy>=2.4.0', # For geocoding in weather
        'cachetools>=5.3.0', # For TTL caches
        'redis>=5.0.0', # For shared state in prod
        'huggingface-hub>=0.23.0', # For HF image gen
        'Pillow>=10.0.0', # For image handling in huggingface_hub
        'stability-sdk>=0.1.0',  # For Stability AI image gen
        'google-api-python-client>=2.0.0'  # For YouTube API integration
    ]
    # Check if pip is available
    try:
        subprocess.check_output([sys.executable, '-m', 'pip', '--version'])
    except subprocess.CalledProcessError:
        print("pip not found. Ensure Python is installed correctly.")
        sys.exit(1)
   
    # Get list of installed packages for more accurate check
    installed_packages = {}
    installed_output = subprocess.check_output([sys.executable, '-m', 'pip', 'list', '--format=freeze']).decode('utf-8')
    for line in installed_output.splitlines():
        if '==' in line:
            name, version = line.split('==', 1)
            installed_packages[name.lower()] = version
   
    for spec in packages:
        name = spec.split('>')[0].split('=')[0].lower() # Normalize name
        if name in installed_packages:
            print(f"{name} already installed (version {installed_packages[name]}).")
            continue
        print(f"Installing {spec}...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', spec])
            print(f"Installed {spec}.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to install {spec}: {e}")
            sys.exit(1)
if __name__ == '__main__':
    install_dependencies()
