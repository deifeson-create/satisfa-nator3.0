import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    layout="wide", 
    page_title="Satisfador 3.0", 
    page_icon="🛡️",
    initial_sidebar_state="collapsed"
)

# --- ESTADO E SEGREDOS ---
if "app_access" not in st.session_state: st.session_state["app_access"] = False
if "token" not in st.session_state: st.session_state["token"] = None
if "pesquisas_list" not in st.session_state: st.session_state["pesquisas_list"] = []

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

# CONFIGURAÇÕES DE NEGÓCIO
ID_PESQUISA_V2 = "35"
ID_PESQUISA_V3 = "43"

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

# --- FUNÇÕES AUXILIARES ---
def normalizar_nome(nome):
    return str(nome).strip().upper() if nome and str(nome) != "nan" else "DESCONHECIDO"

def get_setor(agente):
    nome = normalizar_nome(agente)
    for setor, lista in SETORES_AGENTES.items():
        if any(a in nome for a in lista):
            return setor
    return 'OUTROS'

def criar_link_atendimento(protocolo):
    if not protocolo or str(protocolo) in ["0", "nan", "None", ""]: return None
    proto_str = str(protocolo).strip().replace('.0', '')
    cod = proto_str[-7:] if len(proto_str) >= 7 else proto_str
    return f"https://ateltelecom.matrixdobrasil.ai/atendimento/view/cod_atendimento/{cod}/readonly/true#atendimento-div"

# --- FUNÇÕES DE API ---
def autenticar(url, login, senha):
    try:
        r = requests.post(f"{url}/rest/v2/authuser", json={"login": login, "chave": senha}, timeout=20)
        if r.status_code == 200 and r.json().get("success"): return r.json()["result"]["token"]
    except: pass
    return None

def listar_pesquisas(base_url, token, lista_contas, d_ini, d_fim):
    url = f"{base_url}/rest/v2/relPesquisa"
    headers = {"Authorization": f"Bearer {token}"}
    encontradas = []
    for id_conta in lista_contas:
        try:
            params = {"data_inicial": d_ini.strftime("%Y-%m-%d"), "data_final": d_fim.strftime("%Y-%m-%d"), "id_conta": id_conta, "page": 1, "limit": 100}
            r = requests.get(url, headers=headers, params=params, timeout=10)
            if r.status_code == 200:
                for row in r.json().get("rows", []):
                    encontradas.append({"id": str(row.get("cod_pesquisa")), "nome": row.get("nom_pesquisa")})
        except: pass
    return list({v['id']: v for v in encontradas}.values())

def baixar_dados_regra_rigida(base_url, token, lista_contas, lista_pesquisas, d_ini, d_fim, limit_size):
    url = f"{base_url}/rest/v2/RelPesqAnalitico"
    headers = {"Authorization": f"Bearer {token}"}
    dados_unicos = {}
    
    # Barra de progresso visual
    prog_bar = st.progress(0, text="Iniciando...")
    total_iter = len(lista_contas) * len(lista_pesquisas)
    current_iter = 0

    for id_conta in lista_contas:
        for id_pesquisa in lista_pesquisas:
            current_iter += 1
            prog_bar.progress(current_iter / max(total_iter, 1), text=f"Baixando: Conta {id_conta} - Pesquisa {id_pesquisa}")
            
            page = 1
            loop_vazio = 0
            
            while True:
                try:
                    params = {
                        "data_inicial": d_ini.strftime("%Y-%m-%d"), "data_final": d_fim.strftime("%Y-%m-%d"),
                        "pesquisa": id_pesquisa, "id_conta": id_conta, "page": page, "limit": limit_size
                    }
                    r = requests.get(url, headers=headers, params=params, timeout=45)
                    if r.status_code != 200: break
                    data = r.json()
                    if not data: break
                    
                    count_validos_bloco = 0
                    
                    for bloco in data:
                        # --- FILTRO DE PERGUNTA (Lógica V3) ---
                        nome_pergunta = str(bloco.get("nom_pergunta", "")).strip()
                        nome_lower = nome_pergunta.lower()
                        
                        # REGRA DE OURO: Ignora perguntas sobre "Internet" ou "Serviço" (técnico)
                        # Mantém perguntas sobre "Experiência" ou "Atendimento"
                        if "internet" in nome_lower or "serviço" in nome_lower or "servico" in nome_lower:
                            continue 

                        respostas = bloco.get("respostas", [])
                        for resp in respostas:
                            protocolo = str(resp.get("num_protocolo", ""))
                            # Define chave única (Protocolo ou hash se não tiver)
                            chave = protocolo if (protocolo and protocolo != "0") else f"noprot_{id_conta}_{id_pesquisa}_{len(dados_unicos)}"
                            
                            if chave not in dados_unicos:
                                resp['conta_origem_id'] = str(id_conta)
                                resp['pergunta_origem'] = nome_pergunta
                                dados_unicos[chave] = resp
                                count_validos_bloco += 1
                    
                    if count_validos_bloco == 0 and len(data) > 0:
                        loop_vazio += 1
                        if loop_vazio >= 5: break # Evita loop infinito se só tiver perguntas ignoradas
                    else:
                        loop_vazio = 0

                    if len(data) < (limit_size / 2): break # Fim da paginação
                    page += 1
                    if page > 200: break # Limite de segurança
                except: break
                
    prog_bar.empty()
    return list(dados_unicos.values())

# ==============================================================================
# INTERFACE PRINCIPAL
# ==============================================================================

if not st.session_state["app_access"]:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("<br><h3 style='text-align:center'>🔒 Acesso Restrito</h3>", unsafe_allow_html=True)
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar", type="primary", use_container_width=True):
            if senha == SECRET_SYS_PASS:
                st.session_state["app_access"] = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    st.stop()

if not st.session_state["token"]:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br>### ✨ Satisfador 3.0 (Cloud)", unsafe_allow_html=True)
        if st.button("CONECTAR SISTEMA", type="primary", use_container_width=True):
            t = autenticar(API_URL_SECRET, API_USER_SECRET, API_PASS_SECRET)
            if t:
                st.session_state["token"] = t
                st.rerun()
            else:
                st.error("Falha na autenticação.")

else:
    # --- BARRA LATERAL ---
    with st.sidebar:
        st.markdown("### 📂 Importação Manual")
        uploaded_files = st.file_uploader(
            "Arquivos CSV/Excel", 
            accept_multiple_files=True, 
            type=['csv', 'xlsx'],
            help="Arraste os arquivos de exportação aqui. O sistema filtrará automaticamente as perguntas de 'Internet'."
        )
        
        st.markdown("---")
        st.markdown("### Config API")
        limit_page = st.slider("Velocidade", 50, 500, 100, 50)
        if st.button("Sair", use_container_width=True):
            st.session_state["token"] = None
            st.session_state["app_access"] = False
            st.rerun()

    st.title("Painel de Satisfação")

    with st.container(border=True):
        c_datas, c_contas = st.columns([1, 2])
        with c_datas:
            st.markdown("**Período**")
            c1, c2 = st.columns(2)
            ini = c1.date_input("Início", datetime.today() - timedelta(days=1), label_visibility="collapsed")
            fim = c2.date_input("Fim", datetime.today(), label_visibility="collapsed")
        with c_contas:
            st.markdown("**Contas (API)**")
            ids = list(CONTAS_FIXAS.keys())
            sel_contas = st.multiselect("Selecione", ids, default=["1"] if "1" in ids else None, format_func=lambda x: f"{x} - {CONTAS_FIXAS[x]}", label_visibility="collapsed")
            
        if st.button("🔎 Buscar Pesquisas na API", use_container_width=True):
            if sel_contas:
                st.session_state["pesquisas_list"] = listar_pesquisas(API_URL_SECRET, st.session_state["token"], sel_contas, ini, fim)
            else:
                st.warning("Selecione uma conta.")

    if st.session_state["pesquisas_list"] or uploaded_files:
        with st.container(border=True):
            st.markdown("#### Filtros e Geração")
            col_p, col_s, col_b = st.columns([2, 1, 1])
            with col_p:
                opts = {f"{p['id']} - {p['nome']}": p['id'] for p in st.session_state["pesquisas_list"]}
                # Seleciona V2 e V3 por padrão se existirem
                defs = [k for k in opts.keys() if ID_PESQUISA_V2 in k or ID_PESQUISA_V3 in k]
                sel_pesquisas = st.multiselect("Pesquisas API", list(opts.keys()), default=defs, label_visibility="collapsed")
                ids_pesquisas = [opts[x] for x in sel_pesquisas]
            with col_s:
                sel_setor = st.selectbox("Setor", ["TODOS"] + list(SETORES_AGENTES.keys()) + ["OUTROS"], label_visibility="collapsed")
            with col_b:
                gerar = st.button("🚀 GERAR RELATÓRIO", type="primary", use_container_width=True)

        if gerar:
            raw_data = []
            
            # 1. DADOS DA API
            if ids_pesquisas:
                raw_data = baixar_dados_regra_rigida(API_URL_SECRET, st.session_state["token"], sel_contas, ids_pesquisas, ini, fim, limit_page)
            
            # 2. DADOS DOS ARQUIVOS (COM FILTRO DE NOME)
            if uploaded_files:
                for u_file in uploaded_files:
                    try:
                        # --- FILTRO INTELIGENTE DE ARQUIVO ---
                        fname = u_file.name.lower()
                        
                        # Ignora arquivos de Internet/Serviço Técnico
                        if "servico_de_interne" in fname or "internet" in fname:
                            st.toast(f"Ignorado (Técnico): {u_file.name}", icon="🚫")
                            continue
                        
                        # Garante que é um arquivo de Experiência/Atendimento
                        if "experiencia" in fname or "atendimento" in fname or "avaliar" in fname:
                            if u_file.name.endswith('.xlsx'): df_temp = pd.read_excel(u_file)
                            else: df_temp = pd.read_csv(u_file)
                            
                            # Normaliza colunas
                            df_temp.columns = df_temp.columns.str.strip()
                            mapa = {
                                'Opção': 'nom_valor', 'Agente': 'nom_agente', 'Data': 'dat_resposta', 
                                'Protocolo': 'num_protocolo', 'Resposta': 'nom_resposta', 'Conta': 'conta_origem_id'
                            }
                            df_temp = df_temp.rename(columns=mapa)
                            
                            # Ajusta datas
                            df_temp['dat_resposta'] = pd.to_datetime(df_temp['dat_resposta'], dayfirst=True, errors='coerce')
                            
                            raw_data.extend(df_temp.to_dict(orient='records'))
                            st.toast(f"Processado: {u_file.name}", icon="✅")
                        else:
                            st.toast(f"Ignorado (Nome irrelevante): {u_file.name}", icon="⚠️")

                    except Exception as e:
                        st.error(f"Erro em {u_file.name}: {e}")

            # 3. PROCESSAMENTO E VISUALIZAÇÃO
            if not raw_data:
                st.warning("Nenhum dado válido encontrado.")
            else:
                df = pd.DataFrame(raw_data)
                
                # Tratamento básico
                df['Nota'] = pd.to_numeric(df.get('nom_valor', 0), errors='coerce').fillna(0).astype(int)
                df = df[df['Nota'] > 0] # Remove notas 0 ou vazias se necessário (opcional)
                
                df['Data'] = pd.to_datetime(df.get('dat_resposta', datetime.today()))
                df['Dia'] = df['Data'].dt.strftime('%d/%m')
                df['Agente'] = df.get('nom_agente', 'DESCONHECIDO').apply(normalizar_nome)
                df['Setor'] = df['Agente'].apply(get_setor)
                
                # Mapeia conta (Tenta pelo ID, se falhar usa o valor que veio do arquivo)
                df['Nome_Conta'] = df.get('conta_origem_id', '').map(CONTAS_FIXAS).fillna(df.get('conta_origem_id', 'Desconhecida'))
                df['Link'] = df.get('num_protocolo', '').apply(criar_link_atendimento)

                # Filtro de Setor
                if sel_setor != "TODOS":
                    df = df[df['Setor'] == sel_setor]

                if df.empty:
                    st.info("Sem dados para o setor selecionado.")
                else:
                    # --- DASHBOARD ---
                    st.markdown("---")
                    
                    # KPIs
                    total = len(df)
                    prom = len(df[df['Nota'] >= 8])
                    csat = (prom / total * 100) if total > 0 else 0
                    
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("Avaliações", total)
                    k2.metric("Promotores", prom)
                    k3.metric("CSAT", f"{csat:.1f}%", delta_color="normal" if csat >= 80 else "inverse")
                    k4.metric("Média", f"{df['Nota'].mean():.2f}")

                    # Gráfico Temporal
                    trend = df.groupby('Dia')['Nota'].agg(['count', lambda x: (x>=8).sum()]).reset_index()
                    trend.columns = ['Dia', 'Total', 'Prom']
                    trend['Sat'] = (trend['Prom'] / trend['Total'] * 100).round(1)
                    
                    fig = px.line(trend, x='Dia', y='Sat', markers=True, title="Evolução Diária da Satisfação", text='Sat')
                    fig.update_traces(line_color='#2563eb', textposition="top center")
                    fig.update_layout(yaxis_range=[0, 110], height=300)
                    st.plotly_chart(fig, use_container_width=True)

                    # Ranking
                    st.markdown("### Ranking de Agentes")
                    rank = df.groupby('Agente')['Nota'].agg(['count', 'mean', lambda x: (x>=8).sum()]).reset_index()
                    rank.columns = ['Agente', 'Qtd', 'Media', 'Prom']
                    rank['CSAT'] = (rank['Prom'] / rank['Qtd'] * 100).round(1)
                    rank = rank[rank['Qtd'] >= 3].sort_values('CSAT', ascending=False) # Filtro mínimo de 3 avaliações

                    c_rank, c_pie = st.columns([2, 1])
                    with c_rank:
                        st.dataframe(
                            rank[['Agente', 'CSAT', 'Qtd', 'Media']],
                            column_config={
                                "CSAT": st.column_config.ProgressColumn("Satisfação", format="%.1f%%", min_value=0, max_value=100),
                                "Media": st.column_config.NumberColumn("Nota Média", format="%.2f")
                            },
                            hide_index=True, use_container_width=True
                        )
                    with c_pie:
                        fig_pie = go.Figure(data=[go.Pie(labels=['Promotores', 'Outros'], values=[prom, total-prom], hole=.6, marker_colors=['#10b981', '#ef4444'])])
                        fig_pie.update_layout(showlegend=False, height=250, margin=dict(t=0,b=0,l=0,r=0), 
                                            annotations=[dict(text=f"{csat:.0f}%", x=0.5, y=0.5, font_size=20, showarrow=False)])
                        st.plotly_chart(fig_pie, use_container_width=True)

                    # Detalhes
                    st.markdown("### Detalhamento")
                    st.dataframe(
                        df[['Data', 'Nome_Conta', 'Agente', 'Nota', 'nom_resposta', 'Link']],
                        column_config={"Link": st.column_config.LinkColumn("Ação", display_text="Abrir"), "Data": st.column_config.DatetimeColumn(format="D/M/Y H:m")},
                        hide_index=True, use_container_width=True
                    )
