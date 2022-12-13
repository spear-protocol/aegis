# This process is required as React only will listen to env variables at build time so we pass them in through nginx
# see: https://www.manifold.co/blog/building-a-production-grade-container-for-your-static-javascript-application-b2b2eff83fbd

NGINX_SUB_FILTER=$(cat .env.production | grep '=' | sort | sed -e 's/REACT_APP_\([a-zA-Z0-9_]*\)=\(.*\)/sub_filter\ \"NGINX_REPLACE_\1\" \"$\{\1\}\";/')

cat nginx.conf.sample | sed -e "s|LOCATION_SUB_FILTER|$(echo $NGINX_SUB_FILTER)|" | sed 's|}";\ |}";\n\t|g' > default.template

# Trim off the REACT_APP prefix from environment variables
# cat .env.production | grep = | sort | sed -e 's|REACT_APP_\([a-zA-Z0-9_]*\)=\(.*\)|\1=\2|' > .env.production.temp
# mv .env.production.temp .env.production

envsubst < default.template > default.conf

rm default.template

nginx -g "daemon off;"