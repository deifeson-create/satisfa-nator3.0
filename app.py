import pandas as pd

# Carrega o arquivo (garantindo separador e encoding corretos para BR)
# Ajuste o nome do arquivo para o caminho real onde você salvou
arquivo = "detalhamento_de_pesquisa_6931b4a52a431.xlsx - Sobre_sua_experiencia_neste_.csv"

try:
    df = pd.read_csv(arquivo, sep=';', encoding='latin1', low_memory=False)
except:
    # Fallback se o separador for vírgula
    df = pd.read_csv(arquivo, sep=',', encoding='utf-8', low_memory=False)

# --- AQUI ESTÁ A MÁGICA (FIXAR O NOME) ---
# Em vez de procurar pelo nome exato, procuramos por PALAVRAS-CHAVE da pergunta
coluna_alvo = None

for col in df.columns:
    # Normaliza para minúsculas para evitar erro de Case Sensitive
    col_lower = col.lower()
    
    # Verifica se é a pergunta de NPS/Satisfação desta pesquisa específica
    # Usamos trechos da frase para garantir o match mesmo se houver erros de digitação no final
    if "sobre sua experiência" in col_lower and "atendimento" in col_lower:
        coluna_alvo = col
        break

if coluna_alvo:
    print(f"✅ Coluna de nota encontrada: '{coluna_alvo}'")
    # Renomeia para um padrão que seu dashboard entenda (ex: 'nota' ou 'nps')
    df = df.rename(columns={coluna_alvo: 'nota'})
    
    # Garante que é numérico
    df['nota'] = pd.to_numeric(df['nota'], errors='coerce')
    
    print(f"Total de respostas válidas: {df['nota'].notnull().sum()}")
    print(df['nota'].value_counts().head()) # Mostra prévia para confirmar
else:
    print("❌ ERRO: Não achei a coluna da pergunta. Verifique os nomes abaixo:")
    print(df.columns.tolist())

# --- FIM DA CORREÇÃO ---
