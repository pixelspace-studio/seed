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

# Semillita's voice color (hex, default hot pink)
_response_color = "FF005A"


def _colorize(text: str) -> str:
    """Wrap text in 24-bit ANSI color using _response_color."""
    h = _response_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"


def start():
    """Start the Semillita server."""
    subprocess.Popen(
        [sys.executable, "main.py"],
        stdout=None,
        stderr=None,
    )
    print("Starting Semillita...")


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
    elif t == "injected":
        text = data.get("text", "")[:60]
        return f"  \033[33m[injected]\033[0m {text}"
    elif t in ("response_complete", "idle", "message_received", "interrupted"):
        return None
    else:
        return f"  \033[90m[{t}]\033[0m"


def send_message(text: str):
    """Send a message and print the response (no verbose)."""
    try:
        r = httpx.post(f"{BASE_URL}/message", json={"text": text}, timeout=300)
        r.raise_for_status()
        print(_colorize(r.json()["response"]))
    except httpx.ConnectError:
        print("Error: Semillita is not running. Use 'seed start' first.")
    except Exception as e:
        print(f"Error: {e}")


def send_message_verbose(text: str):
    """Send a message while streaming events via WebSocket."""
    import websockets

    response_text = None
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
                        return
        except Exception:
            pass
        finally:
            done.set()

    def run_ws():
        asyncio.run(listen_events())

    ws_thread = threading.Thread(target=run_ws, daemon=True)
    ws_thread.start()

    import time
    time.sleep(0.2)

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

    done.wait(timeout=2)
    print(f"\n{_colorize(result)}")


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
                        print(f"\n{_colorize(data.get('text', ''))}\n")
        except Exception as e:
            print(f"Error: {e}")

    asyncio.run(_watch())


# ---------------------------------------------------------------------------
# Async interactive chat — multiline, inject, ESC-to-interrupt
# ---------------------------------------------------------------------------

def chat(verbose: bool = True):
    """Interactive chat loop with multiline + inject support."""
    try:
        asyncio.run(_chat_async(verbose))
    except KeyboardInterrupt:
        print("\nbye.")


async def _chat_async(verbose: bool = True):
    """Async chat: always-active input, inject while working, ESC to stop."""
    from prompt_toolkit import PromptSession
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.patch_stdout import patch_stdout
    import websockets

    is_working = False
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=300)

    # --- Key bindings ---
    kb = KeyBindings()

    @kb.add('s-enter')  # Shift+Enter — newline (modern terminals)
    def _newline(event):
        event.current_buffer.insert_text('\n')

    @kb.add('escape')  # ESC — interrupt when working
    def _esc(event):
        if is_working:
            asyncio.get_event_loop().create_task(_send_interrupt())

    async def _send_interrupt():
        try:
            await client.post("/interrupt", timeout=5)
        except Exception:
            pass

    pt = PromptSession(key_bindings=kb)

    # --- WebSocket listener (prints events in real-time) ---
    async def ws_listener():
        nonlocal is_working
        while True:
            try:
                async with websockets.connect(WS_URL) as ws:
                    async for raw in ws:
                        data = json.loads(raw)
                        t = data.get("type", "")

                        if verbose:
                            fmt = _format_event(data)
                            if fmt:
                                print(fmt)

                        if t == "response_complete":
                            print(f"\n{_colorize(data.get('text', ''))}\n")
                            is_working = False
                        elif t in ("idle", "interrupted"):
                            is_working = False
            except asyncio.CancelledError:
                return
            except Exception:
                await asyncio.sleep(1)  # reconnect

    # --- Send /message in background ---
    async def send_msg(text):
        nonlocal is_working
        try:
            r = await client.post("/message", json={"text": text})
            r.raise_for_status()
            # Response is printed by ws_listener on response_complete.
            # Fallback: if ws_listener missed it (disconnected), print here.
            if is_working:
                result = r.json().get("response", "")
                print(f"\n{_colorize(result)}\n")
                is_working = False
        except httpx.ConnectError:
            print("\n  Error: Semillita is not running.\n")
            is_working = False
        except Exception as e:
            if is_working:
                print(f"\n  Error: {e}\n")
                is_working = False

    # --- Main loop ---
    print("Semillita chat")
    print("  Enter = send | Shift+Enter = newline | ESC = stop")
    print("  Commands: /verbose on|off, /color HEX, exit\n")

    ws_task = asyncio.create_task(ws_listener())
    await asyncio.sleep(0.3)  # let WS connect

    try:
        with patch_stdout():
            while True:
                try:
                    prompt = "\033[33minject>\033[0m " if is_working else "you> "
                    text = await pt.prompt_async(prompt)
                    text = text.strip()

                    if not text:
                        continue
                    if text.lower() == "exit":
                        break

                    # /verbose command
                    if text.lower().startswith("/verbose"):
                        parts = text.split()
                        if len(parts) >= 2:
                            verbose = parts[1].lower() == "on"
                        print(f"Verbose: {'on' if verbose else 'off'}")
                        continue

                    # /color command
                    if text.lower().startswith("/color"):
                        global _response_color
                        parts = text.split()
                        if len(parts) >= 2:
                            c = parts[1].lstrip("#")
                            if len(c) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in c):
                                _response_color = c.upper()
                                print(f"Color: {_colorize(_response_color)}")
                            else:
                                print("Invalid hex color. Use: /color FF005A")
                        else:
                            print(f"Color: {_colorize(_response_color)}")
                        continue

                    if is_working:
                        # Inject into current loop
                        try:
                            await client.post("/inject", json={"text": text}, timeout=5)
                        except Exception as e:
                            print(f"  inject error: {e}")
                    else:
                        # Send as new message (non-blocking)
                        is_working = True
                        asyncio.create_task(send_msg(text))
                        await asyncio.sleep(0.05)

                except KeyboardInterrupt:
                    if is_working:
                        await _send_interrupt()
                    continue
                except EOFError:
                    break
    finally:
        ws_task.cancel()
        await client.aclose()

    print("\nbye.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

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
        chat(verbose=True)
    else:
        full_message = " ".join([cmd] + args.rest)
        if args.verbose:
            send_message_verbose(full_message)
        else:
            send_message(full_message)


if __name__ == "__main__":
    main()
