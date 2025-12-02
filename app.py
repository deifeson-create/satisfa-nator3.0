import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    layout="wide", 
    page_title="Satisfador 2.0", 
    page_icon="☁️",
    initial_sidebar_state="collapsed"
)

# ==============================================================================
# 🔒 SEGURANÇA - TELA DE BLOQUEIO
# ==============================================================================
if "app_access" not in st.session_state:
    st.session_state["app_access"] = False

if not st.session_state["app_access"]:
    st.markdown("""
    <style>
        .stApp { background-color: #f8f9fa; }
        .lock-screen {
            max-width: 400px; margin: 100px auto; padding: 30px;
            background: white; border-radius: 12px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.05); text-align: center;
        }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<div class='lock-screen'><h2>🔒 Acesso Restrito</h2>", unsafe_allow_html=True)
        senha_sistema = st.text_input("Digite a senha do sistema", type="password")
        
        if st.button("ENTRAR", type="primary", use_container_width=True):
            # Verifica a senha configurada nos Secrets
            if senha_sistema == st.secrets["geral"]["senha_sistema"]:
                st.session_state["app_access"] = True
                st.rerun()
            else:
                st.error("Senha incorreta!")
        st.markdown("</div>", unsafe_allow_html=True)
    
    st.stop() # Para a execução aqui se não tiver senha

# ==============================================================================
# 🛠️ CONFIGURAÇÕES E CARREGAMENTO DE SEGREDOS
# ==============================================================================

# Tenta carregar credenciais dos Secrets (Nuvem) ou usa vazio se não achar
try:
    API_URL_SECRET = st.secrets["api"]["url"]
    API_USER_SECRET = st.secrets["api"]["user"]
    API_PASS_SECRET = st.secrets["api"]["password"]
except:
    # Fallback para rodar local sem secrets configurado (apenas para teste)
    API_URL_SECRET = ""
    API_USER_SECRET = ""
    API_PASS_SECRET = ""

ID_PESQUISA_V2 = "35"
ID_PESQUISA_V3 = "43"

CONTAS_FIXAS = {
    "1":  "117628-ATEL",
    "15": "ATEL Telecom",
    "14": "ATELAtivo-V2",
    "13": "ClienteInterno_V2",
    "12": "TráfegoPago_V2",
    "11": "SUPORTE ATIVO",
    "9":  "Pascoa",
    "7":  "Tráfego pago",
    "5":  "CLIENTE INTERNO",
    "3":  "LABORATÓRIO"
}

# ==============================================================================
# INÍCIO DO SISTEMA REAL
# ==============================================================================

# --- CSS PERSONALIZADO ---
st.markdown("""
<style>
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    [data-testid="stMetricValue"] {
        font-size: 24px;
        font-weight: bold;
        color: #1f2937;
    }
    .stApp {
        background-color: #f3f4f6;
    }
</style>
""", unsafe_allow_html=True)

if "token" not in st.session_state: st.session_state["token"] = None
if "pesquisas_list" not in st.session_state: st.session_state["pesquisas_list"] = []

SETORES_AGENTES = {
    'CANCELAMENTO': ['BARBOSA', 'ELOISA', 'LARISSA', 'EDUARDO', 'CAMILA', 'SAMARA'],
    'NEGOCIACAO': ['CARLA', 'LENK', 'ANA LUIZA', 'JULIETTI', 'RODRIGO', 'MONALISA', 'RAMOM', 'EDNAEL', 'LETICIA', 'RITA', 'MARIANA', 'FLAVIA S', 'URI', 'CLARA', 'WANDERSON', 'APARECIDA', 'CRISTINA', 'CAIO', 'LUKAS'],
    'SUPORTE': ['VALERIO', 'TARCISIO', 'GRANJA', 'ALICE', 'FERNANDO', 'SANTOS', 'RENAN', 'FERREIRA', 'HUEMILLY', 'LOPES', 'LAUDEMILSON', 'RAYANE', 'LAYS', 'JORGE', 'LIGIA', 'ALESSANDRO', 'GEIBSON', 'ROBERTO', 'OLIVEIRA', 'MAURÍCIO', 'AVOLO', 'CLEBER', 'ROMERIO', 'JUNIOR', 'ISABELA', 'WAGNER', 'CLAUDIA', 'ANTONIO', 'JOSE', 'LEONARDO', 'KLEBSON', 'OZENAIDE'],
    'NRC': ['RILDYVAN', 'MILENA', 'ALVES', 'MONICKE', 'AYLA', 'MARIANY', 'EDUARDA', 'MENEZES', 'JUCIENNY', 'MARIA', 'ANDREZA', 'LUZILENE', 'IGO', 'AIDA', 'CARIBÉ', 'MICHELLY', 'ADRIA', 'ERICA', 'HENRIQUE', 'SHYRLEI', 'ANNA', 'JULIA', 'FERNANDES']
}

def normalizar_nome(nome):
    return str(nome).strip().upper() if nome and str(nome) != "nan" else "DESCONHECIDO"

def get_setor(agente):
    nome = normalizar_nome(agente)
    for setor, lista in SETORES_AGENTES.items():
        if any(a in nome for a in lista):
            return setor
    return 'OUTROS'

# --- API ---

def autenticar(url, login, senha):
    try:
        r = requests.post(f"{url}/rest/v2/authuser", json={"login": login, "chave": senha}, timeout=20)
        if r.status_code == 200 and r.json().get("success"):
            return r.json()["result"]["token"]
        st.toast(f"Erro Login: {r.text}", icon="❌")
    except Exception as e:
        st.toast(f"Erro Conexão: {e}", icon="❌")
    return None

def listar_pesquisas(base_url, token, lista_contas, d_ini, d_fim):
    url = f"{base_url}/rest/v2/relPesquisa"
    headers = {"Authorization": f"Bearer {token}"}
    encontradas = []
    
    with st.spinner("Conectando às contas..."):
        for id_conta in lista_contas:
            for page in range(1, 4): 
                try:
                    params = {"data_inicial": d_ini.strftime("%Y-%m-%d"), "data_final": d_fim.strftime("%Y-%m-%d"), "id_conta": id_conta, "page": page, "limit": 100}
                    r = requests.get(url, headers=headers, params=params, timeout=10)
                    if r.status_code != 200: break
                    rows = r.json().get("rows", [])
                    if not rows: break
                    for row in rows:
                        encontradas.append({"id": str(row.get("cod_pesquisa")), "nome": row.get("nom_pesquisa")})
                    if len(rows) < 100: break
                except: break
                
    return list({v['id']: v for v in encontradas}.values())

def baixar_dados_regra_rigida(base_url, token, lista_contas, lista_pesquisas, d_ini, d_fim, limit_size):
    url = f"{base_url}/rest/v2/RelPesqAnalitico"
    headers = {"Authorization": f"Bearer {token}"}
    
    dados_unicos = {} 
    audit_perguntas = {"Aceitas": set(), "Ignoradas": set()}
    
    progresso = st.progress(0, text="Iniciando download...")
    total_steps = len(lista_contas) * len(lista_pesquisas)
    step = 0
    
    for id_conta in lista_contas:
        for id_pesquisa in lista_pesquisas:
            step += 1
            page = 1
            id_pesquisa_str = str(id_pesquisa)
            
            while True:
                progresso.progress(step / max(total_steps, 1), text=f"Baixando Conta {id_conta} | Pesquisa {id_pesquisa} | Pág {page}")
                
                try:
                    params = {
                        "data_inicial": d_ini.strftime("%Y-%m-%d"),
                        "data_final": d_fim.strftime("%Y-%m-%d"),
                        "pesquisa": id_pesquisa,
                        "id_conta": id_conta,
                        "page": page,
                        "limit": limit_size
                    }
                    
                    r = requests.get(url, headers=headers, params=params, timeout=30)
                    if r.status_code != 200: break
                    
                    data = r.json()
                    if not data: break
                    
                    novos_nesta_pagina = 0
                    
                    for bloco in data:
                        nome_pergunta = str(bloco.get("nom_pergunta", "")).strip()
                        nome_lower = nome_pergunta.lower()
                        
                        if id_pesquisa_str == ID_PESQUISA_V3:
                            if "internet" in nome_lower:
                                audit_perguntas["Ignoradas"].add(f"[V3] {nome_pergunta}")
                                continue 
                        
                        audit_perguntas["Aceitas"].add(f"[{id_pesquisa}] {nome_pergunta}")
                            
                        respostas = bloco.get("respostas", [])
                        if respostas:
                            for resp in respostas:
                                protocolo = str(resp.get("num_protocolo", ""))
                                
                                if protocolo and protocolo != "0":
                                    if protocolo not in dados_unicos:
                                        resp['conta_origem_id'] = str(id_conta)
                                        resp['pergunta_origem'] = nome_pergunta
                                        dados_unicos[protocolo] = resp
                                        novos_nesta_pagina += 1
                                else:
                                    chave = f"noprot_{id_conta}_{id_pesquisa}_{len(dados_unicos)}"
                                    resp['conta_origem_id'] = str(id_conta)
                                    resp['pergunta_origem'] = nome_pergunta
                                    dados_unicos[chave] = resp
                                    novos_nesta_pagina += 1
                    
                    if len(data) < (limit_size / 5): 
                        break
                        
                    page += 1
                    if page > 200: break 
                    
                except Exception as e:
                    break
            
    progresso.empty()
    return list(dados_unicos.values()), audit_perguntas

def criar_link_atendimento(protocolo):
    if not protocolo or str(protocolo) == "0": return None
    proto_str = str(protocolo).strip()
    cod = proto_str[-7:] if len(proto_str) >= 7 else proto_str
    return f"https://ateltelecom.matrixdobrasil.ai/atendimento/view/cod_atendimento/{cod}/readonly/true#atendimento-div"

# ==============================================================================
# TELA 1: CONEXÃO API (AGORA PREENCHIDA AUTOMATICAMENTE PELOS SECRETS)
# ==============================================================================

if not st.session_state["token"]:
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("### 🚀 Conectar à Matrix")
            st.caption("Credenciais carregadas com segurança.")
            
            # Campos vêm preenchidos com os segredos, mas editáveis se precisar
            url = st.text_input("URL da API", value=API_URL_SECRET)
            user = st.text_input("Usuário", value=API_USER_SECRET)
            pw = st.text_input("Senha", value=API_PASS_SECRET, type="password")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("CONECTAR", type="primary", use_container_width=True):
                with st.spinner("Autenticando..."):
                    t = autenticar(url, user, pw)
                    if t:
                        st.session_state["token"] = t
                        st.rerun()

# ==============================================================================
# TELA 2: DASHBOARD
# ==============================================================================

else:
    with st.sidebar:
        st.markdown("### Opções")
        limit_page = st.slider("Velocidade (Itens/Req)", 50, 500, 100, 50)
        if st.button("Sair / Logout", use_container_width=True):
            st.session_state["token"] = None
            st.session_state["app_access"] = False # Bloqueia tudo de novo
            st.rerun()

    st.title("Painel de Satisfação")
    
    with st.container(border=True):
        c_datas, c_contas = st.columns([1, 2])
        with c_datas:
            st.markdown("**Período**")
            d_col1, d_col2 = st.columns(2)
            ini = d_col1.date_input("Início", datetime.today() - timedelta(days=1), label_visibility="collapsed")
            fim = d_col2.date_input("Fim", datetime.today(), label_visibility="collapsed")
        with c_contas:
            st.markdown("**Contas**")
            ids = list(CONTAS_FIXAS.keys())
            padrao = ["1"] if "1" in ids else None
            contas_sel = st.multiselect("Contas", ids, format_func=lambda x: f"{x} - {CONTAS_FIXAS[x]}", default=padrao, label_visibility="collapsed")
            
        if st.button("🔎 1. Mapear Pesquisas Disponíveis", use_container_width=True):
            if contas_sel:
                res = listar_pesquisas(API_URL_SECRET, st.session_state["token"], contas_sel, ini, fim)
                st.session_state["pesquisas_list"] = res
                if not res: st.toast("Nenhuma pesquisa encontrada!", icon="⚠️")
                else: st.toast(f"{len(res)} pesquisas encontradas!", icon="✅")
            else:
                st.toast("Selecione pelo menos uma conta.", icon="⚠️")

    if st.session_state["pesquisas_list"]:
        with st.container(border=True):
            st.markdown("#### 2. Análise")
            c_pesq, c_setor, c_btn = st.columns([2, 1, 1])
            with c_pesq:
                opts = {f"{p['id']} - {p['nome']}": p['id'] for p in st.session_state["pesquisas_list"]}
                defaults = [k for k in opts.keys() if ID_PESQUISA_V2 in k or ID_PESQUISA_V3 in k]
                sels = st.multiselect("Pesquisas", list(opts.keys()), default=defaults, label_visibility="collapsed")
                pesquisas_ids = [opts[s] for s in sels]
            with c_setor:
                setor_sel = st.selectbox("Setor", list(SETORES_AGENTES.keys()) + ["TODOS", "OUTROS"], label_visibility="collapsed")
            with c_btn:
                gerar = st.button("✨ GERAR DASHBOARD", type="primary", use_container_width=True)

        if gerar:
            if not pesquisas_ids:
                st.error("Selecione as pesquisas.")
            else:
                raw_data, audit_results = baixar_dados_regra_rigida(
                    API_URL_SECRET, st.session_state["token"], contas_sel, pesquisas_ids, ini, fim, limit_page
                )
                
                with st.expander("Verificar Regras Aplicadas"):
                    c1, c2 = st.columns(2)
                    c1.success(f"Consideradas:\n" + "\n".join(list(audit_results["Aceitas"])))
                    c2.error(f"Descartadas (Internet):\n" + "\n".join(list(audit_results["Ignoradas"])))

                if not raw_data:
                    st.warning("Nenhum dado encontrado.")
                else:
                    df = pd.DataFrame(raw_data)
                    if 'nom_valor' not in df: df['nom_valor'] = 0
                    if 'nom_agente' not in df: df['nom_agente'] = "DESCONHECIDO"
                    
                    df['Nota'] = pd.to_numeric(df['nom_valor'], errors='coerce')
                    df = df.dropna(subset=['Nota']) 
                    df['Nota'] = df['Nota'].astype(int)
                    
                    df['Agente'] = df['nom_agente'].apply(normalizar_nome)
                    df['Setor'] = df['Agente'].apply(get_setor)
                    df['Nome_Conta'] = df['conta_origem_id'].map(CONTAS_FIXAS).fillna("Desconhecida")
                    df['Link_Acesso'] = df['num_protocolo'].apply(criar_link_atendimento)
                    
                    df_final = df if setor_sel == "TODOS" else df[df['Setor'] == setor_sel]
                    
                    if df_final.empty:
                        st.info("Sem dados para este setor.")
                    else:
                        total = len(df_final)
                        prom = len(df_final[df_final['Nota'] >= 8])
                        det = len(df_final[df_final['Nota'] <= 6])
                        sat_score = (prom / total * 100) if total > 0 else 0
                        media = df_final['Nota'].mean()
                        
                        st.markdown("### Resultados")
                        k1, k2, k3, k4 = st.columns(4)
                        k1.metric("Total Avaliações", total)
                        k2.metric("Promotores (8-10)", prom)
                        k3.metric("Satisfação (CSAT)", f"{sat_score:.2f}%", delta_color="normal")
                        k4.metric("Nota Média", f"{media:.2f}")
                        
                        g1, g2 = st.columns([1, 2])
                        with g1:
                            labels = ['Promotores', 'Outros']
                            colors = ['#10b981', '#ef4444'] 
                            fig = go.Figure(data=[go.Pie(labels=labels, values=[prom, total-prom], hole=.7, marker_colors=colors)])
                            fig.update_layout(showlegend=False, margin=dict(t=20,b=20,l=20,r=20), height=250,
                                              annotations=[dict(text=f"{sat_score:.0f}%", x=0.5, y=0.5, font_size=24, showarrow=False)])
                            st.plotly_chart(fig, use_container_width=True)
                        with g2:
                            rank = df_final.groupby('Agente').agg(
                                Qtd=('Nota', 'count'),
                                Promotores=('Nota', lambda x: (x >= 8).sum()),
                                Media=('Nota', 'mean')
                            ).reset_index()
                            rank['Sat %'] = (rank['Promotores'] / rank['Qtd'] * 100).round(1)
                            rank = rank.sort_values('Sat %', ascending=True) 
                            fig_bar = px.bar(rank, x='Sat %', y='Agente', orientation='h', text='Sat %', title="Ranking por Agente", color='Sat %', color_continuous_scale=['#ef4444', '#f59e0b', '#10b981'])
                            fig_bar.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
                            fig_bar.update_layout(xaxis_title="", yaxis_title="", height=300, coloraxis_showscale=False)
                            st.plotly_chart(fig_bar, use_container_width=True)
                        
                        st.subheader("📋 Detalhamento")
                        st.dataframe(
                            df_final[['dat_resposta', 'Nome_Conta', 'Agente', 'Nota', 'nom_resposta', 'Link_Acesso']],
                            column_config={
                                "Link_Acesso": st.column_config.LinkColumn("Ação", display_text="🔗 Abrir", width="small"),
                                "Nota": st.column_config.NumberColumn("Nota", format="%d ⭐", width="small"),
                                "dat_resposta": "Data/Hora",
                                "nom_resposta": "Comentário"
                            },
                            use_container_width=True, hide_index=True
                        )
                        csv = df_final.to_csv(index=False).encode('utf-8')
                        st.download_button("📥 Baixar Relatório (CSV)", csv, "relatorio_satisfador.csv", "text/csv", use_container_width=True)