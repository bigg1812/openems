#!/usr/bin/env python3
"""Command-line entrypoint for the Mini EMS runtime."""

import sys

# Versions-Guard: muss unter Python 3.9 syntaktisch lauffuehrbar sein (kein
# PEP-604 "X | None"), weil genau das im weiteren Code Python >= 3.10
# voraussetzt. Ohne diesen Check bricht der Import erst tief in
# mini_ems_runtime mit einem kryptischen TypeError ab.
if sys.version_info < (3, 10):
    found = "{}.{}.{}".format(*sys.version_info[:3])
    sys.stderr.write(
        "Fehler: Mini EMS benoetigt Python >= 3.10, gefunden: {}. "
        "Bitte einen Interpreter >= 3.10 verwenden "
        "(z. B. python3.12 bzw. die Projekt-.venv, siehe README).\n".format(found)
    )
    raise SystemExit(1)

from mini_ems_runtime.app import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
