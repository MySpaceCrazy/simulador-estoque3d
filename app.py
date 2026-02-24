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
            
        if 'Data do vencimento' in dados_estoque.columns:
            dados_estoque = dados_estoque.rename(columns={'Data do vencimento': 'Vencimento'})
            
        if 'Vencimento' in dados_estoque.columns:
            dados_estoque['Vencimento'] = pd.to_datetime(dados_estoque['Vencimento'], errors='coerce')
            
        # C. CRUZAR OS DADOS (Left Join)
        df_completo = pd.merge(df_layout, dados_estoque, on="Posição no depósito", how="left")
        
        # Garante que não teremos Nones que quebram o Plotly
        df_completo['Produto'] = df_completo.get('Produto', pd.Series(['-']*len(df_completo))).fillna('-')
        df_completo['Quantidade'] = df_completo.get('Quantidade', pd.Series([0]*len(df_completo))).fillna(0)
        
        df_completo['Status'] = df_completo['Produto'].apply(lambda x: 'Ocupado' if str(x) != '-' else 'Vazio')
        
        hoje = pd.Timestamp.today()
        if 'Vencimento' in df_completo.columns:
            df_completo['Vencido'] = (df_completo['Vencimento'] < hoje) & (df_completo['Status'] == 'Ocupado')
        else:
            df_completo['Vencido'] = False
            
    else:
        # CORREÇÃO 1: Evita enviar None para o Plotly inicializando com strings e zeros
        df_completo = df_layout.copy()
        df_completo['Status'] = 'Vazio'
        df_completo['Vencido'] = False
        df_completo['Vencimento'] = pd.NaT
        df_completo['Produto'] = '-'
        df_completo['Quantidade'] = 0

    df_completo['Cor_Plot'] = df_completo.apply(lambda row: ' ESTRUTURA VAZIA' if row['Status'] == 'Vazio' else str(row['Área_Exibicao']), axis=1)

    return df_completo

df = carregar_dados(arquivo_estoque)

if df.empty:
    st.stop()

# --- BARRA LATERAL: FILTROS E VISUALIZAÇÃO ---
st.sidebar.header("🔍 2. Filtros e Visualização")

mostrar_estrutura = st.sidebar.toggle("Mostrar Estrutura (Porta-Paletes Vazios)", value=True)

produto_pesquisa = st.sidebar.text_input("Pesquisa por Produto (Código)")
endereco_pesquisa = st.sidebar.text_input("Pesquisa por Endereço (ex: 025-071-040-001)")

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
    df_filtrado = df_filtrado[(df_filtrado["Produto"].astype(str).str.contains(produto_pesquisa, na=False)) | (df_filtrado['Status'] == 'Vazio')]
if endereco_pesquisa:
    df_filtrado = df_filtrado[(df_filtrado["Posição no depósito"].str.contains(endereco_pesquisa, na=False)) | (df_filtrado['Status'] == 'Vazio')]
if data_pesquisa != "Todas":
    df_filtrado = df_filtrado[(df_filtrado['Vencimento'].dt.date == data_pesquisa) | (df_filtrado['Status'] == 'Vazio')]

if df_filtrado.empty:
    st.warning("Nenhum dado para exibir com os filtros atuais.")
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

for trace in fig_3d.data:
    nome_legenda = trace.name
    
    if nome_legenda == ' ESTRUTURA VAZIA':
        trace.marker.color = 'rgba(255, 255, 255, 0.0)' 
        trace.marker.line = dict(color='rgba(150, 150, 150, 0.6)', width=2) 
        trace.marker.symbol = 'square'
        trace.marker.size = 6 
    else:
        df_trace = df_filtrado[df_filtrado['Cor_Plot'] == nome_legenda]
        
        # CORREÇÃO 2: O Plotly 3D aceita array para CORES da borda, mas NÃO aceita array para WIDTH.
        # Portanto, enviamos um width fixo de 4, mas usamos rgba(0,0,0,0) (transparente) para ocultar a borda de quem NÃO está vencido.
        line_colors = ['red' if v else 'rgba(0,0,0,0)' for v in df_trace['Vencido']]
        
        trace.marker.line = dict(color=line_colors, width=4) 
        trace.marker.symbol = 'square'
        trace.marker.size = 4.5 

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