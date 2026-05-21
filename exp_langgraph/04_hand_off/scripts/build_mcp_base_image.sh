#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH=$(dirname $(realpath $0))
ROOT_PATH=$SCRIPT_PATH/..

# Builds the MCP Python base image with preinstalled geospatial dependencies.
# Usage:
#   scripts/build_mcp_base_image.sh
#   MCP_DOCKER_IMAGE=my-tag scripts/build_mcp_base_image.sh

IMAGE_TAG="${MCP_DOCKER_IMAGE:-agentic-gis-mcp-python:latest}"
DOCKERFILE_PATH="${ROOT_PATH}/docker/mcp-python-base/Dockerfile"
BUILD_CONTEXT="${ROOT_PATH}/docker/mcp-python-base"

echo "Building MCP base image: ${IMAGE_TAG}"
docker build -t "${IMAGE_TAG}" -f "${DOCKERFILE_PATH}" "${BUILD_CONTEXT}"
echo "Done. Image available as: ${IMAGE_TAG}"

