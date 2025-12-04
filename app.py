import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    layout="wide", 
    page_title="Satisfador 3.0 Pro", 
    page_icon="🛡️",
    initial_sidebar_state="expanded"
)

# --- ESTADO ---
if "app_access" not in st.session_state: st.session_state["app_access"] = False
if "token" not in st.session_state: st.session_state["token"] = None
if "pesquisas_list" not in st.session_state: st.session_state["pesquisas_list"] = []
if "servicos_list" not in st.session_state: st.session_state["servicos_list"] = [] 

# IDs CRÍTICOS (Mapeados dos arquivos)
ID_PESQUISA_V3 = "43"
ID_PERGUNTA_IGNORAR_V3 = "40" # ID da pergunta de Internet (Técnico)

# --- SEGREDOS ---
try:
    SECRET_SYS_PASS = st.secrets["geral"]["senha_sistema"]
    API_URL_SECRET = st.secrets["api"]["url"]
    API_USER_SECRET = st.secrets["api"]["user"]
    API_PASS_SECRET = st.secrets["api"]["password"]
except:
    SECRET_SYS_PASS = "admin" 
    API_URL_SECRET = ""
    API_USER_SECRET = ""
    API_PASS_SECRET = ""

CONTAS_FIXAS = {
    "1":  "117628-ATEL", "15": "ATEL Telecom", "14": "ATELAtivo-V2",
    "13": "ClienteInterno_V2", "12": "TráfegoPago_V2", "11": "SUPORTE ATIVO",
    "9":  "Pascoa", "7":  "Tráfego pago", "5":  "CLIENTE INTERNO", "3":  "LABORATÓRIO"
}

SETORES_AGENTES = {
    'CANCELAMENTO': ['BARBOSA', 'ELOISA', 'LARISSA', 'EDUARDO', 'CAMILA', 'SAMARA'],
    'NEGOCIACAO': ['CARLA', 'LENK', 'ANA LUIZA', 'JULIETTI', 'RODRIGO', 'MONALISA', 'RAMOM', 'EDNAEL', 'LETICIA', 'RITA', 'MARIANA', 'FLAVIA S', 'URI', 'CLARA', 'WANDERSON', 'APARECIDA', 'CRISTINA', 'CAIO', 'LUKAS'],
    'SUPORTE': ['VALERIO', 'TARCISIO', 'GRANJA', 'ALICE', 'FERNANDO', 'SANTOS', 'RENAN', 'FERREIRA', 'HUEMILLY', 'LOPES', 'LAUDEMILSON', 'RAYANE', 'LAYS', 'JORGE', 'LIGIA', 'ALESSANDRO', 'GEIBSON', 'ROBERTO', 'OLIVEIRA', 'MAURÍCIO', 'AVOLO', 'CLEBER', 'ROMERIO', 'JUNIOR', 'ISABELA', 'WAGNER', 'CLAUDIA', 'ANTONIO', 'JOSE', 'LEONARDO', 'KLEBSON', 'OZENAIDE'],
    'NRC': ['RILDYVAN', 'MILENA', 'ALVES', 'MONICKE', 'AYLA', 'MARIANY', 'EDUARDA', 'MENEZES', 'JUCIENNY', 'MARIA', 'ANDREZA', 'LUZILENE', 'IGO', 'AIDA', 'CARIBÉ', 'MICHELLY', 'ADRIA', 'ERICA', 'HENRIQUE', 'SHYRLEI', 'ANNA', 'JULIA', 'FERNANDES']
}

# --- AUXILIARES ---
def normalizar_nome(nome):
    return str(nome).strip().upper() if nome and str(nome) != "nan" else "DESCONHECIDO"

def get_setor(agente):
    nome = normalizar_nome(agente)
    for setor, lista in SETORES_AGENTES.items():
        if any(a in nome for a in lista): return setor
    return 'OUTROS'

def criar_link_atendimento(protocolo):
    if not protocolo or str(protocolo) in ["0", "nan", "None", ""]: return None
    proto_str = str(protocolo).strip().replace('.0', '')
    cod = proto_str[-7:] if len(proto_str) >= 7 else proto_str
    domain = API_URL_SECRET.replace("/rest/v2", "").replace("https://", "") if API_URL_SECRET else "ateltelecom.matrixdobrasil.ai"
    if "api" in domain: domain = "ateltelecom.matrixdobrasil.ai" 
    return f"https://{domain}/atendimento/view/cod_atendimento/{cod}/readonly/true#atendimento-div"

# --- API ---
def autenticar(url, login, senha):
    if not url or not login: return None
    try:
        r = requests.post(f"{url}/rest/v2/authuser", json={"login": login, "chave": senha}, timeout=20)
        if r.status_code == 200 and r.json().get("success"): return r.json()["result"]["token"]
    except: pass
    return None

def listar_pesquisas(base_url, token, lista_contas, d_ini, d_fim):
    url = f"{base_url}/rest/v2/relPesquisa"
    headers = {"Authorization": f"Bearer {token}"}
    encontradas = []
    with st.spinner("Mapeando pesquisas..."):
        for id_conta in lista_contas:
            try:
                params = {"data_inicial": d_ini.strftime("%Y-%m-%d"), "data_final": d_fim.strftime("%Y-%m-%d"), "id_conta": id_conta, "page": 1, "limit": 100}
                r = requests.get(url, headers=headers, params=params, timeout=10)
                if r.status_code == 200:
                    for row in r.json().get("rows", []):
                        encontradas.append({"id": str(row.get("cod_pesquisa")), "nome": row.get("nom_pesquisa")})
            except: pass
    return list({v['id']: v for v in encontradas}.values())

def listar_servicos_api(base_url, token, id_conta, d_ini, d_fim):
    """
    Busca os serviços ativos na conta usando o relatório estatístico.
    Inclui estratégia de fallback para evitar timeouts em períodos longos.
    """
    url = f"{base_url}/rest/v2/relAtEstatistico" 
    headers = {"Authorization": f"Bearer {token}"}
    servicos_encontrados = set()
    
    with st.spinner("Carregando serviços da conta..."):
        
        # --- ESTRATÉGIA 1: Tenta o período completo ---
        sucesso_full = False
        try:
            params = {
                "data_inicial": d_ini.strftime("%Y-%m-%d 00:00:00"),
                "data_final": d_fim.strftime("%Y-%m-%d 23:59:59"),
                "id_conta": id_conta,
                "agrupador": "servico",
                "limit": 500 
            }
            # Timeout aumentado para 25s
            r = requests.get(url, headers=headers, params=params, timeout=25)
            
            if r.status_code == 200:
                data = r.json()
                rows = data if isinstance(data, list) else data.get("rows", [])
                if rows:
                    sucesso_full = True
                    for row in rows:
                        nome = row.get("agrupador") 
                        if nome and nome != "ATENDIMENTO AUTOMATICO":
                            servicos_encontrados.add(str(nome).upper())
        except Exception:
            pass # Falha silenciosa para ir para o fallback

        # --- ESTRATÉGIA 2: Fallback (Últimos 30 dias) ---
        # Se a busca completa falhou ou veio vazia, tenta pegar só os últimos 30 dias
        if not servicos_encontrados:
            try:
                dt_fallback_ini = d_fim - timedelta(days=30)
                if dt_fallback_ini < d_ini: dt_fallback_ini = d_ini 

                params_fallback = {
                    "data_inicial": dt_fallback_ini.strftime("%Y-%m-%d 00:00:00"),
                    "data_final": d_fim.strftime("%Y-%m-%d 23:59:59"),
                    "id_conta": id_conta,
                    "agrupador": "servico",
                    "limit": 500
                }
                
                r = requests.get(url, headers=headers, params=params_fallback, timeout=15)
                
                if r.status_code == 200:
                    data = r.json()
                    rows = data if isinstance(data, list) else data.get("rows", [])
                    for row in rows:
                        nome = row.get("agrupador") 
                        if nome and nome != "ATENDIMENTO AUTOMATICO":
                            servicos_encontrados.add(str(nome).upper())
                    
                    if servicos_encontrados:
                        st.toast("⚠️ Período longo: serviços listados com base nos últimos 30 dias.", icon="ℹ️")
            except Exception:
                pass

    return sorted(list(servicos_encontrados))

def baixar_dados_fracionado(base_url, token, lista_contas, lista_pesquisas, d_ini, d_fim, limit_size):
    url = f"{base_url}/rest/v2/RelPesqAnalitico"
    headers = {"Authorization": f"Bearer {token}"}
    dados_unicos = {}
    
    intervalos = []
    current_start = d_ini
    while current_start <= d_fim:
        current_end = current_start + timedelta(days=20)
        if current_end > d_fim: current_end = d_fim
        intervalos.append((current_start, current_end))
        current_start = current_end + timedelta(days=1)
        if current_start > d_fim: break

    status_text = st.empty()
    prog_bar = st.progress(0)
    
    total_steps = len(intervalos) * len(lista_contas) * len(lista_pesquisas)
    current_step = 0
    total_baixados = 0

    for idx, (dt_start, dt_end) in enumerate(intervalos):
        s_str = dt_start.strftime("%d/%m")
        e_str = dt_end.strftime("%d/%m")
        
        for id_conta in lista_contas:
            for id_pesquisa in lista_pesquisas:
                current_step += 1
                prog = min(current_step / max(total_steps, 1), 1.0)
                prog_bar.progress(prog)
                status_text.markdown(f"⏳ Baixando **{s_str} a {e_str}** | Conta {id_conta} | Pesquisa {id_pesquisa} | Encontrados: **{total_baixados}**")
                
                page = 1
                retry_count = 0 
                
                while True:
                    try:
                        params = {
                            "data_inicial": dt_start.strftime("%Y-%m-%d"),
                            "data_final": dt_end.strftime("%Y-%m-%d"),
                            "pesquisa": id_pesquisa,
                            "id_conta": id_conta,
                            "page": page,
                            "limit": limit_size
                        }
                        
                        r = requests.get(url, headers=headers, params=params, timeout=45)
                        
                        if r.status_code != 200:
                            if retry_count < 2: 
                                retry_count += 1
                                time.sleep(1) 
                                continue
                            else:
                                break 

                        data = r.json()
                        if not data: break 
                        
                        for bloco in data:
                            cod_pergunta = str(bloco.get("cod_pergunta", ""))
                            nom_pergunta = str(bloco.get("nom_pergunta", "")).lower()
                            
                            nome_servico = bloco.get("nom_servico") or bloco.get("servico") or "N/A"

                            if str(id_pesquisa) == ID_PESQUISA_V3 and cod_pergunta == ID_PERGUNTA_IGNORAR_V3: continue
                            if "internet" in nom_pergunta or ("serviço" in nom_pergunta and "atendimento" not in nom_pergunta): continue

                            respostas = bloco.get("respostas", [])
                            for resp in respostas:
                                protocolo = str(resp.get("num_protocolo", ""))
                                agente = str(resp.get("nom_agente", "DESCONHECIDO"))
                                
                                servico_final = nome_servico
                                if servico_final == "N/A":
                                    servico_final = resp.get("nom_servico") or resp.get("servico") or "N/A"

                                if protocolo and protocolo != "0":
                                    chave = f"{protocolo}_{agente}_{cod_pergunta}"
                                else:
                                    chave = f"noprot_{id_conta}_{id_pesquisa}_{len(dados_unicos)}"
                                
                                if chave not in dados_unicos:
                                    resp['conta_origem_id'] = str(id_conta)
                                    resp['pergunta_origem'] = bloco.get("nom_pergunta", "")
                                    resp['nom_servico'] = str(servico_final).upper()
                                    dados_unicos[chave] = resp
                                    total_baixados += 1
                        
                        if len(data) < (limit_size / 2): break 
                        page += 1
                        if page > 100: break 

                    except Exception as e:
                        time.sleep(1)
                        break 
    
    prog_bar.empty()
    status_text.empty()
    return list(dados_unicos.values())

# ==============================================================================
# INTERFACE
# ==============================================================================

if not st.session_state["app_access"]:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<h3 style='text-align:center'>🔒 Acesso Restrito</h3>", unsafe_allow_html=True)
            if not SECRET_SYS_PASS:
                st.error("ERRO: Senha do sistema não configurada nos Secrets!")
            else:
                senha = st.text_input("Senha", type="password")
                if st.button("Entrar", type="primary", use_container_width=True):
                    if senha == SECRET_SYS_PASS:
                        st.session_state["app_access"] = True
                        st.rerun()
                    else: st.error("Senha incorreta.")
    st.stop()

if not st.session_state["token"]:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("### ✨ Satisfador 3.0 Pro")
            if API_URL_SECRET:
                if st.button("CONECTAR SISTEMA", type="primary", use_container_width=True):
                    t = autenticar(API_URL_SECRET, API_USER_SECRET, API_PASS_SECRET)
                    if t:
                        st.session_state["token"] = t
                        st.rerun()
                    else: st.error("Erro de conexão/autenticação.")
            else:
                st.warning("API não configurada nos Secrets.")

else:
    with st.sidebar:
        st.markdown("### 📂 Upload Manual")
        uploaded_files = st.file_uploader("CSV/Excel (Matrix)", accept_multiple_files=True, type=['csv', 'xlsx'])
        st.markdown("---")
        limit_page = st.slider("Itens por Requisição", 50, 500, 100, 50)
        st.divider()
        if st.button("Sair"):
            st.session_state["token"] = None
            st.session_state["app_access"] = False
            st.rerun()

    st.title("Painel de Satisfação (Big Data)")
    
    with st.container(border=True):
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown("**Período**")
            k1, k2 = st.columns(2)
            ini = k1.date_input("Início", datetime.today() - timedelta(days=1), label_visibility="collapsed")
            fim = k2.date_input("Fim", datetime.today(), label_visibility="collapsed")
        with c2:
            st.markdown("**Contas**")
            ids = list(CONTAS_FIXAS.keys())
            padrao = ["1"] if "1" in ids else None
            contas_sel = st.multiselect("Selecione", ids, default=padrao, format_func=lambda x: f"{x} - {CONTAS_FIXAS[x]}", label_visibility="collapsed")
            
        if st.button("🔎 Buscar Pesquisas Disponíveis", use_container_width=True):
            if contas_sel:
                st.session_state["pesquisas_list"] = listar_pesquisas(API_URL_SECRET, st.session_state["token"], contas_sel, ini, fim)
                st.session_state["servicos_list"] = listar_servicos_api(API_URL_SECRET, st.session_state["token"], contas_sel[0], ini, fim)
                
                if not st.session_state["pesquisas_list"]: 
                    st.toast("Nenhuma pesquisa encontrada!", icon="⚠️")
                else: 
                    st.toast(f"Encontradas: {len(st.session_state['pesquisas_list'])} pesquisas e {len(st.session_state['servicos_list'])} serviços.", icon="✅")
            else: st.toast("Selecione uma conta.", icon="⚠️")

    if st.session_state["pesquisas_list"] or uploaded_files:
        with st.container(border=True):
            st.markdown("#### Configuração do Relatório")
            
            opts = {f"{p['id']} - {p['nome']}": p['id'] for p in st.session_state["pesquisas_list"]}
            defs = [k for k in opts.keys() if any(x in k for x in ["35", "43", "5"])]
            sels = st.multiselect("Pesquisas", list(opts.keys()), default=defs, label_visibility="collapsed")
            p_ids = [opts[s] for s in sels]
            
            c_setor, c_servico = st.columns(2)
            
            with c_setor:
                setor_sel = st.selectbox("Filtrar Setor (Inteligente)", ["TODOS"] + list(SETORES_AGENTES.keys()) + ["OUTROS"])
            
            with c_servico:
                opcoes_servico = st.session_state.get("servicos_list", [])
                servicos_sel = st.multiselect("Filtrar Serviços (API)", options=opcoes_servico, placeholder="Selecione serviços específicos (Opcional)")
                if not opcoes_servico: st.caption("⚠️ Nenhum serviço encontrado ou busca pendente.")

            st.markdown("<br>", unsafe_allow_html=True)
            gerar = st.button("🚀 GERAR (Fatiado & Filtrado)", type="primary", use_container_width=True)

        if gerar:
            raw_data = []
            
            if p_ids:
                raw_data = baixar_dados_fracionado(API_URL_SECRET, st.session_state["token"], contas_sel, p_ids, ini, fim, limit_page)
            
            if uploaded_files:
                for u in uploaded_files:
                    try:
                        fname = u.name.lower()
                        if "servico_de_interne" in fname or ("internet" in fname and "experiencia" not in fname): continue
                        if u.name.endswith('.xlsx'): df_t = pd.read_excel(u)
                        else: df_t = pd.read_csv(u)
                        df_t.columns = df_t.columns.str.strip()
                        mapa = {'Opção': 'nom_valor', 'Agente': 'nom_agente', 'Data': 'dat_resposta', 
                                'Protocolo': 'num_protocolo', 'Resposta': 'nom_resposta', 'Conta': 'conta_origem_id',
                                'Serviço': 'nom_servico'} 
                        df_t = df_t.rename(columns=mapa)
                        for col in ['nom_valor', 'nom_agente', 'dat_resposta', 'num_protocolo']:
                            if col not in df_t.columns: df_t[col] = None
                        df_t['dat_resposta'] = pd.to_datetime(df_t['dat_resposta'], dayfirst=True, errors='coerce')
                        raw_data.extend(df_t.to_dict(orient='records'))
                    except: pass

            if not raw_data:
                st.error("Nenhum dado encontrado após processar todos os períodos.")
            else:
                df = pd.DataFrame(raw_data)
                
                df['Nota'] = pd.to_numeric(df['nom_valor'], errors='coerce').fillna(-1) 
                df = df[df['Nota'] >= 0] 
                df['Nota'] = df['Nota'].astype(int)
                
                df['Data'] = pd.to_datetime(df['dat_resposta'])
                df['Dia'] = df['Data'].dt.strftime('%d/%m')
                df['Agente'] = df['nom_agente'].apply(normalizar_nome)
                df['Setor'] = df['Agente'].apply(get_setor)
                df['Nome_Conta'] = df['conta_origem_id'].map(CONTAS_FIXAS).fillna("Outra")
                df['Link'] = df['num_protocolo'].apply(criar_link_atendimento)
                
                if 'nom_servico' not in df.columns: df['Serviço'] = "N/A"
                else: df['Serviço'] = df['nom_servico'].astype(str).str.upper().replace('NAN', 'N/A')
                
                # --- FILTRAGEM INTELIGENTE (CORREÇÃO) ---
                df_final = df.copy()
                
                if setor_sel != "TODOS":
                    servicos_vinculados = df_final[df_final['Setor'] == setor_sel]['Serviço'].unique()
                    mask_setor = (df_final['Setor'] == setor_sel) | (df_final['Serviço'].isin(servicos_vinculados))
                    df_final = df_final[mask_setor]
                
                if servicos_sel:
                    df_final = df_final[df_final['Serviço'].isin(servicos_sel)]
                
                if df_final.empty:
                    st.warning("Sem dados para este conjunto de filtros.")
                else:
                    total = len(df_final)
                    prom = len(df_final[df_final['Nota'] >= 8])
                    csat = (prom / total * 100)
                    media = df_final['Nota'].mean()

                    # AJUSTADO PARA 2 CASAS DECIMAIS
                    st.markdown("### Resultados")
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("Total", total)
                    k2.metric("Promotores", prom)
                    k3.metric("CSAT", f"{csat:.2f}%")
                    k4.metric("Média", f"{media:.2f}")
                    
                    st.divider()
                    
                    # AJUSTADO PARA 2 CASAS DECIMAIS
                    trend = df_final.groupby('Dia').agg(Total=('Nota', 'count'), Prom=('Nota', lambda x: (x>=8).sum())).reset_index()
                    trend['Sat'] = (trend['Prom']/trend['Total']*100).round(2)
                    fig = px.line(trend, x='Dia', y='Sat', markers=True, title="Evolução", text='Sat')
                    fig.update_traces(line_color='#2563eb', textposition="top center")
                    fig.update_layout(yaxis_range=[0, 115], height=300)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.divider()
                    
                    # AJUSTADO PARA 2 CASAS DECIMAIS
                    col_rank, col_pie = st.columns([2, 1])
                    rank = df_final.groupby('Agente').agg(Qtd=('Nota', 'count'), Prom=('Nota', lambda x: (x>=8).sum()), Media=('Nota', 'mean')).reset_index()
                    rank['CSAT'] = (rank['Prom']/rank['Qtd']*100).round(2)
                    rank = rank.sort_values('CSAT', ascending=False)
                    
                    with col_rank:
                        st.dataframe(
                            rank[['Agente', 'CSAT', 'Qtd', 'Media']],
                            column_config={"CSAT": st.column_config.ProgressColumn(format="%.2f%%", min_value=0, max_value=100)},
                            hide_index=True, use_container_width=True
                        )
                    with col_pie:
                        fig_pie = go.Figure(data=[go.Pie(labels=['Prom', 'Outros'], values=[prom, total-prom], hole=.6, marker_colors=['#10b981', '#ef4444'])])
                        fig_pie.update_layout(showlegend=False, height=250, margin=dict(t=0,b=0,l=0,r=0), annotations=[dict(text=f"{csat:.2f}%", x=0.5, y=0.5, font_size=20, showarrow=False)])
                        st.plotly_chart(fig_pie, use_container_width=True)
                    
                    st.subheader("Base de Dados")
                    st.dataframe(df_final[['Data', 'Nome_Conta', 'Setor', 'Agente', 'Serviço', 'Nota', 'nom_resposta', 'Link']], hide_index=True, use_container_width=True, column_config={"Link": st.column_config.LinkColumn("Ver", display_text="Abrir"), "Data": st.column_config.DatetimeColumn(format="D/M/Y H:m")})
