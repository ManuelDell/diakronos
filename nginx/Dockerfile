FROM nginx:1.28-alpine
RUN apk add --no-cache openssl
COPY default.conf.template /etc/nginx/templates/default.conf.template
COPY 19-tls.envsh /docker-entrypoint.d/19-tls.envsh
COPY 40-watch-cert.sh /docker-entrypoint.d/40-watch-cert.sh
COPY sync-cert.sh /usr/local/bin/sync-cert
RUN chmod 755 /docker-entrypoint.d/19-tls.envsh /docker-entrypoint.d/40-watch-cert.sh /usr/local/bin/sync-cert
