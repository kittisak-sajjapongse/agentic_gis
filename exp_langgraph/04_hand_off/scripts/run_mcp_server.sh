#!/usr/bin/env bash

SCRIPT_PATH=$(dirname $(realpath $0))
ROOT_PATH=$SCRIPT_PATH/..

MCP_PORT=8001 python3 $ROOT_PATH/mcp_server.py
