#!/usr/bin/env python3
"""
IndiaQuant MCP Server - Entry Point
This is the main entry point for the IndiaQuant MCP server.
Run this file to start the MCP server.
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import and run the actual server
from server.server import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())