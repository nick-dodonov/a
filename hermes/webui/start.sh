#!/usr/bin/env bash
# https://github.com/nesquena/hermes-webui
# https://get-hermes.ai/
set -eux
docker pull ghcr.io/nesquena/hermes-webui:latest
docker run -d \
  -e WANTED_UID=$(id -u) -e WANTED_GID=$(id -g) \
  -v ~/.hermes:/home/hermeswebui/.hermes \
  -v ~/workspace:/workspace \
  -p 8787:8787 ghcr.io/nesquena/hermes-webui:latest
