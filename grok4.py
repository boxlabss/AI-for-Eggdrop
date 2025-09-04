#!/usr/bin/env python3

import os
import sys
import subprocess
import json
import logging
import time
import hashlib
import random
import string
import uuid
import re
import traceback
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify
from openai import OpenAI, APIError, APIConnectionError, Timeout
import openai
import flask

# Configure logging early
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/xaiChatApi.log')  # Will be overridden by config.json
    ]
)
logger = logging.getLogger(__name__)

logger.info("Starting XaiChatApi.py initialization")

# Load configuration from config.json
def load_config():
    """Load settings from config.json, exiting on failure."""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    logger.debug(f"Attempting to load config from {config_path}")
    try:
        if not os.access(config_path, os.R_OK):
            logger.error(f"No read permission for {config_path}")
            sys.exit(1)
        with open(config_path, 'r') as f:
            config = json.load(f)
        # Override xai_api_key with environment variable if set
        config['xai_api_key'] = os.getenv('XAI_API_KEY', config.get('xai_api_key', ''))
        # Validate required fields
        required_fields = ['xai_api_key', 'api_base_url', 'api_timeout', 'max_tokens', 'temperature', 'max_search_results', 'ignore_inputs', 'log_file', 'flask_host', 'flask_port', 'run_startup_test', 'system_prompt']
        missing = [f for f in required_fields if f not in config]
        if missing:
            logger.error(f"Missing config fields: {missing}")
            sys.exit(1)
        if not config.get('system_prompt') or '{message}' not in config['system_prompt']:
            logger.error("Invalid system_prompt in config.json: must include {message}")
            sys.exit(1)
        # Update logging file handler with config-specified log file
        for handler in logger.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                logger.removeHandler(handler)
        logger.addHandler(logging.FileHandler(config['log_file']))
        logger.info(f"Config loaded: {json.dumps({k: '****' if k == 'xai_api_key' else v for k, v in config.items()}, indent=2)}")
        return config
    except FileNotFoundError:
        logger.error(f"Config file {config_path} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {config_path}: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Config loading failed: {type(e).__name__}: {str(e)}")
        logger.debug(f"Stack trace: {traceback.format_exc()}")
        sys.exit(1)

# Load config
logger.info("Loading configuration")
config = load_config()

# Track last successful API call
last_api_success = None

# Install required dependencies
def install_dependencies():
    """Install required Python packages if not already installed."""
    packages = ['flask>=3.0.0', 'openai>=1.0.0', 'gunicorn>=22.0']
    logger.info("Checking dependencies")
    try:
        installed_packages = subprocess.check_output([sys.executable, '-m', 'pip', 'list']).decode('utf-8')
        logger.debug(f"Installed packages:\n{installed_packages}")
        for pkg in packages:
            pkg_name = pkg.split('>=')[0].split('==')[0]
            try:
                __import__(pkg_name)
                logger.info(f"{pkg} already installed")
            except ImportError:
                logger.info(f"Installing {pkg}...")
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg])
                logger.info(f"Successfully installed {pkg}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Dependency installation failed: {str(e)}")
        sys.exit(1)

# Install dependencies
logger.info("Installing dependencies")
try:
    install_dependencies()
except Exception as e:
    logger.error(f"Startup failed during dependency installation: {type(e).__name__}: {str(e)}")
    logger.debug(f"Stack trace: {traceback.format_exc()}")
    sys.exit(1)

# Initialize Flask app
logger.info("Initializing Flask app")
try:
    app = Flask(__name__)
    app.secret_key = os.urandom(24)
    app.start_time = time.time()
except Exception as e:
    logger.error(f"Startup failed during Flask initialization: {type(e).__name__}: {str(e)}")
    logger.debug(f"Stack trace: {traceback.format_exc()}")
    sys.exit(1)

# Log startup information
logger.info(f"Python version: {sys.version}")
logger.info(f"Flask version: {flask.__version__}")
logger.info(f"OpenAI version: {openai.__version__}")
logger.info(f"Gunicorn command: {' '.join(sys.argv)}")
logger.info(f"Environment: {json.dumps(dict(os.environ), indent=2)}")

# Validate API key
if not config['xai_api_key']:
    logger.error("XAI_API_KEY not provided in config or environment")
    sys.exit(1)

# Test API connectivity at startup if enabled
def test_api_connectivity():
    """Test connectivity to Grok API and log result."""
    global last_api_success
    logger.info("Initializing OpenAI client for connectivity test")
    try:
        client = OpenAI(api_key=config['xai_api_key'], base_url=config['api_base_url'])
        logger.info("OpenAI client started")
        response = client.chat.completions.create(
            model="grok-4",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=10,
            timeout=10.0
        )
        last_api_success = time.time()
        logger.info(f"API connectivity test successful: {response.choices[0].message.content}")
    except Exception as e:
        logger.error(f"API connectivity test failed: {type(e).__name__}: {str(e)}")
        logger.debug(f"Stack trace: {traceback.format_exc()}")
        sys.exit(1)

# Run startup test if enabled
if config['run_startup_test']:
    logger.info("Running startup API connectivity test")
    test_api_connectivity()
else:
    logger.info("Startup API connectivity test disabled in config")

def generate_system_prompt(session_id: str, timestamp: str) -> list:
    """Generate system prompt for Grok using config template."""
    try:
        current_time = datetime.fromtimestamp(float(timestamp), tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        prompt = config['system_prompt'].format(
            session_id=session_id,
            timestamp=timestamp,
            current_time=current_time,
            max_tokens=config['max_tokens'],
            ignore_inputs=', '.join(config['ignore_inputs']),
            message='{message}'
        )
        logger.debug(f"Generated system prompt: {prompt[:100]}... (length: {len(prompt)})")
        return [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "{message}"}
        ]
    except Exception as e:
        logger.error(f"Prompt formatting failed: {type(e).__name__}: {str(e)}")
        logger.debug(f"Stack trace: {traceback.format_exc()}")
        raise

def calculate_time_fallback(query: str, current_time: str) -> str:
    """Calculate fallback response for time queries if search fails."""
    try:
        current = datetime.fromtimestamp(float(current_time), tz=timezone.utc)
        is_bst = 'bst' in query.lower() or 'uk' in query.lower()
        tz_offset = timedelta(hours=1) if is_bst else timedelta(hours=0)
        tz_name = 'BST' if is_bst else 'UTC'
        
        if 'yesterday' in query.lower():
            yesterday = current - timedelta(days=1)
            return yesterday.strftime(f'Yesterday was %A, %B %d, %Y, in {tz_name}.')
        elif any(word in query.lower() for word in ['time', 'date', 'today', 'now']):
            adjusted_time = current + tz_offset
            return adjusted_time.strftime(f'It’s %I:%M %p {tz_name} on %A, %B %d, %Y.')
        return None
    except Exception as e:
        logger.error(f"Time fallback failed: {type(e).__name__}: {str(e)}")
        logger.debug(f"Stack trace: {traceback.format_exc()}")
        return None

def parse_response_date(response: str) -> datetime:
    """Parse date/time from Grok response using regex."""
    try:
        date_patterns = [
            r'\b(\w+ \d{1,2}, \d{4})\b',  # e.g., September 03, 2025
            r'\b(\d{4}-\d{2}-\d{2})\b',   # e.g., 2025-09-03
            r'\b(\d{1,2} \w+ \d{4})\b',   # e.g., 03 September 2025
            r'\b(\d{1,2}:\d{2} (?:AM|PM)?)\b',  # e.g., 04:14 PM or 04:14
            r'\b(\d{4})\b'  # e.g., 2023 (fallback for year only)
        ]
        for pattern in date_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                formats = ['%B %d, %Y', '%Y-%m-%d', '%d %B %Y', '%I:%M %p', '%I:%M', '%Y']
                for fmt in formats:
                    try:
                        parsed = datetime.strptime(date_str, fmt)
                        if fmt in ['%I:%M %p', '%I:%M']:
                            current = datetime.now(timezone.utc)
                            parsed = current.replace(hour=parsed.hour, minute=parsed.minute, second=0, microsecond=0)
                        elif fmt == '%Y':
                            current = datetime.now(timezone.utc)
                            parsed = current.replace(year=parsed.year)
                        return parsed.replace(tzinfo=timezone.utc)
                    except ValueError:
                        continue
        logger.debug(f"No date parsed from response: {response}")
        return None
    except Exception as e:
        logger.debug(f"Date parsing failed: {type(e).__name__}: {str(e)}")
        logger.debug(f"Stack trace: {traceback.format_exc()}")
        return None

def process_grok_response(response, message: str, timestamp: str) -> str:
    """Process Grok API response, applying fallback for invalid time queries."""
    reply = response.choices[0].message.content.strip().replace(r'\\n', '\n')
    logger.debug(f"Processing response: {reply}, token_usage={response.usage}")
    
    if any(word in message.lower() for word in ['time', 'date', 'today', 'now', 'yesterday']):
        current = datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
        parsed_date = parse_response_date(reply)
        is_valid = False
        if parsed_date:
            time_diff = abs((current - parsed_date).total_seconds())
            is_valid = time_diff < 86400  # 24-hour window for time/date queries
            logger.debug(f"Time query validation: parsed_date={parsed_date}, time_diff={time_diff}s, valid={is_valid}, reply={reply}")
        else:
            logger.debug(f"Time query validation: no date parsed, reply={reply}")
        
        if not reply or 'unavailable' in reply.lower() or not is_valid or '2023' in reply:
            fallback = calculate_time_fallback(message, timestamp)
            if fallback:
                reason = 'no date parsed' if not parsed_date else 'invalid date' if not is_valid else 'empty/unavailable'
                if '2023' in reply:
                    reason = 'incorrect year (2023)'
                logger.info(f"Used fallback for time query: {fallback}, reason={reason}")
                return fallback
    
    if 'weather' in message.lower() and 'Unable to get real time results' in reply:
        logger.info(f"Weather fallback triggered: {reply}")
        # Optional: Add custom weather fallback if desired
    
    return reply

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint for Flask server."""
    logger.info("Health check called")
    return jsonify({'status': 'healthy'}), 200, {'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0'}

@app.route('/debug', methods=['GET'])
def debug():
    """Debug endpoint to inspect config and server status."""
    logger.info("Debug endpoint called")
    try:
        with open(config['log_file'], 'r') as f:
            recent_logs = f.readlines()[-5:]
    except Exception as e:
        recent_logs = [f"Error reading log file: {str(e)}"]
    
    status = {
        'config': {k: '****' if k == 'xai_api_key' else v for k, v in config.items()},
        'uptime': time.time() - app.start_time,
        'python_version': sys.version,
        'flask_version': flask.__version__,
        'openai_version': openai.__version__,
        'last_api_success': last_api_success if last_api_success else 'Never',
        'recent_logs': recent_logs,
        'flask_host': config['flask_host'],
        'flask_port': config['flask_port']
    }
    return jsonify(status), 200, {'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0'}

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    """Handle IRC chat queries, process with Grok, and return responses."""
    start_time = time.time()
    session_id = str(uuid.uuid4())
    timestamp = str(time.time())
    
    with app.request_context(request.environ):
        if request.method == 'GET':
            message = request.args.get('message', '')
            nick = request.args.get('nick', 'unknown')
            request_details = {'method': 'GET', 'args': dict(request.args), 'headers': dict(request.headers)}
        else:
            data = request.get_json(silent=True) or {}
            message = data.get('message', '')
            nick = data.get('nick', 'unknown')
            request_details = {'method': 'POST', 'json': data, 'headers': dict(request.headers)}
    
    logger.debug(f"Session ID: {session_id}, Timestamp: {timestamp}, Request details: {json.dumps(request_details, indent=2)}")

    if not message:
        logger.error(f"Session ID: {session_id}, Timestamp: {timestamp}, No message provided")
        return jsonify({'error': 'No message provided', 'fallback': 'Please provide a message!'}), 400, {'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0'}

    if message.lower().strip() in config['ignore_inputs']:
        logger.info(f"Session ID: {session_id}, Timestamp: {timestamp}, Ignored non-substantive input from nick: {nick}, message: {message}")
        return jsonify({'reply': ''}), 200, {'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0', 'X-Session-ID': session_id, 'X-Timestamp': timestamp}

    logger.info(f"Session ID: {session_id}, Timestamp: {timestamp}, Request from nick: {nick}, message: {message}")
    
    try:
        conversation = generate_system_prompt(session_id, timestamp)
        conversation[-1]['content'] = conversation[-1]['content'].format(message=message)
    except Exception as e:
        logger.error(f"Session ID: {session_id}, Timestamp: {timestamp}, Prompt generation failed: {type(e).__name__}: {str(e)}")
        logger.debug(f"Stack trace: {traceback.format_exc()}")
        return jsonify({'error': f"Prompt generation failed: {str(e)}", 'fallback': 'Sorry, I couldn\'t process that!'}), 500, {'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0'}

    search_params = {}
    search_keywords = ['weather', 'death', 'died', 'recent', 'news', 'what happened']  # Removed time-related keywords
    if any(keyword in message.lower() for keyword in search_keywords):
        search_params = {'mode': 'on', 'max_search_results': config['max_search_results']}
        logger.info(f"Session ID: {session_id}, Timestamp: {timestamp}, Live Search enabled for query: {message}")

    logger.debug(f"Session ID: {session_id}, Timestamp: {timestamp}, API request: {json.dumps(conversation, indent=2)}")

    try:
        logger.info(f"Session ID: {session_id}, Timestamp: {timestamp}, Initializing OpenAI client")
        client = OpenAI(api_key=config['xai_api_key'], base_url=config['api_base_url'])
        logger.info(f"Session ID: {session_id}, Timestamp: {timestamp}, OpenAI client started")
        api_start = time.time()
        nonce = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        headers = {
            'X-Cache-Bypass': f"{time.time()}-{nonce}",
            'X-Request-ID': str(random.randint(100000, 999999)),
            'X-Session-ID': session_id,
            'X-Timestamp': timestamp
        }
        logger.debug(f"Session ID: {session_id}, Timestamp: {timestamp}, Request headers: {headers}")
        response = client.chat.completions.create(
            model="grok-4",
            messages=conversation,
            temperature=config['temperature'],
            max_tokens=config['max_tokens'],
            extra_headers=headers,
            extra_body={'search_parameters': search_params} if search_params else {},
            timeout=config['api_timeout']
        )
        api_duration = time.time() - api_start
        global last_api_success
        last_api_success = time.time()
        logger.debug(f"Session ID: {session_id}, Timestamp: {timestamp}, API call took {api_duration:.2f}s")
        logger.debug(f"Session ID: {session_id}, Timestamp: {timestamp}, Raw Grok response: {response.choices[0].message.content}")
        logger.debug(f"Session ID: {session_id}, Timestamp: {timestamp}, Full response: {response.model_dump()}")
        logger.debug(f"Session ID: {session_id}, Timestamp: {timestamp}, Search sources used: {response.usage.num_sources_used if hasattr(response.usage, 'num_sources_used') else 'None'}")

        reply = process_grok_response(response, message, timestamp)
        reply_hash = hashlib.sha256(reply.encode()).hexdigest()
        logger.info(f"Session ID: {session_id}, Timestamp: {timestamp}, Reply (length: {len(reply)}, hash: {reply_hash}): {reply}")
        logger.info(f"Session ID: {session_id}, Timestamp: {timestamp}, Total request time: {time.time() - start_time:.2f}s")
        return jsonify({'reply': reply}), 200, {'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0', 'X-Session-ID': session_id, 'X-Timestamp': timestamp}

    except (APIError, APIConnectionError, Timeout) as e:
        logger.error(f"Session ID: {session_id}, Timestamp: {timestamp}, API call failed: {type(e).__name__}: {str(e)}")
        logger.debug(f"Stack trace: {traceback.format_exc()}")
        if any(word in message.lower() for word in ['time', 'date', 'today', 'now', 'yesterday']):
            fallback = calculate_time_fallback(message, timestamp)
            if fallback:
                logger.info(f"Session ID: {session_id}, Timestamp: {timestamp}, Used fallback for time query: {fallback}, reason=API failure")
                return jsonify({'reply': fallback}), 200, {'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0', 'X-Session-ID': session_id, 'X-Timestamp': timestamp}
        return jsonify({'error': f"API call failed: {str(e)}", 'fallback': 'Sorry, I couldn\'t connect to Grok!'}), 500, {'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0', 'X-Session-ID': session_id, 'X-Timestamp': timestamp}

if __name__ == '__main__':
    logger.info(f"Starting Flask server on {config['flask_host']}:{config['flask_port']}")
    app.run(host=config['flask_host'], port=config['flask_port'], debug=False)