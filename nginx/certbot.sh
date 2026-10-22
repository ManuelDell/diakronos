#!/bin/sh
set -eu
# Idle sidecar remains running/healthy in the other modes; never contacts ACME.
[ "${TLS_MODE:-selfsigned}" = letsencrypt ] || exec sleep infinity
[ -n "${DOMAIN:-}" ] || { echo "letsencrypt requires DOMAIN" >&2; exit 1; }
export DOMAIN=$(printf '%s' "$DOMAIN" | tr '[:upper:]' '[:lower:]')
[ -n "${ACME_EMAIL:-}" ] || { echo "letsencrypt requires ACME_EMAIL" >&2; exit 1; }
case "${ACME_STAGING:-0}" in
  0) server=https://acme-v02.api.letsencrypt.org/directory ;;
  1) server=https://acme-staging-v02.api.letsencrypt.org/directory ;;
  *) echo 'ACME_STAGING must be 0 or 1' >&2; exit 1 ;;
esac
trap 'exit 0' TERM INT
# certonly is idempotent; renew and initial failures retry without restart storms.
while :; do
  if [ ! -s "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    certbot certonly --non-interactive --agree-tos --email "$ACME_EMAIL" \
      --webroot -w /var/www/acme --domain "$DOMAIN" --cert-name "$DOMAIN" --server "$server" || true
  else
    certbot renew --non-interactive --webroot -w /var/www/acme --server "$server" || true
  fi
  sleep 43200 & wait $!
done
