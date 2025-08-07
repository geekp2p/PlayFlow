# droidflow/docker-entrypoint.sh
#!/usr/bin/env sh
set -e

# If command-line arguments are supplied, run them
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

# Default: launch the DroidFlow Flask application
exec python3 /app/app.py