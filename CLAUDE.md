# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An [AstrBot](https://github.com/Soulter/AstrBot) plugin that queries Minecraft Java/Bedrock server status and returns a styled image with MOTD, server icon, player count, ping, and version info. **This plugin is discontinued** per the README.

## Architecture

Two-file plugin with clear separation:

- **`main.py`** — Plugin entry point. Defines `MCPingPlugin(Star)` with a single `@filter.command("mcp")` handler. Receives server IP, tries Java then Bedrock lookup, yields an image result or error text.
- **`data_source.py`** — All query and rendering logic:
  - `get_java_server_status()` / `get_be_server_status()` — async functions that query via `mcstatus` and delegate to image generation
  - `get_server_info_image()` — orchestrates PIL image composition onto `resource/background.png`
  - `draw_*()` helpers — render MOTD (with Minecraft §-color codes), icon, online count, server version, and ping onto the image
  - `color_dict` — maps Minecraft color codes (§0–§g) to RGB tuples
  - Utility: `base64_pil()`, `image_to_bytes()`, `get_font()`, `get_color()`

## Dependencies

- `mcstatus` — Minecraft server status polling (Java + Bedrock)
- `Pillow` — Image generation (referenced but not pinned in requirements.txt)
- AstrBot SDK — `astrbot.api.star`, `astrbot.api.event`, `astrbot.core.message.components`

## Resources

- `resource/background.png` — base image template for status card
- `resource/simhei.ttf` — Chinese font used for all text rendering
