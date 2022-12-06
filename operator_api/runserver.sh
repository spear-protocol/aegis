#!/bin/bash

# wait for database server
./wait_for_it.sh ${POSTGRES_SERVER_HOST}:${POSTGRES_SERVER_PORT} --timeout=0 --             \
# wait for cache server
./wait_for_it.sh ${CACHE_REDIS_HOST}:${CACHE_REDIS_PORT} --timeout=0 --                     \
python3 manage.py makemigrations                                                         && \
python3 manage.py migrate                                                                && \
gunicorn -b 0.0.0.0:3031 -w 4 -k uvicorn.workers.UvicornH11Worker operator_api.asgi:application
