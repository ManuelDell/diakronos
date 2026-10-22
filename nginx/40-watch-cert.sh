#!/bin/sh
set -eu
[ "${TLS_MODE:-selfsigned}" = letsencrypt ] || exit 0
(
  while sleep 30; do
    if /usr/local/bin/sync-cert && [ -f /tls/changed ]; then
      # Switch away from the bootstrap certificate after the first issuance.
      sed -i 's|/tls/bootstrap.pem|/tls/live.pem|;s|/tls/bootstrap.key|/tls/live.key|' /etc/nginx/conf.d/default.conf
      if ! grep -q Strict-Transport-Security /etc/nginx/conf.d/default.conf; then
        sed -i '/ssl_session_tickets off;/a\    add_header Strict-Transport-Security "max-age=31536000" always;' /etc/nginx/conf.d/default.conf
      fi
      if nginx -t && nginx -s reload; then rm -f /tls/changed; fi
    fi
  done
) &
