#!/usr/bin/env python3
"""
Cotistas API — MDN Porto Rico
GET /cotistas/api/list  →  JSON com todos os cotistas do DB Pipefy
"""
import json, os
import urllib.request, urllib.parse
from flask import Flask, jsonify, request
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID     = os.environ.get("PIPEFY_CLIENT_ID", "") or os.environ.get("CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("PIPEFY_CLIENT_SECRET", "") or os.environ.get("CLIENT_SECRET", "")
TOKEN_URL     = "https://app.pipefy.com/oauth/token"
GRAPHQL_URL   = "https://api.pipefy.com/graphql"
DB_COTISTAS   = "304903871"

COTISTAS_IGNORAR = {
    "Rafael França", "Marcel Sanches",
    "Gustavo Pagani", "Maria Wilma Wohlers da Silva",
}
COTISTAS_ALIAS = {
    "CARINA MUZULAN": "Carina / Clovis Muzulan",
    "Clovis Muzulan": "Carina / Clovis Muzulan",
}

_Q_DB = """
query($tid: ID!, $n: Int!, $after: String) {
  table_records(table_id: $tid, first: $n, after: $after) {
    pageInfo { hasNextPage endCursor }
    edges { node { title record_fields { name value array_value } } }
  }
}"""

app = Flask(__name__)


def _get_token():
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["access_token"]


def _gql(token, query, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(GRAPHQL_URL, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def _fetch_db(token, table_id):
    records, after = [], None
    while True:
        d = _gql(token, _Q_DB, {"tid": table_id, "n": 50, "after": after})
        page = d["data"]["table_records"]
        for e in page["edges"]:
            records.append(e["node"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    return records


def _cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


@app.route("/cotistas/api/list")
def list_cotistas():
    try:
        token = _get_token()
        records = _fetch_db(token, DB_COTISTAS)

        result = []
        for rec in records:
            nome_raw = (rec.get("title") or "").strip()
            if not nome_raw or nome_raw in COTISTAS_IGNORAR:
                continue
            nome = COTISTAS_ALIAS.get(nome_raw, nome_raw)
            fmap = {f["name"]: f for f in rec.get("record_fields", [])}

            f_im = fmap.get("Imóvel")
            imovel = ""
            if f_im:
                v = (f_im.get("value") or "").strip()
                try:
                    lst = json.loads(v)
                    imovel = lst[0] if lst else ""
                except Exception:
                    imovel = v

            f_cota = fmap.get("Cota")
            cota = ((f_cota.get("value") or "").strip() if f_cota else "").upper()

            result.append({"nome": nome, "imovel": imovel, "cota": cota})

        result.sort(key=lambda x: (x["imovel"], x["cota"], x["nome"]))
        return _cors(jsonify({"ok": True, "cotistas": result, "total": len(result)}))
    except Exception as e:
        return _cors(jsonify({"ok": False, "error": str(e)})), 500


@app.route("/cotistas/api/list", methods=["OPTIONS"])
def cotistas_options():
    return _cors(jsonify({}))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5002))
    app.run(host="0.0.0.0", port=port, debug=False)
