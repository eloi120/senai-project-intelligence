import streamlit as st
from supabase import create_client


@st.cache_resource
def conectar_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]

    return create_client(url, key)


def consultar_tarefas():
    supabase = conectar_supabase()

    resposta = (
        supabase.table("vw_tarefas_consolidadas").select("*").range(0, 999).execute()
    )

    return resposta.data


def consultar_projetos():
    supabase = conectar_supabase()

    resposta = supabase.table("base_projetos").select("*").range(0, 999).execute()

    return resposta.data


def consultar_reunioes():
    supabase = conectar_supabase()

    resposta = (
        supabase.table("vw_reunioes_tratadas").select("*").range(0, 999).execute()
    )

    return resposta.data


def consultar_auditoria_riscos():
    supabase = conectar_supabase()

    resposta = supabase.table("vw_auditoria_riscos").select("*").range(0, 999).execute()

    return resposta.data
