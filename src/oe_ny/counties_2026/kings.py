from ._common import nyc_config

# Kings County (Brooklyn) 2026 primary.  The ``nyc`` engine reads every
# ``Kings NY *EDLevel.csv`` under the source directory.  See _common.nyc_config.
CONFIG = nyc_config(county="Kings")