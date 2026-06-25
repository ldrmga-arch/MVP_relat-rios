#!/usr/bin/env python3
"""
BI Dashboard — MDN Porto Rico
Instale: pip install flask
Execute: python dashboard_app.py
Computador : http://localhost:5000
Celular    : http://SEU_IP:5000  (mesmo Wi-Fi)
"""

import json, threading, time, socket, os
import urllib.request, urllib.parse
from datetime import datetime, timezone
from flask import Flask, jsonify, Response, request

# ─── Configuração ─────────────────────────────────────────────────────────────
CLIENT_ID     = "gmntttOuval2d0etI6bB0Qq5dbdB-VYXjZcQygyNF4w"
CLIENT_SECRET = "XJPw0LVWIuouVXFBn6KmE9CCC0C8ooXMz1GgVPLJO-0"
TOKEN_URL     = "https://app.pipefy.com/oauth/token"
GRAPHQL_URL   = "https://api.pipefy.com/graphql"
REFRESH_MIN   = 30  # atualiza do Pipefy a cada 30 minutos

# ─── Configuração dos pipes ────────────────────────────────────────────────────
PIPES = {
    "porto_rico": {
        "name": "MDN Porto Rico",
        "sla_unit": "days",
        "phases": [
            {"id": "329509953", "name": "Execução",  "done": False},
            {"id": "329510332", "name": "Análise",   "done": False},
            {"id": "329509954", "name": "Terceiros", "done": False},
            {"id": "329510340", "name": "Validação", "done": False},
            {"id": "329510341", "name": "Recusado",  "done": True},
            {"id": "329509955", "name": "Concluído", "done": True},
        ],
        "sla": {
            "329509953": 4,   # Execução
            "329510332": 2,   # Análise
            "329509954": 15,  # Terceiros
            "329510340": 7,   # Validação
        },
        "field_imovel":      ["Imóveis"],
        "field_descricao":   ["Descreva a solicitação", "Descreva o problema:"],
        "field_solicitante": ["Solicitante"],
    },
    "zeladoria": {
        "name": "MDN Zeladoria",
        "sla_unit": "days",
        "phases": [
            {"id": "329593951", "name": "Triagem",        "done": False},
            {"id": "329593952", "name": "Administrativo", "done": False},
            {"id": "333874425", "name": "Ajuste",         "done": False},
            {"id": "329594119", "name": "Validação",      "done": False},
            {"id": "333032463", "name": "Financeiro",     "done": False},
            {"id": "329594132", "name": "Recusados",      "done": True},
            {"id": "329593953", "name": "Concluído",      "done": True},
        ],
        "sla": {
            "329593951": 1,   # Triagem
            "329593952": 2,   # Administrativo
            "333874425": 2,   # Ajuste
            "329594119": 7,   # Validação
            "333032463": 4,   # Financeiro
        },
        "field_imovel":      ["Selecione o imóvel"],
        "field_descricao":   ["Descreva a solicitação:"],
        "field_solicitante": ["Solicitante:"],
    },
    "atendimento": {
        "name": "MDN Atendimento",
        "sla_unit": "hours",   # SLA medido em horas neste pipe
        "phases": [
            {"id": "329640739", "name": "Caixa de entrada",       "done": False},
            {"id": "329640742", "name": "Aguardando atendimento", "done": False},
            {"id": "329640740", "name": "Em andamento",           "done": False},
            {"id": "329640771", "name": "Validação",              "done": False},
            {"id": "329640741", "name": "Concluído",              "done": True},
        ],
        "sla": {
            "329640739": 2,   # Caixa de entrada = 2h
            "329640742": 2,   # Aguardando atendimento = 2h
            "329640740": 96,  # Em andamento = 4 dias = 96h
            "329640771": 48,  # Validação = 2 dias = 48h
        },
        "field_imovel":      ["Imóvel"],
        "field_descricao":   ["Solicitação:", "Descreva o problema:"],
        "field_solicitante": ["Solicitante:"],
    },
    "aruna": {
        "name":     "Aruna Ilhas",
        "sla_unit": "days",
        "phases": [
            {"id": "343138321", "name": "Envio de documentos",    "done": False},
            {"id": "343138322", "name": "Aguardando documentação", "done": False},
            {"id": "343138465", "name": "Análise técnica",         "done": False},
            {"id": "343138466", "name": "Correções / ajustes",    "done": False},
            {"id": "343198842", "name": "Nova analise",            "done": False},
            {"id": "343138840", "name": "Visita 1",               "done": False},
            {"id": "343138841", "name": "Visita 2",               "done": False},
            {"id": "343138842", "name": "Visita 3",               "done": False},
            {"id": "343138323", "name": "Concluído",              "done": True},
        ],
        "sla": {
            "343138321": 10,  # Envio de documentos = 10 dias
            "343138465": 7,   # Análise técnica = 7 dias
            "343198842": 7,   # Nova analise = 7 dias úteis (≈7 corridos)
            # Aguardando documentação, Correções/ajustes e Visitas = sem prazo
        },
        "field_imovel":      ["Selecionar o lote:"],
        "field_descricao":   ["Observações:"],
        "field_solicitante": ["Selecionar o cliente:"],
    },
    "aruna_compras": {
        "name":     "Aruna Ilhas — Compras",
        "sla_unit": "days",
        "phases": [
            {"id": "343155532", "name": "Pendentes",    "done": False},
            {"id": "343155535", "name": "Orçamento",    "done": False},
            {"id": "343155533", "name": "Aprovação",    "done": False},
            {"id": "343155604", "name": "Compras",      "done": False},
            {"id": "343155536", "name": "Financeiro",   "done": False},
            {"id": "343155537", "name": "Recebimento",  "done": False},
            {"id": "343155534", "name": "Concluído",    "done": True},
        ],
        "sla": {
            "343155532": 1,   # Pendentes
            "343155535": 7,   # Orçamento
            "343155533": 2,   # Aprovação
            "343155604": 5,   # Compras
            "343155536": 4,   # Financeiro
            # Recebimento = sem prazo
        },
        "field_imovel":      [],           # sem campo de imóvel — usa título do card
        "field_descricao":   ["Lista de compras:", "Observação:"],
        "field_solicitante": ["Solicitante:"],
    },
    "aruna_manutencao": {
        "name":     "Aruna Ilhas — Manutenção",
        "sla_unit": "days",
        "phases": [
            {"id": "340686671", "name": "Pendentes",  "done": False},
            {"id": "340686674", "name": "Análise",    "done": False},
            {"id": "340686672", "name": "Terceiros",  "done": False},
            {"id": "340686675", "name": "Validação",  "done": False},
            {"id": "340686676", "name": "Recusado",   "done": True},
            {"id": "340686673", "name": "Concluído",  "done": True},
        ],
        "sla": {
            "340686671": 4,   # Pendentes
            "340686674": 7,   # Análise
            "340686672": 15,  # Terceiros
            "340686675": 1,   # Validação
        },
        "field_imovel":      ["Imóveis", "Selecione o imóvel", "Imóvel"],
        "field_descricao":   ["Descreva a solicitação", "Descreva o problema:", "Observações:"],
        "field_solicitante": ["Solicitante", "Solicitante:"],
    },
    "aruna_ocorrencias": {
        "name":     "Aruna Ilhas — Ocorrências",
        "sla_unit": "days",
        "phases": [
            {"id": "342734207", "name": "Caixa de entrada",       "done": False},
            {"id": "342734210", "name": "Aguardando atendimento", "done": False},
            {"id": "342734208", "name": "Em andamento",           "done": False},
            {"id": "342734211", "name": "Validação",              "done": False},
            {"id": "342734209", "name": "Concluído",              "done": True},
        ],
        "sla": {
            "342734207": 1,   # Caixa de entrada
            "342734210": 1,   # Aguardando atendimento
            "342734208": 4,   # Em andamento
            "342734211": 1,   # Validação
        },
        "field_imovel":      [],           # sem campo de imóvel — usa título do card
        "field_descricao":   ["Solicitação:", "Observação:"],
        "field_solicitante": ["Solicitante:"],
    },
}

# ─── Estado global por pipe ────────────────────────────────────────────────────
def empty_state():
    return {"cards": [], "loading": False, "progress": 0, "last_updated": None, "error": None}

states = {k: empty_state() for k in PIPES}

# ─── API Pipefy ────────────────────────────────────────────────────────────────
QUERY = """
query($phaseId: ID!, $after: String) {
  phase(id: $phaseId) {
    cards(first: 50, after: $after) {
      pageInfo { hasNextPage endCursor }
      edges {
        node {
          id
          title
          created_at
          updated_at
          started_current_phase_at
          due_date
          late
          current_phase { id name }
          assignees { name }
          fields { name value }
          phases_history { phase { id name } duration }
        }
      }
    }
  }
}
"""

def get_token():
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["access_token"]

def gql(token, query, variables=None, retries=3):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(GRAPHQL_URL, data=body, method="POST")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            last_err = e
            wait = attempt * 3
            print(f"[WARN] tentativa {attempt}/{retries} falhou ({e}), aguardando {wait}s...")
            time.sleep(wait)
    raise last_err

def _get_field(fields, field_names):
    """Tenta múltiplos nomes de campo, retorna o primeiro encontrado."""
    for fn in field_names:
        v = fields.get(fn) or ""
        if v:
            return v
    return ""

def _parse_imovel(raw):
    if raw.startswith("["):
        try:
            lst = json.loads(raw)
            return ", ".join(lst) if lst else "—"
        except Exception:
            return raw
    return raw or "—"

def load_cards(pipe_key):
    cfg   = PIPES[pipe_key]
    state = states[pipe_key]
    state.update({"loading": True, "progress": 0, "error": None})
    try:
        token = get_token()
        cards = []

        for phase in cfg["phases"]:
            cursor = None
            while True:
                r  = gql(token, QUERY, {"phaseId": phase["id"], "after": cursor})
                pg = r["data"]["phase"]["cards"]

                for e in pg["edges"]:
                    c      = e["node"]
                    fields = {f["name"]: (f.get("value") or "").strip()
                              for f in c.get("fields", [])}

                    created = (c.get("created_at") or "")[:10]
                    updated = (c.get("updated_at")  or "")[:10]
                    due_raw = c.get("due_date") or ""
                    due     = due_raw[:10] if due_raw else ""

                    # Tempo preciso na fase
                    phase_ref = (c.get("started_current_phase_at") or
                                 c.get("updated_at") or "")
                    try:
                        phase_dt = datetime.fromisoformat(
                            phase_ref.replace("Z", "+00:00"))
                        delta          = datetime.now(timezone.utc) - phase_dt
                        days_in_phase  = delta.days
                        hours_in_phase = int(delta.total_seconds() / 3600)
                    except Exception:
                        days_in_phase = hours_in_phase = 0

                    # SLA e status
                    sla_val  = cfg["sla"].get(phase["id"])
                    sla_unit = cfg.get("sla_unit", "days")
                    time_cmp = hours_in_phase if sla_unit == "hours" else days_in_phase

                    if phase["done"]:
                        status       = "recusado" if phase["name"].lower().startswith("recus") else "concluido"
                        time_display = "—"
                        sla_display  = "—"
                        sla_pct      = 0
                    else:
                        if sla_val:
                            status      = "atrasado" if time_cmp > sla_val else "no_prazo"
                            sla_pct     = round(time_cmp / sla_val * 100)
                            # Display: mostra horas quando SLA da fase < 24h
                            if sla_unit == "hours" and sla_val < 24:
                                time_display = f"{hours_in_phase}h"
                                sla_display  = f"{sla_val}h"
                            else:
                                time_display = f"{days_in_phase}d"
                                sla_display  = f"{sla_val // 24 if sla_unit == 'hours' else sla_val}d"
                        else:
                            status       = "sem_prazo"
                            sla_pct      = 0
                            time_display = f"{days_in_phase}d"
                            sla_display  = "—"

                    # ── Status histórico (pior fase da vida do card) ──────────
                    # Usa phases_history para incluir fases já concluídas
                    hist_status = "sem_prazo"
                    for ph_hist in (c.get("phases_history") or []):
                        ph_id      = (ph_hist.get("phase") or {}).get("id", "")
                        dur_secs   = ph_hist.get("duration") or 0
                        hist_sla   = cfg["sla"].get(ph_id)
                        if not hist_sla:
                            continue
                        time_hist = dur_secs / 3600 if sla_unit == "hours" else dur_secs / 86400
                        if time_hist > hist_sla:
                            hist_status = "atrasado"
                            break
                        else:
                            if hist_status != "atrasado":
                                hist_status = "no_prazo"
                    # Fase atual (para cards ainda em andamento)
                    if not phase["done"] and status == "atrasado":
                        hist_status = "atrasado"
                    elif not phase["done"] and status == "no_prazo" and hist_status != "atrasado":
                        hist_status = "no_prazo"

                    cards.append({
                        "id":            c["id"],
                        "title":         c.get("title") or "—",
                        "created_at":    created,
                        "created_month": created[:7] if created else "",
                        "updated_at":    updated,
                        "due_date":      due,
                        "phase_name":    phase["name"],
                        "phase_done":    phase["done"],
                        "days_in_phase": days_in_phase,
                        "time_display":  time_display,
                        "sla_display":   sla_display,
                        "sla_pct":       sla_pct,
                        "status":        status,
                        "hist_status":   hist_status,
                        "assignees":     [a["name"] for a in c.get("assignees", [])],
                        "imovel":        _parse_imovel(_get_field(fields, cfg["field_imovel"])) if cfg["field_imovel"] else (c.get("title") or "—"),
                        "descricao":     (_get_field(fields, cfg["field_descricao"]) or "—")[:300],
                        "solicitante":   _get_field(fields, cfg["field_solicitante"]) or "—",
                    })

                state["progress"] = len(cards)
                if not pg["pageInfo"]["hasNextPage"]:
                    break
                cursor = pg["pageInfo"]["endCursor"]
                time.sleep(0.2)

        state["cards"]        = cards
        state["last_updated"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        from collections import Counter
        por_fase    = Counter(c["phase_name"]   for c in cards)
        por_status  = Counter(c["status"]       for c in cards)
        por_hist    = Counter(c["hist_status"]  for c in cards)
        sem_history = sum(1 for c in cards if c["phase_done"] and c["hist_status"] == "sem_prazo")
        print(f"\n[OK] [{cfg['name']}] {len(cards)} cards — {state['last_updated']}")
        print(f"     Por fase:        { dict(por_fase) }")
        print(f"     Por status:      { dict(por_status) }")
        print(f"     Por hist_status: { dict(por_hist) }")
        print(f"     Done s/ history: {sem_history} (phases_history vazio p/ esses)\n")

    except Exception as ex:
        state["error"] = str(ex)
        print(f"[ERRO] [{cfg['name']}] {ex}")
    finally:
        state["loading"] = False

def bg_loop(pipe_key):
    while True:
        load_cards(pipe_key)
        time.sleep(REFRESH_MIN * 60)

# ─── Flask ─────────────────────────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/")
def index():
    resp = Response(HTML, content_type="text/html; charset=utf-8")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"]        = "no-cache"
    return resp

@app.route("/api/data")
def api_data():
    pk = request.args.get("pipe", "porto_rico")
    if pk not in states: pk = "porto_rico"
    return jsonify(states[pk])

@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    pk = request.args.get("pipe", "porto_rico")
    if pk not in states: pk = "porto_rico"
    if not states[pk]["loading"]:
        threading.Thread(target=load_cards, args=(pk,), daemon=True).start()
    return jsonify({"ok": True})

# ─── HTML Dashboard ────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BI — MDN Porto Rico</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
:root{
  --bg:#0f172a;--sf:#1e293b;--sf2:#334155;--tx:#f1f5f9;--mu:#94a3b8;
  --pr:#6366f1;--ok:#10b981;--er:#f43f5e;--wn:#f59e0b;--bl:#3b82f6;--gy:#64748b;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--tx);font-family:system-ui,-apple-system,sans-serif}

/* ── NAV ── */
.nav{
  background:var(--sf);border-bottom:1px solid var(--sf2);
  padding:12px 20px;display:flex;align-items:center;gap:12px;
  flex-wrap:wrap;position:sticky;top:0;z-index:100;
}
.nav-logo{font-size:1.1rem;font-weight:700;color:var(--pr);letter-spacing:-.01em}
.nav-sub{color:var(--mu);font-size:.8rem}
#last-upd{color:var(--mu);font-size:.75rem;margin-left:auto}
.btn-r{
  background:var(--pr);color:#fff;border:none;
  padding:7px 16px;border-radius:8px;font-size:.82rem;
  cursor:pointer;font-weight:600;transition:opacity .2s;
}
.btn-r:hover{opacity:.85}.btn-r:disabled{opacity:.45;cursor:not-allowed}

/* ── LOADING ── */
#lb{height:3px;background:var(--sf2);overflow:hidden;display:none}
#lf{height:100%;background:var(--pr);transition:width .4s;width:0}
#lt{text-align:center;padding:7px;font-size:.78rem;color:var(--mu);background:var(--sf);display:none}

/* ── MAIN ── */
.main{padding:20px;max-width:1600px;margin:0 auto}

/* ── FILTERS ── */
.filters{
  background:var(--sf);border-radius:14px;padding:16px 20px;
  margin-bottom:18px;display:flex;gap:14px;flex-wrap:wrap;align-items:flex-end;
}
.f-lbl{font-size:.68rem;color:var(--mu);margin-bottom:5px;text-transform:uppercase;letter-spacing:.05em;display:block}
.f-sel{
  background:var(--sf2);color:var(--tx);border:1px solid #475569;
  border-radius:8px;padding:8px 12px;font-size:.85rem;min-width:170px;outline:none;
}
.f-sel:focus{border-color:var(--pr)}
.btn-clr{
  background:transparent;color:var(--mu);border:1px solid #475569;
  padding:8px 14px;border-radius:8px;cursor:pointer;font-size:.82rem;
}
.btn-clr:hover{color:var(--tx);border-color:#94a3b8}

/* ── KPIs ── */
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:18px}
@media(max-width:1024px){.kpis{grid-template-columns:repeat(3,1fr)}}
@media(max-width:600px){.kpis{grid-template-columns:1fr 1fr}}

.kpi{background:var(--sf);border-radius:14px;padding:18px 16px;border-left:4px solid var(--gy);transition:transform .15s}
.kpi:hover{transform:translateY(-2px)}
.kpi.t{border-color:var(--bl)}.kpi.a{border-color:var(--pr)}
.kpi.e{border-color:var(--er)}.kpi.p{border-color:var(--ok)}.kpi.c{border-color:var(--gy)}
.k-lbl{font-size:.68rem;color:var(--mu);text-transform:uppercase;letter-spacing:.05em}
.k-val{font-size:2.1rem;font-weight:700;margin:6px 0 4px;line-height:1}
.k-sub{font-size:.7rem;color:var(--mu)}
.kpi.t .k-val{color:var(--bl)}.kpi.a .k-val{color:var(--pr)}
.kpi.e .k-val{color:var(--er)}.kpi.p .k-val{color:var(--ok)}

/* ── CHARTS ── */
.ch-grid{display:grid;grid-template-columns:310px 1fr;gap:14px;margin-bottom:18px}
@media(max-width:768px){.ch-grid{grid-template-columns:1fr}}
.ch-card{background:var(--sf);border-radius:14px;padding:20px}
.ch-ttl{font-size:.68rem;color:var(--mu);text-transform:uppercase;letter-spacing:.05em;margin-bottom:14px;font-weight:600}

/* ── TABLE ── */
.tbl-card{background:var(--sf);border-radius:14px;padding:20px}
.tbl-top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px;flex-wrap:wrap;gap:10px}
.tbl-ttl{font-size:.68rem;color:var(--mu);text-transform:uppercase;letter-spacing:.05em;font-weight:600}
.tbl-cnt{font-size:.75rem;color:var(--mu);margin-top:3px}
.tbl-srch{
  background:var(--sf2);color:var(--tx);border:1px solid #475569;
  border-radius:8px;padding:7px 12px;font-size:.85rem;width:230px;outline:none;
}
.tbl-srch:focus{border-color:var(--pr)}
.tbl-wrap{overflow-x:auto}

table{width:100%;border-collapse:collapse;font-size:.82rem}
thead th{
  background:var(--sf2);color:var(--mu);font-weight:600;
  text-transform:uppercase;font-size:.65rem;letter-spacing:.05em;
  padding:10px 12px;text-align:left;cursor:pointer;white-space:nowrap;
  user-select:none;border-bottom:1px solid #475569;
}
thead th:hover{color:var(--tx)}
td{padding:9px 12px;border-bottom:1px solid rgba(51,65,85,.5);vertical-align:middle}
tr:last-child td{border-bottom:none}
tbody tr:hover td{background:rgba(255,255,255,.025)}

/* ── BADGES ── */
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}
.b-atr{background:rgba(244,63,94,.15);color:#f43f5e}
.b-prz{background:rgba(16,185,129,.15);color:#10b981}
.b-spz{background:rgba(245,158,11,.15);color:#f59e0b}
.b-con{background:rgba(100,116,139,.15);color:#94a3b8}
.b-rec{background:rgba(127,29,29,.2);color:#fca5a5}

/* ── PAGINATION ── */
.pg-bar{display:flex;justify-content:space-between;align-items:center;margin-top:14px;flex-wrap:wrap;gap:8px}
.pg-btn{background:var(--sf2);color:var(--tx);border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:.82rem}
.pg-btn:hover{background:#475569}.pg-btn:disabled{opacity:.35;cursor:not-allowed}
.pg-info{color:var(--mu);font-size:.78rem}

/* ── SORT ── */
th.sa::after{content:" ▲";font-size:.5rem}
th.sd::after{content:" ▼";font-size:.5rem}

/* ── BARRA DE SELEÇÃO (empresa + pipe) ── */
.sel-bar{
  background:var(--sf);border-bottom:1px solid var(--sf2);
  padding:10px 20px;display:flex;align-items:center;gap:20px;flex-wrap:wrap;
}
.sel-section{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.sel-label{font-size:.65rem;color:var(--mu);text-transform:uppercase;letter-spacing:.06em;font-weight:600;white-space:nowrap}
.sel-divider{width:1px;height:28px;background:var(--sf2);flex-shrink:0}

/* Empresa */
.company-tab{background:transparent;color:var(--mu);border:1px solid var(--sf2);padding:5px 16px;border-radius:20px;cursor:pointer;font-size:.82rem;font-weight:500;transition:all .15s;white-space:nowrap}
.company-tab:hover{color:var(--tx);border-color:#64748b}
.company-tab.active{background:#1e3a5f;color:#93c5fd;border-color:#3b82f6;font-weight:600}

/* Pipe */
.pipe-tab{background:var(--sf2);color:var(--mu);border:none;padding:5px 14px;border-radius:8px;cursor:pointer;font-size:.8rem;font-weight:500;transition:all .15s;white-space:nowrap}
.pipe-tab:hover{background:#475569;color:var(--tx)}
.pipe-tab.active{background:var(--pr);color:#fff}

/* ── MULTI-SELECT MÊS ── */
.multi-sel-wrap{position:relative}
.mes-btn{display:flex;align-items:center;justify-content:space-between;gap:8px;min-width:190px;cursor:pointer;text-align:left;width:100%}
.mes-dd{
  position:absolute;z-index:200;top:calc(100% + 4px);left:0;
  background:var(--sf);border:1px solid var(--sf2);border-radius:10px;
  min-width:220px;box-shadow:0 8px 24px rgba(0,0,0,.5);
}
.mes-dd-inner{max-height:260px;overflow-y:auto;padding:8px}
.mes-yr{font-size:.65rem;color:var(--mu);text-transform:uppercase;letter-spacing:.05em;padding:6px 8px 2px;font-weight:600}
.mes-item{display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:6px;cursor:pointer;font-size:.82rem;color:var(--tx)}
.mes-item:hover{background:var(--sf2)}
.mes-item input[type=checkbox]{accent-color:var(--pr);cursor:pointer;width:14px;height:14px;flex-shrink:0}
.mes-dd-foot{display:flex;gap:8px;padding:8px;border-top:1px solid var(--sf2)}
.mes-btn-sm{flex:1;padding:5px;border-radius:6px;border:1px solid var(--sf2);background:transparent;color:var(--mu);cursor:pointer;font-size:.78rem}
.mes-btn-sm:hover{background:var(--sf2);color:var(--tx)}
.mes-btn-ok{background:var(--pr);border-color:var(--pr);color:#fff}
.mes-btn-ok:hover{opacity:.85}
.mes-caret{font-size:.65rem;flex-shrink:0}

/* ── UTILS ── */
.trunc{max-width:270px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.trunc-s{max-width:130px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:var(--sf)}
::-webkit-scrollbar-thumb{background:var(--sf2);border-radius:3px}

/* ── EMPTY STATE ── */
.empty{text-align:center;padding:48px;color:var(--mu)}
.empty .spinner{display:inline-block;width:32px;height:32px;border:3px solid var(--sf2);border-top-color:var(--pr);border-radius:50%;animation:spin .8s linear infinite;margin-bottom:12px}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body>

<nav class="nav">
  <span class="nav-logo">⚙ Dashboard Operacional</span>
  <span class="nav-sub" id="navSub">—</span>
  <span id="last-upd">Aguardando dados...</span>
  <button class="btn-r" id="btnR" onclick="forceRefresh()">↻ Atualizar</button>
</nav>

<!-- BARRA: Empresa → Pipe -->
<div class="sel-bar">
  <div class="sel-section">
    <span class="sel-label">Empresa</span>
    <div id="companyTabs"></div>
  </div>
  <div class="sel-divider"></div>
  <div class="sel-section">
    <span class="sel-label">Relatório</span>
    <div id="pipeTabs"></div>
  </div>
</div>

<div id="lb"><div id="lf"></div></div>
<div id="lt">Carregando dados do Pipefy… <span id="lc">0</span> cards processados</div>

<div class="main">

  <!-- FILTROS -->
  <div class="filters">
    <div class="multi-sel-wrap" id="mesWrap">
      <label class="f-lbl">Período de criação</label>
      <button class="f-sel mes-btn" type="button" onclick="toggleMesDD(event)">
        <span id="mesBtnLbl">Todos os meses</span>
        <span class="mes-caret">▾</span>
      </button>
      <div id="mesDD" class="mes-dd" style="display:none">
        <div class="mes-dd-inner" id="mesDDInner"></div>
        <div class="mes-dd-foot">
          <button class="mes-btn-sm" onclick="clearMes()">Limpar</button>
          <button class="mes-btn-sm mes-btn-ok" onclick="closeMesDD()">OK</button>
        </div>
      </div>
    </div>
    <div>
      <label class="f-lbl">Fase</label>
      <select class="f-sel" id="fFase" onchange="applyFilters()">
        <option value="">Todas as fases</option>
      </select>
    </div>
    <div>
      <label class="f-lbl">Status</label>
      <select class="f-sel" id="fStatus" onchange="applyFilters()">
        <option value="">Todos</option>
        <option value="em_andamento">Em andamento</option>
        <option value="atrasado">Atrasado</option>
        <option value="no_prazo">No prazo</option>
        <option value="sem_prazo">Sem prazo</option>
        <option value="concluido">Concluído</option>
        <option value="recusado">Recusado</option>
      </select>
    </div>
    <button class="btn-clr" onclick="clearF()">✕ Limpar filtros</button>
  </div>

  <!-- KPIs -->
  <div class="kpis">
    <div class="kpi t">
      <div class="k-lbl">Total de cards</div>
      <div class="k-val" id="kT">—</div>
      <div class="k-sub">todos os períodos</div>
    </div>
    <div class="kpi a">
      <div class="k-lbl">Em andamento</div>
      <div class="k-val" id="kA">—</div>
      <div class="k-sub">fases ativas</div>
    </div>
    <div class="kpi e">
      <div class="k-lbl">Atrasados</div>
      <div class="k-val" id="kE">—</div>
      <div class="k-sub" id="kEp">—</div>
    </div>
    <div class="kpi p">
      <div class="k-lbl">No prazo</div>
      <div class="k-val" id="kP">—</div>
      <div class="k-sub" id="kPp">—</div>
    </div>
    <div class="kpi c">
      <div class="k-lbl">Concluídos</div>
      <div class="k-val" id="kC">—</div>
      <div class="k-sub">histórico total</div>
    </div>
  </div>

  <!-- GRÁFICOS -->
  <div class="ch-grid">
    <div class="ch-card">
      <div class="ch-ttl">Distribuição por status</div>
      <div style="position:relative;height:270px">
        <canvas id="cPie"></canvas>
      </div>
    </div>
    <div class="ch-card">
      <div class="ch-ttl">Atrasados × No prazo × Sem prazo — por mês de criação</div>
      <div style="position:relative;height:270px">
        <canvas id="cBar"></canvas>
      </div>
    </div>
  </div>

  <!-- TABELA -->
  <div class="tbl-card">
    <div class="tbl-top">
      <div>
        <div class="tbl-ttl">Painel de cards</div>
        <div class="tbl-cnt" id="tblCnt">—</div>
      </div>
      <input class="tbl-srch" id="tblSrch" placeholder="🔍 Buscar por card, imóvel..." oninput="onSearch()">
    </div>
    <div class="tbl-wrap">
      <table>
        <thead><tr>
          <th onclick="srt('id')">ID</th>
          <th onclick="srt('imovel')">Imóvel</th>
          <th onclick="srt('descricao')">Descrição da solicitação</th>
          <th onclick="srt('phase_name')">Fase atual</th>
          <th onclick="srt('days_in_phase')">Tempo na fase</th>
          <th onclick="srt('status')">Status</th>
          <th onclick="srt('created_at')">Criado em</th>
        </tr></thead>
        <tbody id="tblBody"></tbody>
      </table>
    </div>
    <div class="pg-bar">
      <button class="pg-btn" id="bPrev" onclick="changePage(-1)">← Anterior</button>
      <span class="pg-info" id="pgInfo">—</span>
      <button class="pg-btn" id="bNext" onclick="changePage(1)">Próximo →</button>
    </div>
  </div>

</div>

<script>
// ════════════════════════════════════════════
// CONFIGURAÇÃO: EMPRESAS E PIPES
// ════════════════════════════════════════════
const COMPANIES = {
  mdn_porto_rico: 'MDN Porto Rico',
  aruna_ilhas:    'Aruna Ilhas',
};

const PIPE_CONFIG = {
  porto_rico: {
    label:   'Manutenção',
    name:    'MDN Porto Rico — Manutenção',
    company: 'mdn_porto_rico',
    phases:  ['Execução','Análise','Terceiros','Validação','Recusado','Concluído'],
  },
  zeladoria: {
    label:   'Zeladoria',
    name:    'MDN Porto Rico — Zeladoria',
    company: 'mdn_porto_rico',
    phases:  ['Triagem','Administrativo','Ajuste','Validação','Financeiro','Recusados','Concluído'],
  },
  atendimento: {
    label:   'Atendimento',
    name:    'MDN Porto Rico — Atendimento',
    company: 'mdn_porto_rico',
    phases:  ['Caixa de entrada','Aguardando atendimento','Em andamento','Validação','Concluído'],
  },
  aruna: {
    label:   'Análise de projetos',
    name:    'Aruna Ilhas — Aprovações e Obras',
    company: 'aruna_ilhas',
    phases:  ['Envio de documentos','Aguardando documentação','Análise técnica','Correções / ajustes','Nova analise','Visita 1','Visita 2','Visita 3','Concluído'],
  },
  aruna_compras: {
    label:   'Compras',
    name:    'Aruna Ilhas — Compras',
    company: 'aruna_ilhas',
    phases:  ['Pendentes','Orçamento','Aprovação','Compras','Financeiro','Recebimento','Concluído'],
  },
  aruna_manutencao: {
    label:   'Manutenção',
    name:    'Aruna Ilhas — Manutenção',
    company: 'aruna_ilhas',
    phases:  ['Pendentes','Análise','Terceiros','Validação','Recusado','Concluído'],
  },
  aruna_ocorrencias: {
    label:   'Ocorrências',
    name:    'Aruna Ilhas — Ocorrências',
    company: 'aruna_ilhas',
    phases:  ['Caixa de entrada','Aguardando atendimento','Em andamento','Validação','Concluído'],
  },
};

let currentCompany = 'mdn_porto_rico';
let currentPipe    = 'porto_rico';

// ════════════════════════════════════════════
// ESTADO
// ════════════════════════════════════════════
let allCards=[], filtered=[], display=[], lastSeen=null;
let pieChart=null, barChart=null;
let barMonths = [];   // referência global para evitar closure stale no onClick
let curPage=1, pageSize=50;
let srtCol='created_at', srtDir='desc', srchTerm='';

const SL = {atrasado:'Atrasado',no_prazo:'No prazo',sem_prazo:'Sem prazo',concluido:'Concluído',recusado:'Recusado'};
const SC = {atrasado:'b-atr',no_prazo:'b-prz',sem_prazo:'b-spz',concluido:'b-con',recusado:'b-rec'};

// ════════════════════════════════════════════
// FETCH E POLL
// ════════════════════════════════════════════
function buildCompanyTabs(){
  const ct = document.getElementById('companyTabs');
  ct.innerHTML = '';
  Object.entries(COMPANIES).forEach(([key, name])=>{
    ct.innerHTML += `<button class="company-tab${key===currentCompany?' active':''}" onclick="switchCompany('${key}')">${name}</button>`;
  });
}

function buildPipeTabs(){
  const pt = document.getElementById('pipeTabs');
  pt.innerHTML = '';
  Object.entries(PIPE_CONFIG)
    .filter(([,cfg])=>cfg.company===currentCompany)
    .forEach(([key,cfg])=>{
      pt.innerHTML += `<button class="pipe-tab${key===currentPipe?' active':''}" id="tab-${key}" onclick="switchPipe('${key}')">${cfg.label}</button>`;
    });
}

function buildFaseSel(){
  const sel = document.getElementById('fFase');
  const cur = sel.value;
  sel.innerHTML = '<option value="">Todas as fases</option>';
  PIPE_CONFIG[currentPipe].phases.forEach(p=>{
    sel.innerHTML += `<option${p===cur?' selected':''}>${p}</option>`;
  });
}

function _resetPipeState(){
  allCards=[]; filtered=[]; display=[]; lastSeen=null;
  selectedMonths.clear(); updateMesBtn();
  if(pieChart){ pieChart.destroy(); pieChart=null; }
  if(barChart){ barChart.destroy(); barChart=null; }
  buildFaseSel();
  ['fFase','fStatus'].forEach(id=>document.getElementById(id).value='');
  srchTerm=''; document.getElementById('tblSrch').value='';
  document.getElementById('last-upd').textContent='Carregando…';
  document.getElementById('lb').style.display='block';
  document.getElementById('lt').style.display='block';
  renderKPIs(); renderTable();
}

function switchCompany(key){
  if(key === currentCompany) return;
  currentCompany = key;
  buildCompanyTabs();
  // Seleciona o primeiro pipe desta empresa
  const first = Object.entries(PIPE_CONFIG).find(([,c])=>c.company===key);
  if(first){ currentPipe = first[0]; }
  buildPipeTabs();
  _resetPipeState();
  fetchData();
}

function switchPipe(key){
  if(key === currentPipe) return;
  currentPipe = key;
  buildPipeTabs();
  document.getElementById('navSub').textContent = PIPE_CONFIG[key].name;
  _resetPipeState();
  fetchData();
}

async function fetchData(){
  try{
    const d = await(await fetch(`/api/data?pipe=${currentPipe}`)).json();
    const loading = d.loading;

    document.getElementById('lb').style.display  = loading ? 'block' : 'none';
    document.getElementById('lt').style.display  = loading ? 'block' : 'none';
    document.getElementById('btnR').disabled      = loading;

    if(loading){
      document.getElementById('lc').textContent = d.progress.toLocaleString('pt-BR');
      document.getElementById('lf').style.width = Math.min(d.progress/2500*100, 95)+'%';
    }

    if(d.error && !d.loading){
      document.getElementById('last-upd').textContent = '⚠ Erro: '+d.error.slice(0,60);
    } else if(d.last_updated){
      document.getElementById('last-upd').textContent = 'Atualizado: '+d.last_updated;
    } else if(d.loading){
      document.getElementById('last-upd').textContent = 'Carregando…';
    }

    if(!d.loading && d.cards && d.cards.length > 0 && d.last_updated !== lastSeen){
      lastSeen = d.last_updated;
      allCards = d.cards;
      try{ buildMonthSel(); }catch(err){ console.error('buildMonthSel:', err); }
      applyFilters();
    }
  }catch(e){ console.error('fetchData:', e); }
}

async function forceRefresh(){
  await fetch(`/api/refresh?pipe=${currentPipe}`,{method:'POST'});
  document.getElementById('btnR').disabled = true;
}

function poll(){ fetchData(); setTimeout(poll, 15000); }

// ════════════════════════════════════════════
// FILTROS — PERÍODO (multi-select)
// ════════════════════════════════════════════
let selectedMonths = new Set();

function buildMonthSel(){
  const months = [...new Set(allCards.map(c=>c.created_month).filter(Boolean))].sort().reverse();
  const inner = document.getElementById('mesDDInner');
  if(!inner) return;

  // Agrupar por ano
  const byYear = {};
  months.forEach(m=>{ const [y]=m.split('-'); if(!byYear[y])byYear[y]=[]; byYear[y].push(m); });

  inner.innerHTML = '';
  Object.keys(byYear).sort().reverse().forEach(yr=>{
    inner.innerHTML += `<div class="mes-yr">${yr}</div>`;
    byYear[yr].forEach(m=>{
      const [y,mo] = m.split('-');
      const lbl = new Date(y,mo-1).toLocaleDateString('pt-BR',{month:'long'});
      const checked = selectedMonths.has(m) ? 'checked' : '';
      inner.innerHTML += `<label class="mes-item"><input type="checkbox" value="${m}" ${checked} onchange="onMesChange(this)">${lbl.charAt(0).toUpperCase()+lbl.slice(1)}</label>`;
    });
  });
  updateMesBtn();
}

function onMesChange(el){
  if(el.checked) selectedMonths.add(el.value);
  else selectedMonths.delete(el.value);
  updateMesBtn();
  applyFilters();
}

function updateMesBtn(){
  const lbl = document.getElementById('mesBtnLbl');
  if(!lbl) return;
  if(selectedMonths.size === 0){
    lbl.textContent = 'Todos os meses';
  } else if(selectedMonths.size === 1){
    const [m] = selectedMonths;
    const [y,mo] = m.split('-');
    const l = new Date(y,mo-1).toLocaleDateString('pt-BR',{month:'long',year:'numeric'});
    lbl.textContent = l.charAt(0).toUpperCase()+l.slice(1);
  } else {
    lbl.textContent = `${selectedMonths.size} meses selecionados`;
  }
}

function toggleMesDD(e){
  e.stopPropagation();
  const dd = document.getElementById('mesDD');
  dd.style.display = dd.style.display==='none' ? 'block' : 'none';
}

function closeMesDD(){ document.getElementById('mesDD').style.display='none'; }

function clearMes(){
  selectedMonths.clear();
  document.querySelectorAll('#mesDDInner input').forEach(el=>el.checked=false);
  updateMesBtn();
  applyFilters();
}

document.addEventListener('click', e=>{
  const wrap = document.getElementById('mesWrap');
  if(wrap && !wrap.contains(e.target)) closeMesDD();
});

function applyFilters(){
  const fase   = document.getElementById('fFase').value;
  const status = document.getElementById('fStatus').value;

  filtered = allCards.filter(c=>{
    if(selectedMonths.size > 0 && !selectedMonths.has(c.created_month)) return false;
    if(fase && c.phase_name !== fase) return false;
    if(status === 'em_andamento'){
      // Cards ainda em processamento (não concluídos nem recusados)
      if(c.status === 'concluido' || c.status === 'recusado') return false;
    } else if(status === 'atrasado' || status === 'no_prazo' || status === 'sem_prazo'){
      // Filtro histórico: usa hist_status para incluir cards já concluídos
      if((c.hist_status||c.status) !== status) return false;
    } else if(status){
      // concluido / recusado: usa status atual
      if(c.status !== status) return false;
    }
    return true;
  });

  applySearch();
  renderKPIs();
  renderPie();
  renderBar();
}

function applySearch(){
  const t = srchTerm.toLowerCase();
  display = t
    ? filtered.filter(c =>
        (c.id       ||'').toLowerCase().includes(t) ||
        (c.imovel   ||'').toLowerCase().includes(t) ||
        (c.descricao||'').toLowerCase().includes(t) ||
        (c.phase_name||'').toLowerCase().includes(t)||
        (c.title    ||'').toLowerCase().includes(t) ||
        (c.solicitante||'').toLowerCase().includes(t))
    : filtered.slice();
  curPage = 1;
  doSort();
  renderTable();
}

function onSearch(){ srchTerm = document.getElementById('tblSrch').value; applySearch(); }

function clearF(){
  clearMes();
  ['fFase','fStatus'].forEach(id => document.getElementById(id).value='');
  srchTerm=''; document.getElementById('tblSrch').value='';
  applyFilters();
}

// ════════════════════════════════════════════
// KPIs
// ════════════════════════════════════════════
function renderKPIs(){
  const tot = filtered.length;
  const and = filtered.filter(c=>!c.phase_done).length;
  // hist_status: pior status que o card teve em qualquer fase (inclui concluídos)
  const atr = filtered.filter(c=>(c.hist_status||c.status)==='atrasado').length;
  const prz = filtered.filter(c=>(c.hist_status||c.status)==='no_prazo').length;
  const con = filtered.filter(c=>c.status==='concluido').length;
  const wp  = atr + prz;

  document.getElementById('kT').textContent = tot.toLocaleString('pt-BR');
  document.getElementById('kA').textContent = and.toLocaleString('pt-BR');
  document.getElementById('kE').textContent = atr.toLocaleString('pt-BR');
  document.getElementById('kP').textContent = prz.toLocaleString('pt-BR');
  document.getElementById('kC').textContent = con.toLocaleString('pt-BR');
  document.getElementById('kEp').textContent = wp ? Math.round(atr/wp*100)+'% dos com prazo' : 'sem prazo definido';
  document.getElementById('kPp').textContent = wp ? Math.round(prz/wp*100)+'% dos com prazo' : 'sem prazo definido';
}

// ════════════════════════════════════════════
// GRÁFICO PIZZA
// ════════════════════════════════════════════
function renderPie(){
  // Usa hist_status (qualidade histórica do card).
  // Prioridade: recusado > hist atrasado > hist no_prazo > hist sem_prazo
  const ct = {atrasado:0,no_prazo:0,sem_prazo:0,recusado:0};
  filtered.forEach(c=>{
    if(c.status==='recusado')                             ct.recusado++;
    else{
      const hs = c.hist_status || c.status;
      if(ct[hs]!==undefined) ct[hs]++;
      else ct.sem_prazo++;
    }
  });

  const data = {
    labels: ['Atrasado','No prazo','Sem prazo','Recusado'],
    datasets:[{
      data: [ct.atrasado,ct.no_prazo,ct.sem_prazo,ct.recusado],
      backgroundColor: ['#f43f5e','#10b981','#f59e0b','#7f1d1d'],
      borderWidth: 0,
      hoverOffset: 8,
    }]
  };

  const PIE_STATUSES = ['atrasado','no_prazo','sem_prazo','recusado'];

  const opts = {
    responsive:true, maintainAspectRatio:false, cutout:'60%',
    plugins:{
      legend:{position:'bottom',labels:{color:'#94a3b8',boxWidth:10,padding:14,font:{size:10}}},
      tooltip:{callbacks:{label:ctx=>{
        const total = ctx.dataset.data.reduce((a,b)=>a+b,0);
        return ` ${ctx.raw.toLocaleString('pt-BR')} cards (${total?Math.round(ctx.raw/total*100):0}%)`;
      }}},
    },
    onClick:(evt,elements)=>{
      if(!elements.length) return;
      const clicked = PIE_STATUSES[elements[0].index];
      const sel = document.getElementById('fStatus');
      // toggle: clicou de novo na mesma fatia → limpa filtro
      sel.value = (sel.value === clicked) ? '' : clicked;
      applyFilters();
    },
    onHover:(evt,elements)=>{
      evt.native.target.style.cursor = elements.length ? 'pointer' : 'default';
    },
  };

  if(pieChart){ pieChart.data=data; pieChart.update(); }
  else{ pieChart = new Chart(document.getElementById('cPie').getContext('2d'),{type:'doughnut',data,options:opts}); }
}

// ════════════════════════════════════════════
// GRÁFICO BARRAS — histórico por mês
// Sempre mostra TODOS os meses para contexto.
// Clicar num mês filtra KPIs, pizza e tabela.
// Clicar de novo desseleciona (volta ao total).
// ════════════════════════════════════════════
function renderBar(){
  // Usa allCards (não filtrado por mês) para mostrar todos os meses
  // A mesma lógica de hist_status usada nos KPIs e pizza
  const mm = {};
  allCards.forEach(c=>{
    if(!c.created_month) return;
    if(!mm[c.created_month]) mm[c.created_month]={atrasado:0,no_prazo:0,sem_prazo:0};
    const hs = c.hist_status || c.status;
    // concluido/recusado sem hist_status definido → sem_prazo
    const key = (hs==='atrasado'||hs==='no_prazo'||hs==='sem_prazo') ? hs : 'sem_prazo';
    mm[c.created_month][key]++;
  });

  // barMonths é global para que o onClick não use closure stale
  barMonths = Object.keys(mm).sort();
  const labels = barMonths.map(m=>{
    const[y,mo]=m.split('-');
    return new Date(y,mo-1).toLocaleDateString('pt-BR',{month:'short',year:'2-digit'});
  });

  // Destaque visual: meses selecionados = opacidade total, demais = 28%
  const hasSel = selectedMonths.size > 0;
  const al = m => (!hasSel || selectedMonths.has(m)) ? 1.0 : 0.28;

  const data = {
    labels,
    datasets:[
      {label:'Atrasado', data:barMonths.map(m=>mm[m].atrasado), backgroundColor:barMonths.map(m=>`rgba(244,63,94,${al(m)})`),  borderRadius:4},
      {label:'No prazo', data:barMonths.map(m=>mm[m].no_prazo),  backgroundColor:barMonths.map(m=>`rgba(16,185,129,${al(m)})`), borderRadius:4},
      {label:'Sem prazo',data:barMonths.map(m=>mm[m].sem_prazo), backgroundColor:barMonths.map(m=>`rgba(245,158,11,${al(m)})`), borderRadius:4},
    ]
  };

  const opts = {
    responsive:true, maintainAspectRatio:false,
    plugins:{
      legend:{labels:{color:'#94a3b8',boxWidth:10,font:{size:10}}},
      tooltip:{callbacks:{
        title: items=>{
          const m = barMonths[items[0].dataIndex];
          const [y,mo] = m.split('-');
          const isSel = selectedMonths.has(m);
          return new Date(y,mo-1).toLocaleDateString('pt-BR',{month:'long',year:'numeric'})
                 + (isSel ? ' ✓ selecionado' : ' — clique para filtrar');
        }
      }},
    },
    scales:{
      x:{ticks:{color:'#94a3b8',font:{size:9}},grid:{color:'rgba(51,65,85,.4)'}},
      y:{ticks:{color:'#94a3b8',font:{size:9}},grid:{color:'rgba(51,65,85,.4)'}},
    },
    onClick:(evt, elements)=>{
      if(!elements.length) return;
      // Usa barMonths (global) — sem risco de closure stale
      const clicked = barMonths[elements[0].index];
      if(!clicked) return;
      if(selectedMonths.size === 1 && selectedMonths.has(clicked)){
        // Clicou no mesmo mês selecionado → limpa filtro
        selectedMonths.clear();
      } else {
        // Seleciona só este mês (multi-seleção via dropdown)
        selectedMonths.clear();
        selectedMonths.add(clicked);
      }
      // Sincroniza checkboxes do dropdown de meses
      document.querySelectorAll('#mesOpts input[type=checkbox]').forEach(cb=>{
        cb.checked = selectedMonths.has(cb.value);
      });
      updateMesBtn();
      applyFilters();   // atualiza KPIs, pizza, tabela e redesenha barra
    },
    onHover:(evt, elements)=>{
      evt.native.target.style.cursor = elements.length ? 'pointer' : 'default';
    },
  };

  if(barChart){
    barChart.data    = data;
    barChart.options = opts;
    barChart.update('none');   // 'none' = sem animação no re-render (mais rápido)
  } else {
    barChart = new Chart(document.getElementById('cBar').getContext('2d'),{type:'bar',data,options:opts});
  }
}

// ════════════════════════════════════════════
// TABELA
// ════════════════════════════════════════════
function srt(col){
  document.querySelectorAll('thead th').forEach(t=>t.classList.remove('sa','sd'));
  srtDir = (srtCol===col && srtDir==='asc') ? 'desc' : 'asc';
  srtCol = col;
  const cols = ['id','imovel','descricao','phase_name','days_in_phase','status','created_at'];
  const i = cols.indexOf(col);
  if(i>=0) document.querySelectorAll('thead th')[i].classList.add(srtDir==='asc'?'sa':'sd');
  doSort(); curPage=1; renderTable();
}

function doSort(){
  display.sort((a,b)=>{
    let va=a[srtCol]??'', vb=b[srtCol]??'';
    if(srtCol==='days_in_phase') return srtDir==='asc'?Number(va)-Number(vb):Number(vb)-Number(va);
    va=String(va).toLowerCase(); vb=String(vb).toLowerCase();
    return srtDir==='asc'?(va<vb?-1:va>vb?1:0):(va<vb?1:va>vb?-1:0);
  });
}

function renderTable(){
  const tot = display.length;
  const s   = (curPage-1)*pageSize;
  const e   = Math.min(s+pageSize, tot);
  const page= display.slice(s,e);
  const pages = Math.ceil(tot/pageSize)||1;

  document.getElementById('tblCnt').textContent = `${tot.toLocaleString('pt-BR')} cards encontrados`;
  document.getElementById('pgInfo').textContent = `Página ${curPage} de ${pages}`;
  document.getElementById('bPrev').disabled = curPage<=1;
  document.getElementById('bNext').disabled = e>=tot;

  if(!page.length){
    const msg = allCards.length===0
      ? '<div class="empty"><div class="spinner"></div><br>Carregando dados do Pipefy...</div>'
      : '<tr><td colspan="8" style="text-align:center;color:#64748b;padding:36px">Nenhum card encontrado.</td></tr>';
    document.getElementById('tblBody').innerHTML = allCards.length===0 ? `<tr><td colspan="8">${msg}</td></tr>` : msg;
    return;
  }

  const fmt = d => d && d!=='—' ? d.split('-').reverse().join('/') : '—';

  document.getElementById('tblBody').innerHTML = page.map(c=>{
    const desc  = (c.descricao||'—').substring(0,80)+((c.descricao||'').length>80?'…':'');
    const imov  = (c.imovel||'—').substring(0,25)+((c.imovel||'').length>25?'…':'');
    const color = c.phase_done      ? '#64748b'
                : c.status==='atrasado'  ? '#f43f5e'
                : c.sla_pct >= 75        ? '#f59e0b'
                : '#94a3b8';
    const slaLabel = c.sla_display && c.sla_display !== '—' ? ` / SLA ${c.sla_display}` : '';
    const tempo = c.phase_done ? '<span style="color:#475569">—</span>'
                               : `<span style="color:${color};font-weight:600" title="SLA desta fase: ${c.sla_display}">${c.time_display}${slaLabel}</span>`;
    return `<tr>
      <td><code style="color:#64748b;font-size:.7rem">${c.id}</code></td>
      <td class="trunc-s" title="${c.imovel||''}">${imov}</td>
      <td class="trunc"   title="${c.descricao||''}">${desc}</td>
      <td style="white-space:nowrap;color:#cbd5e1">${c.phase_name}</td>
      <td style="text-align:center">${tempo}</td>
      <td><span class="badge ${SC[c.status]||'b-con'}">${SL[c.status]||c.status}</span></td>
      <td style="color:#64748b;font-size:.76rem;white-space:nowrap">${fmt(c.created_at)}</td>
    </tr>`;
  }).join('');
}

function changePage(dir){
  const pages = Math.ceil(display.length/pageSize)||1;
  curPage = Math.max(1, Math.min(curPage+dir, pages));
  renderTable();
}

// ════════════════════════════════════════════
// INICIALIZAÇÃO
// ════════════════════════════════════════════
buildCompanyTabs();
buildPipeTabs();
buildFaseSel();
document.getElementById('navSub').textContent = PIPE_CONFIG[currentPipe].name;
poll();
</script>
</body>
</html>"""

# ─── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*55)
    print("  🚀  BI Dashboard — MDN Porto Rico (Manutenção)")
    print("="*55)
    print("  💻  Computador : http://localhost:5000")
    try:
        ip = socket.gethostbyname(socket.gethostname())
        print(f"  📱  Celular     : http://{ip}:5000  (mesmo Wi-Fi)")
    except Exception:
        pass
    print("  ⏳  Carregando dados dos pipes em background...")
    print("      Porto Rico + Zeladoria (~4.500 cards)")
    print("="*55 + "\n")
    for pk in PIPES:
        threading.Thread(target=bg_loop, args=(pk,), daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
