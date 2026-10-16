"""Imports every alert detector module so each registers itself with the engine.

The worker imports this one module; adding a detector means adding its module here.
"""

from sleeper_assistant import (  # noqa: F401  (each import registers its detector)
    alert_injury,
    alert_waiver,
)
