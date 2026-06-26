"""Cache compartilhado (Upstash Redis REST) usado por pipefy.py e omie.py.

Funções serverless não mantêm estado entre requisições, então o progresso de
carregamentos em chunks é persistido aqui. Defina KV_REST_API_URL/KV_REST_API_TOKEN
(integração Vercel Storage -> Upstash) ou UPSTASH_REDIS_REST_URL/UPSTASH_REDIS_REST_TOKEN
(Upstash direto).
"""

import json, os
import requests

REDIS_URL   = os.environ.get("KV_REST_API_URL")   or os.environ.get("UPSTASH_REDIS_REST_URL")
REDIS_TOKEN = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
CHUNK_SECONDS = 8  # margem de segurança sob o timeout de 10s do plano free da Vercel

def redis_get(key):
    if not REDIS_URL:
        return None
    r = requests.get(f"{REDIS_URL}/get/{key}",
                      headers={"Authorization": f"Bearer {REDIS_TOKEN}"}, timeout=10)
    r.raise_for_status()
    val = r.json().get("result")
    return json.loads(val) if val else None

def redis_set(key, value):
    if not REDIS_URL:
        return
    requests.post(f"{REDIS_URL}/set/{key}",
                  headers={"Authorization": f"Bearer {REDIS_TOKEN}"},
                  data=json.dumps(value), timeout=10)
