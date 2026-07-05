# ⚽ Estimador de Probabilidades - Copa do Mundo 2026

Interface gráfica em Python que mostra, em porcentagem, a chance estimada
de vitória de cada time em jogos da Copa do Mundo 2026 — com base em
odds reais de bookmakers — além de análise opcional por IA e histórico
recente real de cada time.

## ✨ Funcionalidades

- Probabilidades calculadas a partir de odds reais (The Odds API), removendo
  a margem das casas de apostas (overround)
- Análise em texto gerada por IA (Google Gemini), interpretando os números
  sem nunca recomendar apostas
- Retrospecto recente real de cada time (vitórias/empates/derrotas e placares)
- Estatísticas de escanteios e cartões dos últimos jogos, quando disponíveis
  (API-Football)
- Interface pensada para quem não entende de apostas: linguagem simples,
  onboarding guiado e avisos de jogo responsável

## 📦 Requisitos

- Python 3.10+
- `pip install -r requirements.txt`

## 🔑 Chaves necessárias (todas com plano gratuito, sem cartão de crédito)

| Chave | Uso | Obrigatória? | Onde criar |
|---|---|---|---|
| Odds API | Probabilidades de vitória | Sim | https://the-odds-api.com/ |
| Gemini | Análise em texto por IA | Não | https://aistudio.google.com/apikey |
| API-Football | Retrospecto/estatísticas reais | Não | https://dashboard.api-football.com/register |

## 🚀 Como rodar

**Windows (mais fácil):** dê 2 cliques em `iniciar.bat`.

**Linha de comando (qualquer sistema):**
```bash
pip install -r requirements.txt
python estimador_copa_gui.py
```

Na primeira execução, a interface guia você para colar a chave da Odds
API. As demais chaves são opcionais e podem ser configuradas depois pelo
botão "⚙ Configurar chaves".

## ⚠️ Aviso importante

Este projeto tem fins educativos e informativos. As porcentagens e
análises são estimativas baseadas em odds de mercado e dados históricos
— não são garantias de resultado nem aconselhamento financeiro. Se você
for apostar, aposte com responsabilidade e apenas valores que pode
perder.

## 🔒 Segurança

O arquivo `config.json` (onde as chaves ficam salvas localmente) está no
`.gitignore` e nunca deve ser commitado. Se você acidentalmente subir uma
chave de API para um repositório público, revogue-a imediatamente no
painel do respectivo serviço e gere uma nova.
