#!/bin/bash

NGINX_HOSTS=$(echo "$ALLOWED_HOSTS" | sed -r 's/,/ /g')
cp /etc/nginx/nginx.conf.template /etc/nginx/nginx.conf
sed -i "s/NGINX_HOSTS/${NGINX_HOSTS}/" /etc/nginx/nginx.conf
nginx -g 'daemon off;'
