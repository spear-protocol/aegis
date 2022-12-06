#!/usr/bin/env bash

# wait for database server
./wait_for_it.sh ${POSTGRES_SERVER_HOST}:${POSTGRES_SERVER_PORT} --timeout=0 --             \
# wait for cache server
./wait_for_it.sh ${CACHE_REDIS_HOST}:${CACHE_REDIS_PORT} --timeout=0 --                     \
./wait_for_it.sh ${OPERATOR_API_HOST}:${OPERATOR_API_PORT} --timeout=0 --                                           \
celery -A operator_api worker -l info --concurrency 1 -n verifier-worker@%h -Q celery
