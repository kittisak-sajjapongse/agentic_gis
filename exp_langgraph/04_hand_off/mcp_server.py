import json
import os
import subprocess
import tempfile
import uuid
from typing import Annotated, List, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import Field

MCP_NAME = "docker-python"
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "8000"))
MCP_MOUNT_PATH = os.getenv("MCP_MOUNT_PATH")
DEFAULT_IMAGE = os.getenv("MCP_DOCKER_IMAGE", "python:3.11-slim")
HOST_MOUNT_DIR = os.getenv(
    "MCP_DOCKER_HOST_DIR",
    os.path.join(os.getcwd(), "exp", "02_programming_agent_mcp", "runs"),
)
DEFAULT_TIMEOUT_S = int(os.getenv("MCP_DOCKER_TIMEOUT_S", "60"))
CONTAINER_MOUNT_DIR = "/data"

os.makedirs(HOST_MOUNT_DIR, exist_ok=True)

mcp = FastMCP(MCP_NAME, host=MCP_HOST, port=MCP_PORT)


def _to_text(value: str | bytes | None) -> str:
    # subprocess output can be bytes in some error/timeout cases
    # (e.g., TimeoutExpired stdout/stderr), so normalize to str before
    # concatenating/serializing to avoid type errors like:
    # "can't concat str to bytes".
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _build_docker_command(
    host_mount_dir: str,
    script_path: str,
    requirements: Optional[List[str]],
) -> List[str]:
    pip_cmd = ""
    if requirements:
        reqs = " ".join(requirements)
        pip_cmd = f"python -m pip install -q --no-cache-dir {reqs} && "
    run_cmd = f"{pip_cmd}python {script_path}"
    return [
        "docker",
        "run",
        "--rm",
        "-i",
        "-v",
        f"{host_mount_dir}:{CONTAINER_MOUNT_DIR}",
        "-w",
        CONTAINER_MOUNT_DIR,
        DEFAULT_IMAGE,
        "bash",
        "-lc",
        run_cmd,
    ]


# NOTE: FastMCP uses the function docstring as the tool description exposed to MCP clients/LLMs.
# NOTE: We keep the function signature while using Pydantic Field metadata via Annotated
# so MCP exposes per-argument descriptions to the LLM without changing how tools are called.
@mcp.tool()
def run_python(
    code: Annotated[str, Field(description="Python source code to execute inside the container.")],
    host_mount_dir: Annotated[
        str,
        Field(
            description=(
                "Host directory to mount into the container at /data. "
                "If relative, it is resolved from current working directory."
            )
        ),
    ] = HOST_MOUNT_DIR,
    requirements: Annotated[
        Optional[List[str]],
        Field(description="Optional pip package names to install before execution."),
    ] = None,
    timeout_s: Annotated[
        int,
        Field(
            description=(
                "Max execution time in seconds. Optional; if omitted, server default is used."
            )
        ),
    ] = DEFAULT_TIMEOUT_S,
) -> dict:
    """Execute Python code inside a Docker container and return stdout/stderr."""
    mount_dir_abs = os.path.abspath(host_mount_dir)
    os.makedirs(mount_dir_abs, exist_ok=True)

    run_id = uuid.uuid4().hex
    run_dir = tempfile.mkdtemp(prefix=f"run_{run_id}_", dir=mount_dir_abs)
    script_path = os.path.join(run_dir, "script.py")
    with open(script_path, "w", encoding="utf-8") as handle:
        handle.write(code)
    container_script_path = os.path.join(
        CONTAINER_MOUNT_DIR, os.path.basename(run_dir), "script.py"
    )
    cmd = _build_docker_command(mount_dir_abs, container_script_path, requirements)
    print(f"Docker command: {cmd}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        timeout_stdout = _to_text(exc.stdout)
        timeout_stderr = _to_text(exc.stderr)
        return {
            "ok": False,
            "exit_code": None,
            "stdout": timeout_stdout,
            "stderr": timeout_stderr + "\nTimeout exceeded",
            "run_id": run_id,
            "run_dir": run_dir,
        }

    stdout_text = _to_text(result.stdout)
    stderr_text = _to_text(result.stderr)
    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "command": " ".join(cmd),
        "run_id": run_id,
        "run_dir": run_dir,
    }


# NOTE: FastMCP uses the function docstring as the tool description exposed to MCP clients/LLMs.
@mcp.tool()
def list_runs(
    host_mount_dir: Annotated[
        str,
        Field(description="Host directory where run folders are stored."),
    ] = HOST_MOUNT_DIR,
) -> str:
    """List run directories stored on the host mount."""
    mount_dir_abs = os.path.abspath(host_mount_dir)
    os.makedirs(mount_dir_abs, exist_ok=True)
    runs = sorted(os.listdir(mount_dir_abs))
    return json.dumps({"host_mount_dir": mount_dir_abs, "runs": runs})


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "sse").lower()

    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        print(f"Setting up SSE {MCP_HOST}:{MCP_PORT}")
        mcp.run(transport=transport, mount_path=MCP_MOUNT_PATH)
