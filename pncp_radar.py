import json
import time
from datetime import date, timedelta
from pathlib import Path

import requests

BASE_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
UF_ALVO = "SP"
JANELA_DIAS = 30
MODALIDADES_INTERESSE = {
    10: "Manifestação de Interesse",
    12: "Credenciamento",
}

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_TTL_SECONDS = 6 * 60 * 60


def _cache_path(key: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{key}.json"


def _buscar_modalidade(codigo_modalidade: int, data_inicial: str, data_final: str) -> list[dict]:
    cache_key = f"pncp_{codigo_modalidade}_{data_inicial}_{data_final}"
    cache_file = _cache_path(cache_key)
    if cache_file.exists() and (time.time() - cache_file.stat().st_mtime) < CACHE_TTL_SECONDS:
        return json.loads(cache_file.read_text(encoding="utf-8"))

    resultados = []
    pagina = 1
    while True:
        params = {
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "codigoModalidadeContratacao": codigo_modalidade,
            "pagina": pagina,
            "tamanhoPagina": 50,
        }
        for tentativa in range(3):
            try:
                resp = requests.get(BASE_URL, params=params, timeout=60)
                break
            except requests.exceptions.ReadTimeout:
                if tentativa == 2:
                    raise
                time.sleep(2)
        if resp.status_code == 204:
            break
        resp.raise_for_status()
        dados = resp.json()
        pagina_dados = dados.get("data", [])
        resultados.extend(pagina_dados)
        total_paginas = dados.get("totalPaginas", 1)
        if pagina >= total_paginas or not pagina_dados:
            break
        pagina += 1
        time.sleep(0.3)

    cache_file.write_text(json.dumps(resultados, ensure_ascii=False), encoding="utf-8")
    return resultados


def montar_radar_pncp() -> dict:
    hoje = date.today()
    data_inicial = (hoje - timedelta(days=JANELA_DIAS)).strftime("%Y%m%d")
    data_final = hoje.strftime("%Y%m%d")

    avisos = []
    for codigo, nome_modalidade in MODALIDADES_INTERESSE.items():
        try:
            itens = _buscar_modalidade(codigo, data_inicial, data_final)
        except requests.HTTPError as e:
            avisos.append({"erro": f"Falha ao consultar modalidade {codigo} ({nome_modalidade}): {e}"})
            continue
        for it in itens:
            avisos.append({
                "modalidade": nome_modalidade,
                "orgao": (it.get("orgaoEntidade") or {}).get("razaoSocial"),
                "uf": (it.get("unidadeOrgao") or {}).get("ufSigla"),
                "municipio": (it.get("unidadeOrgao") or {}).get("municipioNome"),
                "objeto": it.get("objetoCompra"),
                "dataPublicacao": it.get("dataPublicacaoPncp"),
                "numeroControlePNCP": it.get("numeroControlePNCP"),
                "linkSistemaOrigem": it.get("linkSistemaOrigem"),
            })

    avisos_validos = [a for a in avisos if "erro" not in a]
    avisos_validos.sort(key=lambda a: (a.get("uf") != UF_ALVO, a.get("dataPublicacao") or ""), reverse=False)

    return {
        "geradoEm": hoje.isoformat(),
        "janelaDias": JANELA_DIAS,
        "modalidadesConsultadas": list(MODALIDADES_INTERESSE.values()),
        "totalAvisos": len(avisos_validos),
        "avisos": avisos_validos,
        "erros": [a["erro"] for a in avisos if "erro" in a],
    }


if __name__ == "__main__":
    print(json.dumps(montar_radar_pncp(), ensure_ascii=False, indent=2))
