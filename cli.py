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
_response_color = "A3F7FF"


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
    elif t in ("injected", "response_complete", "idle", "message_received", "interrupted"):
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
    from prompt_toolkit import print_formatted_text as ptprint
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.patch_stdout import patch_stdout
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.input.ansi_escape_sequences import ANSI_SEQUENCES
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.application import get_app_or_none
    import websockets

    # --- Kitty keyboard protocol ---
    # Enables distinct escape sequences for modified keys (Shift+Enter, Ctrl+C, etc).
    # Must deactivate on exit with ESC[<u or the terminal stays in Kitty mode.
    sys.stdout.write("\x1b[>1u")
    sys.stdout.flush()

    # prompt_toolkit maps Shift+Enter to Keys.ControlM (= Enter) by default.
    # We remap both known encodings to Keys.F24 (unused key) so we can bind it.
    ANSI_SEQUENCES["\x1b[27;2;13~"] = Keys.F24   # xterm modifyOtherKeys encoding
    ANSI_SEQUENCES["\x1b[13;2u"] = Keys.F24       # Kitty CSI u encoding
    # Kitty protocol re-encodes ALL keys including Ctrl+C (99=ascii 'c', 5=ctrl modifier).
    # Without this mapping, Ctrl+C shows as raw text "[99;5u" instead of interrupting.
    ANSI_SEQUENCES["\x1b[99;5u"] = Keys.ControlC
    ANSI_SEQUENCES["\x1b[27u"] = Keys.Escape        # Kitty CSI u encoding for ESC

    is_working = False
    _ctrl_c_count = 0  # two Ctrl+C when idle = exit
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=300)

    def _cprint(text):
        """Print colored text through prompt_toolkit's renderer.

        Regular print() inside patch_stdout() mangles ESC bytes (shows as ?[).
        print_formatted_text(ANSI(...)) routes output through prompt_toolkit's
        own VT100 renderer, which handles escape sequences correctly.
        """
        ptprint(ANSI(text))

    def _refresh_prompt():
        """Force prompt redraw (updates inject>/you> when state changes)."""
        app = get_app_or_none()
        if app:
            app.invalidate()

    # --- Key bindings ---
    kb = KeyBindings()

    @kb.add(Keys.F24)             # Shift+Enter — newline
    def _newline(event):
        event.current_buffer.insert_text('\n')

    @kb.add('escape', eager=True)  # ESC — interrupt current work
    def _escape(event):
        if is_working:
            asyncio.ensure_future(_send_interrupt())

    async def _send_interrupt():
        try:
            await client.post("/interrupt", timeout=5)
        except Exception:
            pass

    # Dynamic prompt: prompt_async() accepts a callable, so it re-evaluates
    # on every redraw. Combined with app.invalidate() in _refresh_prompt(),
    # the prompt updates from >> to > when Semillita finishes working.
    def _get_prompt():
        if is_working:
            return '>> '
        return '> '

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
                                _cprint(fmt)

                        if t == "response_complete":
                            is_working = False
                            _refresh_prompt()
                        elif t in ("idle", "interrupted"):
                            is_working = False
                            _refresh_prompt()
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
            result = r.json().get("response", "")
            _cprint(f"\n{_colorize(result)}\n")
        except httpx.ConnectError:
            _cprint("\n  Error: Semillita is not running.\n")
        except Exception as e:
            _cprint(f"\n  Error: {e}\n")
        finally:
            is_working = False
            _refresh_prompt()

    # --- Main loop ---
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")) as _vf:
            _version = _vf.read().strip()
    except Exception:
        _version = "?"
    print(f"Semillita v{_version}")
    print("  Enter = send | Shift+Enter = newline | ESC = interrupt")
    print("  Commands: /verbose on|off, /color HEX, exit\n")

    ws_task = asyncio.create_task(ws_listener())
    await asyncio.sleep(0.3)  # let WS connect

    try:
        with patch_stdout():
            while True:
                try:
                    text = await pt.prompt_async(_get_prompt)
                    text = text.strip()

                    _ctrl_c_count = 0
                    if not text:
                        continue
                    if text.lower() == "exit":
                        break

                    # /verbose command
                    if text.lower().startswith("/verbose"):
                        parts = text.split()
                        if len(parts) >= 2:
                            verbose = parts[1].lower() == "on"
                        _cprint(f"Verbose: {'on' if verbose else 'off'}")
                        continue

                    # /color command
                    if text.lower().startswith("/color"):
                        global _response_color
                        parts = text.split()
                        if len(parts) >= 2:
                            c = parts[1].lstrip("#")
                            if len(c) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in c):
                                _response_color = c.upper()
                                _cprint(f"Color: {_colorize(_response_color)}")
                            else:
                                _cprint("Invalid hex color. Use: /color FF005A")
                        else:
                            _cprint(f"Color: {_colorize(_response_color)}")
                        continue

                    if is_working:
                        # Inject into current loop
                        try:
                            await client.post("/inject", json={"text": text}, timeout=5)
                        except Exception as e:
                            _cprint(f"  inject error: {e}")
                    else:
                        # Send as new message (non-blocking)
                        is_working = True
                        asyncio.create_task(send_msg(text))
                        await asyncio.sleep(0.05)

                except KeyboardInterrupt:
                    _ctrl_c_count += 1
                    if _ctrl_c_count >= 2:
                        break
                    _cprint("  \033[90mCtrl+C again to exit\033[0m")
                    continue
                except EOFError:
                    break
    finally:
        ws_task.cancel()
        await client.aclose()
        # Deactivate Kitty keyboard protocol
        sys.stdout.write("\x1b[<u")
        sys.stdout.flush()

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
