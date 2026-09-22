import json
import time
from datetime import date
from pathlib import Path

import requests

IBGE_JUNQUEIROPOLIS = 3526001
NOME_MUNICIPIO = "Junqueirópolis"
UF_MUNICIPIO = "SP"

BASE_URL = "https://api-publica.transferegov.gestao.gov.br/parcerias"
PORTAL_API = "https://parcerias.transferegov.sistema.gov.br/ep/api/atos-prep"
PORTAL_URL_PROGRAMA = (
    "https://parcerias.transferegov.sistema.gov.br/ep-atos-prep-web/"
    "atos-prep/programa/detalhamento/{id}"
)

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_TTL_SECONDS = 6 * 60 * 60


def _cache_path(key: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{key}.json"


def _cached_get_url(url: str, params: dict, cache_key: str) -> dict | None:
    cache_file = _cache_path(cache_key)
    if cache_file.exists() and (time.time() - cache_file.stat().st_mtime) < CACHE_TTL_SECONDS:
        return json.loads(cache_file.read_text(encoding="utf-8"))

    resp = requests.get(url, params=params, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()
    cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def _cached_get(path: str, params: dict, cache_key: str) -> dict:
    return _cached_get_url(f"{BASE_URL}{path}", params, cache_key)


def get_todos_programas() -> list[dict]:
    data = _cached_get("/programa", {"tamanho_da_pagina": 200, "pagina": 1}, "programas_p1")
    return data["data"]


def get_programas_abertos() -> list[dict]:
    programas = get_todos_programas()
    return [
        p for p in programas
        if p.get("situacao_programa") == "Disponibilizado"
        and p.get("qualificacao_beneficiario") in ("Beneficiário Espontâneo", "Beneficiário Específico")
    ]


def get_propostas_municipio(cd_ibge: int = IBGE_JUNQUEIROPOLIS) -> list[dict]:
    data = _cached_get(
        "/proposta",
        {"cd_ibge_recebedor": cd_ibge, "tamanho_da_pagina": 200, "pagina": 1},
        f"propostas_{cd_ibge}",
    )
    return data["data"]


def valor_proposta(proposta: dict) -> float:
    return proposta.get("nr_vlr_total") or proposta.get("vl_total_planejamento_gastos") or 0


def calcular_gap(programas_abertos: list[dict], propostas: list[dict]) -> list[dict]:
    ids_usados = {p.get("id_programa") for p in propostas}
    return [p for p in programas_abertos if p["id_programa"] not in ids_usados]


def url_portal_programa(id_programa: int) -> str:
    return PORTAL_URL_PROGRAMA.format(id=id_programa)


def get_programa_detalhe(id_programa: int) -> dict | None:
    data = _cached_get_url(
        f"{PORTAL_API}/programa/{id_programa}", {}, f"portal_programa_{id_programa}"
    )
    if data is None:
        return None
    return {
        "url": url_portal_programa(id_programa),
        "captacaoInicio": data.get("dtaInicioRecebPropEspfic"),
        "captacaoFim": data.get("dtaFimRecebPropEspfic"),
        "recebendoProposta": data.get("recebendoProposta"),
        "condicionantes": [
            r["descricaoRequisito"] for r in (data.get("requisitos") or [])
            if r.get("descricaoRequisito")
        ],
        "anexos": [
            a["anexo"]["descricaoAnexo"] or a["anexo"]["nomeArquivo"]
            for a in (data.get("anexos") or []) if a.get("anexo")
        ],
    }


def gerar_minuta(programa: dict) -> str:
    detalhe = get_programa_detalhe(programa["id_programa"])
    bloco_link = f"\nEDITAL/PROGRAMA NO PORTAL: {detalhe['url']}\n" if detalhe else ""
    bloco_captacao = ""
    if detalhe and (detalhe["captacaoInicio"] or detalhe["captacaoFim"]):
        bloco_captacao = (
            f"\nJANELA DE CAPTAÇÃO: {detalhe['captacaoInicio'] or '?'} a "
            f"{detalhe['captacaoFim'] or '?'}\n"
        )
    bloco_condicionantes = "(nenhum requisito publicado nesse programa até o momento)"
    if detalhe and detalhe["condicionantes"]:
        bloco_condicionantes = "\n".join(f"- {c}" for c in detalhe["condicionantes"])
    bloco_anexos = ""
    if detalhe and detalhe["anexos"]:
        lista = "\n".join(f"- {a}" for a in detalhe["anexos"])
        bloco_anexos = f"\n9. DOCUMENTOS/ANEXOS DO PROGRAMA (baixar no portal)\n{lista}\n"

    return f"""MINUTA DE PLANO DE TRABALHO (rascunho automático — revisar antes de usar)
Gerado em {date.today().isoformat()}

MUNICÍPIO PROPONENTE: {NOME_MUNICIPIO} - {UF_MUNICIPIO}

PROGRAMA: {programa.get('nm_programa')}
CÓDIGO: {programa.get('cd_programa')}
ÓRGÃO REPASSADOR: {programa.get('nm_ente_repassador')}
INSTRUMENTO: {programa.get('tp_instrumento')}
{bloco_link}{bloco_captacao}
1. OBJETO
[Adaptar ao projeto específico de Junqueirópolis a partir do objetivo do programa abaixo]

2. OBJETIVO DO PROGRAMA (referência oficial)
{programa.get('ds_objetivo') or '(não informado pela fonte)'}

3. PROBLEMA QUE O PROGRAMA ENDEREÇA
{programa.get('ds_problema') or '(não informado pela fonte)'}

4. PÚBLICO-ALVO
{programa.get('ds_publico_alvo') or '(não informado pela fonte)'}

5. RESULTADO ESPERADO
{programa.get('ds_resultado_esperado') or '(não informado pela fonte)'}

6. JUSTIFICATIVA LOCAL
[Preencher: por que Junqueirópolis precisa deste recurso — dado local, diagnóstico, demanda]

7. CRONOGRAMA E METAS
[Preencher junto com a secretaria responsável]

8. CONDICIONANTES PARA RECEPÇÃO DE RECURSOS (do portal, cláusula suspensiva)
{bloco_condicionantes}
{bloco_anexos}
---
Fonte dos dados do programa: API pública Transferegov (api-publica.transferegov.gestao.gov.br)
Este documento é um ponto de partida gerado automaticamente. Não substitui análise técnica
nem o formulário oficial exigido pelo órgão repassador.
"""


def montar_radar() -> dict:
    programas_abertos = get_programas_abertos()
    propostas = get_propostas_municipio()
    gap = calcular_gap(programas_abertos, propostas)
    todos_programas = get_todos_programas()
    orgao_por_programa = {p["id_programa"]: p.get("nm_ente_repassador") for p in todos_programas}

    oportunidades = []
    for p in gap:
        detalhe = get_programa_detalhe(p["id_programa"])
        oportunidades.append({
            "idPrograma": p["id_programa"],
            "cdPrograma": p.get("cd_programa"),
            "nmPrograma": p.get("nm_programa"),
            "nmEnteRepassador": p.get("nm_ente_repassador"),
            "tpInstrumento": p.get("tp_instrumento"),
            "urlPortal": detalhe["url"] if detalhe else url_portal_programa(p["id_programa"]),
            "captacaoInicio": detalhe["captacaoInicio"] if detalhe else None,
            "captacaoFim": detalhe["captacaoFim"] if detalhe else None,
            "condicionantes": detalhe["condicionantes"] if detalhe else [],
            "anexos": detalhe["anexos"] if detalhe else [],
            "minuta": gerar_minuta(p),
        })

    historico = []
    for p in propostas:
        historico.append({
            "objeto": (p.get("ds_objeto") or "")[:300],
            "situacao": p.get("situacao_proposta"),
            "valor": valor_proposta(p),
            "data": p.get("dt_proposta"),
            "orgao": orgao_por_programa.get(p.get("id_programa")) or "Não identificado",
        })

    return {
        "geradoEm": date.today().isoformat(),
        "municipio": NOME_MUNICIPIO,
        "ibge": IBGE_JUNQUEIROPOLIS,
        "totalProgramasAbertos": len(programas_abertos),
        "valorHistoricoCaptado": sum(h["valor"] for h in historico),
        "oportunidades": sorted(oportunidades, key=lambda o: o["captacaoFim"] or "9999-99-99"),
        "historico": sorted(historico, key=lambda h: h["data"] or "", reverse=True),
    }


if __name__ == "__main__":
    radar = montar_radar()
    print(json.dumps(radar, ensure_ascii=False, indent=2))
