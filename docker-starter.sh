#!/bin/bash

# Build and start the docker containers in detached mode
echo "Starting docker-compose build and up..."
docker-compose up --build -d

echo "Docker containers started successfully!"
