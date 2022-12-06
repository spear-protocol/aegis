FROM python:3.6 AS build

# ARG CUSTOM_RPC_TLS_CERT

ENV PYTHONUNBUFFERED 1

# install custom CA certificate for self-signed RPC nodes
# RUN echo "$CUSTOM_RPC_TLS_CERT" > /usr/local/share/ca-certificates/tls_crt.crt
# RUN update-ca-certificates
# ENV REQUESTS_CA_BUNDLE /etc/ssl/certs/ca-certificates.crt

RUN mkdir /code
RUN mkdir /var/log/hub
WORKDIR /code

# install hub dependencies
ADD requirements-serv.txt /code/
RUN pip install --no-cache-dir -r requirements-serv.txt
RUN mkdir /audit_data_cache
ADD just-deploy /just-deploy/
ADD wait_for_it.sh /code/
ADD operator_api /code/
RUN groupadd -r hubber && useradd --no-log-init  -u 1000 -r -g hubber hubber

FROM build AS prod_build
RUN echo yes | python3 /code/manage.py collectstatic
RUN chown -R hubber:hubber  /code
RUN chown -R hubber:hubber /var/log/hub
USER hubber

FROM build AS dev_build
ADD requirements-dev.txt /code/
RUN pip install --no-cache-dir -r requirements-dev.txt
RUN chown hubber:hubber /var/log/hub
RUN chown hubber:hubber /audit_data_cache
RUN echo yes | python3 /code/manage.py collectstatic
RUN chown -R hubber:hubber  /code
USER hubber

FROM build AS test_build
ADD requirements-dev.txt /code/
RUN pip install --no-cache-dir -r requirements-dev.txt
RUN curl --silent --location https://deb.nodesource.com/setup_10.x | bash -
RUN apt-get update && apt-get install --yes nodejs build-essential git
RUN npm install -g --unsafe-perm ganache-cli
RUN chown hubber:hubber /var/log/hub
RUN chown hubber:hubber /audit_data_cache
RUN chown -R hubber:hubber  /code
USER hubber



