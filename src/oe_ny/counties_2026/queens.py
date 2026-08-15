from ._common import nyc_config

# Queens County 2026 primary.  The ``nyc`` engine reads every ``Queens NY
# *EDLevel.csv`` under the source directory.  See _common.nyc_config.
CONFIG = nyc_config(county="Queens")