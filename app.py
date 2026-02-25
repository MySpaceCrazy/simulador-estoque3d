import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime

st.set_page_config(page_title="Simulador de Estoque 3D", layout="wide")

def formata_br(numero):
    return f"{numero:,.0f}".replace(",", ".")


# ==========================================
# EXTRAI ALTURA REAL DO NÍVEL (P160 → 160)
# ==========================================
def extrair_altura(tp):
    """
    Converte valores como:
    P160 -> 160
    P120 -> 120
    """
    if pd.isna(tp):
        return 160  # altura padrão de segurança

    numeros = ''.join(filter(str.isdigit, str(tp)))
    return int(numeros) if numeros else 160

# ==============================
# FUNÇÃO PARA DESENHAR 3D (Racks)
# ==============================
def criar_caixa(x, y, z, dx, dy, dz, cor, opacity=1.0):
    """Gera um bloco 3D sólido (Mesh3d) para simular o metal da estante"""
    return go.Mesh3d(
        x=[x, x+dx, x+dx, x, x, x+dx, x+dx, x],
        y=[y, y, y+dy, y+dy, y, y, y+dy, y+dy],
        z=[z, z, z, z, z+dz, z+dz, z+dz, z+dz],
        i=[0,0,0,1,1,2,4,5,6,4,5,6],
        j=[1,2,3,2,5,3,5,6,7,0,1,2],
        k=[2,3,1,5,6,7,6,7,4,1,2,3],
        color=cor, opacity=opacity, flatshading=True, hoverinfo='skip', showscale=False
    )

# ==========================================
# SOMBREAMENTO POR ALTURA (ILUMINAÇÃO FAKE)
# ==========================================
def ajustar_cor_por_altura(cor_hex, altura, altura_max):
    """
    Clareia a cor conforme a altura (simula luz vindo de cima)
    """

    cor_hex = cor_hex.lstrip('#')

    r = int(cor_hex[0:2], 16)
    g = int(cor_hex[2:4], 16)
    b = int(cor_hex[4:6], 16)

    fator = 0.55 + (altura / altura_max) * 0.45

    r = min(255, int(r * fator))
    g = min(255, int(g * fator))
    b = min(255, int(b * fator))

    return f"rgb({r},{g},{b})"

# ==========================================
# GERADOR DO MAPA DE CORES (ANTI-RERUN BUG)
# ==========================================
@st.cache_data(show_spinner=False)
def gerar_mapa_cores(df):

    paleta_segura = [
        '#1f77b4', '#2ca02c', '#ff7f0e',
        '#9467bd', '#8c564b', '#17becf',
        '#e377c2', '#7f7f7f', '#bcbd22'
    ]

    mapa = {' ESTRUTURA VAZIA': 'gray'}

    areas = [
        a for a in df["Área_Exibicao"].unique()
        if str(a) != "nan" and str(a) != "Desconhecido"
    ]

    areas.sort()

    for i, area in enumerate(areas):
        mapa[area] = paleta_segura[i % len(paleta_segura)]

    return mapa


st.title("📦 Simulador de Estoque 3D - CD Passo Fundo")

# --- BARRA LATERAL: UPLOAD DE ARQUIVO ---
st.sidebar.header("📁 1. Carga de Dados")
arquivo_estoque = st.sidebar.file_uploader("Faça upload do Estoque (Excel ou CSV)", type=["xlsx", "csv"])

# =====================================================
# CONTROLE INTELIGENTE DE CACHE (limpa só quando muda arquivo)
# =====================================================
if "arquivo_anterior" not in st.session_state:
    st.session_state.arquivo_anterior = None

if arquivo_estoque != st.session_state.arquivo_anterior:
    st.cache_data.clear()
    st.session_state.arquivo_anterior = arquivo_estoque

@st.cache_data(show_spinner=False)
def carregar_dados(arquivo):
    try:
        df_layout = pd.read_csv("EXPORT_20260224_122851.xlsx - Data.csv", encoding="latin-1", sep=";")
        st.write(df_layout.columns.tolist()) # Validação colunas carregadas
    except FileNotFoundError:
        st.error("Arquivo de layout não encontrado na pasta.")
        return pd.DataFrame()

    df_layout[['Corredor', 'Coluna', 'Nível', 'Posição_Extra']] = df_layout['Posição no depósito'].str.split('-', expand=True)
    df_layout['Corredor'] = pd.to_numeric(df_layout['Corredor'])
    df_layout['Coluna'] = pd.to_numeric(df_layout['Coluna'])
    df_layout['Nível'] = pd.to_numeric(df_layout['Nível'])
    
    # Cálculo Y para Visão Macro
    df_layout['Y_Plot'] = df_layout['Corredor'] * 3
    df_layout['Y_Plot'] = df_layout.apply(lambda row: row['Y_Plot'] + 0.8 if row['Coluna'] % 2 == 0 else row['Y_Plot'] - 0.8, axis=1)
    
    # Cálculo Y para Visão Micro (Ímpar -1, Par 1)
    df_layout['Y_Micro'] = df_layout['Coluna'].apply(lambda x: 1 if x % 2 == 0 else -1)
    df_layout['Área_Exibicao'] = df_layout['Área armazmto.'].fillna('Desconhecido')

    # ==========================================
    # ALTURA REAL DO NÍVEL (BASEADO NO SAP)
    # ==========================================
    df_layout['Altura_cm'] = df_layout['Tp. Na posição depósito'].apply(extrair_altura)

    # converte para escala 3D (metros visuais)
    df_layout['Altura_plot'] = df_layout['Altura_cm'] / 100

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
        df_completo['Unidade comercial'] = df_completo.get('Unidade comercial', pd.Series(['-']*len(df_completo))).fillna('-')
        
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
        df_completo['Unidade comercial'] = '-'
        df_completo['Quantidade'] = 0

    df_completo['Cor_Plot'] = df_completo.apply(lambda row: ' ESTRUTURA VAZIA' if row['Status'] == 'Vazio' else str(row['Área_Exibicao']), axis=1)
    return df_completo

df = carregar_dados(arquivo_estoque)

if df.empty:
    st.stop()

# CRIA MAPA DE CORES SEMPRE APÓS CARREGAR DF
mapa_cores = gerar_mapa_cores(df)

# =====================================================
# DASHBOARD RESUMO (INDICADORES DO CD)
# =====================================================
st.markdown("### 📊 Indicadores Gerais do Armazém")

df_ocupado = df[df['Status'] == 'Ocupado']
df_vazio = df[df['Status'] == 'Vazio']

total_posicoes = len(df)
pos_ocupadas = len(df_ocupado)
pos_vazias = len(df_vazio)

# =====================================================
# LAYOUT EM 3 COLUNAS
# =====================================================
col_g1, col_g2, col_g3 = st.columns(3)

# =====================================================
# 1️⃣ GRÁFICO ROSCA — OCUPAÇÃO
# =====================================================
with col_g1:

    fig_ocupacao = go.Figure(data=[go.Pie(
        labels=['Ocupadas', 'Vazias'],
        values=[pos_ocupadas, pos_vazias],
        hole=0.6,
        textinfo='label+percent',
        hovertemplate="<b>%{label}</b><br>Qtd: %{value}<extra></extra>",
        marker=dict(colors=['#2ca02c', '#d3d3d3'])
    )])

    fig_ocupacao.update_layout(
        title=f"Ocupação do Armazém<br>{pos_ocupadas:,} / {total_posicoes:,} posições",
        height=350,
        margin=dict(t=60, b=0, l=0, r=0),
        showlegend=False
    )

    st.plotly_chart(fig_ocupacao, use_container_width=True)

# =====================================================
# 2️⃣ TOP 5 PRODUTOS (BARRA HORIZONTAL)
# =====================================================
with col_g2:

    top5 = (
        df_ocupado
        .groupby('Produto')['Quantidade']
        .sum()
        .sort_values(ascending=False)
        .head(5)
        .reset_index()
    )

    fig_top5 = px.bar(
        top5,
        x='Quantidade',
        y='Produto',
        orientation='h',
        text='Quantidade',
        title="Top 5 Produtos com Maior Estoque"
    )

    fig_top5.update_layout(
        height=350,
        yaxis=dict(categoryorder='total ascending'),
        margin=dict(t=60, b=0, l=0, r=0)
    )

    st.plotly_chart(fig_top5, use_container_width=True)

# =====================================================
# 3️⃣ ESTOQUE POR ÁREA (PIZZA)
# =====================================================
with col_g3:

    estoque_area = (
        df_ocupado
        .groupby('Área_Exibicao')['Quantidade']
        .sum()
        .reset_index()
    )

    cores_area = [
        mapa_cores.get(area, '#cccccc')
        for area in estoque_area['Área_Exibicao']
    ]

    fig_area = go.Figure(data=[go.Pie(
        labels=estoque_area['Área_Exibicao'],
        values=estoque_area['Quantidade'],
        textinfo='percent+label',
        hovertemplate="<b>%{label}</b><br>Qtd: %{value}<extra></extra>",
        marker=dict(colors=cores_area)
    )])

    fig_area.update_layout(
        title="Distribuição de Estoque por Área",
        height=350,
        margin=dict(t=60, b=0, l=0, r=0)
    )

    st.plotly_chart(fig_area, use_container_width=True)

st.markdown("---")

# --- BARRA LATERAL: FILTROS GERAIS ---
st.sidebar.header("🔍 2. Filtros Globais")

mostrar_estrutura = st.sidebar.toggle("Mostrar Estrutura Vazia", value=True)

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
# RESUMO DINÂMICO DOS FILTROS (PONTO 2)
# ==========================================
if produto_pesquisa or area_pesquisa != "Todas" or data_pesquisa != "Todas":
    st.markdown("### 🎯 Resumo do Filtro Aplicado")
    df_f_ocupado = df_filtrado[df_filtrado['Status'] == 'Ocupado']
    
    qtd_pos = len(df_f_ocupado)
    qtd_unidades = df_f_ocupado['Quantidade'].sum()
    qtd_produtos = df_f_ocupado['Produto'].nunique()
    
    c1, c2, c3 = st.columns(3)
    c1.info(f"📍 **Posições Utilizadas:** {formata_br(qtd_pos)}")
    c2.success(f"📦 **Unidades Totais:** {formata_br(qtd_unidades)} un")
    
    # Se for pesquisa por área ou data, mostramos os produtos diferentes
    if area_pesquisa != "Todas" or data_pesquisa != "Todas":
        c3.warning(f"🏷️ **Produtos Diferentes:** {qtd_produtos} SKUs")

st.markdown("---")

# ==========================================
# ABAS DE VISUALIZAÇÃO 3D
# ==========================================
aba_macro, aba_micro = st.tabs(["🌐 Visão Global (Mapa do CD)", "🏗️ Visão Realista do Corredor (Porta-Paletes)"])

evento_macro = None
evento_micro = None

# --- ABA 1: VISÃO MACRO (Galpão Inteiro) ---
with aba_macro:
    st.markdown("##### 📍 Heatmap e Radar do Galpão")
    fig_macro = px.scatter_3d(
        df_filtrado, x='Coluna', y='Y_Plot', z='Altura_plot', color='Cor_Plot',
        color_discrete_map=mapa_cores, hover_name='Posição no depósito',
        hover_data={'Status': True, 'Produto': True, 'Quantidade': True, 'Vencido': True, 'Cor_Plot': False, 'Coluna': False, 'Y_Plot': False, 'Altura_plot': False,'Altura_cm': True, 'Corredor': False}
    )

    for trace in fig_macro.data:
        nome_legenda = trace.name
        if nome_legenda == ' ESTRUTURA VAZIA':
            trace.marker.color = 'rgba(150, 150, 150, 0.3)'
            trace.marker.symbol = 'square-open' 
            trace.marker.size = 3 
        else:
            df_trace = df_filtrado[df_filtrado['Cor_Plot'] == nome_legenda]
            line_colors = ['red' if v else 'rgba(0,0,0,0)' for v in df_trace['Vencido']]
            trace.marker.line = dict(color=line_colors, width=5) 
            trace.marker.symbol = 'square'
            trace.marker.size = 3.5 

    fig_macro.update_layout(
        scene=dict(xaxis_title='Colunas', yaxis_title='Corredores', zaxis_title='Níveis', aspectmode='manual', aspectratio=dict(x=3.5, y=1.5, z=0.5)),
        dragmode="turntable", height=600, margin=dict(l=0, r=0, b=0, t=0), hoverlabel=dict(namelength=-1)
    )
    evento_macro = st.plotly_chart(fig_macro, use_container_width=True, on_select="rerun", selection_mode="points", key="macro_chart")

# --- ABA 2: VISÃO MICRO COM PORTA-PALETES 3D (PONTO 3) ---
with aba_micro:
    st.markdown("##### 🔍 Inspeção Estrutural Realista")
    
    corredores_unicos = sorted(df['Corredor'].unique())
    corredor_alvo = st.selectbox("Selecione o Corredor para renderizar a estrutura:", corredores_unicos)
    
    df_corredor = df_filtrado[df_filtrado['Corredor'] == corredor_alvo].copy()
    
    if df_corredor.empty:
        st.info("Nenhuma posição encontrada neste corredor com os filtros atuais.")
    else:
        # 1. Desenha os paletes e dados flutuantes usando Scatter3D (para capturar os cliques e informações)
        fig_micro = px.scatter_3d(
            df_corredor, x='Coluna', y='Y_Micro', z='Altura_plot', color='Cor_Plot',
            color_discrete_map=mapa_cores, hover_name='Posição no depósito',
            hover_data={'Status': True, 'Produto': True, 'Quantidade': True, 'Vencido': True, 'Cor_Plot': False, 'Coluna': False, 'Y_Micro': False, 'Altura_plot': False,'Altura_cm': True, 'Corredor': False}
        )

        # ------------------------------------------
        # GUARDA OS PALLETES (para renderizar depois)
        # ------------------------------------------
        traces_paletes = list(fig_micro.data)
        fig_micro.data = []

        for trace in fig_micro.data:
            nome_legenda = trace.name
            if nome_legenda == ' ESTRUTURA VAZIA':
                # Palete vazio fica quase invisível, pois a estante de aço vai fazer o contorno
                trace.marker.color = 'rgba(255, 255, 255, 0.0)'
                trace.marker.symbol = 'square-open' 
                trace.marker.size = 1
                trace.marker.line = dict(width=0)
            else:
                # Paletes ocupados ficam como cubões sólidos
                df_trace = df_corredor[df_corredor['Cor_Plot'] == nome_legenda]
                line_colors = ['red' if v else 'rgba(0,0,0,1)' for v in df_trace['Vencido']]
                trace.marker.line = dict(color=line_colors, width=4) 
                trace.marker.symbol = 'square'
                trace.marker.size = 22 # Tamanho gigante para parecer a caixa no rack

                trace.opacity = 0.92 # Micro transparência (profundidade visual)

        # ==========================================
        # IDENTIFICA MÓDULOS REAIS DE RACK
        # ==========================================
        def pares_consecutivos(colunas):
            """
            Retorna pares de colunas vizinhas reais
            Ex: [1,3,5,11,13] -> [(1,3),(3,5),(11,13)]
            """
            colunas = sorted(colunas)
            pares = []

            for i in range(len(colunas) - 1):
                atual = colunas[i]
                prox = colunas[i + 1]

                # módulo válido = diferença padrão (2)
                if prox - atual == 2:
                    pares.append((atual, prox))

            return pares

        # ==========================================
        # ALTURAS REAIS POR ENDEREÇO (PASSO 4)
        # ==========================================
        alturas_reais = (
            df_corredor
            .groupby(['Corredor', 'Coluna'])['Altura_plot']
            .max()
            .reset_index()
        )

        altura_max_estrutura = alturas_reais['Altura_plot'].max()
        niveis_reais = sorted(df_corredor['Altura_plot'].dropna().unique())

        # 2. GERAÇÃO DINÂMICA DA ESTRUTURA METÁLICA (Mesh3d)
        # max_niv = df_corredor['Nível'].max()
        
        # Estrutura Lado Ímpar (Y = -1)
        impares = df_corredor[df_corredor['Coluna'] % 2 != 0]['Coluna'].unique()
        if len(impares) > 0:
            min_c, max_c = min(impares), max(impares)
            for c in impares:

                altura_coluna = alturas_reais.loc[
                    alturas_reais['Coluna'] == c,
                    'Altura_plot'
                ].max()

                cor_coluna = ajustar_cor_por_altura(
                    "#2c3e50",
                    altura_coluna,
                    altura_max_estrutura
                )

                fig_micro.add_trace(
                    criar_caixa(
                        c - 1.1,
                        -1.4,
                        0,
                        0.2,
                        0.8,
                        altura_coluna + 0.3,
                        cor_coluna
                    )
                )
            
            modulos_impares = pares_consecutivos(impares)

            for c1, c2 in modulos_impares:

                largura_modulo = (c2 - c1) + 0.2
                x_inicio = c1 - 1.1

                for n in niveis_reais:
                    cor_viga = ajustar_cor_por_altura(
                        "#e67e22",
                        n,
                        altura_max_estrutura
                    )
                    # frente
                    fig_micro.add_trace(
                        criar_caixa(
                            x_inicio,
                            -0.7,
                            n - 0.08,
                            largura_modulo,
                            0.1,
                            0.15,
                            cor_viga
                        )
                    )

                    cor_viga = ajustar_cor_por_altura(
                        "#e67e22",
                        n,
                        altura_max_estrutura
                    )

                    # fundo
                    fig_micro.add_trace(
                        criar_caixa(
                            x_inicio,
                            -1.4,
                            n - 0.08,
                            largura_modulo,
                            0.1,
                            0.15,
                            cor_viga
                        )
                    )

        # Estrutura Lado Par (Y = 1)
        pares = df_corredor[df_corredor['Coluna'] % 2 == 0]['Coluna'].unique()
        if len(pares) > 0:
            min_c, max_c = min(pares), max(pares)
            for c in pares:

                altura_coluna = alturas_reais.loc[
                    alturas_reais['Coluna'] == c,
                    'Altura_plot'
                ].max()

                cor_coluna = ajustar_cor_por_altura(
                    "#2c3e50",
                    altura_coluna,
                    altura_max_estrutura
                )

                fig_micro.add_trace(
                    criar_caixa(
                        c - 1.1,
                        0.6,
                        0,
                        0.2,
                        0.8,
                        altura_coluna + 0.3,
                        cor_coluna
                    )
                )

            modulos_pares = pares_consecutivos(pares)

            for c1, c2 in modulos_pares:

                largura_modulo = (c2 - c1) + 0.2
                x_inicio = c1 - 1.1

                for n in niveis_reais:
                    
                    cor_viga = ajustar_cor_por_altura(
                        "#e67e22",
                        n,
                        altura_max_estrutura
                    )

                    fig_micro.add_trace(
                        criar_caixa(
                            x_inicio,
                            0.6,
                            n - 0.08,
                            largura_modulo,
                            0.1,
                            0.15,
                            cor_viga
                        )
                    )

                    cor_viga = ajustar_cor_por_altura(
                        "#e67e22",
                        n,
                        altura_max_estrutura
                    )

                    fig_micro.add_trace(
                        criar_caixa(
                            x_inicio,
                            1.3,
                            n - 0.08,
                            largura_modulo,
                            0.1,
                            0.15,
                            cor_viga
                        )
                    )

        # Eixos Invisíveis para efeito de Jogo/Maquete
        eixo_invisivel = dict(showbackground=False, showgrid=False, showline=False, showticklabels=False, title='')
        tamanho_x = max(2, len(df_corredor['Coluna'].unique()) * 0.15)

        # ------------------------------------------
        # REINSERE PALLETES (na frente da estrutura)
        # ------------------------------------------
        for t in traces_paletes:
            fig_micro.add_trace(t)

        fig_micro.update_layout(
            scene=dict(xaxis=eixo_invisivel, yaxis=eixo_invisivel,zaxis=eixo_invisivel,aspectmode='manual',aspectratio=dict(x=tamanho_x, y=0.5, z=0.8),
                camera=dict(
                    eye=dict(x=1.6, y=1.6, z=1.2)
                ),

                lightposition=dict(
                    x=100,
                    y=200,
                    z=300
                )
            ),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            dragmode="turntable", height=800, margin=dict(l=0, r=0, b=0, t=0), showlegend=False, hoverlabel=dict(namelength=-1)
        )
        evento_micro = st.plotly_chart(fig_micro, use_container_width=True, on_select="rerun", selection_mode="points", key="micro_chart")


# ==========================================
# FICHA COMPLETA DO CLIQUE (PONTO 1)
# ==========================================
evento_ativo = None
if evento_macro and len(evento_macro.selection.points) > 0:
    evento_ativo = evento_macro
elif evento_micro and len(evento_micro.selection.points) > 0:
    evento_ativo = evento_micro

if evento_ativo:
    ponto_clicado = evento_ativo.selection.points[0]
    endereco_clicado = ponto_clicado["hovertext"]
    
    dados_endereco = df[df['Posição no depósito'] == endereco_clicado].iloc[0]
    
    st.markdown("---")
    st.markdown(f"### 📋 Ficha Técnica: Endereço `{endereco_clicado}`")
    
    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        st.write(f"**🟢 Status:** {dados_endereco['Status']}")
        st.write(f"**🏢 Área Armaz.:** {dados_endereco['Área_Exibicao']}")
        st.write(f"**📏 Tipo Depósito:** {dados_endereco.get('Tipo de depósito', 'N/A')}")
        
    with col_d2:
        st.write(f"**🏷️ Código Produto:** {dados_endereco['Produto']}")
        st.write(f"**📝 Descrição:** {dados_endereco['Descrição produto']}")
        st.write(f"**📦 Unid. Comercial (UC):** {dados_endereco['Unidade comercial']}")
        
    with col_d3:
        st.write(f"**🔢 Quantidade:** {formata_br(dados_endereco['Quantidade'])} un")
        
        if pd.notna(dados_endereco['Vencimento']):
            data_formatada = dados_endereco['Vencimento'].strftime('%d/%m/%Y')
            if dados_endereco['Vencido']:
                st.error(f"**⏳ Validade:** {data_formatada} (VENCIDO)")
            else:
                st.success(f"**⏳ Validade:** {data_formatada}")
        else:
            st.write("**⏳ Validade:** N/A")