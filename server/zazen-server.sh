#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
umask 077
if [[ ! -x .venv/bin/python ]]; then echo 'Najprej: bash setup-ubuntu.sh'; exit 1; fi
read -r -p 'Demo brez AI klicev? [d/N]: ' simulide_demo
if [[ "$simulide_demo" == [dD] ]]; then
  export SIMULIDE_DEMO=1
else
  unset SIMULIDE_DEMO
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    read -r -s -p 'OpenAI API ključ (ostane samo v pomnilniku): ' OPENAI_API_KEY; echo
    export OPENAI_API_KEY
  fi
fi
if [[ "${SIMULIDE_DEMO:-0}" != 1 ]]; then
  if .venv/bin/python -c "import vector_rag; raise SystemExit(0 if vector_rag.overview()['state']=='ready' else 3)"; then
    :
  else
    read -r -p 'Pripravim dokumentacijo v tvojem OpenAI računu? [D/n]: ' simulide_rag
    if [[ "$simulide_rag" != [nN] ]]; then
      .venv/bin/python setup_vector_rag.py || echo 'Vektorsko iskanje ni pripravljeno; uporabljeni bodo lokalni viri.'
    fi
  fi
fi
exec .venv/bin/python app.py serve --host "${SIMULIDE_BIND:-127.0.0.1}"
