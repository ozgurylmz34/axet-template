# -*- coding: utf-8 -*-
"""Meta araçlar — SAP'ye bağlanmaz."""
from __future__ import annotations

from sapadt._app import profil_tool


@profil_tool()
def ping() -> dict:
    """Sağlık kontrolü — araç katmanı yüklü ve çağrılabilir mi. SAP'ye bağlanmaz.

    `sap-project.json` olmadan da çalışır (fail-closed modda açık kalan tek araç).
    """
    from sapadt import __version__
    from sapadt.project import project_dir
    return {
        "ok": True,
        "service": "sap-adt-cli",
        "version": __version__,
        "project_dir": str(project_dir()),
    }
