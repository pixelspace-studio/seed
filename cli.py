"""Semillita CLI — thin client that talks to the FastAPI server."""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import threading

import httpx

BASE_URL = "http://localhost:9999"
WS_URL = "ws://localhost:9999/stream"

# Color scheme (hex)
_colors = {
    "system": "6B7280",  # cool gray
    "seed": "A3F7FF",    # electric cyan
    "user": "C4B5FD",    # soft lavender
}


def _wordwrap(text: str) -> str:
    """Word-wrap text to terminal width, preserving existing newlines."""
    import shutil
    import textwrap
    width = shutil.get_terminal_size().columns
    lines = text.split("\n")
    wrapped = []
    for line in lines:
        if len(line) <= width:
            wrapped.append(line)
        else:
            wrapped.append(textwrap.fill(line, width=width))
    return "\n".join(wrapped)


def _hex_to_ansi(hex_color: str, text: str) -> str:
    """Wrap text in 24-bit ANSI color from hex."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"


def _colorize(text: str, role: str = "seed") -> str:
    """Word-wrap and colorize text for display."""
    text = _wordwrap(text)
    return _hex_to_ansi(_colors.get(role, _colors["seed"]), text)


def start():
    """Start the Semillita server."""
    subprocess.Popen(
        [sys.executable, "main.py"],
        stdout=None,
        stderr=None,
    )
    print("Starting Semillita...")


def _format_event(data: dict, verbose: bool = True) -> str | None:
    """Format a WebSocket event for display. Returns None to skip."""
    s = lambda txt: _hex_to_ansi(_colors["system"], txt)
    t = data.get("type", "?")
    agent = data.get("agent", "")
    prefix = f"[{agent}] " if agent else ""
    if t == "tool_call":
        args_str = json.dumps(data.get("args", {}), ensure_ascii=False)
        if not verbose and len(args_str) > 120:
            args_str = args_str[:120] + "..."
        return f"  {s(f'{prefix}[{data["tool"]}]')} {args_str}"
    elif t == "tool_result":
        result = data.get("result", "")
        if not verbose and len(result) > 200:
            result = result[:200] + "..."
        return f"  {s(f'{prefix}→ {result}')}"
    elif t == "thinking":
        return f"  {s(f'{prefix}thinking... (iteration {data.get("iteration", "?")})')}"
    elif t == "error":
        return f"  {_hex_to_ansi('FF6B6B', f'{prefix}error: {data.get("message", "?")}')}"
    elif t in ("injected", "response_complete", "idle", "message_received", "interrupted"):
        return None
    else:
        return f"  {s(f'{prefix}[{t}]')}"


def send_message(text: str, agent: str = "semillita"):
    """Send a message and print the response (no verbose)."""
    try:
        r = httpx.post(f"{BASE_URL}/agents/{agent}/message", json={"text": text}, timeout=300)
        r.raise_for_status()
        print(_colorize(r.json()["response"]))
    except httpx.ConnectError:
        print("Error: Semillita is not running. Use 'seed start' first.")
    except Exception as e:
        print(f"Error: {e}")


def send_message_verbose(text: str, agent: str = "semillita"):
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

                    formatted = _format_event(data, verbose=True)
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
        r = httpx.post(f"{BASE_URL}/agents/{agent}/message", json={"text": text}, timeout=300)
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
        r = httpx.get(f"{BASE_URL}/agents", timeout=5)
        print(json.dumps(r.json(), indent=2))
    except httpx.ConnectError:
        print("Semillita is not running.")


def stop():
    """Send interrupt signal to default agent."""
    try:
        r = httpx.post(f"{BASE_URL}/agents/semillita/interrupt", timeout=5)
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
                    formatted = _format_event(data, verbose=True)
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

def chat(verbose: bool = True, model: str = None):
    """Interactive chat loop with multiline + inject support."""
    try:
        asyncio.run(_chat_async(verbose, model))
    except KeyboardInterrupt:
        print("\nbye.")


async def _chat_async(verbose: bool = True, model: str = None):
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
    sys.stdout.write("\x1b[>1u")
    sys.stdout.flush()

    ANSI_SEQUENCES["\x1b[27;2;13~"] = Keys.F24
    ANSI_SEQUENCES["\x1b[13;2u"] = Keys.F24
    ANSI_SEQUENCES["\x1b[99;5u"] = Keys.ControlC
    ANSI_SEQUENCES["\x1b[27u"] = Keys.Escape

    is_working = False
    _ctrl_c_count = 0
    active_agent = "semillita"
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=300)

    def _cprint(text):
        ptprint(ANSI(text))

    def _refresh_prompt():
        app = get_app_or_none()
        if app:
            app.invalidate()

    # --- Key bindings ---
    kb = KeyBindings()

    @kb.add(Keys.F24)
    def _newline(event):
        event.current_buffer.insert_text('\n')

    @kb.add('escape')
    def _escape(event):
        if is_working:
            asyncio.ensure_future(_send_interrupt())

    async def _send_interrupt():
        try:
            await client.post(f"/agents/{active_agent}/interrupt", timeout=5)
        except Exception:
            pass

    def _get_prompt():
        from prompt_toolkit.formatted_text import HTML
        h = _colors["user"]
        sym = '>>' if is_working else '>'
        return HTML(f'<style fg="#{h}">{active_agent}{sym} </style>')

    pt = PromptSession(key_bindings=kb)

    # --- WebSocket listener ---
    async def ws_listener():
        nonlocal is_working
        while True:
            try:
                async with websockets.connect(WS_URL) as ws:
                    async for raw in ws:
                        data = json.loads(raw)
                        t = data.get("type", "")

                        if verbose:
                            fmt = _format_event(data, verbose=True)
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
                await asyncio.sleep(1)

    # --- Send /message in background ---
    async def send_msg(text):
        nonlocal is_working
        try:
            r = await client.post(f"/agents/{active_agent}/message", json={"text": text})
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
    print("  Commands: /model, /agent, /agents, /color, /verbose on|off, exit\n")

    async def _pick_model(out=print):
        """Interactive model picker using GET /models."""
        try:
            # Get current agent status for current model
            r = await client.get(f"/agents/{active_agent}/status", timeout=5)
            current = r.json().get("model", "?")
            # Get models from API
            r = await client.get("/models", timeout=5)
            all_models = r.json()
            text_models = [
                (mid, m["name"]) for mid, m in all_models.items()
                if "text" in m.get("capabilities", [])
            ]
            out("  Models:")
            for i, (mid, name) in enumerate(text_models, 1):
                marker = " *" if mid == current else ""
                out(f"    {i}. {name}{marker}")
            out("")
            choice = input("  Pick a number (enter to keep current): ").strip()
            if choice and choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(text_models):
                    r = await client.post(
                        f"/agents/{active_agent}/model",
                        json={"text": text_models[idx][0]},
                        timeout=5,
                    )
                    r.raise_for_status()
                    out(f"  {r.json().get('result', '')}")
                    return True
                else:
                    out("  Invalid choice.")
            return False
        except Exception as e:
            out(f"  Model switch error: {e}")
            return False

    # Switch model if requested via --model flag
    if model:
        if model == "__pick__":
            await _pick_model()
        else:
            try:
                r = await client.post(
                    f"/agents/{active_agent}/model",
                    json={"text": model},
                    timeout=5,
                )
                r.raise_for_status()
                print(f"  {r.json().get('result', '')}\n")
            except httpx.ConnectError:
                print("  Error: Semillita is not running. Use 'seed start' first.")
                return
            except Exception as e:
                print(f"  Model switch error: {e}\n")

    ws_task = asyncio.create_task(ws_listener())
    await asyncio.sleep(0.3)

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

                    # /model command
                    if text.lower() == "/model":
                        await _pick_model(out=_cprint)
                        continue

                    # /agents command — list all agents
                    if text.lower() == "/agents":
                        try:
                            r = await client.get("/agents", timeout=5)
                            r.raise_for_status()
                            agents_list = r.json()
                            _cprint("  Agents:")
                            for a in agents_list:
                                marker = " *" if a["name"] == active_agent else ""
                                _cprint(f"    {a['name']}: {a['status']} ({a['model']}){marker}")
                        except Exception as e:
                            _cprint(f"  Error: {e}")
                        continue

                    # /agent command — switch active agent
                    if text.lower().startswith("/agent"):
                        parts = text.split()
                        if len(parts) == 1:
                            _cprint(f"  Active agent: {active_agent}")
                        else:
                            new_agent = parts[1]
                            # Verify agent exists
                            try:
                                r = await client.get(f"/agents/{new_agent}/status", timeout=5)
                                r.raise_for_status()
                                if "error" in r.json():
                                    _cprint(f"  Unknown agent: {new_agent}")
                                else:
                                    active_agent = new_agent
                                    _cprint(f"  Switched to {active_agent}")
                                    _refresh_prompt()
                            except Exception as e:
                                _cprint(f"  Error: {e}")
                        continue

                    # /color command — interactive or direct
                    if text.lower().startswith("/color"):
                        parts = text.split()
                        if len(parts) == 1:
                            for role in ("system", "seed", "user"):
                                current = _colors[role]
                                sample = _hex_to_ansi(current, f"{role}: #{current}")
                                _cprint(f"  {sample}")
                            _cprint("")
                            for role in ("system", "seed", "user"):
                                sample = _hex_to_ansi(_colors[role], f"#{_colors[role]}")
                                choice = input(f"  {role} [{sample}\033[0m]: ").strip().lstrip("#")
                                if choice and len(choice) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in choice):
                                    _colors[role] = choice.upper()
                            _cprint("")
                            for role in ("system", "seed", "user"):
                                _cprint(f"  {_hex_to_ansi(_colors[role], f'{role}: #{_colors[role]}')}")
                        elif len(parts) == 3:
                            role = parts[1].lower()
                            c = parts[2].lstrip("#")
                            if role in _colors and len(c) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in c):
                                _colors[role] = c.upper()
                                _cprint(f"  {_hex_to_ansi(_colors[role], f'{role}: #{_colors[role]}')}")
                            else:
                                _cprint("  Usage: /color seed FF005A")
                        else:
                            _cprint("  Usage: /color or /color <system|seed|user> HEX")
                        continue

                    if is_working:
                        try:
                            await client.post(
                                f"/agents/{active_agent}/inject",
                                json={"text": text},
                                timeout=5,
                            )
                        except Exception as e:
                            _cprint(f"  inject error: {e}")
                    else:
                        is_working = True
                        asyncio.create_task(send_msg(text))
                        await asyncio.sleep(0.05)

                except KeyboardInterrupt:
                    _ctrl_c_count += 1
                    if _ctrl_c_count >= 2:
                        break
                    _cprint(f"  {_hex_to_ansi(_colors['system'], 'Ctrl+C again to exit')}")
                    continue
                except EOFError:
                    break
    finally:
        ws_task.cancel()
        await client.aclose()
        sys.stdout.write("\x1b[<u")
        sys.stdout.flush()

    print("\nbye.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(prog="seed", description="Semillita CLI")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show tool calls and events in real-time")
    parser.add_argument("-m", "--model", nargs="?", const="__pick__", default=None,
                        help="Model to use, or pass without value to pick interactively")
    args, positional = parser.parse_known_args()

    cmd = positional[0] if positional else "chat"
    if cmd == "start":
        start()
    elif cmd == "status":
        get_status()
    elif cmd == "stop":
        stop()
    elif cmd == "watch":
        watch()
    elif cmd == "chat":
        chat(verbose=True, model=args.model)
    else:
        full_message = " ".join(positional)
        if args.verbose:
            send_message_verbose(full_message)
        else:
            send_message(full_message)


if __name__ == "__main__":
    main()
