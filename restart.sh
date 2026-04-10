#!/bin/bash
cd "$(dirname "$0")"
pkill -f "python.*main.py" 2>/dev/null
sleep 1
nohup .venv/bin/python main.py > /tmp/feishu-approval-claw.log 2>&1 &
echo "Started PID=$!"
sleep 5
echo "=== LOG ==="
cat /tmp/feishu-approval-claw.log
