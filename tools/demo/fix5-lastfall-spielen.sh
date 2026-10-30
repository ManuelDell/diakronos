#!/bin/sh
# FIX-5 (Operator-Auflage 2) — Lastfall-Messung im Playwright-Abbild.
#
# Das Abbild mcr.microsoft.com/playwright/python:v1.49.0-noble bringt nur die
# Browser mit; das Python-Paket `playwright` fehlt. Dieses Häkchen installiert
# es (gleiche Version wie die Browser) und startet die Messung.
#
#   docker run --rm --network fix5t905_default \
#       -v "$PWD":/w:ro -v <ziel>:/ausgabe -e BASE=http://app:8000 \
#       mcr.microsoft.com/playwright/python:v1.49.0-noble \
#       sh /w/tools/demo/fix5-lastfall-spielen.sh --marke vorher
set -e
python -m pip install -q "playwright==1.49.0"
exec python /w/tools/demo/fix5-lastfall-messen.py "$@"
