import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Configuração da página para ocupar toda a tela
st.set_page_config(page_title="Simulador de Estoque 3D", layout="wide")

st.title("📦 Simulador de Estoque 3D")

# 1. Função para carregar e tratar os dados
@st.cache_data
def carregar_dados():
    # Simulando a carga dos dados (futuramente pd.read_excel('seu_arquivo.xlsx'))
    dados_mock = pd.DataFrame({
        "Posição no depósito": ["020-001-010-001", "020-001-020-001", "020-002-010-001", "021-001-010-001", "021-002-010-002"],
        "UC": ["10001", "10002", "10003", "10004", "10005"],
        "Produto": ["10041398", "8593", "10001226", "10041398", "9999"],
        "Descrição produto": ["ESFOLIANTE", "SABONETE", "ENXAGUANTE", "ESFOLIANTE", "SHAMPOO"],
        "Vencimento": pd.to_datetime(["2029-01-01", "2023-12-31", "2027-12-30", "2025-06-01", "2023-01-01"]),
        "Quantidade": [240, 2232, 72, 100, 50],
        "UMB": ["UN", "UN", "UN", "UN", "UN"],
        "Área": ["PERF", "PERF", "FARM", "PERF", "COSM"],
        "Tp. Posição depósito": ["P080", "P136", "P080", "P080", "P080"]
    })
    
    # --- A ADIÇÃO NOVA COMEÇA AQUI ---
    # Quebrar a string do endereço em 4 novas colunas
    dados_mock[['Corredor', 'Coluna', 'Nível', 'Posição']] = dados_mock['Posição no depósito'].str.split('-', expand=True)
    
    # Transformar as novas colunas em números para o gráfico 3D
    dados_mock['Corredor'] = pd.to_numeric(dados_mock['Corredor'])
    dados_mock['Coluna'] = pd.to_numeric(dados_mock['Coluna'])
    dados_mock['Nível'] = pd.to_numeric(dados_mock['Nível'])
    dados_mock['Posição'] = pd.to_numeric(dados_mock['Posição'])
    # --- A ADIÇÃO NOVA TERMINA AQUI ---
    
    return dados_mock

df = carregar_dados()

# 2. Barra Lateral para Pesquisas e Filtros
st.sidebar.header("🔍 Pesquisas Detalhadas")

# Filtro por Produto
produto_pesquisa = st.sidebar.text_input("Pesquisa por Produto (Reduzido)")

# Filtro por Área
areas_disponiveis = df["Área"].unique()
area_pesquisa = st.sidebar.selectbox("Pesquisa por Área", options=["Todas"] + list(areas_disponiveis))

# Filtro por Vencimento
vencimento_pesquisa = st.sidebar.date_input("Pesquisa por Vencimento", value=None)

# Filtro por Endereço
endereco_pesquisa = st.sidebar.text_input("Pesquisa por Endereço (ex: 020-001-010-001)")

# Aplicar os filtros ao DataFrame
df_filtrado = df.copy()
if produto_pesquisa:
    df_filtrado = df_filtrado[df_filtrado["Produto"] == produto_pesquisa]
if area_pesquisa != "Todas":
    df_filtrado = df_filtrado[df_filtrado["Área"] == area_pesquisa]
if vencimento_pesquisa:
    df_filtrado = df_filtrado[df_filtrado["Vencimento"].dt.date == vencimento_pesquisa]
if endereco_pesquisa:
    df_filtrado = df_filtrado[df_filtrado["Posição no depósito"] == endereco_pesquisa]

# 3. Seção de Dashboards (KPIs)
st.markdown("### 📊 Indicadores Principais")
col1, col2 = st.columns(2)

with col1:
    estoque_total = df_filtrado["Quantidade"].sum()
    st.metric("Estoque Total (Unidades)", f"{estoque_total:,.0f}")

with col2:
    produtos_diferentes = df_filtrado["Produto"].nunique()
    st.metric("Produtos Diferentes", produtos_diferentes)

# 4. Gráficos
col3, col4 = st.columns(2)

with col3:
    st.markdown("**Posições Ocupadas vs Vazias**")
    # Gráfico de rosca simulado (depois podemos calcular as vazias de verdade com base na malha do galpão)
    fig_rosca = px.pie(values=[len(df_filtrado), 10], names=['Ocupadas', 'Vazias'], hole=0.5, 
                       color_discrete_sequence=['#2E86C1', '#D6DBDF'])
    st.plotly_chart(fig_rosca, use_container_width=True)

with col4:
    st.markdown("**Unidades por Área**")
    fig_pizza = px.pie(df_filtrado, values='Quantidade', names='Área')
    st.plotly_chart(fig_pizza, use_container_width=True)

# 5. Simulador 3D do Depósito
st.markdown("### 🏗️ Simulador 3D do Depósito")

# 1. Identificar se o produto está vencido com base na data de hoje
hoje = pd.Timestamp.today()
df_filtrado['Vencido'] = df_filtrado['Vencimento'] < hoje

fig_3d = px.scatter_3d(
    df_filtrado, 
    x='Coluna', 
    y='Corredor', 
    z='Nível',
    color='Área', 
    hover_name='Posição no depósito',
    hover_data={
        'Produto': True, 
        'Descrição produto': True, 
        'Quantidade': True, 
        'Vencimento': '|%d/%m/%Y',
        'Vencido': True, # Adiciona a informação de status no popup do mouse
        'Corredor': False, 
        'Coluna': False, 
        'Nível': False
    },
    title="Visão Espacial do Estoque (Contorno Vermelho = Vencido)"
)

# 2. Ajustar o tamanho base dos paletes
fig_3d.update_traces(marker=dict(size=10, symbol='square')) 

# 3. Criar a lógica do contorno vermelho para os vencidos
for trace in fig_3d.data:
    area_name = trace.name
    # Pega os dados apenas da área atual do loop
    df_trace = df_filtrado[df_filtrado['Área'] == area_name]
    
    # Se estiver vencido a borda é vermelha. Se não, é transparente (rgba com alpha 0)
    line_colors = ['red' if v else 'rgba(0,0,0,0)' for v in df_trace['Vencido']]
    
    # A correção está aqui: passamos a lista de cores, mas a espessura (width) é um número fixo!
    trace.marker.line = dict(color=line_colors, width=5)

# 4. Ajustes finais da câmera e eixos
fig_3d.update_layout(scene=dict(
    xaxis_title='Coluna (Largura)',
    yaxis_title='Corredor (Profundidade)',
    zaxis_title='Nível (Altura)'
))

st.plotly_chart(fig_3d, use_container_width=True)

# Exibição da tabela para verificação detalhada
st.markdown("### 📋 Tabela de Dados")
st.dataframe(df_filtrado)