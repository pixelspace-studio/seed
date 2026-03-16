"""Tool registry — discovers and loads tools from core/tools/ and agents/shared/tools/."""

import importlib
import importlib.util
import os
import sys


class Registry:
    def __init__(self, seed_dir: str):
        self.seed_dir = seed_dir
        self.core_dir = os.path.join(seed_dir, "core", "tools")
        self.custom_dir = os.path.join(seed_dir, "agents", "shared", "tools")
        self._tools: dict[str, dict] = {}

    def _load_from_dir(self, directory: str) -> dict[str, dict]:
        """Load all tool modules from a directory."""
        tools = {}
        if not os.path.isdir(directory):
            return tools

        for filename in sorted(os.listdir(directory)):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue

            filepath = os.path.join(directory, filename)
            module_name = f"_tool_{filename[:-3]}"

            try:
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

                if hasattr(module, "tool") and isinstance(module.tool, dict):
                    t = module.tool
                    if "name" in t and "execute" in t:
                        tools[t["name"]] = t
            except Exception as e:
                print(f"[registry] Error loading {filepath}: {e}")

        return tools

    def load(self):
        """Load core tools and custom tools. Core tools win on conflict."""
        custom = self._load_from_dir(self.custom_dir)
        core = self._load_from_dir(self.core_dir)
        # Core overrides custom
        self._tools = {**custom, **core}

    def reload_custom(self):
        """Re-scan tools/ only (hot reload)."""
        custom = self._load_from_dir(self.custom_dir)
        # Keep core, replace custom
        core_names = set(
            t["name"] for t in self._load_from_dir(self.core_dir).values()
        )
        # Remove old custom tools
        self._tools = {k: v for k, v in self._tools.items() if k in core_names}
        # Add new custom tools (core still wins)
        for name, tool in custom.items():
            if name not in self._tools:
                self._tools[name] = tool

    def get_tools_schema(self) -> list[dict]:
        """Return tool schemas for the AI provider."""
        schemas = []
        for t in self._tools.values():
            schemas.append({
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("parameters", {"type": "object", "properties": {}}),
            })
        return schemas

    def get_tool_names(self) -> list[str]:
        return list(self._tools.keys())

    async def execute(self, name: str, args: dict) -> str:
        """Execute a tool by name with given arguments."""
        if name not in self._tools:
            return f"Error: unknown tool '{name}'"

        tool = self._tools[name]
        fn = tool["execute"]

        try:
            # Filter args to only those the function accepts
            import inspect
            sig = inspect.signature(fn)
            valid_args = {k: v for k, v in args.items() if k in sig.parameters}
            result = await fn(**valid_args)
            return str(result) if result is not None else "OK"
        except Exception as e:
            return f"Error executing {name}: {e}"
