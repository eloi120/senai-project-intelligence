"""SENAI Project Intelligence — protótipo visual com dados de referência validados.

Para produção: substituir os dados de demonstração pelas views no Supabase.
Não usa OpenAI, n8n nem credenciais nesta versão.
"""

from __future__ import annotations

from datetime import date, datetime
from html import escape
from pathlib import Path

from database import (
    consultar_tarefas,
    consultar_projetos,
    consultar_reunioes,
    consultar_auditoria_riscos,
)

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import requests

BASE_DIR = Path(__file__).resolve().parent
PURPLE = "#6258ED"
INK = "#F5F7FF"
MUTED = "#A7AEC7"

st.set_page_config(
    page_title="SENAI Intelligence | Project Control Center",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------
# Dados demonstrativos: somente valores já validados no projeto.
# Não são consultas em tempo real ao Supabase.
# --------------------------------------------------------------
KPIS = [
    {
        "name": "Projetos monitorados",
        "value": "12",
        "detail": "Portfólio SENAI",
        "symbol": "▦",
        "bg": "linear-gradient(135deg,#141B31,#202343)",
        "ink": "#FF829C",
    },
    {
        "name": "Tarefas consolidadas",
        "value": "122",
        "detail": "119 históricas · 3 automáticas",
        "symbol": "▤",
        "bg": "linear-gradient(135deg,#141B31,#25253B)",
        "ink": "#FFC65D",
    },
    {
        "name": "Atas indexadas",
        "value": "8",
        "detail": "28 trechos no RAG",
        "symbol": "◈",
        "bg": "linear-gradient(135deg,#141B31,#19333A)",
        "ink": "#34D399",
    },
    {
        "name": "Riscos críticos",
        "value": "7",
        "detail": "Identificados nas atas",
        "symbol": "⚑",
        "bg": "linear-gradient(135deg,#141B31,#302244)",
        "ink": "#B59AFF",
    },
]

RANKING = pd.DataFrame(columns=["Projeto", "ID", "Atrasadas", "Líder"])


# Carregar tarefas reais do Supabase
@st.cache_data(ttl=60)
def carregar_tarefas():
    return consultar_tarefas()


registros = carregar_tarefas()

TASKS = pd.DataFrame(registros)


@st.cache_data(ttl=60)
def carregar_projetos():
    return consultar_projetos()


PROJETOS = pd.DataFrame(carregar_projetos())
KPIS[0]["value"] = str(len(PROJETOS))


# Carregar reuniões reais do Supabase
@st.cache_data(ttl=60)
def carregar_reunioes():
    return consultar_reunioes()


REUNIOES = pd.DataFrame(carregar_reunioes())


# Auditoria documental dos riscos — Supabase
@st.cache_data(ttl=60)
def carregar_auditoria_riscos():
    return consultar_auditoria_riscos()


AUDITORIA_RISCOS = pd.DataFrame(carregar_auditoria_riscos())


# Consolidar orçamento e custos reais das reuniões
orcamentos = PROJETOS[["Id_Projeto", "Nome_Projeto", "Orcamento_Previsto"]].copy()

orcamentos["Orcamento_Previsto"] = pd.to_numeric(
    orcamentos["Orcamento_Previsto"], errors="coerce"
).fillna(0)

reunioes_financeiras = REUNIOES.copy()

reunioes_financeiras["custo_reuniao"] = pd.to_numeric(
    reunioes_financeiras["custo_reuniao"], errors="coerce"
).fillna(0)

custos = reunioes_financeiras.groupby("Id_Projeto", as_index=False).agg(
    custo_acumulado=("custo_reuniao", "sum"), total_reunioes=("Id_Reuniao", "count")
)

FINANCEIRO = orcamentos.merge(custos, on="Id_Projeto", how="left")

FINANCEIRO["custo_acumulado"] = FINANCEIRO["custo_acumulado"].fillna(0)

FINANCEIRO["total_reunioes"] = FINANCEIRO["total_reunioes"].fillna(0).astype(int)

FINANCEIRO["percentual_orcamento"] = FINANCEIRO.apply(
    lambda linha: (
        linha["custo_acumulado"] / linha["Orcamento_Previsto"] * 100
        if linha["Orcamento_Previsto"] > 0
        else 0
    ),
    axis=1,
)


# Padronizar os nomes das colunas
TASKS = TASKS.rename(
    columns={
        "id_tarefa": "ID",
        "id_projeto": "Projeto",
        "descricao_tarefa": "Descrição",
        "responsavel": "Responsável",
        "prioridade": "Prioridade",
        "data_prazo": "Prazo",
        "status_tarefa": "Status",
        "origem": "Origem",
    }
)


# Padronizar apenas a exibição dos IDs das tarefas automatizadas.
# Os identificadores originais permanecem intactos no Supabase.
if not TASKS.empty and "ID" in TASKS.columns:

    def formatar_id_tarefa(valor):
        texto = str(valor).strip()

        if texto in {"1", "2", "3"}:
            return f"AUTO-{int(texto):03d}"

        return texto

    TASKS["ID"] = TASKS["ID"].apply(formatar_id_tarefa)


KPIS[1]["value"] = str(len(TASKS))
KPIS[1]["detail"] = (
    f"{(TASKS['Origem'] == 'historica').sum()} históricas · "
    f"{(TASKS['Origem'] == 'automatizada').sum()} automatizadas"
)


# Ranking dinâmico: projetos da categoria Desenvolvimento e IA
projetos_ia = PROJETOS[
    PROJETOS["Categoria"].astype(str).str.strip().eq("Desenvolvimento e IA")
].copy()

projetos_ia["Id_Projeto"] = projetos_ia["Id_Projeto"].astype(str).str.strip()

tarefas_atrasadas = TASKS[TASKS["Status"].eq("Atrasado")].copy()
tarefas_atrasadas["Projeto"] = tarefas_atrasadas["Projeto"].astype(str).str.strip()

contagem = tarefas_atrasadas.groupby("Projeto").size().reset_index(name="Atrasadas")

RANKING = projetos_ia.merge(
    contagem, left_on="Id_Projeto", right_on="Projeto", how="left"
)

RANKING["Atrasadas"] = RANKING["Atrasadas"].fillna(0).astype(int)

RANKING = (
    RANKING.rename(columns={"Nome_Projeto": "Nome", "Lider_Responsavel": "Líder"})
    .sort_values("Atrasadas", ascending=False)
    .head(3)
)

RANKING = RANKING[["Nome", "Id_Projeto", "Atrasadas", "Líder"]].rename(
    columns={"Nome": "Projeto", "Id_Projeto": "ID"}
)


# Converter prazos e calcular dias restantes
TASKS["Prazo"] = pd.to_datetime(TASKS["Prazo"], errors="coerce")

TASKS["Dias restantes"] = (
    TASKS["Prazo"].dt.normalize() - pd.Timestamp.today().normalize()
).dt.days

# Ordenar tarefas atrasadas primeiro
TASKS["ordem_status"] = TASKS["Status"].apply(lambda s: 0 if s == "Atrasado" else 1)

TASKS = (
    TASKS.sort_values(["ordem_status", "Prazo"], na_position="last")
    .drop(columns=["ordem_status"])
    .reset_index(drop=True)
)


# --------------------------------------------------------------
# Identidade visual clara e navegação em botões de verdade.
# --------------------------------------------------------------
st.markdown(
    """
<style>
:root {
--purple:#6258ED;
--purple-2:#7A6FFF;
--ink:#F5F7FF;
--muted:#A7AEC7;
--stroke:#23283C;
--panel:#11182A;
--panel-2:#161F34;
--panel-3:#0D1322;
--sidebar:#0B1020;
--bg:#070B14;
}

html, body, [class*="css"] {
font-family: 'Segoe UI', 'Inter', sans-serif;
}

.stApp {
background:
    radial-gradient(circle at top right, rgba(98,88,237,0.12), transparent 28%),
    radial-gradient(circle at top left, rgba(0,194,255,0.08), transparent 22%),
    linear-gradient(180deg, #070B14 0%, #0B1120 100%);
color: var(--ink);
}

header[data-testid="stHeader"] {
background: rgba(11,16,32,0.75);
backdrop-filter: blur(8px);
border-bottom: 1px solid rgba(255,255,255,0.04);
}

#MainMenu { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }

[data-testid="stSidebar"] {
background: linear-gradient(180deg, #0B1020 0%, #0E1426 100%);
border-right: 1px solid rgba(255,255,255,0.05);
}

[data-testid="stSidebar"] > div:first-child {
padding-top: 1.5rem;
}

[data-testid="stSidebar"] .stButton {
margin: 0 0 5px;
}

[data-testid="stSidebar"] .stButton > button {
width: 100%;
justify-content: flex-start;
text-align: left;
border: 1px solid transparent;
border-radius: 12px;
min-height: 46px;
padding: .68rem .86rem;
font-size: .92rem;
font-weight: 600;
color: #A8B0CA;
background: transparent;
box-shadow: none;
transition: all .16s ease;
}

[data-testid="stSidebar"] .stButton > button:hover {
background: rgba(98,88,237,0.10);
color: #FFFFFF;
border: 1px solid rgba(122,111,255,0.18);
}

[data-testid="stSidebar"] .stButton > button[kind="primary"] {
color: white !important;
background: linear-gradient(110deg,#7166FA,#594CE7) !important;
box-shadow: 0 8px 20px rgba(98,88,237,.28);
}

[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
background: linear-gradient(110deg,#796FFF,#5C4FF0) !important;
}

[data-testid="stMainBlockContainer"] {
max-width: 1540px;
padding-top: 2.2rem;
padding-left: 2.3rem;
padding-right: 2.3rem;
}

[data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlock"] {
background-color: var(--panel);
border-radius: 20px;
}

[data-testid="stVerticalBlockBorderWrapper"] {
border-radius: 20px;
}

[data-testid="stVerticalBlockBorderWrapper"]:has(>div) {
box-shadow: 0 12px 30px rgba(0,0,0,.22);
border: 1px solid rgba(255,255,255,0.04);
}

[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMarkdownContainer"] p {
color: #BCC4DD;
}

h1,h2,h3 {
color: #F5F7FF !important;
letter-spacing: -.035em;
}

h1 { font-size:2rem !important; font-weight:800 !important; }
h2 { font-size:1.38rem !important; font-weight:750 !important; }
h3 { font-size:1.05rem !important; }

[data-testid="stDataFrame"] {
border: 1px solid rgba(255,255,255,0.06);
border-radius: 13px;
overflow: hidden;
}

[data-testid="stButton"] button[kind="secondary"]:not([data-testid="stSidebar"] button) {
border: 1px solid rgba(255,255,255,0.08);
border-radius: 11px;
background: #131A2C;
color: #D9E0F6;
}

[data-testid="stButton"] button[kind="primary"]:not([data-testid="stSidebar"] button) {
background: linear-gradient(110deg,#7166FA,#594CE7);
color: white;
border: none;
border-radius: 11px;
}

[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] > div > div {
background: #0F1526 !important;
color: #F5F7FF !important;
border: 1px solid rgba(255,255,255,0.08) !important;
border-radius: 11px !important;
}

.card-kpi {
min-height: 144px;
border-radius: 18px;
padding: 19px 21px;
position: relative;
overflow: hidden;
}

.kpi-label { color:#4F5670; font-size:.85rem; font-weight:650; }
.kpi-value { color:#20233F; font-size:2.1rem; font-weight:820; margin:12px 0 7px; line-height:1.1; }
.kpi-meta { font-size:.76rem; color:#666E88; }
.kpi-icon {
position:absolute;
right:19px;
top:17px;
width:37px;
height:37px;
border-radius:12px;
background:rgba(255,255,255,.82);
display:flex;
align-items:center;
justify-content:center;
font-size:1.2rem;
font-weight:800;
}

.brand {
display:flex;
align-items:center;
gap:12px;
padding:7px 1px 25px;
}

.brand-icon {
width:45px;
height:45px;
border-radius:14px;
display:flex;
justify-content:center;
align-items:center;
background:linear-gradient(135deg,#756CFF,#5545D6);
color:white;
font-size:1.6rem;
box-shadow:0 6px 20px rgba(102,85,235,.25);
}

.brand-title {
color:#F5F7FF;
font-size:1.12rem;
font-weight:800;
line-height:1.15;
}

.brand-sub {
color:#7E88A8;
font-size:.64rem;
letter-spacing:.115em;
font-weight:700;
margin-top:5px;
}

.sidebar-heading {
color:#697394;
font-weight:750;
letter-spacing:.13em;
font-size:.65rem;
margin:1rem 0 .7rem;
}

.tiny-label {
color:#7E89A8;
font-size:.74rem;
font-weight:750;
letter-spacing:.05em;
text-transform:uppercase;
}

.hero-title {
color:#F5F7FF;
font-weight:830;
font-size:2.0rem;
letter-spacing:-.045em;
line-height:1.2;
margin:.34rem 0 .38rem;
}

.hero-sub {
color:#9EA8C6;
font-size:.90rem;
line-height:1.55;
}

.pill {
display:inline-block;
padding:6px 11px;
border-radius:999px;
background:rgba(98,88,237,0.14);
color:#A89DFF;
font-weight:750;
font-size:.72rem;
border: 1px solid rgba(122,111,255,0.16);
}

.section-heading {
color:#F5F7FF;
font-size:1.1rem;
font-weight:800;
letter-spacing:-.02em;
margin-bottom:.1rem;
}

.section-sub {
color:#8C96B4;
font-size:.79rem;
margin-bottom:.8rem;
}

.soft-panel {
background:#0F1628;
border:1px solid rgba(255,255,255,0.06);
border-radius:14px;
padding:17px 20px;
}

.budget-title {
font-weight:800;
color:#E7EBFA;
font-size:1.05rem;
}

.budget-number {
font-size:1.85rem;
font-weight:820;
color:#8F84FF;
margin-top:4px;
}

.risk-row {
padding:12px 0;
border-bottom:1px solid rgba(255,255,255,0.05);
display:flex;
justify-content:space-between;
gap:10px;
align-items:center;
}

.risk-row:last-child { border-bottom:0; }

.risk-project {
font-size:.78rem;
color:#8D97B7;
font-weight:650;
margin-bottom:3px;
}

.risk-name {
font-size:.85rem;
color:#F3F6FF;
font-weight:700;
}

.risk-dot {
width:9px;
height:9px;
background:#FF718C;
display:inline-block;
border-radius:100%;
margin-right:7px;
}

.status-pill {
display:inline-block;
border-radius:100px;
padding:5px 9px;
font-size:.70rem;
font-weight:780;
white-space:nowrap;
}

.note {
color:#9CA7C7;
font-size:.76rem;
line-height:1.55;
}

.footer {
color:#7B86A7;
font-size:.73rem;
margin-top:25px;
padding-top:16px;
border-top:1px solid rgba(255,255,255,0.06);
}

[data-testid="stMetric"] {
background:#0F1526;
border-radius:15px;
border:1px solid rgba(255,255,255,0.06);
padding:15px;
}

[data-testid="stMetricLabel"] {
color:#8F99B8 !important;
}

[data-testid="stMetricValue"] {
color:#F5F7FF !important;
}

[data-testid="stAlert"] {
border-radius:12px;
background: #101A31;
color: #DCE5FF;
border: 1px solid rgba(255,255,255,0.06);
}

/* Contraste aprimorado para componentes e mensagens */
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] span { color: #B8C3DF; }
[data-testid="stDataFrame"] { color-scheme: dark; }
[data-testid="stDataFrame"] [role="grid"] { background-color: #11182A; }
[data-testid="stProgress"] { color: #CED8F3; }
[data-testid="stSelectbox"] label, [data-testid="stTextInput"] label { color: #DCE5F8; }
[data-testid="stVerticalBlockBorderWrapper"] { background: #11182A; }
.stApp [data-testid="stMarkdownContainer"] { color: #DDE5F7; }
@media(max-width:900px) {
[data-testid="stMainBlockContainer"] {
    padding-left:1rem;
    padding-right:1rem;
}
}

/* Ajustes de contraste e alinhamento — v3 */
.card-kpi { min-height:144px; border:1px solid rgba(255,255,255,.10);box-shadow:0 10px 28px rgba(0,0,0,.2); }
.kpi-label {color:#BCC9E3;}
.kpi-value {color:#F8FAFF;}
.kpi-meta {color:#A7B5D0;}
.kpi-icon {background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.10);}
.tiny-label {
    display:inline-flex;align-items:center;gap:6px;color:#C4D0EF;
    font-size:.72rem;font-weight:750;letter-spacing:.06em;text-transform:uppercase;
    background:#182036;border:1px solid rgba(255,255,255,.1);
    border-radius:999px;padding:8px 13px;line-height:1.25;
    position:relative;z-index:2;margin:0;
}
.top-breadcrumb {padding:5px 0 10px;min-height:38px;display:flex;align-items:center;}
/* Títulos e gráficos legíveis no fundo escuro */
.stApp [data-testid="stMetric"] [data-testid="stMetricLabel"] {color:#B6C5E2 !important;}
</style>
""",
    unsafe_allow_html=True,
)


PAGES = [
    ("Visão Executiva", "▦"),
    ("Gestão de Tarefas", "▤"),
    ("Análise Financeira", "◫"),
    ("Monitoramento de Riscos", "⚑"),
    ("Assistente de IA", "✦"),
]
if "pagina" not in st.session_state:
    st.session_state.pagina = "Visão Executiva"


def navigate(target: str) -> None:
    st.session_state.pagina = target
    st.rerun()


with st.sidebar:
    custom_logo = BASE_DIR / "assets" / "logo_senai.png"
    if custom_logo.exists():
        st.image(str(custom_logo), width=150)
        st.markdown("**SENAI Intelligence**")
        st.caption("PROJECT CONTROL CENTER")
    else:
        st.markdown(
            """
        <div class="brand"><div class="brand-icon">◈</div>
        <div><div class="brand-title">SENAI Intelligence</div>
        <div class="brand-sub">PROJECT CONTROL CENTER</div></div></div>
        """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="sidebar-heading">NAVEGAÇÃO</div>', unsafe_allow_html=True)
    for name, icon in PAGES:
        if st.button(
            f"{icon}    {name}",
            key=f"nav_{name}",
            type="primary" if st.session_state.pagina == name else "secondary",
            use_container_width=True,
        ):
            navigate(name)

    st.markdown(
        '<div class="footer">Projeto técnico SENAI · Protótipo visual<br>Não é um sistema oficial do SENAI.</div>',
        unsafe_allow_html=True,
    )

# Cabeçalho compacto, como o da imagem de referência.
top_left, top_search, top_user = st.columns([2.1, 2.9, 1.1], gap="large")
with top_left:
    st.markdown(
        f'<div class="top-breadcrumb"><span class="tiny-label">PAINEL '
        f'<span style="color:#8B91B8">/</span> '
        f"{escape(st.session_state.pagina.upper())}</span></div>",
        unsafe_allow_html=True,
    )
with top_search:
    search = st.text_input(
        "Pesquisa rápida",
        label_visibility="collapsed",
        placeholder="⌕  Pesquisar projeto, tarefa ou risco...",
        key="global_search",
    )
with top_user:
    st.markdown(
        f'<div style="text-align:right;padding-top:8px"><span class="pill">● PRÉVIA LOCAL</span>'
        f'<div style="color:#ABB0C1;font-size:.72rem;margin-top:6px">{date.today().strftime("%d/%m/%Y")}</div></div>',
        unsafe_allow_html=True,
    )


def header(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="hero-title">{escape(title)}</div>'
        f'<div class="hero-sub">{escape(subtitle)}</div>',
        unsafe_allow_html=True,
    )
    st.write("")


def section(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="section-heading">{escape(title)}</div>'
        f'<div class="section-sub">{escape(subtitle)}</div>',
        unsafe_allow_html=True,
    )


def plotly_base(fig: go.Figure, height: int = 290) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Segoe UI, sans-serif", color="#B2BBDD", size=12),
        margin=dict(l=8, r=6, t=16, b=8),
        showlegend=False,
        hoverlabel=dict(bgcolor="#182238", font_color=INK, font_size=12),
    )
    return fig


def render_ranking() -> None:
    frame = RANKING.sort_values("Atrasadas", ascending=True)
    fig = go.Figure(
        go.Bar(
            x=frame["Atrasadas"],
            y=frame["Projeto"],
            orientation="h",
            marker=dict(color=["#B2A8FF", "#8377F7", "#6258ED"], line=dict(width=0)),
            text=frame["Atrasadas"],
            textposition="outside",
            textfont=dict(color="#EAF0FF", size=13),
            customdata=frame[["Líder", "ID"]].to_numpy(),
            hovertemplate="<b>%{y}</b><br>%{x} tarefas atrasadas<br>Líder: %{customdata[0]}<extra></extra>",
        )
    )
    plotly_base(fig, 275)
    fig.update_xaxes(visible=False, range=[0, 13], fixedrange=True)
    fig.update_yaxes(
        showgrid=False, tickfont=dict(color="#B9C5DC", size=12), fixedrange=True
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def render_risk_donut() -> None:
    labels = ["Pendentes", "Concluídas só na ata", "Sem confirmação"]

    # Uma ata pode ter mais de um encaminhamento para o mesmo risco.
    # Contamos cada risco apenas uma vez.
    if AUDITORIA_RISCOS.empty:
        situacoes = pd.Series(dtype="str")
    else:
        riscos_unicos = AUDITORIA_RISCOS.drop_duplicates(subset=["risco_id"])
        situacoes = riscos_unicos["situacao_declarada"]

    pendentes = int((situacoes == "Pendente").sum())
    concluidas = int((situacoes == "Concluída na ata").sum())
    sem_confirmacao = int((situacoes == "Sem confirmação").sum())

    vals = [pendentes, concluidas, sem_confirmacao]
    total = sum(vals)

    # Mantém o gráfico circular quando ainda não há registros.
    valores_grafico = vals if total > 0 else [1, 0, 0]

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=valores_grafico,
            hole=0.74,
            sort=False,
            marker=dict(
                colors=["#FF7992", "#8A7AF4", "#FFC65D"],
                line=dict(color="#11182A", width=4),
            ),
            textinfo="none",
            hovertemplate="%{label}: %{value} riscos<extra></extra>",
        )
    )

    plotly_base(fig, 238)

    fig.add_annotation(
        text=(
            f"<b>{total}</b><br>"
            "<span style='font-size:12px;color:#9FA3B5'>riscos</span>"
        ),
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=26, color=INK),
    )

    st.plotly_chart(
        fig,
        width="stretch",
        config={"displayModeBar": False},
    )

    st.markdown(
        f"""
        <div style="
            display:flex;
            gap:12px;
            justify-content:center;
            flex-wrap:wrap;
            font-size:.72rem;
            color:#A8B5CF;
        ">
            <span>🔴 {pendentes} pendentes</span>
            <span>🟣 {concluidas} só na ata</span>
            <span>🟡 {sem_confirmacao} sem confirmação</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def risk_badge(value: str) -> str:
    c = {
        "Pendente": ("#442135", "#FF9CB1"),
        "Sem confirmação": ("#40331E", "#FFD185"),
        "Concluída na ata": ("#2D2650", "#B7ACFF"),
    }[value]
    return f'<span class="status-pill" style="background:{c[0]};color:{c[1]}">{escape(value)}</span>'


def task_frame(query: str = "") -> pd.DataFrame:
    f = TASKS.copy()
    if query.strip():
        q = query.casefold()
        f = f[f.apply(lambda r: any(q in str(v).casefold() for v in r.values), axis=1)]
    # Atrasadas primeiro; restantes por proximidade do prazo.
    f["ord_status"] = f["Status"].map({"Atrasado": 0, "No prazo": 1}).fillna(2)
    return f.sort_values(["ord_status", "Prazo"]).drop(columns="ord_status")


def executive() -> None:
    left, right = st.columns([3.5, 1], vertical_alignment="center")
    with left:
        header(
            "Visão geral do portfólio",
            "Informações estratégicas, prioridades e decisões em um só lugar.",
        )
    with right:
        if st.button("Explorar tarefas →", type="primary", use_container_width=True):
            navigate("Gestão de Tarefas")

    cols = st.columns(4, gap="medium")
    for col, item in zip(cols, KPIS):
        with col:
            st.markdown(
                f"""
            <div class="card-kpi" style="background:{item["bg"]}">
                <div class="kpi-label">{escape(item["name"])}</div>
                <div class="kpi-icon" style="color:{item["ink"]}">{item["symbol"]}</div>
                <div class="kpi-value">{item["value"]}</div>
                <div class="kpi-meta">{escape(item["detail"])}</div>
            </div>
            """,
                unsafe_allow_html=True,
            )

    st.write("")
    col_chart, col_risk = st.columns([1.55, 1], gap="medium")
    with col_chart:
        with st.container(border=True):
            section(
                "Projetos com mais atrasos",
                "Ranking validado no Supabase · categoria Desenvolvimento e IA",
            )
            render_ranking()
    with col_risk:
        with st.container(border=True):
            section(
                "Situação dos riscos críticos",
                "Conclusões nas atas não equivalem à confirmação na base",
            )
            render_risk_donut()

    col_budget, col_alerts = st.columns([1, 1.15], gap="medium")

    with col_budget:
        with st.container(border=True):
            # Indicadores financeiros de todos os projetos
            orcamento_total = FINANCEIRO["Orcamento_Previsto"].sum()
            custo_total = FINANCEIRO["custo_acumulado"].sum()
            total_reunioes = int(FINANCEIRO["total_reunioes"].sum())

            percentual_total = (
                custo_total / orcamento_total * 100 if orcamento_total > 0 else 0
            )

            def formatar_real(valor):
                return (
                    f"R$ {valor:,.2f}".replace(",", "X")
                    .replace(".", ",")
                    .replace("X", ".")
                )

            section(
                "Orçamento x reuniões",
                f"Visão consolidada · {len(FINANCEIRO)} projetos",
            )

            st.markdown(
                '<div class="budget-title">Custo acumulado de reuniões</div>'
                f'<div class="budget-number">{formatar_real(custo_total)}</div>',
                unsafe_allow_html=True,
            )

            st.progress(
                min(percentual_total / 100, 1.0),
                text=f"{percentual_total:.2f}% do orçamento previsto em custos de reuniões".replace(
                    ".", ","
                ),
            )

            x, y = st.columns(2)

            x.metric("Orçamento previsto", formatar_real(orcamento_total))

            y.metric("Reuniões", str(total_reunioes))

            if st.button("Ver análise financeira →", use_container_width=True):
                navigate("Análise Financeira")

    with col_alerts:
        with st.container(border=True):
            section("Alertas prioritários", "Pontos que merecem atenção da gestão")

            if not AUDITORIA_RISCOS.empty:
                riscos_pendentes = AUDITORIA_RISCOS[
                    AUDITORIA_RISCOS["situacao_declarada"] == "Pendente"
                ].drop_duplicates(subset=["risco_id"])

                for _, risk in riscos_pendentes.iterrows():
                    projeto_id = str(risk["projeto_ata"])

                    projeto_nome = projeto_id

                    if not PROJETOS.empty:
                        encontrado = PROJETOS[
                            PROJETOS["Id_Projeto"].astype(str) == projeto_id
                        ]
                        if not encontrado.empty:
                            projeto_nome = str(encontrado.iloc[0]["Nome_Projeto"])

                    st.markdown(
                        f"""
                        <div class="risk-row">
                            <div>
                                <div class="risk-project">{escape(projeto_id)} · {escape(projeto_nome)}</div>
                                <div class="risk-name"><span class="risk-dot"></span>{escape(str(risk["risco"]))}</div>
                            </div>
                            {risk_badge("Pendente")}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("Nenhum risco disponível na auditoria.")

            if st.button("Ver todos os riscos  →", use_container_width=True):
                navigate("Monitoramento de Riscos")

    st.markdown(
        '<p class="note">Dados consultados diretamente do Supabase, com cache de 60 segundos. '
        "Indicadores de riscos baseados na análise das atas.</p>",
        unsafe_allow_html=True,
    )


def tasks_page() -> None:
    header(
        "Gestão de tarefas",
        "Acompanhe atividades, prazos e prioridades, com atrasos sempre no topo.",
    )
    st.info(
        "Prévia com quatro tarefas de Beatriz Lima verificadas no banco. A consulta de todas as 122 tarefas será integrada ao Supabase.",
        icon="ℹ️",
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Total de tarefas", len(TASKS))
    c2.metric("Atrasadas", int((TASKS["Status"] == "Atrasado").sum()))
    c3.metric("Concluídas", int((TASKS["Status"] == "Concluído").sum()))
    st.write("")
    with st.container(border=True):
        section(
            "Fila de acompanhamento",
            "Ordenação: atrasadas primeiro; depois dias restantes até o prazo",
        )
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            project_opt = st.selectbox(
                "Projeto",
                ["Todos os projetos"] + sorted(TASKS["Projeto"].unique().tolist()),
            )
        with filter_col2:
            status_opt = st.selectbox(
                "Status", ["Todos os status", "Atrasado", "No prazo"]
            )
        f = task_frame(search)
        if project_opt != "Todos os projetos":
            f = f[f["Projeto"] == project_opt]
        if status_opt != "Todos os status":
            f = f[f["Status"] == status_opt]
        f = f[
            [
                "ID",
                "Projeto",
                "Descrição",
                "Responsável",
                "Prioridade",
                "Prazo",
                "Dias restantes",
                "Status",
            ]
        ]
        st.dataframe(
            f,
            width="stretch",
            hide_index=True,
            height=min(520, 105 + len(f) * 44),
            column_config={
                "Prazo": st.column_config.DateColumn(format="DD/MM/YYYY"),
                "Dias restantes": st.column_config.NumberColumn(
                    help="Valores negativos = dias de atraso"
                ),
            },
        )
        st.download_button(
            "↓  Exportar tarefas exibidas",
            data=f.to_csv(index=False).encode("utf-8-sig"),
            file_name="tarefas_senai_amostra.csv",
            mime="text/csv",
            use_container_width=False,
        )


def finance_page() -> None:
    header(
        "Análise financeira",
        "Compare o orçamento previsto com os custos acumulados das reuniões.",
    )

    # Formatação monetária brasileira
    def moeda(valor):
        return (
            f"R$ {float(valor):,.2f}".replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    if FINANCEIRO.empty:
        st.warning("Nenhum dado financeiro disponível.")
        return

    # Seleção dinâmica do projeto
    projetos_disponiveis = FINANCEIRO.sort_values("Id_Projeto").copy()

    opcoes = projetos_disponiveis["Id_Projeto"].tolist()

    projeto_id = st.selectbox(
        "Selecione o projeto",
        options=opcoes,
        index=opcoes.index("PRJ-004") if "PRJ-004" in opcoes else 0,
        format_func=lambda codigo: (
            f"{codigo} — "
            f"{projetos_disponiveis.loc[projetos_disponiveis['Id_Projeto'] == codigo, 'Nome_Projeto'].iloc[0]}"
        ),
    )

    # Dados do projeto escolhido
    projeto = FINANCEIRO[FINANCEIRO["Id_Projeto"] == projeto_id].iloc[0]

    nome = projeto["Nome_Projeto"]
    orcamento = float(projeto["Orcamento_Previsto"])
    custo = float(projeto["custo_acumulado"])
    percentual = float(projeto["percentual_orcamento"])
    reunioes = int(projeto["total_reunioes"])

    # Indicadores principais
    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Orçamento previsto", moeda(orcamento))
    c2.metric("Custo das reuniões", moeda(custo))
    c3.metric("Percentual utilizado", f"{percentual:.2f}%".replace(".", ","))
    c4.metric("Total de reuniões", reunioes)

    st.write("")

    # Comparação visual
    with st.container(border=True):
        section("Orçamento previsto x custo de reuniões", f"{projeto_id} · {nome}")

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                name="Orçamento previsto",
                y=[nome],
                x=[orcamento],
                orientation="h",
                marker_color="#35345E",
                text=[moeda(orcamento)],
                textposition="inside",
                insidetextanchor="end",
                textfont_color="#F5F7FF",
                hovertemplate="Orçamento: %{x:,.2f}<extra></extra>",
            )
        )

        fig.add_trace(
            go.Bar(
                name="Custo das reuniões",
                y=[nome],
                x=[custo],
                orientation="h",
                marker_color=PURPLE,
                text=[moeda(custo)],
                textposition="outside",
                textfont_color="#EAF0FF",
                hovertemplate="Custo: %{x:,.2f}<extra></extra>",
            )
        )

        fig.update_layout(
            barmode="overlay",
            showlegend=True,
            legend=dict(orientation="h", y=1.35, font_color="#EAF0FF"),
            margin=dict(l=10, r=100, t=55, b=20),
        )

        plotly_base(fig, 270)

        fig.update_xaxes(
            showgrid=True, gridcolor="#263044", tickprefix="R$ ", tickformat="~s"
        )

        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        percentual_texto = f"{percentual:.2f}".replace(".", ",")

        st.markdown(
            f"""
            <div class="soft-panel">
                O projeto <b>{escape(str(nome))}</b> possui orçamento de
                <b>{moeda(orcamento)}</b>.
                Foram registrados <b>{reunioes} encontros</b>,
                totalizando <b>{moeda(custo)}</b> em custos de reuniões,
                equivalentes a <b>{percentual_texto}%</b>
                do orçamento previsto.
                <br>
                <small>
                    Este valor representa somente os custos das reuniões,
                    não todas as despesas do projeto.
                </small>
            </div>
            """,
            unsafe_allow_html=True,
        )


def risks_page() -> None:
    header(
        "Monitoramento de riscos",
        "Evidências documentais confrontadas com os registros do Supabase.",
    )

    if AUDITORIA_RISCOS.empty:
        st.warning("Nenhum encaminhamento disponível na auditoria.")
        return

    df = AUDITORIA_RISCOS.copy()

    # Ordenar os riscos pelo número do projeto
    df = df.sort_values(by=["projeto_ata", "tarefa_ata"], ascending=True, kind="stable")

    # Indicadores baseados na auditoria documental
    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Riscos monitorados", df["risco_id"].nunique())

    c2.metric("Encaminhamentos auditados", len(df))

    c3.metric(
        "Divergências de projeto",
        int((df["resultado_auditoria"] == "Divergência de projeto").sum()),
    )

    c4.metric(
        "Descrições para revisão",
        int((df["resultado_auditoria"] == "Descrição diferente - revisar").sum()),
    )

    st.write("")

    # Opções dinâmicas baseadas nas atas cadastradas
    situacoes = sorted(df["situacao_declarada"].dropna().unique().tolist())

    filtro = st.selectbox(
        "Filtrar situação documental",
        ["Todas as situações"] + situacoes,
    )

    if filtro != "Todas as situações":
        df = df[df["situacao_declarada"] == filtro]

    # Aplicar pesquisa global
    if search.strip():
        termo = search.casefold()

        df = df[
            df.astype(str)
            .apply(
                lambda coluna: coluna.str.casefold().str.contains(termo, regex=False)
            )
            .any(axis=1)
        ]

    # Exibir uma seção por risco, não por tarefa
    for risco_id, grupo in df.groupby("risco_id", sort=False):
        risco = grupo.iloc[0]

        with st.container(border=True):
            st.markdown(
                f"### {escape(str(risco['projeto_ata']))} · "
                f"{escape(str(risco['risco']))}"
            )

            st.caption(
                f"Fonte: {risco['arquivo_ata']} · "
                f"Situação na ata: {risco['situacao_declarada']}"
            )

            st.markdown("**Encaminhamentos documentados:**")

            tabela = grupo[
                [
                    "tarefa_ata",
                    "descricao_ata",
                    "projeto_banco",
                    "status_banco",
                    "resultado_auditoria",
                ]
            ].rename(
                columns={
                    "tarefa_ata": "Tarefa",
                    "descricao_ata": "Encaminhamento da ata",
                    "projeto_banco": "Projeto no banco",
                    "status_banco": "Status no banco",
                    "resultado_auditoria": "Resultado da auditoria",
                }
            )

            st.dataframe(
                tabela,
                use_container_width=True,
                hide_index=True,
            )

            if (grupo["resultado_auditoria"] == "Divergência de projeto").any():
                st.markdown(
                    """
                    <div style="
                        background: #192440;
                        border: 1px solid #35466D;
                        border-radius: 10px;
                        padding: 18px 16px;
                        color: #DCE6FF;
                        font-size: 14px;
                        margin-top: 12px;
                    ">
                        Há tarefas cujo ID existe no Supabase, mas pertence
                        a outro projeto. Esses registros não confirmam
                        o encaminhamento da ata.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            elif (
                grupo["resultado_auditoria"] == "Descrição diferente - revisar"
            ).any():
                st.info(
                    "Algumas descrições diferem entre a ata e o banco. "
                    "É necessária revisão antes de confirmar a correspondência."
                )

    if df.empty:
        st.info("Nenhum risco corresponde aos filtros atuais.")

    st.caption(
        "A situação documental não comprova, isoladamente, "
        "que o risco foi resolvido. A auditoria verifica as "
        "referências das tarefas, sem utilizar palavras-chave."
    )


def assistant_page() -> None:
    header(
        "Assistente de IA",
        "Converse com seu agente inteligente sobre projetos, tarefas, reuniões e atas.",
    )

    if "historico_chat" not in st.session_state:
        st.session_state.historico_chat = []

    if "sessao_chat" not in st.session_state:
        import uuid

        st.session_state.sessao_chat = str(uuid.uuid4())

    # Apresentação visual
    with st.container(border=False):
        st.markdown(
            """
            <div class="soft-panel">
                <div style="color:#A99BFF;font-size:1.08rem;font-weight:800">
                    ✦ SENAI Intelligence AI
                </div>
                <div style="color:#A8B5CF;font-size:.85rem;margin-top:6px">
                    Consultas inteligentes aos dados do Supabase
                    e às atas indexadas com RAG.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Campo de entrada permanece fixo no rodapé
    pergunta = st.chat_input("Pergunte sobre projetos, tarefas, reuniões ou riscos...")

    # Salvar a pergunta antes de renderizar o histórico
    if pergunta:
        st.session_state.historico_chat.append({"role": "user", "content": pergunta})

    # Histórico com rolagem própria e automática
    with st.container(height=480, border=False):
        for mensagem in st.session_state.historico_chat:
            with st.chat_message(mensagem["role"]):
                st.markdown(mensagem["content"])

        if pergunta:
            with st.chat_message("assistant"):
                with st.spinner("Consultando o agente de IA..."):
                    try:
                        resposta_http = requests.post(
                            st.secrets["N8N_WEBHOOK_URL"],
                            headers={"X-SENAI-API-KEY": st.secrets["N8N_API_KEY"]},
                            json={
                                "chatInput": pergunta,
                                "sessionId": st.session_state.sessao_chat,
                            },
                            timeout=120,
                        )

                        resposta_http.raise_for_status()
                        dados = resposta_http.json()

                        resposta = dados.get(
                            "response",
                            "O agente não retornou uma resposta.",
                        )

                        if not isinstance(resposta, str):
                            resposta = str(resposta)

                    except requests.RequestException:
                        resposta = (
                            "Não foi possível comunicar com o agente. "
                            "Verifique se o n8n está funcionando."
                        )

                    except ValueError:
                        resposta = "O n8n respondeu, mas não retornou um JSON válido."

                st.markdown(resposta)

            st.session_state.historico_chat.append(
                {"role": "assistant", "content": resposta}
            )


if st.session_state.pagina == "Visão Executiva":
    executive()
elif st.session_state.pagina == "Gestão de Tarefas":
    tasks_page()
elif st.session_state.pagina == "Análise Financeira":
    finance_page()
elif st.session_state.pagina == "Monitoramento de Riscos":
    risks_page()
else:
    assistant_page()

st.markdown(
    '<div class="footer">SENAI Project Intelligence · Protótipo para avaliação técnica · Interface demonstrativa</div>',
    unsafe_allow_html=True,
)
