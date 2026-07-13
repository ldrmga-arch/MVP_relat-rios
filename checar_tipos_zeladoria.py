"""
Verifica todos os valores de 'Seleção de lista' na fase Concluído da Zeladoria.
Execute: python checar_tipos_zeladoria.py
"""
import json, urllib.request, urllib.parse
from collections import Counter

CLIENT_ID     = "gmntttOuval2d0etI6bB0Qq5dbdB-VYXjZcQygyNF4w"
CLIENT_SECRET = "XJPw0LVWIuouVXFBn6KmE9CCC0C8ooXMz1GgVPLJO-0"
TOKEN_URL     = "https://app.pipefy.com/oauth/token"
GRAPHQL_URL   = "https://api.pipefy.com/graphql"
FASE_ZEL_OK   = "329593953"

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
query($pid: ID!, $n: Int!, $after: String) {
  phase(id: $pid) {
    cards(first: $n, after: $after) {
      pageInfo { hasNextPage endCursor }
      edges { node { fields { name value } } }
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

tipos = Counter()
after = None
while True:
    d = gql({"pid": FASE_ZEL_OK, "n": 50, "after": after})
    page = d["phase"]["cards"]
    for e in page["edges"]:
        for f in e["node"]["fields"]:
            if f["name"] == "Seleção de lista" and f.get("value"):
                tipos[f["value"]] += 1
    if not page["pageInfo"]["hasNextPage"]:
        break
    after = page["pageInfo"]["endCursor"]

print("Tipos de zeladoria (Concluído) — contagem:")
for tipo, count in tipos.most_common():
    print(f"  {count:4}x  '{tipo}'")

print("\n✅ Cole o resultado.")
