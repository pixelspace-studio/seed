"""Semillita CLI — thin client that talks to the FastAPI server."""

import argparse
import asyncio
import json
import subprocess
import sys
import threading

import httpx

BASE_URL = "http://localhost:9999"
WS_URL = "ws://localhost:9999/stream"


def start():
    """Start the Semillita server."""
    subprocess.Popen(
        [sys.executable, "main.py"],
        stdout=None,
        stderr=None,
    )
    print("Starting Semillita...")


def send_message(text: str):
    """Send a message and print the response (no verbose)."""
    try:
        r = httpx.post(f"{BASE_URL}/message", json={"text": text}, timeout=300)
        r.raise_for_status()
        print(r.json()["response"])
    except httpx.ConnectError:
        print("Error: Semillita is not running. Use 'seed start' first.")
    except Exception as e:
        print(f"Error: {e}")


def _format_event(data: dict) -> str | None:
    """Format a WebSocket event for display. Returns None to skip."""
    t = data.get("type", "?")
    if t == "tool_call":
        args_str = json.dumps(data.get("args", {}), ensure_ascii=False)
        if len(args_str) > 120:
            args_str = args_str[:120] + "..."
        return f"  \033[90m[{data['tool']}]\033[0m {args_str}"
    elif t == "tool_result":
        result = data.get("result", "")
        if len(result) > 200:
            result = result[:200] + "..."
        return f"  \033[90m→ {result}\033[0m"
    elif t == "thinking":
        return f"  \033[90mthinking... (iteration {data.get('iteration', '?')})\033[0m"
    elif t == "error":
        return f"  \033[31merror: {data.get('message', '?')}\033[0m"
    elif t in ("response_complete", "idle", "message_received", "interrupted"):
        return None  # handled elsewhere
    else:
        return f"  \033[90m[{t}]\033[0m"


def send_message_verbose(text: str):
    """Send a message while streaming events via WebSocket."""
    import websockets

    response_text = None
    error_msg = None
    done = threading.Event()

    async def listen_events():
        try:
            async with websockets.connect(WS_URL) as ws:
                async for msg in ws:
                    data = json.loads(msg)
                    t = data.get("type", "")

                    formatted = _format_event(data)
                    if formatted:
                        print(formatted)

                    if t == "response_complete":
                        nonlocal response_text
                        response_text = data.get("text", "")
                        return
                    elif t == "idle":
                        # Response was delivered
                        return
        except Exception:
            pass
        finally:
            done.set()

    def run_ws():
        asyncio.run(listen_events())

    # Start WebSocket listener in background thread
    ws_thread = threading.Thread(target=run_ws, daemon=True)
    ws_thread.start()

    # Small delay to ensure WebSocket connects before we send
    import time
    time.sleep(0.2)

    # Send the message (blocks until response)
    try:
        r = httpx.post(f"{BASE_URL}/message", json={"text": text}, timeout=300)
        r.raise_for_status()
        result = r.json()["response"]
    except httpx.ConnectError:
        print("Error: Semillita is not running. Use 'seed start' first.")
        return
    except Exception as e:
        print(f"Error: {e}")
        return

    # Wait for WebSocket to finish showing events
    done.wait(timeout=2)

    # Print final response
    print(f"\n{result}")


def get_status():
    """Print current status."""
    try:
        r = httpx.get(f"{BASE_URL}/status", timeout=5)
        print(json.dumps(r.json(), indent=2))
    except httpx.ConnectError:
        print("Semillita is not running.")


def stop():
    """Send interrupt signal."""
    try:
        r = httpx.post(f"{BASE_URL}/interrupt", timeout=5)
        print("Interrupt sent." if r.status_code == 200 else f"Error: {r.status_code}")
    except httpx.ConnectError:
        print("Semillita is not running.")


def watch():
    """Stream events via WebSocket."""
    import websockets

    async def _watch():
        try:
            async with websockets.connect(WS_URL) as ws:
                print("Watching Semillita... (Ctrl+C to stop)")
                async for msg in ws:
                    data = json.loads(msg)
                    formatted = _format_event(data)
                    if formatted:
                        print(formatted)
                    elif data.get("type") == "response_complete":
                        print(f"\n{data.get('text', '')}\n")
        except Exception as e:
            print(f"Error: {e}")

    asyncio.run(_watch())


def chat(verbose: bool = False):
    """Interactive chat loop."""
    mode = "verbose" if verbose else "quiet"
    print(f"Semillita chat ({mode} mode)")
    print("Commands: /verbose on|off, exit\n")

    while True:
        try:
            text = input("you> ").strip()
            if not text:
                continue
            if text.lower() == "exit":
                break

            # Handle /verbose command
            if text.lower().startswith("/verbose"):
                parts = text.split()
                if len(parts) >= 2 and parts[1].lower() == "on":
                    verbose = True
                    print("Verbose mode on.")
                elif len(parts) >= 2 and parts[1].lower() == "off":
                    verbose = False
                    print("Verbose mode off.")
                else:
                    print(f"Verbose mode: {'on' if verbose else 'off'}")
                continue

            if verbose:
                send_message_verbose(text)
            else:
                send_message(text)
            print()
        except (KeyboardInterrupt, EOFError):
            break
    print("\nbye.")


def main():
    parser = argparse.ArgumentParser(prog="seed", description="Semillita CLI")
    parser.add_argument("command", nargs="?", default="chat",
                        help="start | status | stop | watch | chat | or a message to send")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show tool calls and events in real-time")
    parser.add_argument("rest", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args()

    cmd = args.command
    if cmd == "start":
        start()
    elif cmd == "status":
        get_status()
    elif cmd == "stop":
        stop()
    elif cmd == "watch":
        watch()
    elif cmd == "chat":
        chat(verbose=args.verbose)
    else:
        full_message = " ".join([cmd] + args.rest)
        if args.verbose:
            send_message_verbose(full_message)
        else:
            send_message(full_message)


if __name__ == "__main__":
    main()
