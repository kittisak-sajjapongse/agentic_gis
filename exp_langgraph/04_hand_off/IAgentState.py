"""Compatibility shim.

Use domain.state_models for new imports.
"""

from domain.state_models import GISFile, IAgentState

__all__ = ["GISFile", "IAgentState"]
