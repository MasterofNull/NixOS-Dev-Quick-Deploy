#!/usr/bin/env python3
"""
Built-in Computer Use Tools for Local Agents

Provides OpenClaw-like computer control capabilities:
- screenshot: Capture screen or regions
- mouse_move: Move mouse cursor
- mouse_click: Click at coordinates
- keyboard_type: Type text
- get_screen_size: Get screen dimensions

All actions logged for safety and auditing.

Part of Phase 11 Batch 11.2: Computer Use Integration
"""

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tool_registry import (
    SafetyPolicy,
    ToolCategory,
    ToolDefinition,
    ToolRegistry,
)

logger = logging.getLogger(__name__)


# Screenshot storage
SCREENSHOT_DIR = Path.home() / ".local/share/nixos-ai-stack/local-agents/screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


async def screenshot_handler(
    output_path: Optional[str] = None,
    region: Optional[Tuple[int, int, int, int]] = None,
) -> Dict:
    """
    Capture screenshot of entire screen or specific region.

    Args:
        output_path: Optional output path (default: auto-generated)
        region: Optional region as (x, y, width, height)

    Returns:
        {
            "success": bool,
            "path": str,
            "size": [width, height],
            "error": str (if failed)
        }
    """
    try:
        # Generate output path if not provided
        if not output_path:
            import time
            timestamp = int(time.time())
            output_path = str(SCREENSHOT_DIR / f"screenshot_{timestamp}.png")

        # Build scrot command (common Linux screenshot tool)
        # Alternative: gnome-screenshot, import (ImageMagick), maim
        cmd = ["scrot"]

        if region:
            x, y, w, h = region
            cmd.extend(["-a", f"{x},{y},{w},{h}"])

        cmd.append(output_path)

        # Execute screenshot
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Screenshot failed: {result.stderr}",
            }

        # Get image size
        try:
            # Use identify from ImageMagick
            size_result = subprocess.run(
                ["identify", "-format", "%wx%h", output_path],
                capture_output=True,
                text=True,
                timeout=2,
            )
            size_str = size_result.stdout.strip()
            width, height = map(int, size_str.split("x"))
            size = [width, height]
        except:
            size = None

        return {
            "success": True,
            "path": output_path,
            "size": size,
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Screenshot timed out"}
    except FileNotFoundError:
        return {
            "success": False,
            "error": "Screenshot tool not found (install scrot: sudo apt install scrot)",
        }
    except Exception as e:
        return {"success": False, "error": f"Screenshot failed: {e}"}


async def mouse_move_handler(x: int, y: int) -> Dict:
    """
    Move mouse cursor to absolute coordinates.

    Args:
        x: X coordinate
        y: Y coordinate

    Returns:
        {
            "success": bool,
            "position": [x, y],
            "error": str (if failed)
        }
    """
    try:
        # Use xdotool for X11 (most common on Linux)
        result = subprocess.run(
            ["xdotool", "mousemove", str(x), str(y)],
            capture_output=True,
            text=True,
            timeout=2,
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Mouse move failed: {result.stderr}",
            }

        return {
            "success": True,
            "position": [x, y],
        }

    except FileNotFoundError:
        return {
            "success": False,
            "error": "xdotool not found (install: sudo apt install xdotool)",
        }
    except Exception as e:
        return {"success": False, "error": f"Mouse move failed: {e}"}


async def mouse_click_handler(
    x: Optional[int] = None,
    y: Optional[int] = None,
    button: int = 1,
    clicks: int = 1,
) -> Dict:
    """
    Click mouse at coordinates or current position.

    Args:
        x: Optional X coordinate (None = current position)
        y: Optional Y coordinate (None = current position)
        button: Mouse button (1=left, 2=middle, 3=right)
        clicks: Number of clicks (1=single, 2=double)

    Returns:
        {
            "success": bool,
            "position": [x, y],
            "error": str (if failed)
        }
    """
    try:
        cmd = ["xdotool"]

        # Move to position if specified
        if x is not None and y is not None:
            cmd.extend(["mousemove", str(x), str(y)])

        # Click
        cmd.extend(["click", "--repeat", str(clicks), str(button)])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=2,
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Mouse click failed: {result.stderr}",
            }

        # Get current position
        pos_result = subprocess.run(
            ["xdotool", "getmouselocation", "--shell"],
            capture_output=True,
            text=True,
            timeout=2,
        )

        position = [x, y] if x is not None else None
        if pos_result.returncode == 0:
            # Parse X=123\nY=456\n format
            for line in pos_result.stdout.splitlines():
                if line.startswith("X="):
                    pos_x = int(line.split("=")[1])
                elif line.startswith("Y="):
                    pos_y = int(line.split("=")[1])
            position = [pos_x, pos_y]

        return {
            "success": True,
            "position": position,
            "button": button,
            "clicks": clicks,
        }

    except FileNotFoundError:
        return {
            "success": False,
            "error": "xdotool not found (install: sudo apt install xdotool)",
        }
    except Exception as e:
        return {"success": False, "error": f"Mouse click failed: {e}"}


async def keyboard_type_handler(
    text: str,
    delay_ms: int = 12,
) -> Dict:
    """
    Type text using keyboard input.

    Args:
        text: Text to type
        delay_ms: Delay between keystrokes in ms

    Returns:
        {
            "success": bool,
            "characters_typed": int,
            "error": str (if failed)
        }
    """
    try:
        cmd = ["xdotool", "type", "--delay", str(delay_ms), text]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(5, len(text) * delay_ms / 1000 + 2),
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Keyboard type failed: {result.stderr}",
            }

        return {
            "success": True,
            "characters_typed": len(text),
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Keyboard type timed out"}
    except FileNotFoundError:
        return {
            "success": False,
            "error": "xdotool not found (install: sudo apt install xdotool)",
        }
    except Exception as e:
        return {"success": False, "error": f"Keyboard type failed: {e}"}


async def keyboard_press_handler(
    key: str,
    modifiers: Optional[List[str]] = None,
) -> Dict:
    """
    Press keyboard key with optional modifiers.

    Args:
        key: Key name (Return, Escape, Tab, etc.)
        modifiers: Optional modifiers (ctrl, alt, shift, super)

    Returns:
        {
            "success": bool,
            "key": str,
            "error": str (if failed)
        }
    """
    try:
        # Build key combination
        if modifiers:
            key_combo = "+".join(modifiers + [key])
        else:
            key_combo = key

        result = subprocess.run(
            ["xdotool", "key", key_combo],
            capture_output=True,
            text=True,
            timeout=2,
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Key press failed: {result.stderr}",
            }

        return {
            "success": True,
            "key": key,
            "modifiers": modifiers,
        }

    except FileNotFoundError:
        return {
            "success": False,
            "error": "xdotool not found (install: sudo apt install xdotool)",
        }
    except Exception as e:
        return {"success": False, "error": f"Key press failed: {e}"}


async def get_screen_size_handler() -> Dict:
    """
    Get screen dimensions.

    Returns:
        {
            "success": bool,
            "width": int,
            "height": int,
            "error": str (if failed)
        }
    """
    try:
        # Use xdpyinfo to get display info
        result = subprocess.run(
            ["xdpyinfo"],
            capture_output=True,
            text=True,
            timeout=2,
        )

        if result.returncode != 0:
            return {"success": False, "error": "Failed to get display info"}

        # Parse dimensions from output
        # Look for line like: "dimensions:    1920x1080 pixels"
        for line in result.stdout.splitlines():
            if "dimensions:" in line:
                dims = line.split()[1]  # "1920x1080"
                width, height = map(int, dims.split("x"))
                return {
                    "success": True,
                    "width": width,
                    "height": height,
                }

        return {"success": False, "error": "Could not parse screen dimensions"}

    except FileNotFoundError:
        return {
            "success": False,
            "error": "xdpyinfo not found (install: sudo apt install x11-utils)",
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to get screen size: {e}"}


def register_computer_use_tools(registry: ToolRegistry):
    """Register all computer use tools in the registry"""

    # screenshot
    registry.register(ToolDefinition(
        name="screenshot",
        description="Capture screenshot of entire screen or specific region",
        parameters={
            "type": "object",
            "properties": {
                "output_path": {
                    "type": "string",
                    "description": "Optional output path (default: auto-generated)",
                },
                "region": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "minItems": 4,
                    "maxItems": 4,
                    "description": "Optional region as [x, y, width, height]",
                },
            },
        },
        category=ToolCategory.VISION,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=screenshot_handler,
    ))

    # mouse_move
    registry.register(ToolDefinition(
        name="mouse_move",
        description="Move mouse cursor to absolute coordinates",
        parameters={
            "type": "object",
            "properties": {
                "x": {
                    "type": "integer",
                    "description": "X coordinate",
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate",
                },
            },
            "required": ["x", "y"],
        },
        category=ToolCategory.VISION,
        safety_policy=SafetyPolicy.WRITE_SAFE,
        handler=mouse_move_handler,
        requires_confirmation=True,  # Require confirmation for GUI control
        max_calls_per_minute=30,  # Limit to prevent runaway automation
    ))

    # mouse_click
    registry.register(ToolDefinition(
        name="mouse_click",
        description="Click mouse at coordinates or current position",
        parameters={
            "type": "object",
            "properties": {
                "x": {
                    "type": "integer",
                    "description": "Optional X coordinate (None = current position)",
                },
                "y": {
                    "type": "integer",
                    "description": "Optional Y coordinate (None = current position)",
                },
                "button": {
                    "type": "integer",
                    "description": "Mouse button (1=left, 2=middle, 3=right)",
                    "default": 1,
                    "minimum": 1,
                    "maximum": 3,
                },
                "clicks": {
                    "type": "integer",
                    "description": "Number of clicks (1=single, 2=double)",
                    "default": 1,
                    "minimum": 1,
                    "maximum": 3,
                },
            },
        },
        category=ToolCategory.VISION,
        safety_policy=SafetyPolicy.WRITE_SAFE,
        handler=mouse_click_handler,
        requires_confirmation=True,
        max_calls_per_minute=20,
    ))

    # keyboard_type
    registry.register(ToolDefinition(
        name="keyboard_type",
        description="Type text using keyboard input",
        parameters={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to type",
                },
                "delay_ms": {
                    "type": "integer",
                    "description": "Delay between keystrokes in ms",
                    "default": 12,
                    "minimum": 1,
                    "maximum": 1000,
                },
            },
            "required": ["text"],
        },
        category=ToolCategory.VISION,
        safety_policy=SafetyPolicy.WRITE_SAFE,
        handler=keyboard_type_handler,
        requires_confirmation=True,
        max_calls_per_minute=20,
    ))

    # keyboard_press
    registry.register(ToolDefinition(
        name="keyboard_press",
        description="Press keyboard key with optional modifiers (ctrl, alt, shift, super)",
        parameters={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Key name (Return, Escape, Tab, etc.)",
                },
                "modifiers": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["ctrl", "alt", "shift", "super"],
                    },
                    "description": "Optional modifiers",
                },
            },
            "required": ["key"],
        },
        category=ToolCategory.VISION,
        safety_policy=SafetyPolicy.WRITE_SAFE,
        handler=keyboard_press_handler,
        requires_confirmation=True,
        max_calls_per_minute=20,
    ))

    # get_screen_size
    registry.register(ToolDefinition(
        name="get_screen_size",
        description="Get screen dimensions (width, height)",
        parameters={
            "type": "object",
            "properties": {},
        },
        category=ToolCategory.VISION,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=get_screen_size_handler,
    ))

    logger.info("Registered 6 computer use tools")


if __name__ == "__main__":
    # Test computer use tools
    logging.basicConfig(level=logging.INFO)

    async def test():
        from tool_registry import ToolRegistry, ToolCall

        registry = ToolRegistry()
        register_computer_use_tools(registry)

        # Test screenshot
        screenshot_call = ToolCall(
            id="test-screenshot",
            tool_name="screenshot",
            arguments={},
            model_id="test",
            session_id="test",
        )

        result = await registry.execute_tool_call(screenshot_call)
        print(f"\nscreenshot result:")
        print(f"  Status: {result.status}")
        if result.result:
            print(f"  Path: {result.result.get('path')}")
            print(f"  Size: {result.result.get('size')}")

        # Test get_screen_size
        size_call = ToolCall(
            id="test-size",
            tool_name="get_screen_size",
            arguments={},
            model_id="test",
            session_id="test",
        )

        result = await registry.execute_tool_call(size_call)
        print(f"\nget_screen_size result:")
        print(f"  Status: {result.status}")
        if result.result:
            print(f"  Dimensions: {result.result.get('width')}x{result.result.get('height')}")

        # Get statistics
        stats = registry.get_statistics()
        print(f"\nRegistry statistics:")
        print(json.dumps(stats, indent=2))

    asyncio.run(test())
