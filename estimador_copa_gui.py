#!/usr/bin/env python3
"""
Estimador de Probabilidades - Copa do Mundo 2026 (interface gráfica + IA)
===========================================================================

Pensado para quem NÃO entende de apostas: mostra, em linguagem simples,
a chance estimada de vitória de cada time com base nas odds reais do
mercado, e opcionalmente gera uma breve análise em texto usando IA
(Google Gemini, plano gratuito).

FONTES DE DADOS E CUSTO
------------------------
- Odds reais: The Odds API (https://the-odds-api.com) — grátis, sem cartão.
- Análise em texto: Google Gemini via Google AI Studio
  (https://aistudio.google.com/apikey) — grátis, sem cartão. É opcional;
  o programa funciona normalmente sem essa chave, só não gera o texto.

REQUISITOS
----------
    pip install requests
    (tkinter já vem incluído no Python padrão do Windows/Mac)

COMO RODAR (jeito fácil)
-------------------------
Dê dois cliques no arquivo "iniciar.bat" (Windows), na mesma pasta.

AVISO IMPORTANTE
-----------------
As porcentagens e o texto de análise são ESTIMATIVAS baseadas em odds de
mercado e em um modelo de linguagem — não são garantias de resultado nem
recomendação de aposta. O modelo de IA NUNCA vai sugerir "aposte em X"
por design deste programa. Se você for apostar, aposte com
responsabilidade e apenas valores que pode perder. Isto não é
aconselhamento financeiro.
"""

import json
import os
import threading
import tkinter as tk
import unicodedata
import webbrowser
from datetime import datetime
from tkinter import messagebox, ttk

import requests

SPORT_KEY = "soccer_fifa_world_cup"
ODDS_BASE_URL = f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/odds"
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
SITE_CHAVE_ODDS = "https://the-odds-api.com/"
SITE_CHAVE_GEMINI = "https://aistudio.google.com/apikey"
SITE_CHAVE_FOOTBALL = "https://dashboard.api-football.com/register"

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

FOOTBALL_API_BASE = "https://v3.football.api-sports.io"

# Paleta de cores
BG = "#0f1720"
PAINEL = "#182231"
PAINEL_CLARO = "#21304a"
TEXTO = "#e6edf3"
TEXTO_FRACO = "#8b949e"
VERDE = "#3fb950"
VERMELHO = "#f85149"
AZUL = "#58a6ff"
AMARELO = "#d29922"
ROXO = "#a371f7"


# ---------------------------------------------------------------------------
# Configuração local (chaves de API)
# ---------------------------------------------------------------------------

def carregar_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def salvar_config(novos_dados: dict) -> None:
    config = carregar_config()
    config.update(novos_dados)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f)


# ---------------------------------------------------------------------------
# Lógica de negócio - odds e probabilidades
# ---------------------------------------------------------------------------

def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return texto.lower().strip()


def buscar_jogos(api_key: str) -> list:
    params = {
        "regions": "eu,uk,us",
        "markets": "h2h",
        "oddsFormat": "decimal",
        "apiKey": api_key,
    }
    resposta = requests.get(ODDS_BASE_URL, params=params, timeout=15)
    if resposta.status_code == 401:
        raise ValueError("Essa chave de odds não foi aceita. Confira se copiou certinho, sem espaços.")
    resposta.raise_for_status()
    return resposta.json()


def calcular_probabilidades(jogo: dict):
    home, away = jogo["home_team"], jogo["away_team"]
    probs_casa, probs_empate, probs_fora = [], [], []

    for bookmaker in jogo.get("bookmakers", []):
        for mercado in bookmaker.get("markets", []):
            if mercado["key"] != "h2h":
                continue
            odds = {o["name"]: o["price"] for o in mercado["outcomes"]}
            if home not in odds or away not in odds or "Draw" not in odds:
                continue
            inv_casa = 1 / odds[home]
            inv_empate = 1 / odds["Draw"]
            inv_fora = 1 / odds[away]
            total = inv_casa + inv_empate + inv_fora
            probs_casa.append(inv_casa / total * 100)
            probs_empate.append(inv_empate / total * 100)
            probs_fora.append(inv_fora / total * 100)

    if not probs_casa:
        return None

    return {
        "time_casa": home,
        "time_fora": away,
        "prob_casa": sum(probs_casa) / len(probs_casa),
        "prob_empate": sum(probs_empate) / len(probs_empate),
        "prob_fora": sum(probs_fora) / len(probs_fora),
        "num_casas_apostas": len(probs_casa),
        "horario": jogo.get("commence_time", ""),
    }


def formatar_data(iso_str: str) -> str:
    try:
        dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ")
        return dt.strftime("%d/%m às %H:%M (UTC)")
    except (ValueError, TypeError):
        return iso_str or "—"


# ---------------------------------------------------------------------------
# Lógica de negócio - histórico real (API-Football) para escanteios e cartões
# ---------------------------------------------------------------------------

def buscar_id_time(nome: str, api_key: str):
    """
    Procura um time pelo nome e devolve {'id': ..., 'name': ...} ou None.
    Prioriza correspondência exata e seleções nacionais, para evitar
    confundir "Norway" (seleção) com um clube norueguês qualquer
    (ex: "Brann") que também apareça na busca.
    """
    headers = {"x-apisports-key": api_key}
    resposta = requests.get(
        f"{FOOTBALL_API_BASE}/teams", headers=headers, params={"search": nome}, timeout=15
    )
    if resposta.status_code == 401:
        raise ValueError("Chave de estatísticas inválida. Confira em dashboard.api-football.com.")
    resposta.raise_for_status()
    dados = resposta.json().get("response", [])
    if not dados:
        return None

    nome_normalizado = _normalizar(nome)

    # 1) prioridade: nome exatamente igual E marcado como seleção nacional
    for item in dados:
        time = item["team"]
        if _normalizar(time["name"]) == nome_normalizado and time.get("national"):
            return {"id": time["id"], "name": time["name"]}

    # 2) qualquer seleção nacional cujo nome bate exatamente
    for item in dados:
        time = item["team"]
        if time.get("national") and _normalizar(time["name"]) == nome_normalizado:
            return {"id": time["id"], "name": time["name"]}

    # 3) nome exatamente igual, mesmo que não marcado como seleção
    for item in dados:
        time = item["team"]
        if _normalizar(time["name"]) == nome_normalizado:
            return {"id": time["id"], "name": time["name"]}

    # 4) por último, qualquer seleção nacional entre os resultados
    for item in dados:
        time = item["team"]
        if time.get("national"):
            return {"id": time["id"], "name": time["name"]}

    return None


def buscar_h2h(id1: int, id2: int, api_key: str, ultimos: int = 5) -> list:
    """Busca os últimos confrontos diretos reais entre dois times (pode ser raro para seleções)."""
    headers = {"x-apisports-key": api_key}
    resposta = requests.get(
        f"{FOOTBALL_API_BASE}/fixtures/headtohead",
        headers=headers,
        params={"h2h": f"{id1}-{id2}", "last": ultimos},
        timeout=15,
    )
    resposta.raise_for_status()
    return resposta.json().get("response", [])


def buscar_ultimos_jogos_time(id_time: int, api_key: str, quantidade: int = 5) -> list:
    """Busca os últimos jogos reais de um time, contra qualquer adversário."""
    headers = {"x-apisports-key": api_key}
    resposta = requests.get(
        f"{FOOTBALL_API_BASE}/fixtures",
        headers=headers,
        params={"team": id_time, "last": quantidade},
        timeout=15,
    )
    resposta.raise_for_status()
    return resposta.json().get("response", [])


def _extrair_stat(stats_lista: list, nome_stat: str):
    for item in stats_lista:
        if (item.get("type") or "").lower() == nome_stat.lower():
            try:
                return float(item.get("value"))
            except (TypeError, ValueError):
                return None
    return None


def buscar_estatisticas_fixture(fixture_id: int, api_key: str) -> list:
    headers = {"x-apisports-key": api_key}
    resposta = requests.get(
        f"{FOOTBALL_API_BASE}/fixtures/statistics",
        headers=headers,
        params={"fixture": fixture_id},
        timeout=15,
    )
    if resposta.status_code == 429:
        raise ValueError("Limite diário gratuito da API de estatísticas foi atingido. Tente novamente amanhã.")
    if resposta.status_code == 401:
        raise ValueError("Chave de estatísticas inválida ou expirada.")
    resposta.raise_for_status()
    return resposta.json().get("response", [])


def resumir_forma_recente(id_time: int, fixtures: list) -> dict:
    """
    Resume o retrospecto real de um time nos últimos jogos (vitórias,
    empates, derrotas e placares) usando dados que já vêm na própria
    lista de jogos — não depende do endpoint de estatísticas detalhadas,
    que nem sempre está disponível para seleções no plano gratuito.
    """
    detalhes = []
    vitorias = empates = derrotas = 0

    for fixture in fixtures:
        times = fixture.get("teams", {})
        gols = fixture.get("goals", {})
        if times.get("home", {}).get("id") == id_time:
            adversario = times.get("away", {}).get("name", "?")
            gols_time, gols_adv = gols.get("home"), gols.get("away")
            venceu = times.get("home", {}).get("winner")
        else:
            adversario = times.get("home", {}).get("name", "?")
            gols_time, gols_adv = gols.get("away"), gols.get("home")
            venceu = times.get("away", {}).get("winner")

        if venceu is True:
            resultado, cor = "V", None
            vitorias += 1
        elif venceu is False:
            resultado = "D"
            derrotas += 1
        else:
            resultado = "E"
            empates += 1

        data = (fixture.get("fixture", {}).get("date") or "")[:10]
        detalhes.append(f"{data}: {resultado} {gols_time}x{gols_adv} vs {adversario}")

    return {
        "jogos": len(fixtures),
        "vitorias": vitorias,
        "empates": empates,
        "derrotas": derrotas,
        "detalhes": detalhes,
    }


def calcular_estatisticas_time(id_time: int, fixtures: list, api_key: str):
    """
    Para os últimos jogos REAIS de um time (contra qualquer adversário),
    calcula a média de escanteios e cartões A FAVOR desse time e a % de
    jogos que ultrapassaram linhas comuns — sem nenhuma estimativa ou IA,
    só matemática em cima de estatísticas reais de partidas já ocorridas.
    """
    escanteios_lista, cartoes_lista = [], []

    for fixture in fixtures:
        fixture_id = fixture["fixture"]["id"]
        try:
            stats_resposta = buscar_estatisticas_fixture(fixture_id, api_key)
        except requests.exceptions.RequestException:
            continue

        for time_stats in stats_resposta:
            if time_stats.get("team", {}).get("id") != id_time:
                continue  # queremos só as estatísticas DESSE time, não do adversário
            stats = time_stats.get("statistics", [])
            escanteios = _extrair_stat(stats, "Corner Kicks")
            amarelos = _extrair_stat(stats, "Yellow Cards") or 0
            vermelhos = _extrair_stat(stats, "Red Cards") or 0
            if escanteios is not None:
                escanteios_lista.append(escanteios)
            cartoes_lista.append(amarelos + vermelhos)

    if not escanteios_lista and not cartoes_lista:
        return None

    def pct_acima(lista, limite):
        if not lista:
            return None
        return sum(1 for v in lista if v > limite) / len(lista) * 100

    return {
        "jogos_analisados": max(len(escanteios_lista), len(cartoes_lista)),
        "media_escanteios": (sum(escanteios_lista) / len(escanteios_lista)) if escanteios_lista else None,
        "pct_escanteios_acima_4_5": pct_acima(escanteios_lista, 4.5),
        "media_cartoes": (sum(cartoes_lista) / len(cartoes_lista)) if cartoes_lista else None,
        "pct_cartoes_acima_1_5": pct_acima(cartoes_lista, 1.5),
    }


# ---------------------------------------------------------------------------
# Lógica de negócio - análise em texto via IA (Google Gemini, gratuito)
# ---------------------------------------------------------------------------

def gerar_analise_ia(gemini_key: str, est: dict, contexto_extra: str = None) -> str:
    """
    Pede a um modelo de IA (Gemini) para escrever um comentário
    interpretando os números já calculados (e, se disponível, dados reais
    de forma recente). O modelo é instruído a NUNCA recomendar apostas e
    a se basear apenas nos dados fornecidos — nunca inventar.
    """
    bloco_extra = ""
    if contexto_extra:
        bloco_extra = f"\nDados reais adicionais de forma recente (use-os, mas não invente nada além disso):\n{contexto_extra}\n"

    prompt = f"""
Você é um analista esportivo educativo e cauteloso. Você vai comentar um
confronto de futebol usando SOMENTE os dados abaixo — não invente
estatísticas, notícias, lesões ou informações externas que não estejam
aqui:

- Confronto: {est['time_casa']} x {est['time_fora']}
- Chance de vitória do {est['time_casa']}: {est['prob_casa']:.1f}%
- Chance de empate: {est['prob_empate']:.1f}%
- Chance de vitória do {est['time_fora']}: {est['prob_fora']:.1f}%
- Esses números vêm da média de {est['num_casas_apostas']} casas de apostas
{bloco_extra}
Escreva um comentário (4 a 6 frases, em português do Brasil), em tom
neutro e educativo, explicando o que esses números sugerem sobre o jogo.
Se houver dados de forma recente acima, relacione-os com as
probabilidades de mercado (ex: se o retrospecto recente combina ou
contrasta com o favoritismo indicado pelas odds).

Regras obrigatórias:
- NUNCA recomende apostar, nunca diga "boa aposta", "aposte em" ou
  equivalentes.
- NUNCA prometa ou sugira um resultado como certo.
- Deixe implícito que isso é uma leitura da opinião do mercado e do
  retrospecto recente, não uma previsão garantida.
- Não invente forma recente, lesões, escalações ou notícias que não
  estejam explicitamente nos dados acima.
"""
    corpo = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 700,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    resposta = requests.post(GEMINI_URL, params={"key": gemini_key}, json=corpo, timeout=25)

    if resposta.status_code in (400, 403):
        raise ValueError("Chave de IA inválida, expirada ou sem permissão. Gere uma nova em aistudio.google.com/apikey.")
    if resposta.status_code == 429:
        raise ValueError("Limite gratuito de uso da IA atingido no momento. Tente novamente em alguns minutos.")
    resposta.raise_for_status()

    dados = resposta.json()
    try:
        partes = dados["candidates"][0]["content"]["parts"]
        texto_completo = "".join(p.get("text", "") for p in partes).strip()
        if not texto_completo:
            raise KeyError("resposta vazia")
        return texto_completo
    except (KeyError, IndexError, TypeError):
        motivo = dados.get("promptFeedback", {}).get("blockReason")
        if motivo:
            raise ValueError(f"A IA não gerou resposta (motivo: {motivo}).")
        raise ValueError("Não consegui interpretar a resposta da IA.")


# ---------------------------------------------------------------------------
# Interface gráfica
# ---------------------------------------------------------------------------

class JanelaBoasVindas(tk.Toplevel):
    """Assistente simples exibido na primeira vez que o programa é aberto."""

    def __init__(self, master, ao_concluir):
        super().__init__(master)
        self.ao_concluir = ao_concluir
        self.title("Bem-vindo!")
        self.geometry("500x460")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()

        tk.Label(
            self, text="👋 Bem-vindo ao Estimador de Probabilidades",
            font=("Segoe UI", 13, "bold"), bg=BG, fg=TEXTO, wraplength=440, justify="left",
        ).pack(pady=(20, 8), padx=20, anchor="w")

        texto = (
            "Este programa mostra, em porcentagem, a chance estimada de cada time "
            "vencer um jogo da Copa do Mundo 2026 — com base nas odds reais das "
            "casas de apostas. Você não precisa entender de apostas para usar.\n\n"
            "Para funcionar, precisa de uma chave de acesso gratuita (sem cartão). "
            "A chave de análise por IA é opcional e pode ser configurada depois."
        )
        tk.Label(
            self, text=texto, font=("Segoe UI", 9), bg=BG, fg=TEXTO_FRACO,
            wraplength=440, justify="left",
        ).pack(padx=20, anchor="w")

        passo1 = tk.Frame(self, bg=PAINEL, padx=12, pady=10)
        passo1.pack(fill="x", padx=20, pady=(16, 6))
        tk.Label(
            passo1, text="Passo 1 — Criar a chave de dados (obrigatória)",
            font=("Segoe UI", 9, "bold"), bg=PAINEL, fg=TEXTO,
        ).pack(anchor="w")
        tk.Button(
            passo1, text="🌐 Abrir the-odds-api.com e criar minha chave",
            command=lambda: webbrowser.open(SITE_CHAVE_ODDS),
            bg=AZUL, fg="#0f1720", relief="flat", padx=8, pady=4, cursor="hand2",
        ).pack(anchor="w", pady=(6, 0))

        passo2 = tk.Frame(self, bg=PAINEL, padx=12, pady=10)
        passo2.pack(fill="x", padx=20, pady=(6, 6))
        tk.Label(
            passo2, text="Passo 2 — Colar a chave de dados aqui",
            font=("Segoe UI", 9, "bold"), bg=PAINEL, fg=TEXTO,
        ).pack(anchor="w")
        self.entry_chave = tk.Entry(passo2, width=44, font=("Segoe UI", 9))
        self.entry_chave.pack(anchor="w", pady=(6, 0))

        tk.Label(
            self, text="💡 A chave de IA (Google Gemini) é opcional — configure quando quiser em \"⚙ Configurar chaves\".",
            font=("Segoe UI", 8, "italic"), bg=BG, fg=TEXTO_FRACO,
            wraplength=440, justify="left",
        ).pack(padx=20, pady=(10, 0), anchor="w")

        self.lbl_erro = tk.Label(self, text="", bg=BG, fg=VERMELHO, font=("Segoe UI", 8))
        self.lbl_erro.pack(padx=20, anchor="w")

        tk.Button(
            self, text="Começar a usar →", command=self._concluir,
            bg=VERDE, fg="white", relief="flat", padx=14, pady=6,
            font=("Segoe UI", 10, "bold"), cursor="hand2",
        ).pack(pady=16)

    def _concluir(self):
        chave = self.entry_chave.get().strip()
        if not chave:
            self.lbl_erro.config(text="Cole a chave de dados antes de continuar.")
            return
        salvar_config({"odds_api_key": chave})
        self.destroy()
        self.ao_concluir(chave)


class JanelaDetalhe(tk.Toplevel):
    """Janela com visual grande, explicação e botão de análise por IA. Rolável, para nunca cortar conteúdo."""

    def __init__(self, master, est: dict, gemini_key: str, football_key: str):
        super().__init__(master)
        self.est = est
        self.gemini_key = gemini_key
        self.football_key = football_key
        self.contexto_extra = None
        self.title(f"{est['time_casa']} x {est['time_fora']}")
        self.geometry("480x640")
        self.minsize(420, 360)
        self.configure(bg=BG)
        self.resizable(True, True)

        # --- área rolável: nada fica escondido, mesmo em telas pequenas ---
        canvas_rolagem = tk.Canvas(self, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas_rolagem.yview)
        conteudo = tk.Frame(canvas_rolagem, bg=BG)

        conteudo.bind(
            "<Configure>",
            lambda e: canvas_rolagem.configure(scrollregion=canvas_rolagem.bbox("all")),
        )
        janela_interna = canvas_rolagem.create_window((0, 0), window=conteudo, anchor="nw")
        canvas_rolagem.configure(yscrollcommand=scrollbar.set)

        # a área interna acompanha a largura da janela ao redimensionar
        canvas_rolagem.bind(
            "<Configure>",
            lambda e: canvas_rolagem.itemconfig(janela_interna, width=e.width),
        )

        def _rolar_com_mouse(event):
            canvas_rolagem.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas_rolagem.bind("<Enter>", lambda e: canvas_rolagem.bind_all("<MouseWheel>", _rolar_com_mouse))
        canvas_rolagem.bind("<Leave>", lambda e: canvas_rolagem.unbind_all("<MouseWheel>"))

        canvas_rolagem.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        tk.Label(
            conteudo, text=f"{est['time_casa']}  x  {est['time_fora']}",
            font=("Segoe UI", 14, "bold"), bg=BG, fg=TEXTO,
        ).pack(pady=(20, 4))

        tk.Label(
            conteudo, text=formatar_data(est["horario"]),
            font=("Segoe UI", 9), bg=BG, fg=TEXTO_FRACO,
        ).pack(pady=(0, 14))

        favorito = max(
            [("casa", est["prob_casa"]), ("empate", est["prob_empate"]), ("fora", est["prob_fora"])],
            key=lambda x: x[1],
        )[0]

        linhas = [
            ("casa", f"Vitória de {est['time_casa']}", est["prob_casa"]),
            ("empate", "Empate", est["prob_empate"]),
            ("fora", f"Vitória de {est['time_fora']}", est["prob_fora"]),
        ]

        for chave, rotulo, pct in linhas:
            cor = VERDE if chave == favorito else PAINEL_CLARO
            linha_frame = tk.Frame(conteudo, bg=BG)
            linha_frame.pack(fill="x", padx=24, pady=5)

            topo = tk.Frame(linha_frame, bg=BG)
            topo.pack(fill="x")
            tk.Label(
                topo, text=rotulo, font=("Segoe UI", 10, "bold" if chave == favorito else "normal"),
                bg=BG, fg=TEXTO,
            ).pack(side="left")
            tk.Label(
                topo, text=f"{pct:.1f}%", font=("Segoe UI", 10, "bold"),
                bg=BG, fg=VERDE if chave == favorito else TEXTO,
            ).pack(side="right")

            barra = tk.Canvas(linha_frame, height=16, bg=PAINEL, highlightthickness=0)
            barra.pack(fill="x", pady=(3, 0))
            barra.bind("<Configure>", lambda e, c=barra, p=pct, cor=cor: self._desenhar_barra(c, p, cor))

        tk.Label(
            conteudo,
            text=(
                "💡 Essa porcentagem reflete a opinião do mercado de apostas, "
                "não uma previsão garantida — azarões vencem favoritos com frequência."
            ),
            font=("Segoe UI", 8), bg=BG, fg=TEXTO_FRACO, wraplength=420, justify="left",
        ).pack(padx=24, pady=(14, 4))

        tk.Label(
            conteudo, text=f"Baseado em {est['num_casas_apostas']} casa(s) de apostas diferentes.",
            font=("Segoe UI", 8, "italic"), bg=BG, fg=TEXTO_FRACO,
        ).pack()

        # --- seção de análise por IA ---
        tk.Frame(conteudo, bg=PAINEL_CLARO, height=1).pack(fill="x", padx=24, pady=16)

        cabecalho_ia = tk.Frame(conteudo, bg=BG)
        cabecalho_ia.pack(fill="x", padx=24)
        tk.Label(
            cabecalho_ia, text="🧠 Análise por IA (opcional)",
            font=("Segoe UI", 10, "bold"), bg=BG, fg=ROXO,
        ).pack(side="left")

        self.btn_gerar_ia = tk.Button(
            conteudo, text="Gerar análise em texto", command=self._gerar_analise,
            bg=ROXO, fg="white", relief="flat", padx=10, pady=5, cursor="hand2",
        )
        self.btn_gerar_ia.pack(padx=24, pady=(8, 8), anchor="w")

        self.texto_ia = tk.Text(
            conteudo, height=6, wrap="word", bg=PAINEL, fg=TEXTO, font=("Segoe UI", 9),
            relief="flat", padx=10, pady=8, state="disabled",
        )
        self.texto_ia.pack(fill="x", padx=24)

        tk.Label(
            conteudo,
            text="A IA só interpreta os números acima — ela nunca recomenda apostas. "
                 "Dica: busque o histórico real (abaixo) primeiro para uma análise mais completa.",
            font=("Segoe UI", 7, "italic"), bg=BG, fg=TEXTO_FRACO, wraplength=420, justify="left",
        ).pack(padx=24, pady=(4, 10), anchor="w")

        if not self.gemini_key:
            self._escrever_ia(
                "Você ainda não configurou uma chave de IA (gratuita). "
                "Feche esta janela e clique em \"⚙ Configurar chaves\" para adicionar."
            )
            self.btn_gerar_ia.config(state="disabled")

        # --- seção de histórico real (escanteios e cartões) ---
        tk.Frame(conteudo, bg=PAINEL_CLARO, height=1).pack(fill="x", padx=24, pady=16)

        tk.Label(
            conteudo, text="📊 Histórico real de confrontos diretos",
            font=("Segoe UI", 10, "bold"), bg=BG, fg=AMARELO,
        ).pack(padx=24, anchor="w")

        tk.Label(
            conteudo,
            text="Média de escanteios e cartões dos últimos jogos de cada time (contra qualquer adversário) — dados reais, sem estimativa nem IA.",
            font=("Segoe UI", 8), bg=BG, fg=TEXTO_FRACO, wraplength=420, justify="left",
        ).pack(padx=24, pady=(2, 8), anchor="w")

        self.btn_gerar_stats = tk.Button(
            conteudo, text="Buscar histórico real", command=self._gerar_estatisticas,
            bg=AMARELO, fg="#0f1720", relief="flat", padx=10, pady=5, cursor="hand2",
        )
        self.btn_gerar_stats.pack(padx=24, pady=(0, 8), anchor="w")

        self.texto_stats = tk.Text(
            conteudo, height=7, wrap="word", bg=PAINEL, fg=TEXTO, font=("Segoe UI", 9),
            relief="flat", padx=10, pady=8, state="disabled",
        )
        self.texto_stats.pack(fill="x", padx=24, pady=(0, 20))

        if not self.football_key:
            self._escrever(
                self.texto_stats,
                "Você ainda não configurou a chave de estatísticas (gratuita, API-Football). "
                "Feche esta janela e clique em \"⚙ Configurar chaves\" para adicionar."
            )
            self.btn_gerar_stats.config(state="disabled")

    def _desenhar_barra(self, canvas: tk.Canvas, pct: float, cor: str):
        canvas.delete("all")
        largura = canvas.winfo_width() or 420
        canvas.create_rectangle(0, 0, largura, 16, fill=PAINEL, width=0)
        canvas.create_rectangle(0, 0, largura * (pct / 100), 16, fill=cor, width=0)

    def _escrever(self, widget: tk.Text, texto: str):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", texto)
        widget.config(state="disabled")

    def _escrever_ia(self, texto: str):
        self._escrever(self.texto_ia, texto)

    def _gerar_analise(self):
        self.btn_gerar_ia.config(state="disabled", text="Gerando análise...")
        self._escrever_ia("Gerando análise, aguarde alguns segundos... 🧠")
        threading.Thread(target=self._trabalho_gerar_analise, daemon=True).start()

    def _trabalho_gerar_analise(self):
        try:
            texto = gerar_analise_ia(self.gemini_key, self.est, contexto_extra=getattr(self, "contexto_extra", None))
            self.after(0, lambda: self._escrever_ia(texto))
        except ValueError as e:
            self.after(0, lambda: self._escrever_ia(f"⚠ {e}"))
        except requests.exceptions.RequestException:
            self.after(0, lambda: self._escrever_ia(
                "⚠ Não consegui conectar à IA. Verifique sua internet e tente de novo."
            ))
        finally:
            self.after(0, lambda: self.btn_gerar_ia.config(state="normal", text="Gerar novamente"))

    def _gerar_estatisticas(self):
        self.btn_gerar_stats.config(state="disabled", text="Buscando histórico...")
        self._escrever(self.texto_stats, "Buscando os últimos jogos reais dos dois times, aguarde... 📊")
        threading.Thread(target=self._trabalho_gerar_estatisticas, daemon=True).start()

    def _formatar_stats_time(self, nome: str, resultado: dict) -> str:
        texto = f"⚽ {nome} (últimos {resultado['jogos_analisados']} jogo(s) reais, qualquer adversário)\n"
        if resultado["media_escanteios"] is not None:
            texto += (
                f"   ⛳ Escanteios a favor: média de {resultado['media_escanteios']:.1f} por jogo "
                f"({resultado['pct_escanteios_acima_4_5']:.0f}% dos jogos com mais de 4.5)\n"
            )
        if resultado["media_cartoes"] is not None:
            texto += (
                f"   🟨 Cartões recebidos: média de {resultado['media_cartoes']:.1f} por jogo "
                f"({resultado['pct_cartoes_acima_1_5']:.0f}% dos jogos com mais de 1.5)\n"
            )
        if resultado["jogos_analisados"] < 4:
            texto += "   ⚠ Amostra pequena — número pouco confiável.\n"
        return texto

    def _formatar_forma(self, nome: str, forma: dict) -> str:
        texto = f"📈 {nome} — retrospecto real dos últimos {forma['jogos']} jogos: "
        texto += f"{forma['vitorias']}V {forma['empates']}E {forma['derrotas']}D\n"
        for linha in forma["detalhes"]:
            texto += f"   • {linha}\n"
        return texto

    def _trabalho_gerar_estatisticas(self):
        try:
            time1 = buscar_id_time(self.est["time_casa"], self.football_key)
            time2 = buscar_id_time(self.est["time_fora"], self.football_key)

            if not time1 or not time2:
                self.after(0, lambda: self._escrever(
                    self.texto_stats,
                    "Não encontrei um ou os dois times na base de dados. Tente o nome oficial em inglês."
                ))
                return

            jogos1 = buscar_ultimos_jogos_time(time1["id"], self.football_key, quantidade=5)
            jogos2 = buscar_ultimos_jogos_time(time2["id"], self.football_key, quantidade=5)

            partes_texto = []
            contexto_ia = []

            # --- forma recente real: sempre disponível, não depende do endpoint de estatísticas ---
            if jogos1:
                forma1 = resumir_forma_recente(time1["id"], jogos1)
                partes_texto.append(self._formatar_forma(time1["name"], forma1))
                contexto_ia.append(
                    f"{time1['name']}: {forma1['vitorias']}V {forma1['empates']}E {forma1['derrotas']}D "
                    f"nos últimos {forma1['jogos']} jogos."
                )
            if jogos2:
                partes_texto.append(self._formatar_forma(time2["name"], forma2 := resumir_forma_recente(time2["id"], jogos2)))
                contexto_ia.append(
                    f"{time2['name']}: {forma2['vitorias']}V {forma2['empates']}E {forma2['derrotas']}D "
                    f"nos últimos {forma2['jogos']} jogos."
                )

            # --- escanteios/cartões: melhor esforço, pode não estar disponível para seleções ---
            aviso_stats = None
            resultado1 = resultado2 = None
            try:
                resultado1 = calcular_estatisticas_time(time1["id"], jogos1, self.football_key) if jogos1 else None
                resultado2 = calcular_estatisticas_time(time2["id"], jogos2, self.football_key) if jogos2 else None
            except ValueError as e:
                aviso_stats = str(e)  # ex: limite diário da API atingido

            if resultado1:
                partes_texto.append("\n" + self._formatar_stats_time(time1["name"], resultado1))
            if resultado2:
                partes_texto.append("\n" + self._formatar_stats_time(time2["name"], resultado2))

            if resultado1 and resultado2 and resultado1["media_escanteios"] and resultado2["media_escanteios"]:
                soma_escanteios = resultado1["media_escanteios"] + resultado2["media_escanteios"]
                partes_texto.append(
                    f"\n📐 Soma das médias: ~{soma_escanteios:.1f} escanteios no total do jogo "
                    f"(aproximação simples).\n"
                )
            elif aviso_stats:
                partes_texto.append(f"\n⚠ Escanteios/cartões indisponíveis agora: {aviso_stats}")
            else:
                partes_texto.append(
                    "\nℹ Escanteios/cartões: sem estatísticas detalhadas registradas para os jogos recentes "
                    "desses times (comum em jogos de seleção na base gratuita)."
                )

            self.contexto_extra = " ".join(contexto_ia) if contexto_ia else None

            texto_final = "\n".join(partes_texto) if partes_texto else "Não encontrei nenhum dado disponível para esses times."
            self.after(0, lambda: self._escrever(self.texto_stats, texto_final))

        except ValueError as e:
            self.after(0, lambda: self._escrever(self.texto_stats, f"⚠ {e}"))
        except requests.exceptions.RequestException:
            self.after(0, lambda: self._escrever(
                self.texto_stats, "⚠ Não consegui conectar ao servidor de estatísticas. Tente de novo."
            ))
        finally:
            self.after(0, lambda: self.btn_gerar_stats.config(state="normal", text="Buscar novamente"))



class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Estimador de Probabilidades - Copa do Mundo 2026")
        self.geometry("940x660")
        self.minsize(820, 580)
        self.configure(bg=BG)

        self.odds_api_key = ""
        self.gemini_api_key = ""
        self.football_api_key = ""
        self.jogos_calculados = []

        self._montar_estilo()
        self._montar_topo()
        self._montar_acoes()
        self._montar_resultado()
        self._montar_rodape()

        config = carregar_config()
        self.odds_api_key = config.get("odds_api_key", "")
        self.gemini_api_key = config.get("gemini_api_key", "")
        self.football_api_key = config.get("football_api_key", "")

        if self.odds_api_key:
            self._set_status("Clique em \"Ver todos os jogos\" para começar.", ok=True)
        else:
            self.after(300, lambda: JanelaBoasVindas(self, self._ao_concluir_boas_vindas))

    # -- construção da interface ---------------------------------------------

    def _ao_concluir_boas_vindas(self, chave: str):
        self.odds_api_key = chave
        self._set_status("Tudo pronto! Clique em \"Ver todos os jogos\" para começar.", ok=True)
        self._listar_todos_os_jogos()

    def _montar_estilo(self):
        estilo = ttk.Style(self)
        estilo.theme_use("clam")
        estilo.configure(
            "Treeview", background=PAINEL, fieldbackground=PAINEL, foreground=TEXTO,
            rowheight=32, borderwidth=0, font=("Segoe UI", 9),
        )
        estilo.configure(
            "Treeview.Heading", background=PAINEL_CLARO, foreground=TEXTO,
            borderwidth=0, font=("Segoe UI", 9, "bold"),
        )
        estilo.map("Treeview", background=[("selected", AZUL)])

    def _montar_topo(self):
        frame = tk.Frame(self, bg=BG, pady=14, padx=18)
        frame.pack(fill="x")

        tk.Label(
            frame, text="⚽ Quem tem mais chance de ganhar?",
            font=("Segoe UI", 16, "bold"), bg=BG, fg=TEXTO,
        ).pack(anchor="w")

        tk.Label(
            frame,
            text="Estimativas da Copa do Mundo 2026 com odds reais do mercado + análise opcional por IA.",
            font=("Segoe UI", 9), bg=BG, fg=TEXTO_FRACO,
        ).pack(anchor="w", pady=(2, 10))

        tk.Button(
            frame, text="⚙ Configurar chaves", command=self._abrir_configuracao,
            bg=PAINEL, fg=TEXTO, relief="flat", padx=8, pady=4, cursor="hand2",
        ).pack(side="left")

    def _montar_acoes(self):
        frame = tk.Frame(self, bg=BG, padx=18, pady=4)
        frame.pack(fill="x")

        caixa1 = tk.LabelFrame(
            frame, text="  Já sei os dois times  ", bg=PAINEL, fg=TEXTO,
            font=("Segoe UI", 9, "bold"), bd=1, relief="groove",
        )
        caixa1.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=4)

        linha = tk.Frame(caixa1, bg=PAINEL, pady=10, padx=10)
        linha.pack(fill="x")
        self.entry_time1 = tk.Entry(linha, width=15, font=("Segoe UI", 9))
        self.entry_time1.pack(side="left", padx=4)
        tk.Label(linha, text="x", bg=PAINEL, fg=TEXTO).pack(side="left")
        self.entry_time2 = tk.Entry(linha, width=15, font=("Segoe UI", 9))
        self.entry_time2.pack(side="left", padx=4)
        self.entry_time1.bind("<Return>", lambda e: self._buscar_confronto_especifico())
        self.entry_time2.bind("<Return>", lambda e: self._buscar_confronto_especifico())

        tk.Button(
            caixa1, text="🔍 Ver a chance deste jogo", command=self._buscar_confronto_especifico,
            bg=VERDE, fg="white", relief="flat", padx=10, pady=5, cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        ).pack(pady=(0, 10))

        caixa2 = tk.LabelFrame(
            frame, text="  Não sei ainda, quero ver tudo  ", bg=PAINEL, fg=TEXTO,
            font=("Segoe UI", 9, "bold"), bd=1, relief="groove",
        )
        caixa2.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=4)

        tk.Label(
            caixa2, text="Mostra todos os jogos com odds já divulgadas.",
            bg=PAINEL, fg=TEXTO_FRACO, font=("Segoe UI", 8), wraplength=300, justify="left",
        ).pack(padx=10, pady=(12, 6))

        tk.Button(
            caixa2, text="📋 Ver todos os jogos", command=self._listar_todos_os_jogos,
            bg=VERDE, fg="white", relief="flat", padx=10, pady=5, cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        ).pack(pady=(0, 10))

    def _montar_resultado(self):
        frame = tk.Frame(self, bg=BG, padx=18, pady=8)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame, text="💡 Dê 2 cliques em um jogo para ver o detalhe e gerar a análise por IA.",
            bg=BG, fg=TEXTO_FRACO, font=("Segoe UI", 8, "italic"),
        ).pack(anchor="w", pady=(0, 4))

        colunas = ("favorito", "casa", "empate", "fora", "quando")
        self.tabela = ttk.Treeview(frame, columns=colunas, show="tree headings", height=14)
        self.tabela.heading("#0", text="Confronto")
        self.tabela.heading("favorito", text="Quem é favorito")
        self.tabela.heading("casa", text="% time 1")
        self.tabela.heading("empate", text="% empate")
        self.tabela.heading("fora", text="% time 2")
        self.tabela.heading("quando", text="Quando é")

        self.tabela.column("#0", width=230)
        self.tabela.column("favorito", width=170)
        self.tabela.column("casa", width=90, anchor="center")
        self.tabela.column("empate", width=90, anchor="center")
        self.tabela.column("fora", width=90, anchor="center")
        self.tabela.column("quando", width=150, anchor="center")

        self.tabela.tag_configure("favorito_casa", foreground=VERDE)
        self.tabela.tag_configure("favorito_fora", foreground=VERDE)
        self.tabela.tag_configure("equilibrado", foreground=AMARELO)

        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=scroll.set)
        self.tabela.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")

        self.tabela.bind("<Double-1>", self._abrir_detalhe)

    def _montar_rodape(self):
        rodape = tk.Frame(self, bg=PAINEL_CLARO)
        rodape.pack(fill="x", side="bottom")

        tk.Label(
            rodape,
            text=(
                "🔞 Jogo responsável: estimativas e análises são conteúdo educativo, "
                "não garantia de resultado nem aconselhamento financeiro. "
                "A IA nunca recomenda apostas. Aposte só o que pode perder."
            ),
            bg=PAINEL_CLARO, fg=TEXTO_FRACO, font=("Segoe UI", 8),
            wraplength=900, justify="left", padx=12, pady=6,
        ).pack(anchor="w")

        self.status = tk.Label(
            self, text="Pronto.", anchor="w", bg=PAINEL_CLARO, fg=TEXTO_FRACO,
            font=("Segoe UI", 8), padx=12, pady=4,
        )
        self.status.pack(fill="x", side="bottom")

    # -- configuração ----------------------------------------------------------

    def _abrir_configuracao(self):
        janela = tk.Toplevel(self)
        janela.title("Configurar chaves")
        janela.geometry("460x600")
        janela.configure(bg=BG)
        janela.resizable(False, False)

        # -- chave de odds --
        tk.Label(
            janela, text="1. Chave de dados de odds (obrigatória)",
            font=("Segoe UI", 10, "bold"), bg=BG, fg=TEXTO,
        ).pack(pady=(18, 4), padx=20, anchor="w")

        entry_odds = tk.Entry(janela, width=48, font=("Segoe UI", 9), show="•")
        entry_odds.pack(padx=20, anchor="w")
        entry_odds.insert(0, self.odds_api_key)

        tk.Button(
            janela, text="🌐 Criar chave grátis (the-odds-api.com)",
            command=lambda: webbrowser.open(SITE_CHAVE_ODDS),
            bg=AZUL, fg="#0f1720", relief="flat", padx=8, pady=3, cursor="hand2",
            font=("Segoe UI", 8),
        ).pack(padx=20, pady=(6, 0), anchor="w")

        # -- chave de IA --
        tk.Label(
            janela, text="2. Chave de IA / Google Gemini (opcional)",
            font=("Segoe UI", 10, "bold"), bg=BG, fg=TEXTO,
        ).pack(pady=(20, 4), padx=20, anchor="w")

        entry_gemini = tk.Entry(janela, width=48, font=("Segoe UI", 9), show="•")
        entry_gemini.pack(padx=20, anchor="w")
        entry_gemini.insert(0, self.gemini_api_key)

        tk.Button(
            janela, text="🌐 Criar chave grátis (aistudio.google.com)",
            command=lambda: webbrowser.open(SITE_CHAVE_GEMINI),
            bg=ROXO, fg="white", relief="flat", padx=8, pady=3, cursor="hand2",
            font=("Segoe UI", 8),
        ).pack(padx=20, pady=(6, 0), anchor="w")

        # -- chave de estatísticas históricas --
        tk.Label(
            janela, text="3. Chave de histórico real / API-Football (opcional)",
            font=("Segoe UI", 10, "bold"), bg=BG, fg=TEXTO,
        ).pack(pady=(20, 4), padx=20, anchor="w")

        entry_football = tk.Entry(janela, width=48, font=("Segoe UI", 9), show="•")
        entry_football.pack(padx=20, anchor="w")
        entry_football.insert(0, self.football_api_key)

        tk.Button(
            janela, text="🌐 Criar chave grátis (dashboard.api-football.com)",
            command=lambda: webbrowser.open(SITE_CHAVE_FOOTBALL),
            bg=AMARELO, fg="#0f1720", relief="flat", padx=8, pady=3, cursor="hand2",
            font=("Segoe UI", 8),
        ).pack(padx=20, pady=(6, 0), anchor="w")

        mostrar_var = tk.BooleanVar(value=False)

        def alternar():
            show = "" if mostrar_var.get() else "•"
            entry_odds.config(show=show)
            entry_gemini.config(show=show)
            entry_football.config(show=show)

        tk.Checkbutton(
            janela, text="Mostrar chaves", variable=mostrar_var, command=alternar,
            bg=BG, fg=TEXTO_FRACO, selectcolor=BG, activebackground=BG,
            font=("Segoe UI", 8),
        ).pack(padx=20, pady=(12, 0), anchor="w")

        def salvar():
            odds_chave = entry_odds.get().strip()
            gemini_chave = entry_gemini.get().strip()
            football_chave = entry_football.get().strip()
            if not odds_chave:
                messagebox.showwarning("Atenção", "A chave de dados de odds é obrigatória.")
                return
            salvar_config({
                "odds_api_key": odds_chave,
                "gemini_api_key": gemini_chave,
                "football_api_key": football_chave,
            })
            self.odds_api_key = odds_chave
            self.gemini_api_key = gemini_chave
            self.football_api_key = football_chave
            self._set_status("Chaves atualizadas com sucesso.", ok=True)
            janela.destroy()

        tk.Button(
            janela, text="Salvar", command=salvar,
            bg=VERDE, fg="white", relief="flat", padx=14, pady=5, cursor="hand2",
        ).pack(pady=16)

    # -- utilitários de interface ----------------------------------------------

    def _set_status(self, texto: str, ok: bool = True):
        self.status.config(text=texto, fg=VERDE if ok else VERMELHO)

    def _limpar_tabela(self):
        for item in self.tabela.get_children():
            self.tabela.delete(item)

    def _adicionar_linha(self, est: dict):
        diferenca = est["prob_casa"] - est["prob_fora"]
        if abs(diferenca) < 8:
            favorito_texto, tag = "🟡 Equilibrado", "equilibrado"
        elif diferenca > 0:
            favorito_texto, tag = f"🟢 {est['time_casa']}", "favorito_casa"
        else:
            favorito_texto, tag = f"🟢 {est['time_fora']}", "favorito_fora"

        item_id = self.tabela.insert(
            "", "end",
            text=f"{est['time_casa']}  x  {est['time_fora']}",
            values=(
                favorito_texto,
                f"{est['prob_casa']:.0f}%",
                f"{est['prob_empate']:.0f}%",
                f"{est['prob_fora']:.0f}%",
                formatar_data(est["horario"]),
            ),
            tags=(tag,),
        )
        self.jogos_calculados.append((item_id, est))

    def _abrir_detalhe(self, _evento):
        selecionado = self.tabela.selection()
        if not selecionado:
            return
        item_id = selecionado[0]
        for iid, est in self.jogos_calculados:
            if iid == item_id:
                JanelaDetalhe(self, est, self.gemini_api_key, self.football_api_key)
                return

    # -- ações que disparam chamadas de rede (em thread separada) --------------

    def _garantir_chave(self) -> bool:
        if not self.odds_api_key:
            resposta = messagebox.askyesno(
                "Chave necessária",
                "Você ainda não configurou sua chave de dados de odds.\n\nDeseja configurar agora?",
            )
            if resposta:
                self._abrir_configuracao()
            return False
        return True

    def _buscar_confronto_especifico(self):
        if not self._garantir_chave():
            return
        time1 = self.entry_time1.get().strip()
        time2 = self.entry_time2.get().strip()
        if not time1 or not time2:
            messagebox.showinfo("Faltou informação", "Digite o nome dos dois times, em inglês (ex: Brazil, England).")
            return

        self._set_status("Procurando esse jogo... 🔎", ok=True)
        threading.Thread(
            target=self._trabalho_buscar_confronto, args=(time1, time2), daemon=True
        ).start()

    def _trabalho_buscar_confronto(self, time1, time2):
        try:
            jogos = buscar_jogos(self.odds_api_key)
            busca1, busca2 = _normalizar(time1), _normalizar(time2)
            encontrado = None
            for jogo in jogos:
                nomes = {_normalizar(jogo["home_team"]), _normalizar(jogo["away_team"])}
                if any(busca1 in n for n in nomes) and any(busca2 in n for n in nomes):
                    encontrado = jogo
                    break

            if not encontrado:
                self.after(0, lambda: self._set_status(
                    "Não achei esse jogo. Tente o nome do time em inglês (ex: Brazil, Mexico, England).",
                    ok=False,
                ))
                return

            est = calcular_probabilidades(encontrado)
            if not est:
                self.after(0, lambda: self._set_status(
                    "Esse jogo existe, mas as casas de apostas ainda não divulgaram odds.", ok=False
                ))
                return

            def atualizar():
                self._limpar_tabela()
                self.jogos_calculados.clear()
                self._adicionar_linha(est)
                self._set_status("Encontrado! Dê 2 cliques no jogo para ver o detalhe.", ok=True)

            self.after(0, atualizar)

        except ValueError as e:
            self.after(0, lambda: self._set_status(str(e), ok=False))
        except requests.exceptions.RequestException:
            self.after(0, lambda: self._set_status(
                "Não consegui conectar à internet. Verifique sua conexão e tente de novo.", ok=False
            ))

    def _listar_todos_os_jogos(self):
        if not self._garantir_chave():
            return
        self._set_status("Buscando todos os jogos disponíveis... 🔎", ok=True)
        threading.Thread(target=self._trabalho_listar_jogos, daemon=True).start()

    def _trabalho_listar_jogos(self):
        try:
            jogos = buscar_jogos(self.odds_api_key)
            if not jogos:
                self.after(0, lambda: self._set_status(
                    "Nenhum jogo com odds publicadas no momento.", ok=False
                ))
                return

            estimativas = []
            for jogo in jogos:
                est = calcular_probabilidades(jogo)
                if est:
                    estimativas.append(est)

            def atualizar():
                self._limpar_tabela()
                self.jogos_calculados.clear()
                for est in estimativas:
                    self._adicionar_linha(est)
                self._set_status(f"{len(estimativas)} jogo(s) encontrado(s).", ok=True)

            self.after(0, atualizar)

        except ValueError as e:
            self.after(0, lambda: self._set_status(str(e), ok=False))
        except requests.exceptions.RequestException:
            self.after(0, lambda: self._set_status(
                "Não consegui conectar à internet. Verifique sua conexão e tente de novo.", ok=False
            ))


if __name__ == "__main__":
    app = App()
    app.mainloop()
