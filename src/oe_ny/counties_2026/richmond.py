from ._common import nyc_config

# Richmond County (Staten Island) 2026 primary.  Only Democratic contests were
# held (3 files: CD11, State Comptroller, SD23).  The ``nyc`` engine reads every
# ``Richmond NY *EDLevel.csv`` under the source directory.  See
# _common.nyc_config.
CONFIG = nyc_config(county="Richmond")