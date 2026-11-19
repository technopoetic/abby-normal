"""Manual smoke test: speak MCP stdio to the real server process.

Not part of the unit suite — run directly:
    .venv/bin/python tests/smoke_stdio.py
"""

import json
import os
import subprocess
import sys
import threading

# Spawn the server directly: without this flag, server.py's venv guard
# re-executes itself as a child, and terminate() below would only kill the
# outer wrapper, leaving the real server running as an orphan.
env = {**os.environ, "ABBY_NORMAL_IN_VENV": "1"}

proc = subprocess.Popen(
    [".venv/bin/python", "mcp/server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
)

responses = []


def reader():
    for line in proc.stdout:
        responses.append(json.loads(line))


t = threading.Thread(target=reader, daemon=True)
t.start()


def send(msg):
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()


send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "smoke", "version": "0"},
}})
send({"jsonrpc": "2.0", "method": "notifications/initialized"})
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})

import time
deadline = time.time() + 15
while len(responses) < 2 and time.time() < deadline:
    time.sleep(0.1)

proc.terminate()
proc.wait(timeout=10)
err = proc.stderr.read()

ok = True
if not responses:
    print("FAIL: no responses from server")
    print("stderr:", err)
    sys.exit(1)

init = responses[0]
server_info = init.get("result", {}).get("serverInfo", {})
print("initialize ->", server_info)
if server_info.get("name") != "abby-normal":
    print("FAIL: unexpected serverInfo")
    ok = False

tools_list = next((r for r in responses if r.get("id") == 2), None)
if tools_list is None:
    print("FAIL: no tools/list response")
    ok = False
else:
    names = sorted(t["name"] for t in tools_list["result"]["tools"])
    print("tools ->", names)
    if names != ["abby_recall", "abby_save"]:
        print("FAIL: unexpected tool list")
        ok = False

if err.strip():
    print("stderr output (non-fatal):")
    print(err)

print("SMOKE OK" if ok else "SMOKE FAILED")
sys.exit(0 if ok else 1)
