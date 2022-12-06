#!/bin/bash

set -e

if [ "$1" = "test" ]; then
    docker-compose -f docker-compose-test.yml -p test up -d --build
elif [ "$1" = "prod" ]; then
    docker-compose -f docker-compose-prod.yml up -d --build
else
docker-compose -f docker-compose-dev.yml -p dev up -d --build
fi
