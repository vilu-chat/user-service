#!/bin/sh
set -e
# Compose convenience: migrate, then serve. In Kubernetes run `flask --app app db upgrade`
# as a Job or init container instead (see design.md, "Database and migrations").
flask --app app db upgrade
exec gunicorn 'app:create_app()' --bind 0.0.0.0:8001 --workers 2 --threads 4
