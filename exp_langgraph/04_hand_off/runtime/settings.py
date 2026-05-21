from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppSettings:
    openai_model: str = "gpt-4o"
    llm_temperature: float = 0.0
    mcp_server_url: str = "http://127.0.0.1:8001/sse"
    docker_mcp_server_name: str = "docker-python"
    data_mount_dir: str = ""
    state_file: str = ""
    persistence_backend: str = "json"

    @classmethod
    def from_env(cls) -> "AppSettings":
        default_data_mount = str(Path.cwd() / "data")
        default_state_file = str(Path.cwd() / "data" / "poc_state.json")
        return cls(
            openai_model=os.getenv("OPENAI_MODEL", cls.openai_model),
            llm_temperature=float(
                os.getenv("LLM_TEMPERATURE", str(cls.llm_temperature))
            ),
            mcp_server_url=os.getenv("MCP_SERVER_URL", cls.mcp_server_url),
            docker_mcp_server_name=os.getenv(
                "DOCKER_MCP_SERVER_NAME", cls.docker_mcp_server_name
            ),
            data_mount_dir=os.getenv("DATA_MOUNT_DIR", default_data_mount),
            state_file=os.getenv("POC_STATE_FILE", default_state_file),
            persistence_backend=os.getenv(
                "POC_PERSISTENCE_BACKEND", cls.persistence_backend
            ),
        )
