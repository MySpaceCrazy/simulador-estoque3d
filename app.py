import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
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

    df_layout[['Corredor', 'Coluna', 'Nível', 'Posição_Extra']] = df_layout['Posição no depósito'].str.split('-', expand=True)
    df_layout['Corredor'] = pd.to_numeric(df_layout['Corredor'])
    df_layout['Coluna'] = pd.to_numeric(df_layout['Coluna'])
    df_layout['Nível'] = pd.to_numeric(df_layout['Nível'])
    df_layout['Y_Plot'] = df_layout['Corredor'] * 3
    df_layout['Y_Plot'] = df_layout.apply(lambda row: row['Y_Plot'] + 0.8 if row['Coluna'] % 2 == 0 else row['Y_Plot'] - 0.8, axis=1)
    df_layout['Y_Micro'] = df_layout['Coluna'].apply(lambda x: 1 if x % 2 == 0 else -1)
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

# --- 3. DASHBOARD SUPERIOR (PONTO 2) ---
st.markdown("### 📊 Painel de Controle")
df_real = df[df['Área_Exibicao'] != 'Desconhecido']
ocupadas = len(df_real[df_real['Status'] == 'Ocupado'])
vazias = len(df_real[df_real['Status'] == 'Vazio'])
taxa = (ocupadas/(ocupadas+vazias)*100) if (ocupadas+vazias)>0 else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("📦 Ocupadas", formata_br(ocupadas))
m2.metric("🟩 Vazias", formata_br(vazias))
m3.metric("📈 Ocupação", f"{taxa:.1f}%")
m4.metric("🔍 Unid. no Filtro", formata_br(df_filtrado[df_filtrado['Status'] == 'Ocupado']['Quantidade'].sum()))

g1, g2 = st.columns([1, 2])
with g1:
    st.plotly_chart(px.pie(names=['Ocupadas', 'Vazias'], values=[ocupadas, vazias], hole=0.5, height=300, title="Ocupação Geral"), use_container_width=True)
with g2:
    df_top = df_real[df_real['Status'] == 'Ocupado'].groupby('Produto')['Quantidade'].sum().reset_index().sort_values('Quantidade', ascending=False).head(5)
    st.plotly_chart(px.bar(df_top, x='Quantidade', y='Produto', orientation='h', title="Top 5 Produtos", height=300), use_container_width=True)

# --- 4. ABAS 3D ---
st.markdown("---")
aba1, aba2 = st.tabs(["🌐 Visão Global", "🏗️ Visão Realista (Corredor)"])

paleta = ['#1f77b4', '#2ca02c', '#ff7f0e', '#9467bd', '#8c564b', '#17becf']
cores_map = {' ESTRUTURA VAZIA': 'gray'}
for i, a in enumerate(areas): cores_map[a] = paleta[i % len(paleta)]

evento_macro = None
evento_micro = None

with aba1:
    if df_filtrado.empty: st.warning("Sem dados no filtro.")
    else:
        fig_macro = px.scatter_3d(df_filtrado, x='Coluna', y='Y_Plot', z='Nível', color='Cor_Plot', color_discrete_map=cores_map,
                                  hover_name='Posição no depósito', height=600)
        fig_macro.update_layout(scene=dict(aspectmode='manual', aspectratio=dict(x=3.5, y=1.5, z=0.5)), dragmode="turntable")
        evento_macro = st.plotly_chart(fig_macro, use_container_width=True, on_select="rerun", selection_mode="points", key="m1")

with aba2:
    corr_alvo = st.selectbox("Selecione o Corredor:", sorted(df['Corredor'].unique()))
    df_c = df_filtrado[df_filtrado['Corredor'] == corr_alvo]
    if df_c.empty: st.info("Corredor vazio com este filtro.")
    else:
        fig_micro = px.scatter_3d(df_c, x='Coluna', y='Y_Micro', z='Nível', color='Cor_Plot', color_discrete_map=cores_map, height=700)
        # DESENHAR ESTRUTURA (PONTO 3)
        max_n = df_c['Nível'].max()
        cols = sorted(df_c['Coluna'].unique())
        for side in [-1, 1]:
            side_df = df_c[df_c['Y_Micro'] == side]
            if side_df.empty: continue
            min_col, max_col = side_df['Coluna'].min(), side_df['Coluna'].max()
            for c in range(min_col, max_col + 2, 2):
                fig_micro.add_trace(criar_caixa(c-1.1, side*1.2, 0, 0.2, 0.5, max_n+0.5, "#2c3e50")) # Colunas
            for n in range(1, int(max_n)+1):
                fig_micro.add_trace(criar_caixa(min_col-1.1, side*1.2, n-0.2, (max_col-min_col)+2, 0.1, 0.1, "#e67e22")) # Vigas
        
        fig_micro.update_layout(scene=dict(xaxis=dict(showgrid=False), yaxis=dict(showgrid=False), zaxis=dict(showgrid=False)), dragmode="turntable")
        evento_micro = st.plotly_chart(fig_micro, use_container_width=True, on_select="rerun", selection_mode="points", key="m2")

# --- 5. FICHA TÉCNICA (PONTO 1) ---
ev = evento_macro if (evento_macro and len(evento_macro.selection.points)>0) else evento_micro
if ev and len(ev.selection.points)>0:
    end = ev.selection.points[0]["hovertext"]
    d = df[df['Posição no depósito'] == end].iloc[0]
    st.markdown(f"### 📋 Ficha Técnica: `{end}`")
    c1, c2, c3 = st.columns(3)
    c1.write(f"**Área:** {d['Área_Exibicao']}\n\n**Status:** {d['Status']}")
    c2.write(f"**Produto:** {d['Produto']}\n\n**Descrição:** {d.get('Descrição produto','-')}")
    c3.write(f"**Quantidade:** {formata_br(d['Quantidade'])}\n\n**UC:** {d.get('Unidade comercial','-')}")
    if pd.notna(d['Vencimento']):
        st.error(f"📅 **Vencimento:** {d['Vencimento'].strftime('%d/%m/%Y')}") if d['Vencido'] else st.success(f"📅 **Vencimento:** {d['Vencimento'].strftime('%d/%m/%Y')}")