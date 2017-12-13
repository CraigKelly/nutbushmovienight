"""log - our centralized logging.

IMPORTANT!
Because logging is needed at such a low level, this file should NEVER import
from other sub-packages/modules in nbmn. All other python files can confidently
import functions from us without worrying about cyclical dependencies
"""

import daiquiri


def setup(level):
    """Centralized logging setup."""
    daiquiri.setup(level=level)

def app_logger():
    """Centralized logger."""
    return daiquiri.getLogger("nbmn")
