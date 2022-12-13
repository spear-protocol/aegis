# Stage 1 - Building react app
FROM node:10 as react-build

WORKDIR /app

# RUN apk add --no-cache git

COPY package.json /app
RUN npm install
COPY . /app
COPY .env.production /app/tempenv.production

# Replace all environment variables which will be set at runtime with placeholders
RUN cat tempenv.production | grep = | sort | sed -e 's|REACT_APP_\([a-zA-Z0-9_]*\)=\(.*\)|REACT_APP_\1=NGINX_REPLACE_\1|' > .env.production

RUN npm run build


# Stage 2 - the production environment
FROM nginx:alpine

# This is a hack around the envsubst nginx config. Because we have `$uri` set up,
# it would replace this as well. Now we just reset it to its original value.
ENV uri \$uri

WORKDIR /etc/nginx/conf.d
COPY nginx.conf.sample .
COPY .env.production .
COPY script.sh .
COPY --from=react-build /app/build /usr/share/nginx/html
EXPOSE 80

# Install envsubst
RUN apk add gettext libintl
CMD ["/bin/sh", "script.sh"] 