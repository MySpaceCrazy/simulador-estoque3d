import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Simulador de Estoque 3D", layout="wide")

st.title("📦 Simulador de Estoque 3D - CD Passo Fundo")

# 1. Função para carregar a Malha e cruzar com o Estoque
@st.cache_data
def carregar_dados():
    # A. Carregar o ESQUELETO (Layout do Galpão)
    try:
        # Lê o CSV mantendo o encoding para evitar erros nos acentos
        df_layout = pd.read_csv("EXPORT_20260224_122851.xlsx - Data.csv", encoding="latin-1")
    except FileNotFoundError:
        st.error("Arquivo de layout não encontrado. Coloque o CSV na mesma pasta do app.py.")
        return pd.DataFrame()

    # SOLUÇÃO: Em vez de renomear as colunas do CSV, nós quebramos a string do endereço!
    df_layout[['Corredor', 'Coluna', 'Nível', 'Posição_Extra']] = df_layout['Posição no depósito'].str.split('-', expand=True)
    
    # Converter para números para desenhar no gráfico 3D
    df_layout['Corredor'] = pd.to_numeric(df_layout['Corredor'])
    df_layout['Coluna'] = pd.to_numeric(df_layout['Coluna'])
    df_layout['Nível'] = pd.to_numeric(df_layout['Nível'])

    # B. Carregar o ESTOQUE (Mock por enquanto, peguei endereços reais do seu CSV)
    dados_estoque = pd.DataFrame({
        "Posição no depósito": ["025-071-040-001", "025-073-010-001", "001-053-020-001", "001-053-030-001"],
        "UC": ["10001", "10002", "10003", "10004"],
        "Produto": ["10041398", "8593", "10001226", "99999"],
        "Descrição produto": ["ESFOLIANTE", "SABONETE", "ENXAGUANTE", "SHAMPOO"],
        "Vencimento": pd.to_datetime(["2029-01-01", "2023-12-31", "2027-12-30", "2023-01-01"]),
        "Quantidade": [240, 2232, 72, 100],
        "Área_Estoque": ["PERF", "PERF", "FARM", "COSM"] 
    })

    # C. CRUZAR OS DADOS (Left Join)
    # Mantém todos os endereços do layout e preenche com o estoque onde houver
    df_completo = pd.merge(df_layout, dados_estoque, on="Posição no depósito", how="left")

    # D. Identificar o que é Vazio e o que está Ocupado
    # Se não tem 'Produto', a Área de Exibição vira 'VAZIO'
    df_completo['Área_Exibicao'] = df_completo['Área_Estoque'].fillna('VAZIO')
    df_completo['Status'] = df_completo['Produto'].apply(lambda x: 'Ocupado' if pd.notna(x) else 'Vazio')
    
    # Lógica de Vencimento
    hoje = pd.Timestamp.today()
    df_completo['Vencido'] = (df_completo['Vencimento'] < hoje) & (df_completo['Status'] == 'Ocupado')

    return df_completo

df = carregar_dados()

if df.empty:
    st.stop() # Para a execução se não achar o arquivo

# 2. Barra Lateral para Filtros
st.sidebar.header("🔍 Pesquisas Detalhadas")
produto_pesquisa = st.sidebar.text_input("Pesquisa por Produto (Reduzido)")

# Lista de áreas tira o "VAZIO" para não sujar o filtro
areas_disponiveis = [a for a in df["Área_Exibicao"].unique() if a != "VAZIO"]
area_pesquisa = st.sidebar.selectbox("Pesquisa por Área", options=["Todas"] + areas_disponiveis)

endereco_pesquisa = st.sidebar.text_input("Pesquisa por Endereço (ex: 025-071-040-001)")

# Aplicar filtros
df_filtrado = df.copy()
if produto_pesquisa:
    # Se pesquisar produto, apaga o resto do galpão
    df_filtrado = df_filtrado[df_filtrado["Produto"] == produto_pesquisa]
if area_pesquisa != "Todas":
    # Aqui mostramos a área pesquisada E os vazios para manter a referência visual (opcional)
    df_filtrado = df_filtrado[(df_filtrado["Área_Exibicao"] == area_pesquisa) | (df_filtrado["Área_Exibicao"] == 'VAZIO')]
if endereco_pesquisa:
    df_filtrado = df_filtrado[df_filtrado["Posição no depósito"] == endereco_pesquisa]


# 3. Simulador 3D do Depósito
st.markdown("### 🏗️ Simulador 3D do Depósito - CD Passo Fundo")

# Vamos forçar a cor cinza transparente para os buracos 'VAZIO'
mapa_cores = {'VAZIO': 'rgba(200, 200, 200, 0.1)'} # Cinza claro quase transparente
# As outras áreas (PERF, FARM, etc.) o Plotly escolhe automaticamente cores vibrantes

fig_3d = px.scatter_3d(
    df_filtrado, 
    x='Coluna', 
    y='Corredor', 
    z='Nível',
    color='Área_Exibicao', 
    color_discrete_map=mapa_cores,
    hover_name='Posição no depósito',
    hover_data={
        'Status': True,
        'Produto': True, 
        'Quantidade': True, 
        'Vencido': True,
        'Área_Exibicao': False,
        'Corredor': False, 'Coluna': False, 'Nível': False
    },
    title="Malha Completa do Galpão (Cinza = Vazio | Colorido = Ocupado)"
)

# Ajuste do tamanho dos paletes. Como agora temos milhares, diminuímos um pouco o 'size' para não virar uma bagunça
fig_3d.update_traces(marker=dict(size=4, symbol='square')) 

# Lógica da borda vermelha para os vencidos
for trace in fig_3d.data:
    area_name = trace.name
    if area_name == 'VAZIO':
        continue # Não aplica borda em posições vazias
        
    df_trace = df_filtrado[df_filtrado['Área_Exibicao'] == area_name]
    line_colors = ['red' if v else 'rgba(0,0,0,0)' for v in df_trace['Vencido']]
    trace.marker.line = dict(color=line_colors, width=4)

fig_3d.update_layout(
    scene=dict(
        xaxis_title='Coluna',
        yaxis_title='Corredor',
        zaxis_title='Nível',
        aspectmode='data' # Isso faz o gráfico respeitar as proporções reais da planta!
    ),
    height=700 # Deixa o gráfico mais alto na tela
)

st.plotly_chart(fig_3d, use_container_width=True)

# Dashboards básicos apenas para produtos em estoque
df_estoque_real = df_filtrado[df_filtrado['Status'] == 'Ocupado']
st.markdown("### 📊 Indicadores Principais")
col1, col2 = st.columns(2)
col1.metric("Posições Ocupadas", len(df_estoque_real))
col2.metric("Posições Vazias", len(df_filtrado[df_filtrado['Status'] == 'Vazio']))