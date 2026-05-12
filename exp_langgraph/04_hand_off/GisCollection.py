"""Compatibility shim.

Use domain.gis_catalog.GIS_COLLECTION for new imports.
"""

from domain.gis_catalog import GIS_COLLECTION

__all__ = ["GIS_COLLECTION"]
