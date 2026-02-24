import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Simulador de Estoque 3D", layout="wide")

st.title("📦 Simulador de Estoque 3D - CD Passo Fundo")

# --- BARRA LATERAL: UPLOAD DE ARQUIVO ---
st.sidebar.header("📁 1. Carga de Dados")
arquivo_estoque = st.sidebar.file_uploader("Faça upload do Estoque (Excel ou CSV)", type=["xlsx", "csv"])

# 1. Função para carregar a Malha e cruzar com o Estoque
@st.cache_data
def carregar_dados(arquivo):
    # A. Carregar o ESQUELETO (Layout do Galpão - Fixo)
    try:
        df_layout = pd.read_csv("EXPORT_20260224_122851.xlsx - Data.csv", encoding="latin-1", sep=";")
    except FileNotFoundError:
        st.error("Arquivo de layout não encontrado na pasta.")
        return pd.DataFrame()

    df_layout[['Corredor', 'Coluna', 'Nível', 'Posição_Extra']] = df_layout['Posição no depósito'].str.split('-', expand=True)
    df_layout['Corredor'] = pd.to_numeric(df_layout['Corredor'])
    df_layout['Coluna'] = pd.to_numeric(df_layout['Coluna'])
    df_layout['Nível'] = pd.to_numeric(df_layout['Nível'])

    # B. Carregar o ESTOQUE DO USUÁRIO
    if arquivo is not None:
        if arquivo.name.endswith('.csv'):
            dados_estoque = pd.read_csv(arquivo, sep=';', encoding='latin-1')
        else:
            dados_estoque = pd.read_excel(arquivo)
            
        # Converter data de vencimento se ela existir no arquivo
        if 'Vencimento' in dados_estoque.columns:
            dados_estoque['Vencimento'] = pd.to_datetime(dados_estoque['Vencimento'], errors='coerce')
            
        # C. CRUZAR OS DADOS (Left Join)
        df_completo = pd.merge(df_layout, dados_estoque, on="Posição no depósito", how="left")
        
        # Identificar o que é Vazio e o que está Ocupado
        df_completo['Área_Exibicao'] = df_completo.get('Área_Estoque', pd.Series([None]*len(df_completo))).fillna('VAZIO')
        df_completo['Status'] = df_completo.get('Produto', pd.Series([None]*len(df_completo))).apply(lambda x: 'Ocupado' if pd.notna(x) else 'Vazio')
        
        hoje = pd.Timestamp.today()
        if 'Vencimento' in df_completo.columns:
            df_completo['Vencido'] = (df_completo['Vencimento'] < hoje) & (df_completo['Status'] == 'Ocupado')
        else:
            df_completo['Vencido'] = False
            
    else:
        # Se o usuário ainda não subiu o arquivo, mostra a malha toda vazia
        df_completo = df_layout.copy()
        df_completo['Área_Exibicao'] = 'VAZIO'
        df_completo['Status'] = 'Vazio'
        df_completo['Vencido'] = False
        df_completo['Produto'] = None
        df_completo['Quantidade'] = None

    return df_completo

# Passamos o arquivo upado para a função
df = carregar_dados(arquivo_estoque)

if df.empty:
    st.stop()

# --- BARRA LATERAL: FILTROS E VISUALIZAÇÃO ---
st.sidebar.header("🔍 2. Filtros e Visualização")

# O pulo do gato para melhorar a visualização:
mostrar_vazios = st.sidebar.toggle("Mostrar Posições Vazias na Planta?", value=False)

produto_pesquisa = st.sidebar.text_input("Pesquisa por Produto (Código)")
areas_disponiveis = [a for a in df["Área_Exibicao"].unique() if a != "VAZIO"]
area_pesquisa = st.sidebar.selectbox("Pesquisa por Área", options=["Todas"] + areas_disponiveis)
endereco_pesquisa = st.sidebar.text_input("Pesquisa por Endereço (ex: 025-071-040-001)")

# Aplicar filtros
df_filtrado = df.copy()

if not mostrar_vazios:
    # Remove as posições vazias da visualização 3D para limpar a tela
    df_filtrado = df_filtrado[df_filtrado['Status'] == 'Ocupado']

if produto_pesquisa:
    df_filtrado = df_filtrado[df_filtrado["Produto"].astype(str).str.contains(produto_pesquisa, na=False)]
if area_pesquisa != "Todas":
    # Se estiver filtrando por área, e o usuário quiser ver os vazios, mantemos os vazios na tela
    if mostrar_vazios:
        df_filtrado = df_filtrado[(df_filtrado["Área_Exibicao"] == area_pesquisa) | (df_filtrado["Área_Exibicao"] == 'VAZIO')]
    else:
        df_filtrado = df_filtrado[df_filtrado["Área_Exibicao"] == area_pesquisa]
if endereco_pesquisa:
    df_filtrado = df_filtrado[df_filtrado["Posição no depósito"].str.contains(endereco_pesquisa, na=False)]

# 3. Simulador 3D do Depósito
st.markdown("### 🏗️ Simulador 3D do Depósito - CD Passo Fundo")

if arquivo_estoque is None:
    st.info("👈 Faça o upload da sua planilha de estoque na barra lateral para popular o galpão.")

# Definir as cores (Vazio fica transparente, ocupados pegam cores dinâmicas)
mapa_cores = {'VAZIO': 'rgba(200, 200, 200, 0.05)'}

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
    }
)

fig_3d.update_traces(marker=dict(size=4, symbol='square')) 

# Lógica da borda vermelha para os vencidos
for trace in fig_3d.data:
    area_name = trace.name
    if area_name == 'VAZIO':
        continue 
        
    df_trace = df_filtrado[df_filtrado['Área_Exibicao'] == area_name]
    line_colors = ['red' if v else 'rgba(0,0,0,0)' for v in df_trace['Vencido']]
    trace.marker.line = dict(color=line_colors, width=4)

fig_3d.update_layout(
    scene=dict(
        xaxis_title='Coluna',
        yaxis_title='Corredor',
        zaxis_title='Nível',
        aspectmode='data' 
    ),
    height=750,
    margin=dict(l=0, r=0, b=0, t=0) # Tira as margens em branco do gráfico
)

st.plotly_chart(fig_3d, use_container_width=True)

# Dashboards
df_estoque_real = df[df['Status'] == 'Ocupado'] # Pega do DF original para não ser afetado pelo filtro de visualização
st.markdown("### 📊 Indicadores Principais")
col1, col2 = st.columns(2)
col1.metric("Total de Posições Ocupadas", len(df_estoque_real))
col2.metric("Total de Posições Vazias", len(df[df['Status'] == 'Vazio']))