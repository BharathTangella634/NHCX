#!/bin/bash

# Build and start the docker containers in detached mode
echo "Starting docker-compose build and up..."
docker compose build --no-cache && docker compose up -d

echo "Docker containers started successfully!"
