#!/bin/bash
# Semillita — setup and deploy script
# Usage:
#   First time:  ./setup.sh install
#   Update:      ./setup.sh update
#   Start:       ./setup.sh start
#   Stop:        ./setup.sh stop
#   Restart:     ./setup.sh restart

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

case "${1:-help}" in
  install)
    echo "Installing Semillita..."
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/playwright install chrome
    if [ ! -f .env ]; then
      echo "ANTHROPIC_API_KEY=" > .env
      echo "Created .env — add your API key before starting."
    fi
    echo "Done. Run: ./setup.sh start"
    ;;

  update)
    echo "Pulling latest..."
    git pull
    .venv/bin/pip install -r requirements.txt
    echo "Restarting..."
    $0 restart
    ;;

  start)
    if [ -f .pid ] && kill -0 "$(cat .pid)" 2>/dev/null; then
      echo "Already running (PID $(cat .pid))"
      exit 0
    fi
    echo "Starting Semillita..."
    nohup .venv/bin/python main.py > data/server.log 2>&1 &
    echo $! > .pid
    echo "Semillita is awake (PID $!, log: data/server.log)"
    ;;

  stop)
    if [ -f .pid ]; then
      PID=$(cat .pid)
      if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "Stopped (PID $PID)"
      fi
      rm -f .pid
    else
      echo "Not running."
    fi
    ;;

  restart)
    $0 stop
    sleep 1
    $0 start
    ;;

  *)
    echo "Usage: ./setup.sh {install|update|start|stop|restart}"
    ;;
esac
