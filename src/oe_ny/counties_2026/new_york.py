from ._common import nyc_config

# New York County (Manhattan) 2026 primary.  The NYC BoE publishes one
# EDLevel.csv per contest; the ``nyc`` engine reads every ``New York NY
# *EDLevel.csv`` under the source directory.  See _common.nyc_config for the
# format notes (22-field rows, IN-PLAY filter, tally rows, no Ballots Cast
# synthesis).
CONFIG = nyc_config(county="New York")