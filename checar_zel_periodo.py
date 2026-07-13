"""
Lista todos os cards de Zeladoria (Concluído) no período 27/05 a 26/06
mostrando tipo, imóvel, valor e custeio.
Execute: python checar_zel_periodo.py
"""
import json, urllib.request, urllib.parse
from datetime import date
from collections import Counter

CLIENT_ID     = "gmntttOuval2d0etI6bB0Qq5dbdB-VYXjZcQygyNF4w"
CLIENT_SECRET = "XJPw0LVWIuouVXFBn6KmE9CCC0C8ooXMz1GgVPLJO-0"
TOKEN_URL     = "https://app.pipefy.com/oauth/token"
GRAPHQL_URL   = "https://api.pipefy.com/graphql"
FASE_ZEL_OK   = "329593953"

PERIODO_INI = date(2026, 5, 27)
PERIODO_FIM = date(2026, 6, 26)

payload = urllib.parse.urlencode({
    "grant_type": "client_credentials",
    "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
}).encode()
req = urllib.request.Request(TOKEN_URL, data=payload, method="POST")
req.add_header("Content-Type", "application/x-www-form-urlencoded")
with urllib.request.urlopen(req, timeout=30) as r:
    TOKEN = json.loads(r.read())["access_token"]
print("Token OK\n")

# Sem filtro de data (API não suporta nessa fase) — filtramos no Python
Q = """
query($pid: ID!, $n: Int!, $after: String) {
  phase(id: $pid) {
    cards(first: $n, after: $after) {
      pageInfo { hasNextPage endCursor }
      edges { node { id title created_at fields { name value } } }
    }
  }
}"""

def gql(variables):
    body = json.dumps({"query": Q, "variables": variables}).encode()
    req = urllib.request.Request(GRAPHQL_URL, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["data"]

def to_date(s):
    try: return date.fromisoformat(str(s)[:10])
    except: return None

def parse_json_array(val):
    if not val: return ""
    try:
        lst = json.loads(val)
        return lst[0] if lst else ""
    except: return str(val).strip('[]"\'')

# Carrega todos os cards da fase
all_cards, after = [], None
while True:
    d = gql({"pid": FASE_ZEL_OK, "n": 50, "after": after})
    page = d["phase"]["cards"]
    for e in page["edges"]:
        all_cards.append(e["node"])
    if not page["pageInfo"]["hasNextPage"]: break
    after = page["pageInfo"]["endCursor"]

# Filtra pelo período
cards = [c for c in all_cards
         if PERIODO_INI <= (to_date(c["created_at"]) or date.min) <= PERIODO_FIM]

print(f"Total carregado: {len(all_cards)} | No período ({PERIODO_INI} a {PERIODO_FIM}): {len(cards)}\n")
print(f"{'Data':<12} {'Tipo':<25} {'Imóvel':<22} {'Custeio':<25} {'Valor'}")
print("-" * 110)

tipos = Counter()
for card in cards:
    flds = {f["name"]: (f.get("value") or "") for f in card.get("fields", [])}
    dt      = card["created_at"][:10]
    tipo    = flds.get("Seleção de lista", "")
    imovel  = parse_json_array(flds.get("Selecione o imóvel", ""))
    custeio = flds.get("Responsável pela cobrança", "") or flds.get("Cobrança para", "")
    valor   = flds.get("Valor da cobrança", "0")
    tipos[tipo] += 1
    print(f"{dt:<12} {tipo:<25} {imovel:<22} {custeio:<25} {valor}")

print("\n── Resumo por tipo ─────────────────────")
for t, c in tipos.most_common():
    print(f"  {c:3}x  '{t}'")

print("\n✅ Pronto.")
