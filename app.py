import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Simulador de Estoque 3D", layout="wide")

# Função para formatar números no padrão BR (ex: 1.000)
def formata_br(numero):
    return f"{numero:,.0f}".replace(",", ".")

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
    
    # TRUQUE DO VÃO LIVRE: Afasta os corredores e separa lado Par e Ímpar
    df_layout['Y_Plot'] = df_layout['Corredor'] * 3
    df_layout['Y_Plot'] = df_layout.apply(
        lambda row: row['Y_Plot'] + 0.8 if row['Coluna'] % 2 == 0 else row['Y_Plot'] - 0.8, 
        axis=1
    )
    
    df_layout['Área_Exibicao'] = df_layout['Área armazmto.'].fillna('Desconhecido')

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
            
        # C. CRUZAR OS DADOS
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
        # Cria a estrutura aramada vazia se não houver upload
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
st.sidebar.header("🔍 2. Filtros")

mostrar_estrutura = st.sidebar.toggle("Mostrar Estrutura (Porta-Paletes Vazios)", value=True)

areas_disponiveis = [a for a in df["Área_Exibicao"].unique() if str(a) != "nan" and str(a) != "Desconhecido" and a != " ESTRUTURA VAZIA"]
areas_disponiveis.sort()
area_pesquisa = st.sidebar.selectbox("Pesquisa por Área", options=["Todas"] + areas_disponiveis)

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


# ==========================================
# 3. DASHBOARDS E INDICADORES (Agora no topo!)
# ==========================================
st.markdown("---")
st.markdown("### 📊 Indicadores da Operação")

# Dados para os cards
df_real = df[df['Área_Exibicao'] != 'Desconhecido']
total_posicoes = len(df_real)
ocupadas = len(df_real[df_real['Status'] == 'Ocupado'])
vazias = len(df_real[df_real['Status'] == 'Vazio'])
vencidos = len(df_real[df_real['Vencido'] == True])
taxa_ocupacao = (ocupadas / total_posicoes * 100) if total_posicoes > 0 else 0

# Dados filtrados para resumo
df_filtrado_ocupado = df_filtrado[df_filtrado['Status'] == 'Ocupado']
qtd_filtrada = df_filtrado_ocupado['Quantidade'].sum()

# Linha de Métricas Gerais
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("📦 Ocupadas (Geral)", formata_br(ocupadas))
col2.metric("🟩 Vazias (Geral)", formata_br(vazias))
col3.metric("📈 Ocupação (Geral)", f"{taxa_ocupacao:.1f}%")
col4.metric("🚨 Vencidos", formata_br(vencidos))
col5.metric("🔍 Qtd. Peças no Filtro", formata_br(qtd_filtrada))

# Linha de Gráficos
st.markdown("<br>", unsafe_allow_html=True)
graf_col1, graf_col2 = st.columns([1, 2])

with graf_col1:
    fig_pizza = px.pie(
        names=['Ocupadas', 'Vazias'], 
        values=[ocupadas, vazias], 
        title="Ocupação do Galpão",
        color_discrete_sequence=['#1f77b4', '#e6e6e6'],
        hole=0.5 # Transforma em gráfico de rosca
    )
    fig_pizza.update_layout(height=350, margin=dict(t=40, b=0, l=0, r=0))
    st.plotly_chart(fig_pizza, use_container_width=True)

with graf_col2:
    if not df_real[df_real['Status'] == 'Ocupado'].empty:
        top_produtos = df_real[df_real['Status'] == 'Ocupado'].groupby(['Produto', 'Descrição produto'])['Quantidade'].sum().reset_index()
        top_produtos = top_produtos.sort_values(by='Quantidade', ascending=False).head(5)
        top_produtos['Label'] = top_produtos['Produto'].astype(str) + " - " + top_produtos['Descrição produto'].str[:20] + "..."
        
        fig_bar = px.bar(
            top_produtos, 
            x='Quantidade', 
            y='Label', 
            orientation='h',
            title="Top 5 Produtos em Estoque (Geral)",
            text_auto='.2s',
            color_discrete_sequence=['#2ca02c']
        )
        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, height=350, margin=dict(t=40, b=0, l=0, r=0))
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Faça o upload do estoque para ver os produtos.")

if df_filtrado.empty:
    st.warning("Nenhum dado para exibir com os filtros atuais no mapa 3D.")
    st.stop()


# ==========================================
# 4. SIMULADOR 3D
# ==========================================
st.markdown("---")
st.markdown("### 🏗️ Mapa 3D do CD")

paleta_segura = ['#1f77b4', '#2ca02c', '#ff7f0e', '#9467bd', '#8c564b', '#17becf', '#e377c2', '#7f7f7f', '#bcbd22']
mapa_cores = {' ESTRUTURA VAZIA': 'gray'}
for i, area in enumerate(areas_disponiveis):
    mapa_cores[area] = paleta_segura[i % len(paleta_segura)]

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
        # TRUQUE DO VISUAL ARAMADO: square-open desenha apenas as bordas do quadrado
        trace.marker.color = 'rgba(150, 150, 150, 0.5)'
        trace.marker.symbol = 'square-open' 
        trace.marker.size = 5 
    else:
        # CUBOS CHEIOS (Ocupados)
        df_trace = df_filtrado[df_filtrado['Cor_Plot'] == nome_legenda]
        line_colors = ['red' if v else 'rgba(0,0,0,0)' for v in df_trace['Vencido']]
        trace.marker.line = dict(color=line_colors, width=5) 
        trace.marker.symbol = 'square'
        trace.marker.size = 4.5 

fig_3d.update_layout(
    scene=dict(
        xaxis_title='Colunas',
        yaxis_title='Corredores',
        zaxis_title='Níveis',
        aspectmode='manual',
        aspectratio=dict(x=3.5, y=1.5, z=0.5) # Deixa o galpão mais largo
    ),
    dragmode="turntable", # GARANTE que o clique e arraste vai rotacionar a câmera
    height=750,
    margin=dict(l=0, r=0, b=0, t=0),
    legend_title_text='Legenda do Depósito'
)

# Renderiza o gráfico e CAPTURA O CLIQUE
evento = st.plotly_chart(fig_3d, use_container_width=True, on_select="rerun", selection_mode="points")

# ==========================================
# PAINEL DE DETALHES DO CLIQUE
# ==========================================
if evento and len(evento.selection.points) > 0:
    ponto_clicado = evento.selection.points[0]
    endereco_clicado = ponto_clicado["hovertext"]
    
    dados_endereco = df[df['Posição no depósito'] == endereco_clicado].iloc[0]
    
    st.markdown(f"### 🔎 Informações do Endereço: `{endereco_clicado}`")
    
    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        st.write(f"**Área Armaz.:** {dados_endereco['Área_Exibicao']}")
        st.write(f"**Status:** {dados_endereco['Status']}")
    with col_d2:
        st.write(f"**Código Produto:** {dados_endereco['Produto']}")
        st.write(f"**Descrição:** {dados_endereco['Descrição produto']}")
    with col_d3:
        st.write(f"**Quantidade:** {formata_br(dados_endereco['Quantidade'])} un")
        if pd.notna(dados_endereco['Vencimento']):
            data_formatada = dados_endereco['Vencimento'].strftime('%d/%m/%Y')
            if dados_endereco['Vencido']:
                st.error(f"**Validade:** {data_formatada} (VENCIDO)")
            else:
                st.success(f"**Validade:** {data_formatada}")
        else:
            st.write("**Validade:** N/A")