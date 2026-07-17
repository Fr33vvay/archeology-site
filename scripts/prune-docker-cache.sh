#!/usr/bin/env bash
# Чистит кэш сборок Docker. Данные Postgres/media и рабочие образы не трогает.
set -euo pipefail

LOG="${DOCKER_PRUNE_LOG:-/home/freeway/docker-builder-prune.log}"

{
  echo "=== $(date -Is) ==="
  docker builder prune -af
  echo
  docker system df
  echo
  df -h /
  echo
} >>"$LOG" 2>&1
