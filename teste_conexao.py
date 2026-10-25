from database import consultar_tarefas

tarefas = consultar_tarefas()

print(f"Total de tarefas encontradas: {len(tarefas)}")

if tarefas:
    print("Primeira tarefa:")
    print(tarefas[0])


import streamlit as st

st.title("Teste de conexão — Supabase")
st.success(f"Total de tarefas encontradas: {len(tarefas)}")
