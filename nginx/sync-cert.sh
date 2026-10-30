#!/bin/sh
set -eu
[ "${TLS_MODE:-selfsigned}" = letsencrypt ] || exit 0
DOMAIN=$(printf '%s' "$DOMAIN" | tr '[:upper:]' '[:lower:]')
source_dir="/etc/letsencrypt/live/$DOMAIN"
[ -s "$source_dir/fullchain.pem" ] && [ -s "$source_dir/privkey.pem" ] || exit 0
# Certbot replaces symlinks. Copy into nginx's private volume, no Docker socket.
if cmp -s "$source_dir/fullchain.pem" /tls/live.pem && cmp -s "$source_dir/privkey.pem" /tls/live.key; then exit 0; fi
# An expired ACME file must not prevent nginx's bootstrap and certbot renewal.
openssl x509 -in "$source_dir/fullchain.pem" -noout -checkend 0 >/dev/null 2>&1 || exit 0
cp "$source_dir/fullchain.pem" /tls/live.pem.new
cp "$source_dir/privkey.pem" /tls/live.key.new
chmod 600 /tls/live.key.new
mv /tls/live.pem.new /tls/live.pem
mv /tls/live.key.new /tls/live.key
# watcher detects this marker even if content changes only in the private key.
printf '%s' "$DOMAIN" > /tls/live.domain
touch /tls/changed
