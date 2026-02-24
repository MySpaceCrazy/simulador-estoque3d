import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Simulador de Estoque 3D", layout="wide")

st.title("📦 Simulador de Estoque 3D - CD Passo Fundo")

# --- BARRA LATERAL: UPLOAD DE ARQUIVO ---
st.sidebar.header("📁 1. Carga de Dados")
arquivo_estoque = st.sidebar.file_uploader("Faça upload do Estoque (Excel ou CSV)", type=["xlsx", "csv"])

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
    
    # GARANTIA 1: Usa o Tp.posição depósito da base fixa para as cores
    df_layout['Área_Exibicao'] = df_layout['Tp.posição depósito'].fillna('Desconhecido')

    # B. Carregar o ESTOQUE DO USUÁRIO
    if arquivo is not None:
        if arquivo.name.endswith('.csv'):
            try:
                dados_estoque = pd.read_csv(arquivo, sep=None, engine='python', encoding='utf-8')
            except UnicodeDecodeError:
                arquivo.seek(0)
                dados_estoque = pd.read_csv(arquivo, sep=None, engine='python', encoding='latin-1')
        else:
            dados_estoque = pd.read_excel(arquivo)
            
        # Padroniza a coluna de Vencimento caso o sistema gere com nome diferente
        if 'Data do vencimento' in dados_estoque.columns:
            dados_estoque = dados_estoque.rename(columns={'Data do vencimento': 'Vencimento'})
            
        if 'Vencimento' in dados_estoque.columns:
            dados_estoque['Vencimento'] = pd.to_datetime(dados_estoque['Vencimento'], errors='coerce')
            
        # C. CRUZAR OS DADOS (Left Join)
        df_completo = pd.merge(df_layout, dados_estoque, on="Posição no depósito", how="left")
        df_completo['Status'] = df_completo.get('Produto', pd.Series([None]*len(df_completo))).apply(lambda x: 'Ocupado' if pd.notna(x) else 'Vazio')
        
        hoje = pd.Timestamp.today()
        if 'Vencimento' in df_completo.columns:
            df_completo['Vencido'] = (df_completo['Vencimento'] < hoje) & (df_completo['Status'] == 'Ocupado')
        else:
            df_completo['Vencido'] = False
            
    else:
        # Se vazio, monta a malha pura
        df_completo = df_layout.copy()
        df_completo['Status'] = 'Vazio'
        df_completo['Vencido'] = False
        df_completo['Vencimento'] = pd.NaT

    # Cria uma coluna corigatória pro Plotly separar o que é Vazio e o que tem Cor
    df_completo['Cor_Plot'] = df_completo.apply(lambda row: ' ESTRUTURA VAZIA' if row['Status'] == 'Vazio' else row['Área_Exibicao'], axis=1)

    return df_completo

df = carregar_dados(arquivo_estoque)

if df.empty:
    st.stop()

# --- BARRA LATERAL: FILTROS E VISUALIZAÇÃO ---
st.sidebar.header("🔍 2. Filtros e Visualização")

mostrar_estrutura = st.sidebar.toggle("Mostrar Estrutura (Porta-Paletes Vazios)", value=True)

produto_pesquisa = st.sidebar.text_input("Pesquisa por Produto (Código)")
endereco_pesquisa = st.sidebar.text_input("Pesquisa por Endereço (ex: 025-071-040-001)")

# GARANTIA 2: Filtro por Data de Vencimento
df_ocupado = df[df['Status'] == 'Ocupado']
if 'Vencimento' in df.columns and len(df_ocupado) > 0:
    datas_unicas = df_ocupado['Vencimento'].dt.date.dropna().unique().tolist()
    datas_unicas.sort()
else:
    datas_unicas = []

data_pesquisa = st.sidebar.selectbox("Pesquisa por Data de Vencimento", options=["Todas"] + datas_unicas)

# Aplicar filtros
df_filtrado = df.copy()

if not mostrar_estrutura:
    df_filtrado = df_filtrado[df_filtrado['Status'] == 'Ocupado']

if produto_pesquisa:
    # Mostra o produto E a estrutura para dar contexto geográfico no galpão
    df_filtrado = df_filtrado[(df_filtrado["Produto"].astype(str).str.contains(produto_pesquisa, na=False)) | (df_filtrado['Status'] == 'Vazio')]
if endereco_pesquisa:
    df_filtrado = df_filtrado[(df_filtrado["Posição no depósito"].str.contains(endereco_pesquisa, na=False)) | (df_filtrado['Status'] == 'Vazio')]
if data_pesquisa != "Todas":
    # Aqui também mantemos a estrutura vazia de fundo (se o toggle estiver ativo) para o usuário saber onde a data está fisicamente
    df_filtrado = df_filtrado[(df_filtrado['Vencimento'].dt.date == data_pesquisa) | (df_filtrado['Status'] == 'Vazio')]

# Para evitar travar o navegador se a pesquisa retornar só vazios:
if not mostrar_estrutura and df_filtrado.empty:
    st.warning("Nenhum palete encontrado com esses filtros.")
    st.stop()


# 3. Simulador 3D do Depósito
st.markdown("### 🏗️ Simulador 3D do Depósito - CD Passo Fundo")

if arquivo_estoque is None:
    st.info("👈 Faça o upload da sua planilha de estoque na barra lateral para popular os porta-paletes.")

fig_3d = px.scatter_3d(
    df_filtrado, 
    x='Coluna', 
    y='Corredor', 
    z='Nível',
    color='Cor_Plot', 
    hover_name='Posição no depósito',
    hover_data={
        'Status': True,
        'Produto': True, 
        'Quantidade': True, 
        'Vencido': True,
        'Cor_Plot': False,
        'Corredor': False, 'Coluna': False, 'Nível': False
    }
)

# GARANTIA 3: Efeito visual Porta-Palete vs Palete Colorido
for trace in fig_3d.data:
    nome_legenda = trace.name
    
    if nome_legenda == ' ESTRUTURA VAZIA':
        # ESTRUTURA DO RACK (Maior, fundo transparente, borda cinza escura)
        trace.marker.color = 'rgba(255, 255, 255, 0.0)' 
        trace.marker.line = dict(color='rgba(150, 150, 150, 0.6)', width=2) 
        trace.marker.symbol = 'square'
        trace.marker.size = 6 
    else:
        # PALETE OCUPADO COM ESTOQUE (Sólido, colorido, um pouco menor para "caber dentro" do rack)
        df_trace = df_filtrado[df_filtrado['Cor_Plot'] == nome_legenda]
        # Borda vermelha grossa se vencido, senão borda preta fina
        line_colors = ['red' if v else 'black' for v in df_trace['Vencido']]
        line_widths = [5 if v else 1 for v in df_trace['Vencido']]
        
        trace.marker.line = dict(color=line_colors, width=line_widths)
        trace.marker.symbol = 'square'
        trace.marker.size = 4.5 # Um pouquinho menor que o tamanho 6 da estrutura vazia

fig_3d.update_layout(
    scene=dict(
        xaxis_title='Coluna',
        yaxis_title='Corredor',
        zaxis_title='Nível',
        aspectmode='data' 
    ),
    height=750,
    margin=dict(l=0, r=0, b=0, t=0),
    legend_title_text='Legenda do Depósito'
)

st.plotly_chart(fig_3d, use_container_width=True)

# Dashboards
df_estoque_real = df[df['Status'] == 'Ocupado']
st.markdown("### 📊 Indicadores Principais")
col1, col2, col3 = st.columns(3)
col1.metric("Total de Posições Ocupadas", len(df_estoque_real))
col2.metric("Total de Posições Vazias", len(df[df['Status'] == 'Vazio']))
col3.metric("Paletes Vencidos", len(df[df['Vencido'] == True]))