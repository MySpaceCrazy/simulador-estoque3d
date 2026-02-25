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

# --- FUNÇÃO ESTRUTURAL (Racks Metálicos) ---
def criar_caixa(x, y, z, dx, dy, dz, cor, opacity=1.0):
    return go.Mesh3d(
        x=[x, x+dx, x+dx, x, x, x+dx, x+dx, x],
        y=[y, y, y+dy, y+dy, y, y, y+dy, y+dy],
        z=[z, z, z, z, z+dz, z+dz, z+dz, z+dz],
        i=[0,0,0,1,1,2,4,5,6,4,5,6], j=[1,2,3,2,5,3,5,6,7,0,1,2], k=[2,3,1,5,6,7,6,7,4,1,2,3],
        color=cor, opacity=opacity, flatshading=True, hoverinfo='skip', showscale=False
    )

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
    
    # EXTRAÇÃO DA ALTURA REAL (P160 -> 1.6)
    def extrair_altura(texto):
        nums = re.findall(r'\d+', str(texto))
        return float(nums[0]) / 100 if nums else 1.6 # Default 1.6m se não achar
    
    df_layout['Altura_Nivel'] = df_layout['Tp.posição depósito'].apply(extrair_altura)
    
    # CÁLCULO DE Z ACUMULADO (Empilhamento Real)
    # Ordenamos por endereço para garantir que o nível 010 venha antes do 020 no cálculo
    df_layout = df_layout.sort_values(['Corredor', 'Coluna', 'Nível'])
    df_layout['Z_Real'] = df_layout.groupby(['Corredor', 'Coluna'])['Altura_Nivel'].cumsum() - df_layout['Altura_Nivel']
    
    # Ajuste Y (Corredores e Ruas)
    df_layout['Y_Plot'] = df_layout['Corredor'] * 4
    df_layout['Y_Plot'] = df_layout.apply(lambda row: row['Y_Plot'] + 1.0 if row['Coluna'] % 2 == 0 else row['Y_Plot'] - 1.0, axis=1)
    df_layout['Y_Micro'] = df_layout['Coluna'].apply(lambda x: 1.2 if x % 2 == 0 else -1.2)
    
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
aba1, aba2 = st.tabs(["🌐 Visão Global", "🏗️ Visão Realista (Alturas de Engenharia)"])

paleta = ['#1f77b4', '#2ca02c', '#ff7f0e', '#9467bd', '#8c564b', '#17becf']
cores_map = {' ESTRUTURA VAZIA': 'gray'}
for i, a in enumerate(areas): cores_map[a] = paleta[i % len(paleta)]

with aba1:
    fig_macro = px.scatter_3d(df_filtrado, x='Coluna', y='Y_Plot', z='Z_Real', color='Cor_Plot', 
                              color_discrete_map=cores_map, hover_name='Posição no depósito', height=600)
    fig_macro.update_layout(scene=dict(aspectmode='data'), dragmode="turntable")
    evento_macro = st.plotly_chart(fig_macro, use_container_width=True, on_select="rerun", selection_mode="points", key="m1")

with aba2:
    corr_alvo = st.selectbox("Selecione o Corredor:", sorted(df['Corredor'].unique()))
    df_c = df_filtrado[df_filtrado['Corredor'] == corr_alvo]
    
    if df_c.empty: 
        st.info("Corredor vazio com este filtro.")
    else:
        # Gráfico base: agora o Z é a 'Z_Real' (altura acumulada em metros)
        fig_micro = px.scatter_3d(df_c, x='Coluna', y='Y_Micro', z='Z_Real', color='Cor_Plot', 
                                  color_discrete_map=cores_map, height=750)
        
        max_h = df_c['Z_Real'].max() + 2
        for side in df_c['Y_Micro'].unique():
            df_side = df_c[df_c['Y_Micro'] == side]
            min_col, max_col = df_side['Coluna'].min(), df_side['Coluna'].max()
            
            # COLUNAS (Montantes)
            for c in range(min_col, max_col + 2, 2):
                fig_micro.add_trace(criar_caixa(c-1.1, side-0.4, 0, 0.2, 0.8, max_h, "#2c3e50", 0.8))
            
            # VIGAS (Baseadas no Tp.posição depósito)
            for _, row in df_side.iterrows():
                # Desenha a viga exatamente na base (Z_Real) de cada endereço
                fig_micro.add_trace(criar_caixa(row['Coluna']-1.1, side-0.4, row['Z_Real'], 2.2, 0.8, 0.1, "#e67e22", 0.9))
        
        fig_micro.update_layout(scene=dict(xaxis=dict(showgrid=False), yaxis=dict(showgrid=False), zaxis=dict(showgrid=True),
                                aspectmode='data'), dragmode="turntable")
        evento_micro = st.plotly_chart(fig_micro, use_container_width=True, on_select="rerun", selection_mode="points", key="m2")

# --- 5. FICHA TÉCNICA ---
ev = evento_macro if (evento_macro and len(evento_macro.selection.points)>0) else (evento_micro if (evento_micro and len(evento_micro.selection.points)>0) else None)
if ev:
    end = ev.selection.points[0]["hovertext"]
    d = df[df['Posição no depósito'] == end].iloc[0]
    st.markdown(f"### 📋 Ficha Técnica: `{end}`")
    c1, c2, c3 = st.columns(3)
    c1.write(f"**Área:** {d['Área_Exibicao']}\n\n**Altura do Nível:** {d['Altura_Nivel']}m ({d['Tp.posição depósito']})")
    c2.write(f"**Produto:** {d['Produto']}\n\n**Descrição:** {d.get('Descrição produto','-')}")
    c3.write(f"**Quantidade:** {formata_br(d['Quantidade'])}\n\n**UC:** {d.get('Unidade comercial','-')}")