import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import re
from datetime import datetime

st.set_page_config(page_title="Simulador de Estoque 3D", layout="wide")

def formata_br(numero):
    return f"{numero:,.0f}".replace(",", ".")

# ==================================================
# FUNÇÕES DE DESENHO 3D (GÊMEOS DIGITAIS)
# ==================================================

# 1. Bloco Genérico (usado para vigas, colunas e cargas)
def criar_mesh_bloco(x, y, z, dx, dy, dz, cor, opacity=1.0, nome_hover=None):
    """Gera um bloco sólido 3D (Mesh3d)"""
    return go.Mesh3d(
        x=[x, x+dx, x+dx, x, x, x+dx, x+dx, x],
        y=[y, y, y+dy, y+dy, y, y, y+dy, y+dy],
        z=[z, z, z, z, z+dz, z+dz, z+dz, z+dz],
        i=[0,0,0,1,1,2,4,5,6,4,5,6], j=[1,2,3,2,5,3,5,6,7,0,1,2], k=[2,3,1,5,6,7,6,7,4,1,2,3],
        color=cor, opacity=opacity, flatshading=True, 
        hoverinfo='text' if nome_hover else 'skip', hovertext=nome_hover, showscale=False
    )

# 2. Palete Realista (Base de madeira + Carga colorida)
def criar_palete_visual(x_base, y_base, z_base, cor_carga, endereco_hover, vencido=False):
    """Cria o conjunto visual de um palete com carga em cima"""
    traces = []
    
    # Dimensões aproximadas do palete visual
    largura_p = 1.0  # um pouco menor que o vão de 1.1
    profund_p = 1.0
    alt_base = 0.15  # altura da madeira
    alt_carga = 1.3  # altura média da carga
    
    offset_x = 0.05 # Centralizar no vão
    
    # A. Base do Palete (Madeira)
    cor_madeira = '#8b4513' # Marrom sela
    traces.append(criar_mesh_bloco(x_base + offset_x, y_base, z_base, largura_p, profund_p, alt_base, cor_madeira, nome_hover=endereco_hover))
    
    # B. Carga (Caixas em cima)
    # Se estiver vencido, a carga fica vermelha brilhante, senão usa a cor da área
    cor_final_carga = '#ff0000' if vencido else cor_carga
    opacity_carga = 0.95
    
    traces.append(criar_mesh_bloco(x_base + offset_x, y_base, z_base + alt_base, largura_p, profund_p, alt_carga, cor_final_carga, opacity=opacity_carga, nome_hover=endereco_hover))
    
    return traces


st.title("📦 Simulador de Estoque 3D - CD Passo Fundo")

# --- 1. CARGA DE DADOS ---
st.sidebar.header("📁 1. Carga de Dados")
arquivo_estoque = st.sidebar.file_uploader("Faça upload do Estoque", type=["xlsx", "csv"])

@st.cache_data
def carregar_dados(arquivo):
    try:
        df_layout = pd.read_csv("EXPORT_20260224_122851.xlsx - Data.csv", encoding="latin-1", sep=";")
    except FileNotFoundError:
        return pd.DataFrame()

    # Tratamento de coordenadas
    df_layout[['Corr_Num', 'Col_Num', 'Niv_Num', 'Pos_Extra']] = df_layout['Posição no depósito'].str.split('-', expand=True)
    df_layout['Corredor'] = pd.to_numeric(df_layout['Corr_Num'])
    df_layout['Coluna'] = pd.to_numeric(df_layout['Col_Num'])
    df_layout['Nível'] = pd.to_numeric(df_layout['Niv_Num'])
    
    # EXTRAÇÃO DA ALTURA REAL (P160 -> 1.6m)
    def extrair_altura(texto):
        nums = re.findall(r'\d+', str(texto))
        return float(nums[0]) / 100 if nums else 1.6 
    
    df_layout['Altura_Nivel_M'] = df_layout['Tp.posição depósito'].apply(extrair_altura)
    
    # CÁLCULO DE Z ACUMULADO (Empilhamento Real)
    df_layout = df_layout.sort_values(['Corredor', 'Coluna', 'Nível'])
    # Calcula onde começa a base do palete (soma das alturas anteriores)
    df_layout['Z_Base_Real'] = df_layout.groupby(['Corredor', 'Coluna'])['Altura_Nivel_M'].cumsum() - df_layout['Altura_Nivel_M']
    
    # Ajustes Y e Área
    df_layout['Y_Plot'] = df_layout['Corredor'] * 4
    df_layout['Y_Plot'] = df_layout.apply(lambda row: row['Y_Plot'] + 1.0 if row['Coluna'] % 2 == 0 else row['Y_Plot'] - 1.0, axis=1)
    df_layout['Y_Micro'] = df_layout['Coluna'].apply(lambda x: 0.2 if x % 2 == 0 else -1.4) # Ajuste fino para encaixar na estrutura
    df_layout['Área_Exibicao'] = df_layout['Área armazmto.'].fillna('Desconhecido')

    if arquivo:
        if arquivo.name.endswith('.csv'):
            try: dados_estoque = pd.read_csv(arquivo, sep=None, engine='python', encoding='utf-8')
            except: arquivo.seek(0); dados_estoque = pd.read_csv(arquivo, sep=None, engine='python', encoding='latin-1')
        else: dados_estoque = pd.read_excel(arquivo)
        
        if 'Data do vencimento' in dados_estoque.columns: dados_estoque = dados_estoque.rename(columns={'Data do vencimento': 'Vencimento'})
        if 'Vencimento' in dados_estoque.columns: dados_estoque['Vencimento'] = pd.to_datetime(dados_estoque['Vencimento'], errors='coerce')
            
        df_completo = pd.merge(df_layout, dados_estoque, on="Posição no depósito", how="left")
        df_completo['Produto'] = df_completo.get('Produto', pd.Series(['-']*len(df_completo))).fillna('-')
        df_completo['Quantidade'] = df_completo.get('Quantidade', pd.Series([0]*len(df_completo))).fillna(0)
        df_completo['Status'] = df_completo['Produto'].apply(lambda x: 'Ocupado' if str(x) != '-' else 'Vazio')
        
        hoje = pd.Timestamp.today()
        df_completo['Vencido'] = (df_completo['Vencimento'] < hoje) & (df_completo['Status'] == 'Ocupado')
    else:
        df_completo = df_layout.copy()
        df_completo['Status'] = 'Vazio'
        df_completo['Vencido'] = False
        df_completo['Produto'] = '-'
        df_completo['Quantidade'] = 0

    df_completo['Cor_Plot'] = df_completo.apply(lambda row: ' ESTRUTURA VAZIA' if row['Status'] == 'Vazio' else str(row['Área_Exibicao']), axis=1)
    return df_completo

df = carregar_dados(arquivo_estoque)
if df.empty: st.stop()

# --- 2. FILTROS ---
st.sidebar.header("🔍 2. Filtros Globais")
mostrar_vazio = st.sidebar.toggle("Mostrar Estrutura Vazia", value=True)
areas = sorted([a for a in df["Área_Exibicao"].unique() if a != " ESTRUTURA VAZIA"])
area_sel = st.sidebar.selectbox("Área", ["Todas"] + areas)
prod_sel = st.sidebar.text_input("Produto (Código)")
end_sel = st.sidebar.text_input("Endereço")

df_filtrado = df.copy()
if not mostrar_vazio: df_filtrado = df_filtrado[df_filtrado['Status'] == 'Ocupado']
if area_sel != "Todas": df_filtrado = df_filtrado[df_filtrado["Área_Exibicao"] == area_sel]
if prod_sel: df_filtrado = df_filtrado[df_filtrado["Produto"].astype(str).str.contains(prod_sel)]
if end_sel: df_filtrado = df_filtrado[df_filtrado["Posição no depósito"].str.contains(end_sel)]

# --- 3. DASHBOARD ---
st.markdown("### 📊 Painel de Controle")
df_real = df[df['Área_Exibicao'] != 'Desconhecido']
ocupadas = len(df_real[df_real['Status'] == 'Ocupado'])
vazias = len(df_real[df_real['Status'] == 'Vazio'])
m1, m2, m3, m4 = st.columns(4)
m1.metric("📦 Ocupadas", formata_br(ocupadas))
m2.metric("🟩 Vazias", formata_br(vazias))
m3.metric("📈 Ocupação", f"{(ocupadas/(ocupadas+vazias)*100):.1f}%")
m4.metric("🔍 Unid. no Filtro", formata_br(df_filtrado[df_filtrado['Status'] == 'Ocupado']['Quantidade'].sum()))

# --- 4. ABAS 3D ---
aba1, aba2 = st.tabs(["🌐 Visão Global (Cubos)", "🏗️ Visão Realista (Paletes 3D)"])

paleta = ['#1f77b4', '#2ca02c', '#ff7f0e', '#9467bd', '#8c564b', '#17becf']
cores_map = {' ESTRUTURA VAZIA': 'gray'}
for i, a in enumerate(areas): cores_map[a] = paleta[i % len(paleta)]

# Variáveis para capturar o clique
evento_macro = None
evento_micro = None
fig_micro_click_handler = None # Figura auxiliar para capturar cliques na aba realista

# --- ABA 1: MACRO (Pontos/Cubos simples) ---
with aba1:
    # Usamos Z_Base_Real para posicionar corretamente
    fig_macro = px.scatter_3d(df_filtrado, x='Coluna', y='Y_Plot', z='Z_Base_Real', color='Cor_Plot', 
                              color_discrete_map=cores_map, hover_name='Posição no depósito', height=600)
    # Ajuste visual para parecer cubos em vez de esferas
    fig_macro.update_traces(marker=dict(symbol='square', size=5, line=dict(width=1, color='DarkSlateGrey')))
    
    fig_macro.update_layout(scene=dict(aspectmode='data'), dragmode="turntable", title="Visão Geral do CD (Quadrados representam posições)")
    evento_macro = st.plotly_chart(fig_macro, use_container_width=True, on_select="rerun", selection_mode="points", key="m1")

# --- ABA 2: MICRO (Paletes Realistas Mesh3D) ---
with aba2:
    corr_alvo = st.selectbox("Selecione o Corredor:", sorted(df['Corredor'].unique()))
    df_c = df_filtrado[df_filtrado['Corredor'] == corr_alvo].copy()
    
    if df_c.empty: 
        st.info("Corredor vazio com este filtro.")
    else:
        # Inicializa figura vazia para construção manual
        fig_realista = go.Figure()

        # 1. DESENHAR ESTRUTURA (Vigas e Colunas)
        max_h_total = (df_c['Z_Base_Real'] + df_c['Altura_Nivel_M']).max()
        
        for side_y in df_c['Y_Micro'].unique():
            df_side = df_c[df_c['Y_Micro'] == side_y]
            if df_side.empty: continue
            
            min_col, max_col = df_side['Coluna'].min(), df_side['Coluna'].max()
            # Colunas Verticais
            for c in range(min_col, max_col + 2, 2):
                fig_realista.add_trace(criar_mesh_bloco(c-1.15, side_y-0.1, 0, 0.15, 1.2, max_h_total+0.5, "#2c3e50", 1.0))
            
            # Vigas Horizontais (Baseadas na altura real Z_Base_Real)
            z_vigas = df_side[df_side['Z_Base_Real'] > 0]['Z_Base_Real'].unique()
            for z_viga in z_vigas:
                # Viga frontal e traseira
                fig_realista.add_trace(criar_mesh_bloco(min_col-1.1, side_y-0.1, z_viga-0.1, (max_col-min_col)+2.2, 0.1, 0.1, "#e67e22"))
                fig_realista.add_trace(criar_mesh_bloco(min_col-1.1, side_y+1.0, z_viga-0.1, (max_col-min_col)+2.2, 0.1, 0.1, "#e67e22"))

        # 2. DESENHAR PALETES (Ocupados) E ÁREAS DE CLIQUE (Vazios)
        for _, row in df_c.iterrows():
            cor_area = cores_map.get(row['Cor_Plot'], 'gray')
            
            if row['Status'] == 'Ocupado':
                # Desenha o palete realista (base + carga)
                pallet_meshes = criar_palete_visual(row['Coluna']-1.1, row['Y_Micro'], row['Z_Base_Real'], cor_area, row['Posição no depósito'], row['Vencido'])
                for mesh in pallet_meshes:
                    fig_realista.add_trace(mesh)
            else:
                # VAZIO: Desenha um bloco transparente apenas para permitir o HOVER/CLIQUE
                fig_realista.add_trace(criar_mesh_bloco(row['Coluna']-1.1, row['Y_Micro'], row['Z_Base_Real'], 1.0, 1.0, 0.2, 'white', opacity=0.0, nome_hover=row['Posição no depósito']))

        # Configuração da Câmera e Cena
        camera = dict(eye=dict(x=2.5, y=0.5, z=0.5)) # Visão lateral inicial
        fig_realista.update_layout(
            scene=dict(xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False), aspectmode='data', camera=camera),
            dragmode="turntable", height=750, title=f"Visão Realista: Corredor {corr_alvo}", showlegend=False, margin=dict(l=0, r=0, t=30, b=0)
        )
        
        # Hack para capturar clique em Mesh3d no Streamlit: usamos um scatter invisível por cima
        # (Isso é necessário pois o on_select do st.plotly_chart não funciona bem nativamente com Mesh3d puro ainda)
        fig_micro_click_handler = px.scatter_3d(df_c, x='Coluna', y='Y_Micro', z='Z_Base_Real', hover_name='Posição no depósito')
        fig_micro_click_handler.update_traces(marker=dict(opacity=0)) # Totalmente invisível
        fig_micro_click_handler.update_layout(scene=fig_realista.layout.scene, showlegend=False, dragmode="turntable", height=750, margin=dict(l=0, r=0, t=30, b=0))
        
        # Renderiza a cena realista visualmente
        st.plotly_chart(fig_realista, use_container_width=True)
        # Renderiza o capturador de cliques invisível (hack)
        evento_micro = st.plotly_chart(fig_micro_click_handler, use_container_width=True, on_select="rerun", selection_mode="points", key="m2_clicker")
        # Move o capturador para cima do gráfico visual usando CSS hack para sobrepor (opcional, mas melhora UX)
        st.markdown("""<style>iframe[title="streamlit_plotly_events.plotly_events"]:nth-of-type(2) {position: absolute; top: 0; left: 0; opacity: 0; z-index: 10;}</style>""", unsafe_allow_html=True)


# --- 5. FICHA TÉCNICA ---
# Lógica para detectar qual evento foi disparado (Macro ou Micro)
ev = None
if evento_macro and len(evento_macro.selection.points) > 0:
    ev = evento_macro
elif evento_micro and len(evento_micro.selection.points) > 0:
    ev = evento_micro

if ev:
    end = ev.selection.points[0]["hovertext"]
    try:
        d = df[df['Posição no depósito'] == end].iloc[0]
        st.markdown(f"### 📋 Ficha Técnica: `{end}`")
        c1, c2, c3 = st.columns(3)
        altura_format = f"{d['Altura_Nivel_M']:.1f}m"
        c1.write(f"**Área:** {d['Área_Exibicao']}\n\n**Status:** {d['Status']}\n\n**Altura Vão:** {altura_format}")
        c2.write(f"**Produto:** {d['Produto']}\n\n**Descrição:** {d.get('Descrição produto','-')}")
        c3.write(f"**Quantidade:** {formata_br(d['Quantidade'])}\n\n**UC:** {d.get('Unidade comercial','-')}")
        if pd.notna(d.get('Vencimento')):
            st.error(f"📅 **Vencimento:** {d['Vencimento'].strftime('%d/%m/%Y')} (VENCIDO)") if d['Vencido'] else st.success(f"📅 **Vencimento:** {d['Vencimento'].strftime('%d/%m/%Y')}")
    except IndexError:
        st.warning("Erro ao buscar detalhes. Tente recarregar a página.")