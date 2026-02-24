import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

st.set_page_config(page_title="Simulador de Estoque 3D", layout="wide")

st.title("📦 Simulador de Estoque 3D - CD Passo Fundo")

# --- BARRA LATERAL: UPLOAD ---
st.sidebar.header("📁 1. Carga de Dados")
arquivo_estoque = st.sidebar.file_uploader("Faça upload do Estoque (Excel ou CSV)", type=["xlsx", "csv"])

@st.cache_data
def carregar_dados(arquivo):
    try:
        df_layout = pd.read_csv("EXPORT_20260224_122851.xlsx - Data.csv", encoding="latin-1", sep=";")
    except FileNotFoundError:
        st.error("Arquivo de layout não encontrado na pasta.")
        return pd.DataFrame()

    df_layout[['Corredor', 'Coluna', 'Nível', 'Posição_Extra']] = df_layout['Posição no depósito'].str.split('-', expand=True)
    df_layout['Corredor'] = pd.to_numeric(df_layout['Corredor'])
    df_layout['Coluna'] = pd.to_numeric(df_layout['Coluna'])
    df_layout['Nível'] = pd.to_numeric(df_layout['Nível'])
    
    # TRUQUE DE ENGENHARIA 3D: O Espaçamento Físico
    # Multiplicamos o corredor por 3 para afastar os corredores uns dos outros.
    # Depois, se a coluna for par, empurramos um pouco pra cima (+0.8), se for ímpar, pra baixo (-0.8).
    # Isso cria o "vão livre" (rua) no meio do corredor!
    df_layout['Y_Plot'] = df_layout['Corredor'] * 3
    df_layout['Y_Plot'] = df_layout.apply(
        lambda row: row['Y_Plot'] + 0.8 if row['Coluna'] % 2 == 0 else row['Y_Plot'] - 0.8, 
        axis=1
    )
    
    df_layout['Área_Exibicao'] = df_layout['Área armazmto.'].fillna('Desconhecido')

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
            
        df_completo = pd.merge(df_layout, dados_estoque, on="Posição no depósito", how="left")
        
        df_completo['Produto'] = df_completo.get('Produto', pd.Series(['-']*len(df_completo))).fillna('-')
        df_completo['Quantidade'] = df_completo.get('Quantidade', pd.Series([0]*len(df_completo))).fillna(0)
        df_completo['Descrição produto'] = df_completo.get('Descrição produto', pd.Series(['-']*len(df_completo))).fillna('-')
        
        df_completo['Status'] = df_completo['Produto'].apply(lambda x: 'Ocupado' if str(x) != '-' else 'Vazio')
        
        hoje = pd.Timestamp.today()
        if 'Vencimento' in df_completo.columns:
            df_completo['Vencido'] = (df_completo['Vencimento'] < hoje) & (df_completo['Status'] == 'Ocupado')
        else:
            df_completo['Vencido'] = False
            
    else:
        df_completo = df_layout.copy()
        df_completo['Status'] = 'Vazio'
        df_completo['Vencido'] = False
        df_completo['Vencimento'] = pd.NaT
        df_completo['Produto'] = '-'
        df_completo['Descrição produto'] = '-'
        df_completo['Quantidade'] = 0

    df_completo['Cor_Plot'] = df_completo.apply(lambda row: ' ESTRUTURA VAZIA' if row['Status'] == 'Vazio' else str(row['Área_Exibicao']), axis=1)

    return df_completo

df = carregar_dados(arquivo_estoque)

if df.empty:
    st.stop()

# --- BARRA LATERAL: FILTROS E VISUALIZAÇÃO ---
st.sidebar.header("🔍 2. Filtros e Visualização")

mostrar_estrutura = st.sidebar.toggle("Mostrar Estrutura (Porta-Paletes Vazios)", value=True)

areas_disponiveis = [a for a in df["Área_Exibicao"].unique() if str(a) != "nan" and str(a) != "Desconhecido"]
areas_disponiveis.sort()
area_pesquisa = st.sidebar.selectbox("Pesquisa por Área de Armazenagem", options=["Todas"] + areas_disponiveis)

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

if area_pesquisa != "Todas":
    df_filtrado = df_filtrado[df_filtrado["Área_Exibicao"] == area_pesquisa]

if produto_pesquisa:
    df_filtrado = df_filtrado[(df_filtrado["Produto"].astype(str).str.contains(produto_pesquisa, na=False)) | (df_filtrado['Status'] == 'Vazio')]
if endereco_pesquisa:
    df_filtrado = df_filtrado[(df_filtrado["Posição no depósito"].str.contains(endereco_pesquisa, na=False)) | (df_filtrado['Status'] == 'Vazio')]
if data_pesquisa != "Todas":
    df_filtrado = df_filtrado[(df_filtrado['Vencimento'].dt.date == data_pesquisa) | (df_filtrado['Status'] == 'Vazio')]

if df_filtrado.empty:
    st.warning("Nenhum dado para exibir com os filtros atuais.")
    st.stop()

# ==========================================
# CAIXA RESUMO DOS FILTROS APLICADOS
# ==========================================
df_filtrado_ocupado = df_filtrado[df_filtrado['Status'] == 'Ocupado']

st.markdown("### 📋 Resumo da Pesquisa Atual")
res_col1, res_col2, res_col3 = st.columns(3)
res_col1.info(f"**Total de Unidades:** {df_filtrado_ocupado['Quantidade'].sum():,.0f} un")
res_col2.success(f"**Produtos Diferentes:** {df_filtrado_ocupado['Produto'].nunique()} SKUs")
res_col3.warning(f"**Endereços Utilizados:** {len(df_filtrado_ocupado)} posições")

st.markdown("---")


# ==========================================
# SIMULADOR 3D
# ==========================================
st.markdown("### 🏗️ Mapa 3D do CD")

if arquivo_estoque is None:
    st.info("👈 Faça o upload da sua planilha de estoque para popular o galpão.")

paleta_segura = ['#1f77b4', '#2ca02c', '#ff7f0e', '#9467bd', '#8c564b', '#17becf', '#e377c2', '#7f7f7f', '#bcbd22']
mapa_cores = {' ESTRUTURA VAZIA': 'rgba(255, 255, 255, 0)'}
for i, area in enumerate(areas_disponiveis):
    mapa_cores[area] = paleta_segura[i % len(paleta_segura)]

# Note que agora usamos Y_Plot para o eixo Y
fig_3d = px.scatter_3d(
    df_filtrado, 
    x='Coluna', 
    y='Y_Plot', 
    z='Nível',
    color='Cor_Plot',
    color_discrete_map=mapa_cores,
    hover_name='Posição no depósito',
    hover_data={
        'Status': True, 'Produto': True, 'Quantidade': True, 'Vencido': True,
        'Cor_Plot': False, 'Coluna': False, 'Y_Plot': False, 'Nível': False, 'Corredor': False
    }
)

for trace in fig_3d.data:
    nome_legenda = trace.name
    if nome_legenda == ' ESTRUTURA VAZIA':
        trace.marker.color = 'rgba(255, 255, 255, 0.0)' 
        trace.marker.line = dict(color='rgba(150, 150, 150, 0.5)', width=2) 
        trace.marker.symbol = 'square'
        trace.marker.size = 5 
    else:
        df_trace = df_filtrado[df_filtrado['Cor_Plot'] == nome_legenda]
        line_colors = ['red' if v else 'rgba(0,0,0,0)' for v in df_trace['Vencido']]
        trace.marker.line = dict(color=line_colors, width=6) 
        trace.marker.symbol = 'square'
        trace.marker.size = 4 

# Esticando o galpão para ele não ficar um cubo quadrado
fig_3d.update_layout(
    scene=dict(
        xaxis_title='Comprimento (Colunas)',
        yaxis_title='Profundidade (Corredores)',
        zaxis_title='Altura (Níveis)',
        aspectmode='manual',
        aspectratio=dict(x=3, y=1.5, z=0.5) # x=3 faz o galpão ficar largo!
    ),
    height=600,
    margin=dict(l=0, r=0, b=0, t=0),
    legend_title_text='Legenda do Depósito',
    clickmode='event+select'
)

# Renderiza o gráfico e CAPTURA O CLIQUE do usuário (Requer Streamlit 1.35+)
evento = st.plotly_chart(fig_3d, use_container_width=True, on_select="rerun", selection_mode="points")

# ==========================================
# PAINEL DE DETALHES DO CLIQUE
# ==========================================
if evento and len(evento.selection.points) > 0:
    ponto_clicado = evento.selection.points[0]
    endereco_clicado = ponto_clicado["hovertext"]
    
    st.markdown("---")
    st.markdown(f"### 🔎 Detalhes do Endereço: `{endereco_clicado}`")
    
    # Busca os dados completos daquele endereço no dataframe
    dados_endereco = df[df['Posição no depósito'] == endereco_clicado].iloc[0]
    
    col_d1, col_d2, col_d3 = st.columns(3)
    
    with col_d1:
        st.write(f"**Área Armaz.:** {dados_endereco['Área_Exibicao']}")
        st.write(f"**Tipo Depósito:** {dados_endereco['Tipo de depósito'] if 'Tipo de depósito' in df.columns else 'N/A'}")
        st.write(f"**Status:** {dados_endereco['Status']}")
        
    with col_d2:
        st.write(f"**Código Produto:** {dados_endereco['Produto']}")
        st.write(f"**Descrição:** {dados_endereco['Descrição produto']}")
        
    with col_d3:
        st.write(f"**Quantidade:** {dados_endereco['Quantidade']} un")
        
        # Formata a data bonitinha se existir
        if pd.notna(dados_endereco['Vencimento']):
            data_formatada = dados_endereco['Vencimento'].strftime('%d/%m/%Y')
            if dados_endereco['Vencido']:
                st.error(f"**Validade:** {data_formatada} (VENCIDO)")
            else:
                st.success(f"**Validade:** {data_formatada}")
        else:
            st.write("**Validade:** N/A")