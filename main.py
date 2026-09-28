from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from AutoJoin.bootstrap import init_deps

init_deps()

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        try:
            import pythoncom
            import win32crypt
            import win32gui
            from AutoJoin.teams import TeamsAdapter
            TeamsAdapter()  # Verify packaged UI Automation dependencies.
            diagnostic = "OK"
            code = 0
        except Exception:
            diagnostic = traceback.format_exc()
            code = 1
        target = os.environ.get("TEAMS_AUTOJOIN_DIAG_FILE")
        if target:
            Path(target).write_text(diagnostic, encoding="utf-8")
        raise SystemExit(code)
    from AutoJoin.app import App
    App().run()
