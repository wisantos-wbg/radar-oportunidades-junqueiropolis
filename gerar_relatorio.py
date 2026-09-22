import json
from pathlib import Path

import transferegov_radar as tg
import pncp_radar as pncp

ROOT = Path(__file__).parent
OUT_HTML = ROOT / "docs" / "index.html"
OUT_JSON = ROOT / "docs" / "data.json"


def fmt_brl(v: float) -> str:
    return "R$ " + f"{v:,.0f}".replace(",", ".")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Radar de Oportunidades — Junqueirópolis/SP</title>
<style>
:root{
  --bg:#0f1115;--panel:#171a21;--panel2:#1e222b;--text:#eef0f3;--muted:#98a2b3;
  --accent:#3d9df6;--accent2:#2ecc8f;--border:#2a2f3a;--warn:#f5b942;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,"Segoe UI",Inter,sans-serif;line-height:1.55}
header{padding:1.4rem 2rem;border-bottom:1px solid var(--border)}
header h1{margin:0;font-size:1.4rem}
header .sub{color:var(--muted);font-size:.9rem;margin-top:.3rem}
main{max-width:1100px;margin:0 auto;padding:1.5rem 2rem 3rem}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin-bottom:1.6rem}
.kpi{background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:1.1rem 1.3rem}
.kpi .n{font-size:1.6rem;font-weight:800;color:var(--accent)}
.kpi .l{color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.03em}
h2{font-size:1.05rem;margin:2rem 0 .8rem}
.card{background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:1.1rem 1.3rem;margin-bottom:1.2rem}
table{width:100%;border-collapse:collapse;font-size:.86rem}
th,td{text-align:left;padding:.55rem .6rem;border-bottom:1px solid var(--border);vertical-align:top}
th{color:var(--muted);font-weight:700;font-size:.72rem;text-transform:uppercase;letter-spacing:.03em}
tr:hover td{background:var(--panel2)}
.acao{color:var(--accent);cursor:pointer;background:none;border:none;font-size:.82rem;padding:.15rem .4rem}
a{color:var(--accent)}
.vazio{color:var(--muted);font-style:italic;padding:.6rem 0}
.aviso{color:var(--warn);font-size:.85rem;margin:.4rem 0}
footer{max-width:1100px;margin:2rem auto;padding:0 2rem 2rem;color:var(--muted);font-size:.78rem}
.modal{display:none;position:fixed;inset:0;background:#000c;z-index:9999;align-items:center;justify-content:center;padding:1.5rem}
.modal.on{display:flex}
.modal-box{background:var(--panel);border:1px solid var(--border);border-radius:18px;max-width:700px;width:100%;max-height:85vh;overflow:auto;padding:1.4rem}
.modal-box pre{white-space:pre-wrap;font-size:.84rem;background:var(--panel2);padding:1rem;border-radius:10px}
.modal-close{float:right;background:none;border:none;color:var(--muted);font-size:1.2rem;cursor:pointer}
</style>
</head>
<body>
<header>
  <h1>Radar de Oportunidades — Junqueirópolis/SP</h1>
  <div class="sub">Transferegov (ainda não usadas) + PNCP (credenciamentos/manifestações de interesse) · gerado em __GERADO_EM__</div>
</header>
<main>
  <div class="kpis">
    <div class="kpi"><div class="n">__TOTAL_ABERTOS__</div><div class="l">programas federais abertos agora</div></div>
    <div class="kpi"><div class="n">__TOTAL_OPORTUNIDADES__</div><div class="l">ainda não usados por Junqueirópolis</div></div>
    <div class="kpi"><div class="n">__VALOR_HISTORICO__</div><div class="l">já captado historicamente (Transferegov)</div></div>
    <div class="kpi"><div class="n">__TOTAL_PNCP__</div><div class="l">avisos PNCP (credenciamento/manif. interesse, __JANELA_DIAS__ dias)</div></div>
  </div>

  <h2>Transferegov — oportunidades abertas ainda não usadas</h2>
  <div class="card">
    <table>
      <thead><tr><th>Programa</th><th>Órgão repassador</th><th>Instrumento</th><th>Prazo captação</th><th></th></tr></thead>
      <tbody id="tbodyOportunidades"></tbody>
    </table>
    <div id="vazioOportunidades" class="vazio" style="display:none">Nenhuma oportunidade aberta pendente no momento.</div>
  </div>

  <h2>PNCP — credenciamentos e manifestações de interesse (últimos __JANELA_DIAS__ dias)</h2>
  __PNCP_AVISOS_HTML__
  <div class="card">
    <table>
      <thead><tr><th>Órgão</th><th>UF/Município</th><th>Objeto</th><th>Publicado em</th><th></th></tr></thead>
      <tbody id="tbodyPncp"></tbody>
    </table>
    <div id="vazioPncp" class="vazio" style="display:none">Nenhum aviso nessas modalidades nos últimos __JANELA_DIAS__ dias.</div>
  </div>

  <h2>Histórico de propostas já enviadas (Transferegov)</h2>
  <div class="card">
    <table>
      <thead><tr><th>Objeto</th><th>Situação</th><th>Valor</th><th>Data</th><th>Órgão</th></tr></thead>
      <tbody id="tbodyHistorico"></tbody>
    </table>
  </div>
</main>
<footer>
  Transferegov: API pública (api-publica.transferegov.gestao.gov.br), módulo Parcerias. "Oportunidade aberta" =
  programa com situação Disponibilizado e candidatura direta (Espontâneo/Específico), fora emenda parlamentar.
  PNCP: API pública (pncp.gov.br/api/consulta) — cobre credenciamento e manifestação de interesse nacionalmente,
  não filtrado por município (ver comentário no topo de pncp_radar.py). Minutas são rascunhos automáticos, não
  substituem o formulário oficial de nenhum órgão repassador nem a submissão manual.
</footer>

<div class="modal" id="modal">
  <div class="modal-box">
    <button class="modal-close" onclick="document.getElementById('modal').classList.remove('on')">✕</button>
    <div id="modalBody"></div>
  </div>
</div>

<script>
const DATA = __DADOS_JSON__;

function escapeHtml(s){ return (s||"").toString().replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }

function renderOportunidades(){
  const linhas = DATA.transferegov.oportunidades;
  document.getElementById("tbodyOportunidades").innerHTML = linhas.map((o,i)=>`<tr>
    <td>${escapeHtml(o.nmPrograma)}</td><td>${escapeHtml(o.nmEnteRepassador)}</td>
    <td>${escapeHtml(o.tpInstrumento)}</td><td>${o.captacaoFim||"-"}</td>
    <td style="white-space:nowrap">
      <button class="acao" onclick="abrirMinuta(${i})">📋 minuta</button>
      &nbsp;<a href="${o.urlPortal}" target="_blank" rel="noopener">🔗 edital</a>
    </td></tr>`).join("");
  document.getElementById("vazioOportunidades").style.display = linhas.length ? "none" : "block";
}

function abrirMinuta(i){
  const o = DATA.transferegov.oportunidades[i];
  document.getElementById("modalBody").innerHTML =
    `<h2>${escapeHtml(o.nmPrograma)}</h2>
     <p><a href="${o.urlPortal}" target="_blank" rel="noopener">🔗 abrir programa no Transferegov.br</a></p>
     <pre>${escapeHtml(o.minuta)}</pre>`;
  document.getElementById("modal").classList.add("on");
}

function renderPncp(){
  const linhas = DATA.pncp.avisos;
  document.getElementById("tbodyPncp").innerHTML = linhas.map(a=>`<tr>
    <td>${escapeHtml(a.orgao)}</td><td>${escapeHtml(a.uf)} / ${escapeHtml(a.municipio)}</td>
    <td>${escapeHtml((a.objeto||"").slice(0,160))}${(a.objeto||"").length>160?"…":""}</td>
    <td>${a.dataPublicacao||"-"}</td>
    <td>${a.linkSistemaOrigem?`<a href="${a.linkSistemaOrigem}" target="_blank" rel="noopener">🔗 ver</a>`:""}</td>
    </tr>`).join("");
  document.getElementById("vazioPncp").style.display = linhas.length ? "none" : "block";
}

function renderHistorico(){
  const linhas = DATA.transferegov.historico.slice(0,100);
  document.getElementById("tbodyHistorico").innerHTML = linhas.map(p=>`<tr>
    <td>${escapeHtml(p.objeto)}</td><td>${escapeHtml(p.situacao)}</td>
    <td>${p.valorFmt}</td><td>${p.data||""}</td><td>${escapeHtml(p.orgao)}</td></tr>`).join("");
}

renderOportunidades(); renderPncp(); renderHistorico();
</script>
</body>
</html>
"""


def gerar():
    radar_tg = tg.montar_radar()
    radar_pncp = pncp.montar_radar_pncp()

    for h in radar_tg["historico"]:
        h["valorFmt"] = fmt_brl(h["valor"])

    dados = {"transferegov": radar_tg, "pncp": radar_pncp}
    dados_json = json.dumps(dados, ensure_ascii=False).replace("</script>", "<\\/script>")

    aviso_pncp_html = ""
    if radar_pncp.get("erros"):
        aviso_pncp_html = "".join(f'<div class="aviso">⚠ {e}</div>' for e in radar_pncp["erros"])

    html = (TEMPLATE
            .replace("__DADOS_JSON__", dados_json)
            .replace("__GERADO_EM__", radar_tg["geradoEm"])
            .replace("__TOTAL_ABERTOS__", str(radar_tg["totalProgramasAbertos"]))
            .replace("__TOTAL_OPORTUNIDADES__", str(len(radar_tg["oportunidades"])))
            .replace("__VALOR_HISTORICO__", fmt_brl(radar_tg["valorHistoricoCaptado"]))
            .replace("__TOTAL_PNCP__", str(radar_pncp["totalAvisos"]))
            .replace("__JANELA_DIAS__", str(radar_pncp["janelaDias"]))
            .replace("__PNCP_AVISOS_HTML__", aviso_pncp_html))

    OUT_HTML.parent.mkdir(exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    OUT_JSON.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"painel: {OUT_HTML} | {len(radar_tg['oportunidades'])} oportunidades Transferegov | "
          f"{radar_pncp['totalAvisos']} avisos PNCP | {OUT_HTML.stat().st_size // 1024} KB")


if __name__ == "__main__":
    gerar()
