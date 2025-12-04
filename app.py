import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    layout="wide", 
    page_title="Satisfador 3.0", 
    page_icon="🛡️",
    initial_sidebar_state="collapsed"
)

# --- ESTADO E VARIÁVEIS GLOBAIS ---
if "app_access" not in st.session_state: st.session_state["app_access"] = False
if "token" not in st.session_state: st.session_state["token"] = None
if "pesquisas_list" not in st.session_state: st.session_state["pesquisas_list"] = []

# IDs MAREADOS (CRUCIAL PARA O FUNCIONAMENTO)
ID_PESQUISA_V3 = "43"
ID_PERGUNTA_IGNORAR_V3 = "40" # Pergunta sobre Internet

# --- CARREGAMENTO DE SEGREDOS (CLOUD) ---
try:
    SECRET_SYS_PASS = st.secrets["geral"]["senha_sistema"]
    API_URL_SECRET = st.secrets["api"]["url"]
    API_USER_SECRET = st.secrets["api"]["user"]
    API_PASS_SECRET = st.secrets["api"]["password"]
except:
    # Fallback para evitar erro de compilação se os secrets não existirem
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
    # Monta link padrão (ajuste o domínio se necessário, aqui usa o da secrets ou padrão)
    domain = API_URL_SECRET.replace("/rest/v2", "").replace("https://", "") if API_URL_SECRET else "ateltelecom.matrixdobrasil.ai"
    if "api" in domain: domain = "ateltelecom.matrixdobrasil.ai" # Fallback comum
    return f"https://{domain}/atendimento/view/cod_atendimento/{cod}/readonly/true#atendimento-div"

# --- FUNÇÕES DE API ---
def autenticar(url, login, senha):
    if not url or not login: return None
    try:
        r = requests.post(f"{url}/rest/v2/authuser", json={"login": login, "chave": senha}, timeout=20)
        if r.status_code == 200 and r.json().get("success"):
            return r.json()["result"]["token"]
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

def baixar_dados_inteligente(base_url, token, lista_contas, lista_pesquisas, d_ini, d_fim, limit_size):
    url = f"{base_url}/rest/v2/RelPesqAnalitico"
    headers = {"Authorization": f"Bearer {token}"}
    dados_unicos = {}
    
    prog_bar = st.progress(0, text="Iniciando download...")
    total_steps = len(lista_contas) * len(lista_pesquisas)
    current_step = 0

    for id_conta in lista_contas:
        for id_pesquisa in lista_pesquisas:
            current_step += 1
            prog_bar.progress(current_step / max(total_steps, 1), text=f"Conta {id_conta} | Pesquisa {id_pesquisa}")
            
            page = 1
            loop_vazio = 0
            
            while True:
                try:
                    params = {
                        "data_inicial": d_ini.strftime("%Y-%m-%d"), "data_final": d_fim.strftime("%Y-%m-%d"),
                        "pesquisa": id_pesquisa, "id_conta": id_conta, "page": page, "limit": limit_size
                    }
                    r = requests.get(url, headers=headers, params=params, timeout=40)
                    if r.status_code != 200: break
                    data = r.json()
                    if not data: break
                    
                    count_validos = 0
                    
                    for bloco in data:
                        # ======================================================
                        # 🚨 LÓGICA DE FILTRAGEM (V3/V2)
                        # ======================================================
                        cod_pergunta = str(bloco.get("cod_pergunta", ""))
                        nom_pergunta = str(bloco.get("nom_pergunta", "")).lower()

                        # 1. Filtro por ID (Mais preciso): 
                        # Se for a Pesquisa V3 (43) e a pergunta for a de Internet (40) -> IGNORA
                        if str(id_pesquisa) == ID_PESQUISA_V3 and cod_pergunta == ID_PERGUNTA_IGNORAR_V3:
                            continue

                        # 2. Filtro por Nome (Segurança):
                        # Se tiver "internet" no nome e NÃO tiver "experiência" ou "atendimento" -> IGNORA
                        if "internet" in nom_pergunta or ("serviço" in nom_pergunta and "atendimento" not in nom_pergunta):
                            continue

                        # Se passou, processa as respostas
                        respostas = bloco.get("respostas", [])
                        for resp in respostas:
                            protocolo = str(resp.get("num_protocolo", ""))
                            chave = protocolo if (protocolo and protocolo != "0") else f"noprot_{id_conta}_{id_pesquisa}_{len(dados_unicos)}"
                            
                            if chave not in dados_unicos:
                                resp['conta_origem_id'] = str(id_conta)
                                resp['pergunta_origem'] = bloco.get("nom_pergunta", "") # Salva nome original
                                dados_unicos[chave] = resp
                                count_validos += 1
                    
                    if count_validos == 0 and len(data) > 0:
                        loop_vazio += 1
                        if loop_vazio >= 3: break # Evita loop infinito em pesquisas só de internet
                    else:
                        loop_vazio = 0
                    
                    if len(data) < (limit_size / 2): break
                    page += 1
                    if page > 300: break
                except: break
            
    prog_bar.empty()
    return list(dados_unicos.values())

# ==============================================================================
# TELA 0: BLOQUEIO DE SEGURANÇA (GATEKEEPER)
# ==============================================================================

if not st.session_state["app_access"]:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<h3 style='text-align:center'>🔒 Acesso Restrito</h3>", unsafe_allow_html=True)
            if not SECRET_SYS_PASS:
                st.error("ERRO: Senha do sistema não configurada nos Secrets!")
            else:
                senha = st.text_input("Senha de Acesso", type="password", placeholder="Digite a senha do sistema")
                if st.button("Entrar", type="primary", use_container_width=True):
                    if senha == SECRET_SYS_PASS:
                        st.session_state["app_access"] = True
                        st.rerun()
                    else:
                        st.error("Senha incorreta.")
    st.stop()

# ==============================================================================
# TELA 1: LOGIN NA API (CONEXÃO)
# ==============================================================================

if not st.session_state["token"]:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("### ✨ Satisfador 3.0 (Cloud)")
            
            if API_URL_SECRET: 
                st.info(f"API Configurada via Secrets")
                if st.button("CONECTAR SISTEMA", type="primary", use_container_width=True):
                    with st.spinner("Autenticando..."):
                        t = autenticar(API_URL_SECRET, API_USER_SECRET, API_PASS_SECRET)
                        if t:
                            st.session_state["token"] = t
                            st.rerun()
                        else:
                            st.error("Falha ao conectar. Verifique os Secrets.")
            else: 
                st.warning("API não configurada nos Secrets (.streamlit/secrets.toml)!")

else:
    # ==============================================================================
    # TELA 2: DASHBOARD (PRINCIPAL)
    # ==============================================================================
    
    with st.sidebar:
        st.markdown("### 📂 Importação Manual")
        uploaded_files = st.file_uploader(
            "CSV/Excel (Matrix)", 
            accept_multiple_files=True, 
            type=['csv', 'xlsx'],
            help="Arraste os arquivos de exportação aqui. O sistema filtrará automaticamente as perguntas de 'Internet'."
        )
        
        st.markdown("---")
        limit_page = st.slider("Velocidade API", 50, 500, 100, 50)
        st.divider()
        if st.button("Sair (Logout)", use_container_width=True):
            st.session_state["token"] = None
            st.session_state["app_access"] = False
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
            st.markdown("**Contas Alvo (API)**")
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

    # Se já tiver pesquisas na lista OU arquivos carregados
    if st.session_state["pesquisas_list"] or uploaded_files:
        with st.container(border=True):
            st.markdown("#### 2. Análise e Filtros")
            c_pesq, c_setor, c_btn = st.columns([2, 1, 1])
            with c_pesq:
                opts = {f"{p['id']} - {p['nome']}": p['id'] for p in st.session_state["pesquisas_list"]}
                # Seleção automática inteligente (Tenta achar V2 e V3 pelos IDs conhecidos ou nomes comuns)
                defaults = [k for k in opts.keys() if any(x in k for x in ["35", "43", "5"])]
                sels = st.multiselect("Pesquisas (API)", list(opts.keys()), default=defaults, label_visibility="collapsed")
                pesquisas_ids = [opts[s] for s in sels]
            with c_setor:
                setor_sel = st.selectbox("Setor", list(SETORES_AGENTES.keys()) + ["TODOS", "OUTROS"], label_visibility="collapsed")
            with c_btn:
                gerar = st.button("✨ GERAR DASHBOARD", type="primary", use_container_width=True)

        if gerar:
            raw_data = []
            
            # --- 1. BAIXA DA API (COM FILTRO DE PERGUNTA) ---
            if pesquisas_ids:
                raw_data = baixar_dados_inteligente(
                    API_URL_SECRET, st.session_state["token"], contas_sel, pesquisas_ids, ini, fim, limit_page
                )
            
            # --- 2. PROCESSA ARQUIVOS (COM FILTRO DE NOME) ---
            if uploaded_files:
                for u_file in uploaded_files:
                    try:
                        fname = u_file.name.lower()
                        # Ignora arquivos puramente técnicos se o nome deixar óbvio
                        if "servico_de_interne" in fname or ("internet" in fname and "experiencia" not in fname):
                            st.toast(f"Ignorado (Técnico): {u_file.name}", icon="🚫")
                            continue
                        
                        if u_file.name.endswith('.xlsx'): df_temp = pd.read_excel(u_file)
                        else: df_temp = pd.read_csv(u_file)
                        
                        df_temp.columns = df_temp.columns.str.strip()
                        mapa = {'Opção': 'nom_valor', 'Agente': 'nom_agente', 'Data': 'dat_resposta', 
                                'Protocolo': 'num_protocolo', 'Resposta': 'nom_resposta', 'Conta': 'conta_origem_id'}
                        df_temp = df_temp.rename(columns=mapa)
                        
                        # Padroniza e limpa
                        for col in ['nom_valor', 'nom_agente', 'dat_resposta', 'num_protocolo', 'nom_resposta', 'conta_origem_id']:
                            if col not in df_temp.columns: df_temp[col] = None
                        
                        df_temp['dat_resposta'] = pd.to_datetime(df_temp['dat_resposta'], dayfirst=True, errors='coerce')
                        raw_data.extend(df_temp.to_dict(orient='records'))
                        st.toast(f"Importado: {u_file.name}", icon="✅")
                    except Exception as e:
                        st.error(f"Erro no arquivo {u_file.name}: {e}")

            # --- 3. PROCESSAMENTO FINAL ---
            if not raw_data:
                st.warning("Nenhum dado encontrado (verifique datas ou contas).")
            else:
                df = pd.DataFrame(raw_data)
                
                # Tratamento de Notas (0 a 10)
                df['Nota'] = pd.to_numeric(df['nom_valor'], errors='coerce').fillna(0).astype(int)
                df = df[df['Nota'] > 0] # Opcional: remover notas 0 se forem erros
                
                # Tratamentos Gerais
                df['Data'] = pd.to_datetime(df['dat_resposta'])
                df['Dia'] = df['Data'].dt.strftime('%d/%m')
                df['Agente'] = df['nom_agente'].apply(normalizar_nome)
                df['Setor'] = df['Agente'].apply(get_setor)
                df['Nome_Conta'] = df['conta_origem_id'].map(CONTAS_FIXAS).fillna("Outra/Arquivo")
                df['Link_Acesso'] = df['num_protocolo'].apply(criar_link_atendimento)
                
                # Filtro de Dashboard (Setor)
                df_final = df if setor_sel == "TODOS" else df[df['Setor'] == setor_sel]
                
                if df_final.empty:
                    st.info(f"Sem dados para o setor {setor_sel}.")
                else:
                    # --- KPI ---
                    total = len(df_final)
                    prom = len(df_final[df_final['Nota'] >= 8])
                    det = len(df_final[df_final['Nota'] <= 6])
                    sat_score = (prom / total * 100) if total > 0 else 0
                    media = df_final['Nota'].mean()
                    
                    st.markdown("### Resultados Gerais")
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("Total Avaliações", total)
                    k2.metric("Promotores (8-10)", prom)
                    k3.metric("Satisfação (CSAT)", f"{sat_score:.1f}%", delta_color="normal" if sat_score >= 80 else "inverse")
                    k4.metric("Nota Média", f"{media:.2f}")
                    
                    st.divider()
                    
                    # --- GRÁFICO TEMPORAL ---
                    trend = df_final.groupby('Dia').agg(Total=('Nota', 'count'), Prom=('Nota', lambda x: (x >= 8).sum())).reset_index()
                    trend['Sat %'] = (trend['Prom'] / trend['Total'] * 100).round(1)
                    fig_line = px.line(trend, x='Dia', y='Sat %', markers=True, text='Sat %', title="Evolução Diária")
                    fig_line.update_traces(line_color='#2563eb', textposition="top center")
                    fig_line.update_layout(height=300, yaxis_range=[0, 110])
                    st.plotly_chart(fig_line, use_container_width=True)

                    st.divider()
                    
                    # --- RANKING E PIE CHART ---
                    c_rank, c_pie = st.columns([2, 1])
                    rank_geral = df_final.groupby('Agente').agg(
                        Qtd=('Nota', 'count'),
                        Prom=('Nota', lambda x: (x >= 8).sum()),
                        Media=('Nota', 'mean')
                    ).reset_index()
                    rank_geral['Sat %'] = (rank_geral['Prom'] / rank_geral['Qtd'] * 100).round(1)
                    rank_geral = rank_geral.sort_values('Sat %', ascending=False)
                    
                    with c_rank:
                        st.markdown("#### Ranking de Agentes")
                        st.dataframe(
                            rank_geral[['Agente', 'Sat %', 'Qtd', 'Media']],
                            column_config={
                                "Sat %": st.column_config.ProgressColumn("CSAT", format="%.1f%%", min_value=0, max_value=100),
                                "Media": st.column_config.NumberColumn("Média", format="%.2f")
                            },
                            hide_index=True, use_container_width=True
                        )
                    with c_pie:
                        st.markdown("#### Distribuição")
                        labels = ['Promotores', 'Detratores/Neutros']
                        fig = go.Figure(data=[go.Pie(labels=labels, values=[prom, total-prom], hole=.6, marker_colors=['#10b981', '#ef4444'])])
                        fig.update_layout(showlegend=False, height=250, margin=dict(t=0,b=0,l=0,r=0),
                                          annotations=[dict(text=f"{sat_score:.0f}%", x=0.5, y=0.5, font_size=24, showarrow=False)])
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # --- DETALHAMENTO ---
                    st.subheader("📋 Detalhamento das Notas")
                    st.dataframe(
                        df_final[['Data', 'Nome_Conta', 'Agente', 'Nota', 'nom_resposta', 'Link_Acesso']],
                        column_config={
                            "Link_Acesso": st.column_config.LinkColumn("Ação", display_text="🔗 Abrir"),
                            "Nota": st.column_config.NumberColumn("Nota", format="%d ⭐"),
                            "Data": st.column_config.DatetimeColumn(format="D/M/Y H:m")
                        },
                        use_container_width=True, hide_index=True
                    )
