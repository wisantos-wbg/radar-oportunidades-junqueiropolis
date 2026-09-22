# Radar de Oportunidades — Junqueirópolis/SP

Painel automático diário: cruza os programas abertos do Transferegov com o
histórico de propostas de Junqueirópolis (IBGE 3526001) e mostra o que ainda
não foi usado, mais um radar complementar de credenciamentos/manifestações
de interesse no PNCP. Rodar local: `pip install -r requirements.txt && python
gerar_relatorio.py`. Em produção roda sozinho via GitHub Actions
(`.github/workflows/atualizar-radar.yml`), publicando em `docs/index.html`
(GitHub Pages). Sem chaves de API — as duas fontes são públicas. Minutas são
rascunhos de partida; submissão em qualquer plataforma continua manual.
