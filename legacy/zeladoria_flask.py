#!/usr/bin/env python3
"""
Zeladoria API — MDN Porto Rico
GET /zeladoria/api/cards?ini=2026-05-27&fim=2026-06-26
Retorna cards da fase Concluído filtrados pelo período.
"""
import json, os, re
from datetime import date
import urllib.request, urllib.parse
from flask import Flask, jsonify, request
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID     = os.environ.get("PIPEFY_CLIENT_ID", "") or os.environ.get("CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("PIPEFY_CLIENT_SECRET", "") or os.environ.get("CLIENT_SECRET", "")
TOKEN_URL     = "https://app.pipefy.com/oauth/token"
GRAPHQL_URL   = "https://api.pipefy.com/graphql"

FASE_ZEL_OK = "329593953"  # Zeladoria — Concluído

_Q_PHASE = """
query($pid: ID!, $n: Int!, $after: String, $from: String, $to: String) {
  phase(id: $pid) {
    cards(first: $n, after: $after, filter: {created_at: {from: $from, to: $to}}) {
      pageInfo { hasNextPage endCursor }
      edges { node { id title created_at fields { name value } } }
    }
  }
}"""

_Q_PHASE_NOFILTER = """
query($pid: ID!, $n: Int!, $after: String) {
  phase(id: $pid) {
    cards(first: $n, after: $after) {
      pageInfo { hasNextPage endCursor }
      edges { node { id title created_at fields { name value } } }
    }
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
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def _fetch_phase(token, phase_id, date_from, date_to):
    cards, after = [], None
    use_filter = bool(date_from and date_to)
    while True:
        try:
            if use_filter:
                d = _gql(token, _Q_PHASE, {
                    "pid": phase_id, "n": 50, "after": after,
                    "from": date_from, "to": date_to,
                })
            else:
                d = _gql(token, _Q_PHASE_NOFILTER, {"pid": phase_id, "n": 50, "after": after})
        except Exception:
            if use_filter:
                use_filter, after, cards = False, None, []
                continue
            raise
        page = d["data"]["phase"]["cards"]
        for e in page["edges"]:
            cards.append(e["node"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    return cards


def _parse_json_array(val):
    if not val:
        return ""
    try:
        lst = json.loads(val)
        return lst[0] if lst else ""
    except Exception:
        return str(val).strip('[]"\'')


def _parse_float(val):
    if not val:
        return 0.0
    nums = re.findall(r'\d+(?:[.,]\d+)?', str(val).replace(",", "."))
    return float(nums[-1].replace(",", ".")) if nums else 0.0


def _cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


@app.route("/zeladoria/api/cards")
def cards():
    ini = request.args.get("ini", "")
    fim = request.args.get("fim", "")
    if not ini or not fim:
        return _cors(jsonify({"ok": False, "error": "Parâmetros ini e fim são obrigatórios"})), 400

    try:
        ini_d = date.fromisoformat(ini)
        fim_d = date.fromisoformat(fim)
    except ValueError:
        return _cors(jsonify({"ok": False, "error": "Formato de data inválido. Use AAAA-MM-DD"})), 400

    try:
        token = _get_token()
        raw = _fetch_phase(token, FASE_ZEL_OK, ini, fim)

        result = []
        for card in raw:
            created = (card.get("created_at") or "")[:10]
            try:
                dt = date.fromisoformat(created)
                if not (ini_d <= dt <= fim_d):
                    continue
            except Exception:
                pass

            fields = {f["name"]: (f.get("value") or "") for f in card.get("fields", [])}
            tipo     = fields.get("Seleção de lista", "")
            custeio  = (fields.get("Responsável pela cobrança", "")
                        or fields.get("Cobrança para", ""))

            result.append({
                "id":       card["id"],
                "data":     created,
                "imovel":   _parse_json_array(fields.get("Selecione o imóvel", "")),
                "tipo":     tipo,
                "descricao": fields.get("Descreva a solicitação:", "")[:200],
                "valor":    _parse_float(fields.get("Valor da cobrança", "0")),
                "custeio":  custeio,
                "cotista":  _parse_json_array(fields.get("Selecione o cotista:", "")),
            })

        result.sort(key=lambda x: (x["imovel"], x["data"]))
        return _cors(jsonify({"ok": True, "cards": result, "total": len(result)}))
    except Exception as e:
        return _cors(jsonify({"ok": False, "error": str(e)})), 500


@app.route("/zeladoria/api/cards", methods=["OPTIONS"])
def cards_options():
    return _cors(jsonify({}))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5003))
    app.run(host="0.0.0.0", port=port, debug=False)
