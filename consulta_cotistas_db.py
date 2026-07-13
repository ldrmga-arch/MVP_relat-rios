"""
Consulta rápida — PR-Cotistas database
Traz: Nome do cotista, Imóvel, Cota (somente PR RR)
Execute: python consulta_cotistas_db.py
"""
import json, urllib.request, urllib.parse

CLIENT_ID     = "gmntttOuval2d0etI6bB0Qq5dbdB-VYXjZcQygyNF4w"
CLIENT_SECRET = "XJPw0LVWIuouVXFBn6KmE9CCC0C8ooXMz1GgVPLJO-0"
TOKEN_URL     = "https://app.pipefy.com/oauth/token"
GRAPHQL_URL   = "https://api.pipefy.com/graphql"
DB_COTISTAS   = "304903871"

payload = urllib.parse.urlencode({
    "grant_type": "client_credentials",
    "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
}).encode()
req = urllib.request.Request(TOKEN_URL, data=payload, method="POST")
req.add_header("Content-Type", "application/x-www-form-urlencoded")
with urllib.request.urlopen(req, timeout=30) as r:
    TOKEN = json.loads(r.read())["access_token"]
print("Token OK\n")

Q = """
query($tid: ID!, $after: String) {
  table_records(table_id: $tid, first: 50, after: $after) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        title
        record_fields { name value }
      }
    }
  }
}"""

def gql(variables):
    body = json.dumps({"query": Q, "variables": variables}).encode()
    req = urllib.request.Request(GRAPHQL_URL, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read())
    if "errors" in resp or "data" not in resp:
        print("RESPOSTA BRUTA:", json.dumps(resp, indent=2, ensure_ascii=False))
        raise SystemExit("Erro na query — veja resposta acima")
    return resp

# Paginar e coletar todos os registros
all_records = []
after = None
while True:
    data = gql({"tid": DB_COTISTAS, "after": after})
    page = data["data"]["table_records"]
    for edge in page["edges"]:
        node = edge["node"]
        fields = {f["name"]: (f["value"] or "") for f in node["record_fields"]}
        all_records.append({"title": node["title"], "fields": fields})
    if not page["pageInfo"]["hasNextPage"]:
        break
    after = page["pageInfo"]["endCursor"]

print(f"Total de registros: {len(all_records)}\n")

# Primeiro: mostrar TODOS os nomes de campos (do primeiro registro)
if all_records:
    print("── Campos disponíveis no banco:")
    for k in all_records[0]["fields"]:
        print(f"  '{k}'")
    print()

# Depois: filtrar PR RR e exibir
print("── Cotistas com imóvel PR RR ──────────────────────────────")
print(f"{'Nome (title)':<35} {'Imóvel':<25} {'Cota'}")
print("-" * 80)

for rec in all_records:
    f = rec["fields"]
    # Tentar vários nomes possíveis para imóvel e cota
    imovel = (f.get("Imóvel") or f.get("Imovel") or f.get("imóvel") or
              f.get("PR-Imóveis") or f.get("Imóveis") or "")
    cota   = (f.get("Cota") or f.get("cota") or f.get("Porcentagem") or
              f.get("Percentual") or f.get("Quota") or "")

    # Normaliza JSON array se vier como ["valor"]
    def parse_arr(v):
        v = str(v).strip()
        if v.startswith("["):
            try:
                lst = json.loads(v)
                return lst[0] if lst else ""
            except Exception:
                pass
        return v

    imovel = parse_arr(imovel)
    cota   = parse_arr(cota)

    if "PR RR" in imovel or "PR RR" in rec["title"]:
        print(f"{rec['title']:<35} {imovel:<25} {cota}")

print("\n✅ Cole o resultado aqui.")
