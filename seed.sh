#!/bin/bash
# Seed — setup and deploy script
# Usage:
#   First time:  ./seed.sh install
#   Update:      ./seed.sh update
#   Start:       ./seed.sh start
#   Stop:        ./seed.sh stop
#   Restart:     ./seed.sh restart

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
      cp .env.example .env
      echo ""
      echo "Created .env from template."
      echo "Open it and add your API keys before starting:"
      echo "  open .env        (opens in default editor)"
      echo "  — or —"
      echo "  nano .env        (edit in terminal)"
      echo ""
    fi
    echo "Done. Run: ./seed.sh start"
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
    echo "Usage: ./seed.sh {install|update|start|stop|restart}"
    ;;
esac
