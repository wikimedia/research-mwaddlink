import os

bind = "0.0.0.0:8000"
# Emit events to sidecar container in production.
statsd_host = "localhost:9125"
statsd_prefix = "linkrecommendation"
# See https://docs.gunicorn.org/en/stable/design.html#how-many-workers which
# suggests the formula (2 x $num_cores) + 1
# Conservatively assuming 2 cores
workers = 5
# Processing recommendations for larger pages is slow.
timeout = os.environ.get("GUNICORN_TIMEOUT", 30)
graceful_timeout = os.environ.get("GUNICORN_TIMEOUT", 30)
loglevel = os.environ.get("GUNICORN_LOGLEVEL", "warning")
preload_app = True
