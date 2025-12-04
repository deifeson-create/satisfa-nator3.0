import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="Tira-Teima (Debug)", page_icon="🐞")

# ==============================================================================
# 1. CONFIGURAÇÃO E SEGREDOS
# ==============================================================================
try:
    API_URL = st.secrets["api"]["url"]
    API_USER = st.secrets["api"]["user"]
    API_PASS = st.secrets["api"]["password"]
except:
    # Fallback para teste local se não tiver secrets
    API_URL = ""
    API_USER = ""
    API_PASS = ""

# ==============================================================================
# 2. FUNÇÕES DE CONEXÃO
# ==============================================================================
def autenticar():
    try:
        r = requests.post(f"{API_URL}/rest/v2/authuser", json={"login": API_USER, "chave": API_PASS}, timeout=10)
        if r.status_code == 200 and r.json().get("success"):
            return r.json()["result"]["token"]
    except Exception as e:
        st.error(f"Erro ao conectar: {e}")
    return None

def listar_pesquisas(token, conta_id, d_ini, d_fim):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        params = {"data_inicial": d_ini, "data_final": d_fim, "id_conta": conta_id, "page": 1, "limit": 100}
        r = requests.get(f"{API_URL}/rest/v2/relPesquisa", headers=headers, params=params)
        return r.json().get("rows", [])
    except:
        return []

# ==============================================================================
# 3. INTERFACE DE DIAGNÓSTICO
# ==============================================================================
st.title("🐞 Tira-Teima: Diagnóstico de Pesquisa")
st.markdown("""
Este script mostra **exatamente** o que a API devolve e aplica a regra de filtro linha a linha.
Use isso para entender por que a **V2** ou **V3** não estão aparecendo.
""")

if not API_URL:
    st.error("Configure os Secrets (.streamlit/secrets.toml) primeiro!")
    st.stop()

if "token_debug" not in st.session_state:
    st.session_state["token_debug"] = None

# --- LOGIN ---
if not st.session_state["token_debug"]:
    if st.button("Conectar na API"):
        t = autenticar()
        if t:
            st.session_state["token_debug"] = t
            st.rerun()
        else:
            st.error("Falha no Login")
else:
    # --- SELEÇÃO ---
    c1, c2, c3 = st.columns(3)
    dt_ini = c1.date_input("Início", datetime.today() - timedelta(days=2))
    dt_fim = c2.date_input("Fim", datetime.today())
    conta_id = c3.text_input("ID da Conta", "1") # Padrão 1 (ATEL)

    if st.button("Listar Pesquisas Disponíveis"):
        pesquisas = listar_pesquisas(st.session_state["token_debug"], conta_id, dt_ini.strftime("%Y-%m-%d"), dt_fim.strftime("%Y-%m-%d"))
        if not pesquisas:
            st.warning("Nenhuma pesquisa retornada pela API para esta conta/data.")
        else:
            st.session_state["lista_debug"] = pesquisas

    # --- ANÁLISE PROFUNDA ---
    if "lista_debug" in st.session_state:
        opts = {f"{p['cod_pesquisa']} - {p['nom_pesquisa']}": p['cod_pesquisa'] for p in st.session_state["lista_debug"]}
        sel_pesquisa = st.selectbox("Selecione a Pesquisa para Auditar (V2 ou V3)", list(opts.keys()))
        
        if st.button("🕵️ AUDITAR DADOS BRUTOS"):
            id_p = opts[sel_pesquisa]
            headers = {"Authorization": f"Bearer {st.session_state['token_debug']}"}
            
            # Baixa APENAS a primeira página para teste
            params = {
                "data_inicial": dt_ini.strftime("%Y-%m-%d"),
                "data_final": dt_fim.strftime("%Y-%m-%d"),
                "pesquisa": id_p,
                "id_conta": conta_id,
                "page": 1,
                "limit": 100
            }
            
            with st.spinner("Baixando dados brutos da API..."):
                r = requests.get(f"{API_URL}/rest/v2/RelPesqAnalitico", headers=headers, params=params)
                data = r.json()

            st.divider()
            st.subheader(f"Resultado da Auditoria: {sel_pesquisa}")
            
            if not data:
                st.error("🚨 A API retornou uma lista VAZIA ([]).")
                st.info("Motivos possíveis: Ninguém respondeu essa pesquisa nestas datas ou o ID da conta está errado.")
            else:
                st.success(f"A API retornou {len(data)} blocos de dados brutos.")
                
                # --- LOGICA DE TIRA-TEIMA ---
                audit_log = []
                
                for i, bloco in enumerate(data):
                    # Pega o nome da pergunta EXATO como vem da API
                    nome_pergunta = str(bloco.get("nom_pergunta", "SEM_NOME"))
                    nome_lower = nome_pergunta.lower()
                    
                    status = "✅ APROVADO"
                    motivo = "Passou nos filtros"
                    
                    # 1. TESTE DA REGRA DE FILTRO (INTERNET/SERVIÇO)
                    if "internet" in nome_lower or "serviço" in nome_lower or "servico" in nome_lower:
                        status = "❌ RECUSADO"
                        motivo = "Contém 'internet' ou 'serviço' no nome"
                    
                    # 2. TESTE DE RESPOSTAS
                    respostas = bloco.get("respostas", [])
                    qtd_respostas = len(respostas)
                    
                    if qtd_respostas == 0:
                        status = "⚠️ VAZIO"
                        motivo = "Pergunta existe, mas não tem respostas no array"

                    # Adiciona ao log para visualização
                    audit_log.append({
                        "Index": i,
                        "Pergunta (API)": nome_pergunta,
                        "Qtd Respostas": qtd_respostas,
                        "STATUS": status,
                        "MOTIVO": motivo
                    })

                df_audit = pd.DataFrame(audit_log)
                
                # Mostra tabela colorida
                def color_status(val):
                    color = 'green' if 'APROVADO' in val else 'red' if 'RECUSADO' in val else 'orange'
                    return f'color: {color}; font-weight: bold'

                st.dataframe(df_audit.style.applymap(color_status, subset=['STATUS']), use_container_width=True)

                st.markdown("### 🔍 Exemplo da Estrutura Bruta (JSON)")
                st.caption("Verifique se os campos 'nom_pergunta' ou 'respostas' estão vindo como esperado.")
                st.json(data[0])
