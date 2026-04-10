import json
import os
import subprocess
import tempfile
import uuid
from typing import List, Optional

from mcp.server.fastmcp import FastMCP

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

os.makedirs(HOST_MOUNT_DIR, exist_ok=True)

mcp = FastMCP(MCP_NAME, host=MCP_HOST, port=MCP_PORT)


def _build_docker_command(
    script_path: str,
    requirements: Optional[List[str]],
    workdir: str,
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
        f"{HOST_MOUNT_DIR}:{workdir}",
        "-w",
        workdir,
        DEFAULT_IMAGE,
        "bash",
        "-lc",
        run_cmd,
    ]


@mcp.tool()
def run_python(
    code: str,
    requirements: Optional[List[str]] = None,
    workdir: str = "/data",
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> dict:
    """Execute Python code inside a Docker container and return stdout/stderr."""
    run_id = uuid.uuid4().hex
    run_dir = tempfile.mkdtemp(prefix=f"run_{run_id}_", dir=HOST_MOUNT_DIR)
    script_path = os.path.join(run_dir, "script.py")
    with open(script_path, "w", encoding="utf-8") as handle:
        handle.write(code)
    container_script_path = os.path.join(workdir, os.path.basename(run_dir), "script.py")
    cmd = _build_docker_command(container_script_path, requirements, workdir)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "exit_code": None,
            "stdout": exc.stdout or "",
            "stderr": (exc.stderr or "") + "\nTimeout exceeded",
            "run_id": run_id,
            "run_dir": run_dir,
        }

    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "command": " ".join(cmd),
        "run_id": run_id,
        "run_dir": run_dir,
    }


@mcp.tool()
def list_runs() -> str:
    """List run directories stored on the host mount."""
    runs = sorted(os.listdir(HOST_MOUNT_DIR))
    return json.dumps({"runs": runs})


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "sse").lower()

    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        print(f"Setting up SSE {MCP_HOST}:{MCP_PORT}")
        mcp.run(transport=transport, mount_path=MCP_MOUNT_PATH)
