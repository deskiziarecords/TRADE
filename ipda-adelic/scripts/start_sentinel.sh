#!/bin/bash
echo "Starting Adelic-Koopman SOS-27-X Sentinel Stack..."
cd "$(dirname "$0")/../docker" || exit
docker-compose up -d --build
echo "System deployed. Monitor with: docker-compose logs -f sentinel"
