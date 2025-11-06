
### 1. Install System Dependencies
Install required system packages for Python, Eggdrop, and Tcl.
```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip build-essential tcl-dev tcllib
```

### 2. Create and Activate Virtual Environment
Set up a Python 3.11 virtual environment named `xai_env`.
```bash
python3.11 -m venv ~/xai_env
source ~/xai_env/bin/activate
```

### 3. Install Python Dependencies
Install required Python packages for `XaiChatApi.py`.
```bash
./install_dependencies.py
```
Verify installation:
```bash
pip list | grep -E 'Flask|openai|gunicorn'
```
Expected output:
```
Flask             3.1.1
gunicorn          23.0.0
openai            1.97.1
```

### 4. Run XaiChatApi.py, make sure chmod +x 
read gunicorn

### 5. Modify config.json
Replace `YOUR_XAI_API_KEY` with your xAI API key from https://dashboard.x.ai.


### 6. Install and Configure Eggdrop

```bash
wget https://ftp.eggheads.org/pub/eggdrop/source/1.9/eggdrop-1.9.5.tar.gz
tar -xzf eggdrop-1.9.5.tar.gz
cd eggdrop-1.9.5
./configure
make config
make
sudo make install
cd ..
rm -rf eggdrop-1.9.5 eggdrop-1.9.5.tar.gz
```

Configure Eggdrop:
```bash
cd ~/eggdrop
./eggdrop -m eggdrop.conf
```
Edit `eggdrop.conf` to set your IRC server, port, and channels (e.g., `#test` or `#virtulus`). Example:
```tcl
set nick "Grok"
set altnick "Grok_"
set realname "xAI IRC Bot"
set servers {irc.example.com:6667}
set channels "#test #virtulus"
source scripts/grok.tcl
```
Save and exit.

### 8. grok.tcl
place grok.tcl in ~/eggdrop/scripts/grok.tcl

### 10. Start Eggdrop
Run Eggdrop to connect to the IRC server.
```bash
cd ~/eggdrop
./eggdrop -m eggdrop.conf
```
Set the `+grok` flag in the target channel (e.g., `#test`):
```irc
/chanset #test +grok
```

### 11. Test the Setup
Verify the bot responds correctly in IRC and via curl.

#### Curl Tests
```bash
source ~/xai_env/bin/activate
curl -v http://127.0.0.1:5000/health
curl -v http://127.0.0.1:5000/debug
curl -v "http://127.0.0.1:5000/chat?message=what%20day%20was%20it%20yesterday%20GMT%2B1%20or%20UK&nick=eck"
curl -v "http://127.0.0.1:5000/chat?message=what%20time%20is%20it%20in%20London?&nick=eck"
curl -v "http://127.0.0.1:5000/chat?message=weather%20for%20reno&nick=eck"
curl -v "http://127.0.0.1:5000/chat?message=tell%20me%20a%20nsfw%20joke&nick=eck"
curl -v "http://127.0.0.1:5000/chat?message=test&nick=eck"
```
Expected responses (04:39 AM BST, July 24, 2025):
- `{"status":"healthy"}`
- `{"config":{...},"uptime":~X,"python_version":"3.11.2 ...","flask_version":"3.1.1","openai_version":"1.97.1","last_api_success":~1753327813,"recent_logs":[...]}`
- `{"reply":"Yesterday was Wednesday, July 23, 2025, in BST (UTC+1)."}` (55 chars)
- `{"reply":"It’s 04:39 AM BST on Thursday, July 24, 2025."}` (47 chars)
- `{"reply":"Unable to get real time results. DeepSearch is not working."}` (59 chars, if `DeepSearch` fails)
- `{"reply":"Why did the cucumber blush? It overheard the carrots talking about their steamy encounter!"}` (87 chars)
- `{"reply":"Whoa, sounds wild—mind clarifying?"}` (35 chars)

#### Check Logs
- Gunicorn logs:
  ```bash
  cat /tmp/gunicorn.log
  ```
  Expect:
  - `[INFO] Starting gunicorn 23.0.0`
  - `[INFO] Listening at: http://127.0.0.1:5000`
  - `[INFO] Booting worker with pid: ...` (4 workers)
- API logs:
  ```bash
  cat /tmp/xaiChatApi.log
  ```
  Expect:
  - `Config loaded: {...}`
  - `API connectivity test successful: Pong! ...`
  - `Session ID: ..., Timestamp: ..., Request from nick: ..., message: ..., Reply: ...`
- Eggdrop logs:
  ```tcl
  .set errorInfo
  ```
  Expect no Tcl errors.

## Troubleshooting
1. **Gunicorn Fails to Start**:
   - Check `/tmp/gunicorn.log`:
     ```bash
     cat /tmp/gunicorn.log
     ```
     Look for `[ERROR] Worker failed to boot`.
   - Verify `XaiChatApi.py` syntax:
     ```bash
     python3.11 -m py_compile XaiChatApi.py
     ```
   - Restart:
     ```bash
     pkill -f gunicorn
     source ~/xai_env/bin/activate
     gunicorn -w 4 -b 127.0.0.1:5000 xaiChatApi:app --log-file /tmp/gunicorn.log --log-level debug --timeout 60 --max-requests 500 --max-requests-jitter 50 --preload
     ```

2. **Config Issues**:
   - If `/tmp/xaiChatApi.log` shows `Config file not found`:
     ```bash
     ls -l config.json
     ```
     Ensure the file exists and is readable (`chmod 644`).
   - If `Invalid JSON`:
     ```bash
     cat config.json | python3.11 -m json.tool
     ```
     Fix syntax errors and restore.

3. **API Errors**:
   - Check `/tmp/xaiChatApi.log` for `API call failed`.
   - Test API directly:
     ```bash
     curl -X POST https://api.x.ai/v1/chat/completions -H "Authorization: Bearer $XAI_API_KEY" -H "Content-Type: application/json" -d '{"model":"grok-3","messages":[{"role":"user","content":"ping"}],"max_tokens":10}'
     ```
     Expect: `{"choices":[{"message":{"content":"Pong! ..."}}]}`.
   - Verify API key at https://dashboard.x.ai

4. **Eggdrop Issues**:
   - Check logs:
     ```tcl
     .set errorInfo
     ```
     Look for Tcl or HTTP errors.
   - Ensure `+grok` flag:
     ```irc
     /chanset #test +grok
     ```

6. **DeepSearch Failures**:
   - If time/weather queries return fallbacks, check `/tmp/xaiChatApi.log` for `DeepSearch enabled` or `API call failed`.

## Maintenance
- **Restart Gunicorn**:
  ```bash
  pkill -f gunicorn
  source ~/xai_env/bin/activate
  gunicorn -w 4 -b 127.0.0.1:5000 xaiChatApi:app --log-file /tmp/gunicorn.log --log-level debug --timeout 60 --max-requests 500 --max-requests-jitter 50 --preload
  ```
- **Restart Eggdrop**:
  ```bash
  cd ~/eggdrop
  ./eggdrop -m eggdrop.conf
  ```
- **Update API Key**:
  Edit `config.json` with new key from https://dashboard.x.ai.
- **Monitor Logs**:
  ```bash
  tail -f /tmp/gunicorn.log /tmp/xaiChatApi.log
  ```
