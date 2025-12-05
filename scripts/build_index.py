#!/usr/bin/env python3
"""
Build documentation indexes for WPILib MCP plugins.

This is a convenience wrapper that calls individual plugin build scripts.
Each vendor maintains their own build_index.py in their plugin directory.

Usage:
    python scripts/build_index.py wpilib --version 2025
    python scripts/build_index.py rev
    python scripts/build_index.py ctre
    python scripts/build_index.py redux
    python scripts/build_index.py all

For vendor-specific options, run the plugin's build script directly:
    python -m wpilib_mcp.plugins.wpilib.build_index --help
"""

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path


PLUGINS_DIR = Path(__file__).parent.parent / "src" / "wpilib_mcp" / "plugins"


def get_available_plugins() -> list[str]:
    """Get list of plugins with build scripts."""
    plugins = []
    for plugin_dir in PLUGINS_DIR.iterdir():
        if plugin_dir.is_dir() and not plugin_dir.name.startswith("_"):
            build_script = plugin_dir / "build_index.py"
            if build_script.exists():
                plugins.append(plugin_dir.name)
    return sorted(plugins)


def run_plugin_build(plugin: str, extra_args: list[str]) -> int:
    """Run a plugin's build script."""
    module = f"wpilib_mcp.plugins.{plugin}.build_index"
    
    cmd = [sys.executable, "-m", module] + extra_args
    print(f"\n{'='*60}")
    print(f"Building index for: {plugin}")
    print(f"{'='*60}\n")
    
    result = subprocess.run(cmd, cwd=PLUGINS_DIR.parent.parent.parent)
    return result.returncode


def main():
    available = get_available_plugins()
    
    parser = argparse.ArgumentParser(
        description="Build documentation indexes for WPILib MCP plugins",
        epilog=f"Available plugins: {', '.join(available)}"
    )
    parser.add_argument(
        "plugin",
        choices=available + ["all"],
        help="Plugin to build index for, or 'all' for all plugins"
    )
    parser.add_argument(
        "--version",
        default="stable",
        help="Documentation version (passed to plugin build script)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args, extra_args = parser.parse_known_args()
    
    # Build extra args to pass to plugin scripts
    if args.version != "stable":
        extra_args.extend(["--version", args.version])
    if args.verbose:
        extra_args.append("--verbose")
    
    # Determine which plugins to build
    if args.plugin == "all":
        plugins = available
    else:
        plugins = [args.plugin]
    
    # Run builds
    failed = []
    for plugin in plugins:
        if plugin not in available:
            print(f"Warning: Plugin '{plugin}' has no build script, skipping")
            continue
        
        ret = run_plugin_build(plugin, extra_args)
        if ret != 0:
            failed.append(plugin)
    
    # Summary
    print(f"\n{'='*60}")
    print("Build Summary")
    print(f"{'='*60}")
    print(f"Plugins processed: {len(plugins)}")
    
    if failed:
        print(f"Failed: {', '.join(failed)}")
        return 1
    else:
        print("All builds successful!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
