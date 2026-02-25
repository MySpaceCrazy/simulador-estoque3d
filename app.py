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

# ==============================
# FUNÇÃO PARA DESENHAR CUBOS 3D
# ==============================
def criar_caixa(x, y, z, dx, dy, dz, cor, opacity=1.0, hovertext=None):
    return go.Mesh3d(
        x=[x, x+dx, x+dx, x, x, x+dx, x+dx, x],
        y=[y, y, y+dy, y+dy, y, y, y+dy, y+dy],
        z=[z, z, z, z, z+dz, z+dz, z+dz, z+dz],
        i=[0,0,0,1,1,2,4,5,6,4,5,6],
        j=[1,2,3,2,5,3,5,6,7,0,1,2],
        k=[2,3,1,5,6,7,6,7,4,1,2,3],
        color=cor, opacity=opacity, flatshading=True, 
        hoverinfo='text' if hovertext else 'skip', hovertext=hovertext, showscale=False
    )

st.title("📦 Simulador de Estoque 3D - CD Passo Fundo")

# --- BARRA LATERAL: CARGA DE DADOS ---
st.sidebar.header("📁 1. Carga de Dados")
arquivo_estoque = st.sidebar.file_uploader("Faça upload do Estoque (Excel ou CSV)", type=["xlsx", "csv"])

@st.cache_data
def carregar_dados(arquivo):
    try:
        df_layout = pd.read_csv("EXPORT_20260224_122851.xlsx - Data.csv", encoding="latin-1", sep=";")
    except FileNotFoundError:
        st.error("Arquivo de layout não encontrado.")
        return pd.DataFrame()

    # Tratamento de Endereços
    df_layout[['Corredor', 'Coluna', 'Nível', 'Posição_Extra']] = df_layout['Posição no depósito'].str.split('-', expand=True)
    df_layout['Corredor'] = pd.to_numeric(df_layout['Corredor'])
    df_layout['Coluna'] = pd.to_numeric(df_layout['Coluna'])
    df_layout['Nível'] = pd.to_numeric(df_layout['Nível'])
    
    # EXTRAÇÃO DA ALTURA REAL (P160 -> 1.6m)
    def extrair_h(texto):
        nums = re.findall(r'\d+', str(texto))
        return float(nums[0]) / 100 if nums else 1.6 
    
    df_layout['H_Nivel_M'] = df_layout['Tp.posição depósito'].apply(extrair_h)
    
    # CÁLCULO DE POSIÇÃO Z REAL (Empilhamento)
    df_layout = df_layout.sort_values(['Corredor', 'Coluna', 'Nível'])
    df_layout['Z_Base_Real'] = df_layout.groupby(['Corredor', 'Coluna'])['H_Nivel_M'].cumsum() - df_layout['H_Nivel_M']
    
    # Coordenadas Y
    df_layout['Y_Plot'] = df_layout['Corredor'] * 3
    df_layout['Y_Plot'] = df_layout.apply(lambda row: row['Y_Plot'] + 0.8 if row['Coluna'] % 2 == 0 else row['Y_Plot'] - 0.8, axis=1)
    df_layout['Y_Micro'] = df_layout['Coluna'].apply(lambda x: 1 if x % 2 == 0 else -1)
    df_layout['Área_Exibicao'] = df_layout['Área armazmto.'].fillna('Desconhecido')

    if arquivo is not None:
        if arquivo.name.endswith('.csv'):
            try: dados_estoque = pd.read_csv(arquivo, sep=None, engine='python', encoding='utf-8')
            except: arquivo.seek(0); dados_estoque = pd.read_csv(arquivo, sep=None, engine='python', encoding='latin-1')
        else: dados_estoque = pd.read_excel(arquivo)
            
        if 'Data do vencimento' in dados_estoque.columns:
            dados_estoque = dados_estoque.rename(columns={'Data do vencimento': 'Vencimento'})
        if 'Vencimento' in dados_estoque.columns:
            dados_estoque['Vencimento'] = pd.to_datetime(dados_estoque['Vencimento'], errors='coerce')
            
        df_completo = pd.merge(df_layout, dados_estoque, on="Posição no depósito", how="left")
        
        # Manter todas as colunas originais
        df_completo['Produto'] = df_completo.get('Produto', pd.Series(['-']*len(df_completo))).fillna('-')
        df_completo['Quantidade'] = df_completo.get('Quantidade', pd.Series([0]*len(df_completo))).fillna(0)
        df_completo['Status'] = df_completo['Produto'].apply(lambda x: 'Ocupado' if str(x) != '-' else 'Vazio')
        
        hoje = pd.Timestamp.today()
        df_completo['Vencido'] = (df_completo['Vencimento'] < hoje) & (df_completo['Status'] == 'Ocupado')
    else:
        df_completo = df_layout.copy()
        df_completo['Status'], df_completo['Vencido'], df_completo['Produto'] = 'Vazio', False, '-'
        df_completo['Quantidade'] = 0

    df_completo['Cor_Plot'] = df_completo.apply(lambda row: ' ESTRUTURA VAZIA' if row['Status'] == 'Vazio' else str(row['Área_Exibicao']), axis=1)
    return df_completo

df = carregar_dados(arquivo_estoque)
if df.empty: st.stop()

# --- FILTROS ---
st.sidebar.header("🔍 2. Filtros Globais")
mostrar_vazio = st.sidebar.toggle("Mostrar Estrutura Vazia", value=True)
areas = sorted([a for a in df["Área_Exibicao"].unique() if a != " ESTRUTURA VAZIA"])
area_sel = st.sidebar.selectbox("Área", ["Todas"] + areas)
prod_sel = st.sidebar.text_input("Produto (Código)")
data_sel = st.sidebar.selectbox("Data de Vencimento", ["Todas"] + sorted(df[df['Status']=='Ocupado']['Vencimento'].dt.date.dropna().unique().tolist()))

df_filtrado = df.copy()
if not mostrar_vazio: df_filtrado = df_filtrado[df_filtrado['Status'] == 'Ocupado']
if area_sel != "Todas": df_filtrado = df_filtrado[df_filtrado["Área_Exibicao"] == area_sel]
if prod_sel: df_filtrado = df_filtrado[df_filtrado["Produto"].astype(str).str.contains(prod_sel)]
if data_sel != "Todas": df_filtrado = df_filtrado[(df_filtrado['Vencimento'].dt.date == data_sel) | (df_filtrado['Status'] == 'Vazio')]

# ==========================================
# RESUMO DINÂMICO
# ==========================================
st.markdown("### 🎯 Resumo da Operação")
df_f_oc = df_filtrado[df_filtrado['Status'] == 'Ocupado']
c1, c2, c3, c4 = st.columns(4)
c1.metric("📍 Posições Utilizadas", formata_br(len(df_f_oc)))
c2.metric("📦 Unidades Totais", formata_br(df_f_oc['Quantidade'].sum()))
c3.metric("🏷️ SKUs Diferentes", df_f_oc['Produto'].nunique())
c4.metric("🚨 Vencidos", formata_br(len(df_f_oc[df_f_oc['Vencido']==True])))

st.markdown("---")

# --- ABAS ---
aba_macro, aba_micro = st.tabs(["🌐 Visão Global", "🏗️ Visão Realista (Corredor)"])

paleta = ['#1f77b4', '#2ca02c', '#ff7f0e', '#9467bd', '#8c564b', '#17becf']
mapa_cores = {' ESTRUTURA VAZIA': 'gray'}
for i, area in enumerate(areas): mapa_cores[area] = paleta[i % len(paleta)]

# --- ABA 1: MACRO ---
with aba_macro:
    fig_macro = px.scatter_3d(df_filtrado, x='Coluna', y='Y_Plot', z='Z_Base_Real', color='Cor_Plot',
                              color_discrete_map=mapa_cores, hover_name='Posição no depósito', height=600)
    fig_macro.update_traces(marker=dict(symbol='square', size=3))
    fig_macro.update_layout(scene=dict(aspectmode='data'), dragmode="turntable")
    evento_macro = st.plotly_chart(fig_macro, use_container_width=True, on_select="rerun", selection_mode="points", key="macro")

# --- ABA 2: MICRO (Alturas reais e Cubos) ---
with aba_micro:
    corredor_alvo = st.selectbox("Selecione o Corredor:", sorted(df['Corredor'].unique()))
    df_corredor = df_filtrado[df_filtrado['Corredor'] == corredor_alvo].copy()
    
    if df_corredor.empty:
        st.info("Nenhuma posição neste corredor.")
    else:
        fig_micro = px.scatter_3d(df_corredor, x='Coluna', y='Y_Micro', z='Z_Base_Real', hover_name='Posição no depósito')
        fig_micro.update_traces(marker=dict(size=1, opacity=0))

        # Desenho dos Cubos
        for _, row in df_corredor.iterrows():
            if row['Status'] == 'Ocupado':
                cor = 'red' if row['Vencido'] else mapa_cores.get(row['Área_Exibicao'], 'blue')
                fig_micro.add_trace(criar_caixa(row['Coluna']-0.4, row['Y_Micro']-0.4, row['Z_Base_Real'], 
                                                0.8, 0.8, row['H_Nivel_M']*0.8, cor, hovertext=row['Posição no depósito']))

        # Estrutura (Apenas níveis reais)
        for side in [-1, 1]:
            df_side = df_corredor[df_corredor['Y_Micro'] == side]
            if df_side.empty: continue
            min_c, max_c = df_side['Coluna'].min(), df_side['Coluna'].max()
            niveis_h = sorted(df_side['Z_Base_Real'].unique())
            max_h = df_side['Z_Base_Real'].max() + df_side['H_Nivel_M'].max()
            
            for c in range(min_c, max_c + 3, 2):
                fig_micro.add_trace(criar_caixa(c - 1.1, side-0.4, 0, 0.2, 0.8, max_h, "#2c3e50"))
            
            for zh in niveis_h:
                if zh == 0 and len(niveis_h) > 1: continue 
                fig_micro.add_trace(criar_caixa(min_c - 1.1, side-0.4, zh - 0.05, (max_c - min_c) + 2.2, 0.1, 0.1, "#e67e22"))
                fig_micro.add_trace(criar_caixa(min_c - 1.1, side+0.3, zh - 0.05, (max_c - min_c) + 2.2, 0.1, 0.1, "#e67e22"))

        fig_micro.update_layout(scene=dict(xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=True), aspectmode='data'),
                                paper_bgcolor='rgba(0,0,0,0)', dragmode="turntable", height=800, showlegend=False)
        evento_micro = st.plotly_chart(fig_micro, use_container_width=True, on_select="rerun", selection_mode="points", key="micro")

# --- FICHA TÉCNICA ---
ev = evento_macro if (evento_macro and len(evento_macro.selection.points)>0) else (evento_micro if (evento_micro and len(evento_micro.selection.points)>0) else None)
if ev:
    end = ev.selection.points[0]["hovertext"]
    d = df[df['Posição no depósito'] == end].iloc[0]
    st.markdown("---")
    st.markdown(f"### 📋 Ficha Técnica: `{end}`")
    c1, c2, c3 = st.columns(3)
    c1.write(f"**Status:** {d['Status']}\n\n**Área:** {d['Área_Exibicao']}\n\n**Vão:** {d['H_Nivel_M']}m")
    c2.write(f"**Produto:** {d['Produto']}\n\n**Descrição:** {d.get('Descrição produto','-')}")
    c3.write(f"**Quantidade:** {formata_br(d['Quantidade'])}\n\n**UC:** {d.get('Unidade comercial','-')}")