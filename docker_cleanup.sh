#!/bin/bash
# Nightly Docker cleanup script

# Prune unused containers, networks, images, and volumes
# -a: Remove all unused images, not just dangling ones
# --volumes: Prune volumes
# -f: Force bypass confirmation prompt (required for cron without interactive tty)
echo "Starting Docker cleanup at $(date)"
docker system prune -a --volumes -f
echo "Docker cleanup completed successfully at $(date)"