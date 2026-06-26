#!/usr/bin/env python3
"""
BI Financeiro — Omie
Rotas servidas sob o prefixo /omie (ver vercel.json).
Local: python api/omie.py  ->  http://localhost:5001/omie
"""

import json, os, time
from datetime import datetime, date
from flask import Flask, jsonify, Response, request
import requests
from dotenv import load_dotenv
from _cache import redis_get, redis_set, CHUNK_SECONDS

load_dotenv()

# ─── Configuração ──────────────────────────────────────────────────────────────
APP_KEY    = os.environ.get("App_Key", "") or os.environ.get("OMIE_APP_KEY", "")
APP_SECRET = os.environ.get("App_Secret", "") or os.environ.get("OMIE_APP_SECRET", "")
USE_MOCK   = not APP_KEY or not APP_SECRET   # sem chaves -> usa dados de exemplo

OMIE_BASE = "https://app.omie.com.br/api/v1"
ENDPOINTS = {
    "contas_pagar":    "/financas/contapagar/",
    "contas_receber":  "/financas/contareceber/",
    "extrato":         "/financas/extrato/",
}

app = Flask(__name__)

# ─── Estado (persistido no Redis entre invocações) ────────────────────────────
STEPS = ["pessoas", "pagar", "receber", "saldo"]

def empty_state():
    return {
        "contas_pagar": [], "contas_receber": [], "saldo_caixa": 0.0,
        "loading": False, "last_updated": None, "error": None, "mock": USE_MOCK,
        "_step_idx": 0, "_page": 1,
        "_partial_pessoas": {}, "_partial_pagar": [], "_partial_receber": [],
        "_accounts": None, "_account_idx": 0, "_saldo_acc": 0.0,
    }

def state_key():
    return "omie:state"

def load_state():
    return redis_get(state_key()) or empty_state()

def save_state(st):
    redis_set(state_key(), st)

def public_view(st):
    return {k: v for k, v in st.items() if not k.startswith("_")}

# ─── Chamada genérica à API Omie ────────────────────────────────────────────────
def omie_call(endpoint, call, param, retries=4):
    payload = {
        "call": call,
        "app_key": APP_KEY,
        "app_secret": APP_SECRET,
        "param": [param],
    }
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(OMIE_BASE + endpoint, json=payload, timeout=60)
            data = r.json()
        except requests.exceptions.RequestException as e:
            last_err = e
            time.sleep(5)
            continue
        if "faultstring" in data:
            if "REDUNDANT" in data.get("faultcode", "") or "redundante" in data["faultstring"].lower():
                time.sleep(31)
                last_err = RuntimeError(data["faultstring"])
                continue
            raise RuntimeError(data["faultstring"])
        r.raise_for_status()
        time.sleep(0.3)
        return data
    raise last_err

MESES_PASSADO = 12
MESES_FUTURO  = 3

def periodo_filtro():
    """Janela de datas (emissão) usada para não puxar o histórico inteiro a cada refresh."""
    hoje = date.today()
    de  = hoje.replace(day=1)
    for _ in range(MESES_PASSADO):
        de = (de.replace(day=1) - __import__("datetime").timedelta(days=1)).replace(day=1)
    mes_ate = hoje.month - 1 + MESES_FUTURO
    ano_ate = hoje.year + mes_ate // 12
    mes_ate = mes_ate % 12 + 1
    ate = date(ano_ate, mes_ate, 1)
    return de.strftime("%d/%m/%Y"), ate.strftime("%d/%m/%Y")

def load_contas_pagar_page(pagina):
    """Retorna (registros_da_pagina, total_de_paginas)."""
    de, ate = periodo_filtro()
    data = omie_call(ENDPOINTS["contas_pagar"], "ListarContasPagar", {
        "pagina": pagina, "registros_por_pagina": 200,
        "filtrar_por_data_de": de, "filtrar_por_data_ate": ate,
    })
    return data.get("conta_pagar_cadastro", []), data.get("total_de_paginas", 1)

def load_contas_receber_page(pagina):
    de, ate = periodo_filtro()
    data = omie_call(ENDPOINTS["contas_receber"], "ListarContasReceber", {
        "pagina": pagina, "registros_por_pagina": 200,
        "filtrar_por_data_de": de, "filtrar_por_data_ate": ate,
    })
    return data.get("conta_receber_cadastro", []), data.get("total_de_paginas", 1)

def load_pessoas_page(pagina):
    """Cadastro unificado de clientes/fornecedores (codigo -> razão social)."""
    data = omie_call("/geral/clientes/", "ListarClientes",
                      {"pagina": pagina, "registros_por_pagina": 200})
    pessoas = {str(c["codigo_cliente_omie"]): c.get("razao_social") or c.get("nome_fantasia") or ""
               for c in data.get("clientes_cadastro", [])}
    return pessoas, data.get("total_de_paginas", 1)

def enriquecer(registros, campo_codigo, campo_nome, pessoas):
    for r in registros:
        cod = str(r.get(campo_codigo))
        r[campo_nome] = pessoas.get(cod, f"Cód. {cod}")
    return registros

def load_contas_correntes():
    data = omie_call("/geral/contacorrente/", "ListarContasCorrentes",
                      {"pagina": 1, "registros_por_pagina": 100})
    return [c for c in data.get("ListarContasCorrentes", []) if c.get("inativo") != "S"]

def load_saldo_conta(conta):
    hoje = date.today().strftime("%d/%m/%Y")
    extrato = omie_call(ENDPOINTS["extrato"], "ListarExtrato", {
        "nCodCC": conta["nCodCC"],
        "dPeriodoInicial": conta.get("saldo_data", "01/01/2000"),
        "dPeriodoFinal": hoje,
    })
    return extrato.get("nSaldoAtual", 0.0)

# ─── Dados mock (sem credenciais Omie) ──────────────────────────────────────────
def mock_data():
    hoje = date.today()
    contas_pagar, contas_receber = [], []
    for m in range(1, 13):
        for i in range(3):
            contas_pagar.append({
                "data_vencimento": f"{15+i:02d}/{m:02d}/{hoje.year}",
                "valor_documento": 1200.0 + i * 350 + m * 20,
                "fornecedor": f"Fornecedor {i+1}",
                "status_titulo": "VENCIDO" if m < hoje.month else ("PAGO" if m < hoje.month else "A VENCER"),
            })
            contas_receber.append({
                "data_vencimento": f"{10+i:02d}/{m:02d}/{hoje.year}",
                "valor_documento": 2000.0 + i * 500 + m * 30,
                "cliente": f"Cliente {i+1}",
                "status_titulo": "RECEBIDO" if m < hoje.month else "A RECEBER",
            })
    return contas_pagar, contas_receber, 18540.32

def process_chunk():
    """Avança o carregamento por um tempo limitado (CHUNK_SECONDS) e persiste o
    progresso no Redis. Repetidamente chamado pelo polling do frontend até
    completar todos os passos (pessoas -> pagar -> receber -> saldo)."""
    st = load_state()

    if USE_MOCK:
        cp, cr, saldo = mock_data()
        st = empty_state()
        st["contas_pagar"], st["contas_receber"], st["saldo_caixa"] = cp, cr, saldo
        st["last_updated"] = datetime.now().isoformat()
        save_state(st)
        return st

    if not st["loading"]:
        st = empty_state()
        st["loading"] = True

    deadline = time.time() + CHUNK_SECONDS
    try:
        while time.time() < deadline and st["_step_idx"] < len(STEPS):
            step = STEPS[st["_step_idx"]]

            if step == "pessoas":
                pessoas, total_paginas = load_pessoas_page(st["_page"])
                st["_partial_pessoas"].update(pessoas)
            elif step == "pagar":
                registros, total_paginas = load_contas_pagar_page(st["_page"])
                st["_partial_pagar"] += registros
            elif step == "receber":
                registros, total_paginas = load_contas_receber_page(st["_page"])
                st["_partial_receber"] += registros
            else:  # saldo
                if st["_accounts"] is None:
                    st["_accounts"] = load_contas_correntes()
                    st["_account_idx"] = 0
                    st["_saldo_acc"] = 0.0
                if st["_account_idx"] >= len(st["_accounts"]):
                    st["_step_idx"] += 1
                    continue
                conta = st["_accounts"][st["_account_idx"]]
                st["_saldo_acc"] += load_saldo_conta(conta)
                st["_account_idx"] += 1
                continue

            if st["_page"] >= total_paginas:
                st["_step_idx"] += 1
                st["_page"] = 1
            else:
                st["_page"] += 1

        if st["_step_idx"] >= len(STEPS):
            pessoas = st["_partial_pessoas"]
            st["contas_pagar"]   = enriquecer(st["_partial_pagar"],   "codigo_cliente_fornecedor", "fornecedor", pessoas)
            st["contas_receber"] = enriquecer(st["_partial_receber"], "codigo_cliente_fornecedor", "cliente",    pessoas)
            st["saldo_caixa"]    = st["_saldo_acc"]
            st["last_updated"]   = datetime.now().isoformat()
            st["loading"]        = False
            st["error"]          = None
            st["_step_idx"], st["_page"]           = 0, 1
            st["_partial_pessoas"]                 = {}
            st["_partial_pagar"], st["_partial_receber"] = [], []
            st["_accounts"], st["_account_idx"], st["_saldo_acc"] = None, 0, 0.0
    except Exception as ex:
        st["error"]   = str(ex)
        st["loading"] = False

    save_state(st)
    return st

# ─── Rotas ───────────────────────────────────────────────────────────────────
@app.route("/omie")
def index():
    return Response(HTML, content_type="text/html; charset=utf-8")

@app.route("/omie/api/data")
def api_data():
    try:
        st = load_state()
        if st["loading"] or not st["last_updated"]:
            st = process_chunk()
        return jsonify(public_view(st))
    except Exception as ex:
        import traceback
        return jsonify({"debug_error": str(ex), "debug_trace": traceback.format_exc()}), 500

@app.route("/omie/api/refresh", methods=["POST"])
def api_refresh():
    st = empty_state()
    st["loading"] = True
    save_state(st)
    process_chunk()
    return jsonify({"ok": True})

# ─── HTML Dashboard ──────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BI Financeiro — Omie</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root{--bg:#0f1117;--card:#1a1d27;--border:#2a2e3a;--txt:#e6e8ee;--muted:#8b8fa3;
        --green:#3ecf8e;--red:#f25c5c;--blue:#5b8def;--yellow:#e7b34a;}
  *{box-sizing:border-box;}
  body{margin:0;background:var(--bg);color:var(--txt);font-family:Segoe UI,Roboto,Arial,sans-serif;}
  header{padding:16px 20px;display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;
         border-bottom:1px solid var(--border);}
  header h1{font-size:18px;margin:0;}
  .filters{display:flex;gap:8px;align-items:center;flex-wrap:wrap;}
  select,button{background:var(--card);color:var(--txt);border:1px solid var(--border);
         border-radius:8px;padding:8px 12px;font-size:14px;}
  button{cursor:pointer;}
  button:hover{border-color:var(--blue);}
  .mock-badge{background:var(--yellow);color:#1a1d27;padding:4px 10px;border-radius:6px;font-size:12px;font-weight:600;}
  main{padding:20px;max-width:1200px;margin:0 auto;}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin-bottom:24px;}
  .card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px;}
  .card .label{color:var(--muted);font-size:13px;margin-bottom:6px;}
  .card .value{font-size:24px;font-weight:700;}
  .card.green .value{color:var(--green);}
  .card.red .value{color:var(--red);}
  .card.blue .value{color:var(--blue);}
  .panel{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px;margin-bottom:24px;}
  .panel h2{font-size:15px;margin:0 0 12px 0;color:var(--muted);}
  table{width:100%;border-collapse:collapse;font-size:12px;}
  th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--border);}
  th{color:var(--muted);font-weight:600;}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:20px;}
  @media (max-width:800px){.grid2{grid-template-columns:1fr;}}
  .status-pago{color:var(--green);} .status-vencido{color:var(--red);} .status-pendente{color:var(--yellow);}
  footer{text-align:center;color:var(--muted);font-size:12px;padding:20px;}
  .table-toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between;margin-bottom:10px;}
  .table-toolbar select{font-size:12px;padding:5px 8px;}
  .table-pager{display:flex;gap:8px;align-items:center;font-size:12px;color:var(--muted);}
  .table-pager button{padding:4px 10px;font-size:12px;}
  .table-pager button:disabled{opacity:.4;cursor:default;}
  th.sortable{cursor:pointer;}
  th.sortable:hover{color:var(--txt);}
</style>
</head>
<body>
<header>
  <h1>📊 BI Financeiro — Omie</h1>
  <div class="filters">
    <span id="mockBadge" class="mock-badge" style="display:none;">DADOS DE EXEMPLO (sem credenciais Omie)</span>
    <label>Mês: <select id="mesFiltro" onchange="render()"></select></label>
    <button onclick="refreshData()">↻ Atualizar</button>
  </div>
</header>
<main>
  <div class="cards">
    <div class="card red"><div class="label">Contas a Pagar (mês)</div><div class="value" id="cardPagar">—</div></div>
    <div class="card green"><div class="label">Contas a Receber (mês)</div><div class="value" id="cardReceber">—</div></div>
    <div class="card blue"><div class="label">Saldo de Caixa</div><div class="value" id="cardSaldo">—</div></div>
  </div>

  <div class="panel">
    <h2>Fluxo de Caixa — Mês a Mês</h2>
    <canvas id="chartFluxo" height="90"></canvas>
  </div>

  <div class="grid2">
    <div class="panel">
      <h2>Contas a Pagar</h2>
      <div class="table-toolbar">
        <label>Ordenar por:
          <select id="ordPagar" onchange="render()">
            <option value="data_vencimento">Vencimento</option>
            <option value="valor_documento">Valor</option>
            <option value="status_titulo">Status</option>
          </select>
        </label>
        <button onclick="toggleDir('pagar')" id="dirPagar">↓ Decrescente</button>
        <label>Por página:
          <select id="pageSizePagar" onchange="changePageSize('pagar')">
            <option>10</option><option selected>25</option><option>50</option><option>100</option>
          </select>
        </label>
      </div>
      <table><thead><tr><th>Vencimento</th><th>Fornecedor</th><th>Valor</th><th>Status</th></tr></thead>
      <tbody id="tblPagar"></tbody></table>
      <div class="table-pager">
        <button onclick="changePage('pagar',-1)" id="prevPagar">‹ Anterior</button>
        <span id="pageInfoPagar"></span>
        <button onclick="changePage('pagar',1)" id="nextPagar">Próxima ›</button>
      </div>
    </div>
    <div class="panel">
      <h2>Contas a Receber</h2>
      <div class="table-toolbar">
        <label>Ordenar por:
          <select id="ordReceber" onchange="render()">
            <option value="data_vencimento">Vencimento</option>
            <option value="valor_documento">Valor</option>
            <option value="status_titulo">Status</option>
          </select>
        </label>
        <button onclick="toggleDir('receber')" id="dirReceber">↓ Decrescente</button>
        <label>Por página:
          <select id="pageSizeReceber" onchange="changePageSize('receber')">
            <option>10</option><option selected>25</option><option>50</option><option>100</option>
          </select>
        </label>
      </div>
      <table><thead><tr><th>Vencimento</th><th>Cliente</th><th>Valor</th><th>Status</th></tr></thead>
      <tbody id="tblReceber"></tbody></table>
      <div class="table-pager">
        <button onclick="changePage('receber',-1)" id="prevReceber">‹ Anterior</button>
        <span id="pageInfoReceber"></span>
        <button onclick="changePage('receber',1)" id="nextReceber">Próxima ›</button>
      </div>
    </div>
  </div>

  <footer id="lastUpdated"></footer>
</main>

<script>
let raw = null, chart = null;
const dir  = { pagar: 'desc', receber: 'desc' };
const page = { pagar: 1, receber: 1 };

function brl(v){ return (v||0).toLocaleString('pt-BR', {style:'currency', currency:'BRL'}); }
function parseDate(d){ const [dd,mm,yy] = d.split('/'); return new Date(`${yy}-${mm}-${dd}`); }
function mesKey(d){ const dt = parseDate(d); return `${dt.getFullYear()}-${String(dt.getMonth()+1).padStart(2,'0')}`; }
function mesLabel(key){ const [y,m] = key.split('-'); const nomes=['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']; return `${nomes[parseInt(m)-1]}/${y}`; }
function statusClass(s){ s=(s||'').toUpperCase(); if(s.includes('PAGO')||s.includes('RECEBIDO')||s.includes('CONCLU')) return 'status-pago'; if(s.includes('VENC')) return 'status-vencido'; return 'status-pendente'; }

function fillMesFiltro(){
  const meses = new Set();
  [...raw.contas_pagar, ...raw.contas_receber].forEach(c => meses.add(mesKey(c.data_vencimento)));
  const ordenados = [...meses].sort();
  const sel = document.getElementById('mesFiltro');
  const atualSel = sel.value;
  sel.innerHTML = '<option value="">Todos os meses</option>' +
    ordenados.map(k => `<option value="${k}">${mesLabel(k)}</option>`).join('');
  const hoje = new Date();
  const atual = `${hoje.getFullYear()}-${String(hoje.getMonth()+1).padStart(2,'0')}`;
  sel.value = atualSel && ordenados.includes(atualSel) ? atualSel : (ordenados.includes(atual) ? atual : '');
}

function toggleDir(tipo){
  dir[tipo] = dir[tipo] === 'desc' ? 'asc' : 'desc';
  document.getElementById('dir' + (tipo==='pagar'?'Pagar':'Receber')).textContent = dir[tipo]==='desc' ? '↓ Decrescente' : '↑ Crescente';
  page[tipo] = 1;
  render();
}

function changePageSize(tipo){ page[tipo] = 1; render(); }

function changePage(tipo, delta){ page[tipo] += delta; render(); }

function ordenar(arr, campo, direcao){
  const sorted = [...arr].sort((a,b) => {
    let av = a[campo], bv = b[campo];
    if(campo === 'data_vencimento'){ av = parseDate(av); bv = parseDate(bv); }
    if(typeof av === 'string') av = av.toLowerCase();
    if(typeof bv === 'string') bv = bv.toLowerCase();
    return av > bv ? 1 : av < bv ? -1 : 0;
  });
  return direcao === 'desc' ? sorted.reverse() : sorted;
}

function renderTabela(tipo, dados, ordCampo, colunaExtra, rowFn){
  const ordenado = ordenar(dados, ordCampo, dir[tipo]);
  const pageSize = parseInt(document.getElementById('pageSize' + (tipo==='pagar'?'Pagar':'Receber')).value);
  const totalPaginas = Math.max(1, Math.ceil(ordenado.length / pageSize));
  page[tipo] = Math.min(Math.max(1, page[tipo]), totalPaginas);
  const inicio = (page[tipo]-1) * pageSize;
  const pagina = ordenado.slice(inicio, inicio + pageSize);

  const sufixo = tipo==='pagar' ? 'Pagar' : 'Receber';
  document.getElementById('tbl'+sufixo).innerHTML = pagina.map(rowFn).join('') || '<tr><td colspan="4">Sem registros</td></tr>';
  document.getElementById('pageInfo'+sufixo).textContent = `Página ${page[tipo]} de ${totalPaginas} (${ordenado.length} registros)`;
  document.getElementById('prev'+sufixo).disabled = page[tipo] <= 1;
  document.getElementById('next'+sufixo).disabled = page[tipo] >= totalPaginas;
}

function render(){
  if(!raw) return;
  const mes = document.getElementById('mesFiltro').value;
  const filtro = (arr) => mes ? arr.filter(c => mesKey(c.data_vencimento) === mes) : arr;

  const pagar   = filtro(raw.contas_pagar);
  const receber = filtro(raw.contas_receber);

  document.getElementById('cardPagar').textContent   = brl(pagar.reduce((s,c)=>s+c.valor_documento,0));
  document.getElementById('cardReceber').textContent = brl(receber.reduce((s,c)=>s+c.valor_documento,0));
  document.getElementById('cardSaldo').textContent   = brl(raw.saldo_caixa);

  renderTabela('pagar', pagar, document.getElementById('ordPagar').value, null, c =>
    `<tr><td>${c.data_vencimento}</td><td>${c.fornecedor}</td><td>${brl(c.valor_documento)}</td><td class="${statusClass(c.status_titulo)}">${c.status_titulo}</td></tr>`
  );
  renderTabela('receber', receber, document.getElementById('ordReceber').value, null, c =>
    `<tr><td>${c.data_vencimento}</td><td>${c.cliente}</td><td>${brl(c.valor_documento)}</td><td class="${statusClass(c.status_titulo)}">${c.status_titulo}</td></tr>`
  );

  renderChart(mes);
}

function renderChart(mesSelecionado){
  const meses = new Set();
  raw.contas_pagar.forEach(c => meses.add(mesKey(c.data_vencimento)));
  raw.contas_receber.forEach(c => meses.add(mesKey(c.data_vencimento)));
  let ordenados = [...meses].sort();
  if(mesSelecionado) ordenados = ordenados.filter(k => k === mesSelecionado);

  const despesas = ordenados.map(k => raw.contas_pagar.filter(c=>mesKey(c.data_vencimento)===k).reduce((s,c)=>s+c.valor_documento,0));
  const receitas = ordenados.map(k => raw.contas_receber.filter(c=>mesKey(c.data_vencimento)===k).reduce((s,c)=>s+c.valor_documento,0));

  const ctx = document.getElementById('chartFluxo').getContext('2d');
  if(chart) chart.destroy();
  chart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ordenados.map(mesLabel),
      datasets: [
        {label:'Receitas', data:receitas, backgroundColor:'#3ecf8e'},
        {label:'Despesas', data:despesas, backgroundColor:'#f25c5c'},
      ]
    },
    options: {
      responsive:true,
      plugins:{legend:{labels:{color:'#e6e8ee'}}},
      scales:{
        x:{ticks:{color:'#8b8fa3'}, grid:{color:'#2a2e3a'}},
        y:{ticks:{color:'#8b8fa3'}, grid:{color:'#2a2e3a'}},
      }
    }
  });
}

async function load(){
  const r = await fetch('/omie/api/data');
  raw = await r.json();
  document.getElementById('mockBadge').style.display = raw.mock ? 'inline-block' : 'none';
  if(raw.error && !raw.loading){
    document.getElementById('lastUpdated').textContent = '⚠ Erro: '+raw.error.slice(0,80);
  } else if(raw.loading){
    document.getElementById('lastUpdated').textContent = 'Carregando…';
  } else if(raw.last_updated){
    document.getElementById('lastUpdated').textContent = `Última atualização: ${new Date(raw.last_updated).toLocaleString('pt-BR')}`;
  }
  if(!raw.loading){
    fillMesFiltro();
    render();
  }
  return raw.loading;
}

async function refreshData(){ await load(); }

async function poll(){
  const stillLoading = await load();
  setTimeout(poll, stillLoading ? 800 : 60000);
}
poll();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
