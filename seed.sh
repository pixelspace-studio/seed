#!/bin/bash
# Seed — setup, configure, and run Semillita
# Usage:
#   First time:  ./seed.sh install
#   Configure:   ./seed.sh config
#   Start:       ./seed.sh start
#   Stop:        ./seed.sh stop
#   Restart:     ./seed.sh restart
#   Update:      ./seed.sh update
#   Chat:        ./seed.sh chat

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

case "${1:-help}" in
  install)
    echo ""
    echo "  Installing Seed..."
    echo ""
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
    .venv/bin/playwright install chrome 2>/dev/null
    if [ ! -f .env ]; then
      cp .env.example .env
    fi
    echo ""
    echo "  Installed. Now configure your API keys:"
    echo ""
    echo "    ./seed.sh config"
    echo ""
    ;;

  config)
    echo ""
    echo "  Seed — Configuration"
    echo "  ────────────────────"
    echo ""

    # Load current values
    [ -f .env ] && source .env

    # ANTHROPIC_API_KEY
    current="${ANTHROPIC_API_KEY}"
    if [ -n "$current" ]; then
      display="...${current: -8}"
    else
      display="(not set)"
    fi
    printf "  Anthropic API Key [%s]: " "$display"
    read -r input
    if [ -n "$input" ]; then
      if grep -q "^ANTHROPIC_API_KEY=" .env 2>/dev/null; then
        sed -i '' "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$input|" .env
      else
        echo "ANTHROPIC_API_KEY=$input" >> .env
      fi
    fi

    # OPENAI_API_KEY
    current="${OPENAI_API_KEY}"
    if [ -n "$current" ]; then
      display="...${current: -8}"
    else
      display="(not set)"
    fi
    printf "  OpenAI API Key [%s]: " "$display"
    read -r input
    if [ -n "$input" ]; then
      if grep -q "^OPENAI_API_KEY=" .env 2>/dev/null; then
        sed -i '' "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=$input|" .env
      else
        echo "OPENAI_API_KEY=$input" >> .env
      fi
    fi

    # BRAVE_SEARCH_API_KEY
    current="${BRAVE_SEARCH_API_KEY}"
    if [ -n "$current" ]; then
      display="...${current: -8}"
    else
      display="(not set)"
    fi
    printf "  Brave Search API Key [%s]: " "$display"
    read -r input
    if [ -n "$input" ]; then
      if grep -q "^BRAVE_SEARCH_API_KEY=" .env 2>/dev/null; then
        sed -i '' "s|^BRAVE_SEARCH_API_KEY=.*|BRAVE_SEARCH_API_KEY=$input|" .env
      else
        echo "BRAVE_SEARCH_API_KEY=$input" >> .env
      fi
    fi

    # MODEL
    current="${MODEL:-claude-sonnet-4-6}"
    printf "  Model [%s]: " "$current"
    read -r input
    if [ -n "$input" ]; then
      if grep -q "^MODEL=" .env 2>/dev/null; then
        sed -i '' "s|^MODEL=.*|MODEL=$input|" .env
      else
        echo "MODEL=$input" >> .env
      fi
    fi

    # PORT
    current="${SEED_PORT:-9999}"
    printf "  Port [%s]: " "$current"
    read -r input
    if [ -n "$input" ]; then
      if grep -q "^SEED_PORT=" .env 2>/dev/null; then
        sed -i '' "s|^SEED_PORT=.*|SEED_PORT=$input|" .env
      else
        echo "SEED_PORT=$input" >> .env
      fi
    fi

    echo ""
    echo "  Configuration saved to .env"
    echo "  Start Seed with: ./seed.sh start"
    echo ""
    ;;

  update)
    echo "  Pulling latest..."
    git pull
    .venv/bin/pip install -q -r requirements.txt
    echo "  Restarting..."
    $0 restart
    ;;

  start)
    if [ -f .pid ] && kill -0 "$(cat .pid)" 2>/dev/null; then
      echo "  Already running (PID $(cat .pid))"
      exit 0
    fi
    mkdir -p data
    echo "  Starting Seed..."
    nohup .venv/bin/python main.py > data/server.log 2>&1 &
    echo $! > .pid
    sleep 2
    if kill -0 "$(cat .pid)" 2>/dev/null; then
      echo ""
      echo "  Semillita is awake (PID $(cat .pid))"
      echo "  Log: data/server.log"
      echo ""
      echo "  Chat:  ./seed.sh chat"
      echo "  Stop:  ./seed.sh stop"
      echo ""
    else
      echo "  Failed to start. Check data/server.log"
      rm -f .pid
      exit 1
    fi
    ;;

  stop)
    if [ -f .pid ]; then
      PID=$(cat .pid)
      if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "  Stopped (PID $PID)"
      fi
      rm -f .pid
    else
      echo "  Not running."
    fi
    ;;

  restart)
    $0 stop
    sleep 1
    $0 start
    ;;

  chat)
    if [ ! -f .pid ] || ! kill -0 "$(cat .pid)" 2>/dev/null; then
      echo "  Seed is not running. Starting..."
      $0 start
    fi
    .venv/bin/python cli.py chat "${@:2}"
    ;;

  *)
    echo ""
    echo "  Seed — a self-building AI agent"
    echo ""
    echo "  Usage: ./seed.sh <command>"
    echo ""
    echo "  Commands:"
    echo "    install    Install dependencies (first time only)"
    echo "    config     Set API keys and preferences"
    echo "    start      Start the server"
    echo "    stop       Stop the server"
    echo "    restart    Restart the server"
    echo "    update     Pull latest code and restart"
    echo "    chat       Open interactive chat (starts server if needed)"
    echo ""
    ;;
esac
