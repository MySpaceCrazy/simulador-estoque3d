import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import re
from datetime import datetime

st.set_page_config(page_title="Simulador de Estoque 3D", layout="wide")

def formata_br(numero):
    return f"{numero:,.0f}".replace(",", ".")

# ==================================================
# MOTOR DE RENDERIZAÇÃO OTIMIZADO (Single Trace)
# ==================================================
class Gerador3D:
    """Agrupa múltiplos cubos em uma única malha para máxima performance"""
    def __init__(self):
        self.x, self.y, self.z = [], [], []
        self.i, self.j, self.k = [], [], []
        self.count = 0

    def add_box(self, x, y, z, dx, dy, dz):
        # Vértices do cubo
        vx = [x, x+dx, x+dx, x, x, x+dx, x+dx, x]
        vy = [y, y, y+dy, y+dy, y, y, y+dy, y+dy]
        vz = [z, z, z, z, z+dz, z+dz, z+dz, z+dz]
        
        # Índices dos triângulos (12 triângulos por cubo)
        ii = [0, 0, 0, 1, 1, 2, 4, 5, 6, 4, 5, 6]
        jj = [1, 2, 3, 2, 5, 3, 5, 6, 7, 0, 1, 2]
        kk = [2, 3, 1, 5, 6, 7, 6, 7, 4, 1, 2, 3]
        
        offset = self.count * 8
        self.x.extend(vx); self.y.extend(vy); self.z.extend(vz)
        self.i.extend([idx + offset for idx in ii])
        self.j.extend([idx + offset for idx in jj])
        self.k.extend([idx + offset for idx in kk])
        self.count += 1

    def build_mesh(self, cor, nome, opacity=1.0):
        return go.Mesh3d(
            x=self.x, y=self.y, z=self.z, i=self.i, j=self.j, k=self.k,
            color=cor, opacity=opacity, name=nome, flatshading=True, showlegend=True
        )

st.title("📦 Simulador de Estoque 3D - CD Passo Fundo")

# --- 1. CARGA DE DADOS ---
st.sidebar.header("📁 1. Carga de Dados")
arquivo_estoque = st.sidebar.file_uploader("Faça upload do Estoque", type=["xlsx", "csv"])

@st.cache_data
def carregar_dados(arquivo):
    try:
        df_layout = pd.read_csv("EXPORT_20260224_122851.xlsx - Data.csv", encoding="latin-1", sep=";")
    except FileNotFoundError: return pd.DataFrame()

    df_layout[['Corr_Num', 'Col_Num', 'Niv_Num', 'Pos_Extra']] = df_layout['Posição no depósito'].str.split('-', expand=True)
    df_layout['Corredor'] = pd.to_numeric(df_layout['Corr_Num'])
    df_layout['Coluna'] = pd.to_numeric(df_layout['Col_Num'])
    df_layout['Nível'] = pd.to_numeric(df_layout['Niv_Num'])
    
    def extrair_h(texto):
        nums = re.findall(r'\d+', str(texto))
        return float(nums[0]) / 100 if nums else 1.6 
    
    df_layout['H_Nivel'] = df_layout['Tp.posição depósito'].apply(extrair_h)
    df_layout = df_layout.sort_values(['Corredor', 'Coluna', 'Nível'])
    df_layout['Z_Base'] = df_layout.groupby(['Corredor', 'Coluna'])['H_Nivel'].cumsum() - df_layout['H_Nivel']
    
    # Coordenadas de visualização
    df_layout['Y_Macro'] = df_layout['Corredor'] * 4 + (df_layout['Coluna'] % 2 * 1.5)
    df_layout['Y_Micro'] = df_layout['Coluna'].apply(lambda x: 1.5 if x % 2 == 0 else -1.5)
    df_layout['Área_Exibicao'] = df_layout['Área armazmto.'].fillna('Desconhecido')

    if arquivo:
        if arquivo.name.endswith('.csv'):
            try: d_est = pd.read_csv(arquivo, sep=None, engine='python', encoding='utf-8')
            except: arquivo.seek(0); d_est = pd.read_csv(arquivo, sep=None, engine='python', encoding='latin-1')
        else: d_est = pd.read_excel(arquivo)
        
        if 'Data do vencimento' in d_est.columns: d_est = d_est.rename(columns={'Data do vencimento': 'Vencimento'})
        if 'Vencimento' in d_est.columns: d_est['Vencimento'] = pd.to_datetime(d_est['Vencimento'], errors='coerce')
        
        df_completo = pd.merge(df_layout, d_est, on="Posição no depósito", how="left")
        df_completo['Produto'] = df_completo.get('Produto', pd.Series(['-']*len(df_completo))).fillna('-')
        df_completo['Quantidade'] = df_completo.get('Quantidade', pd.Series([0]*len(df_completo))).fillna(0)
        df_completo['Status'] = df_completo['Produto'].apply(lambda x: 'Ocupado' if str(x) != '-' else 'Vazio')
        df_completo['Vencido'] = (df_completo['Vencimento'] < pd.Timestamp.today()) & (df_completo['Status'] == 'Ocupado')
    else:
        df_completo = df_layout.copy()
        df_completo['Status'], df_completo['Vencido'], df_completo['Produto'] = 'Vazio', False, '-'

    return df_completo

df = carregar_dados(arquivo_estoque)
if df.empty: st.stop()

# --- 2. FILTROS ---
st.sidebar.header("🔍 2. Filtros Globais")
mostrar_vazio = st.sidebar.toggle("Mostrar Estrutura Vazia", value=True)
areas = sorted([a for a in df["Área_Exibicao"].unique() if a != "Desconhecido"])
area_sel = st.sidebar.selectbox("Área", ["Todas"] + areas)
prod_sel = st.sidebar.text_input("Produto (Código)")

df_f = df.copy()
if not mostrar_vazio: df_f = df_f[df_f['Status'] == 'Ocupado']
if area_sel != "Todas": df_f = df_f[df_f["Área_Exibicao"] == area_sel]
if prod_sel: df_f = df_f[df_f["Produto"].astype(str).str.contains(prod_sel)]

# --- 3. ABAS ---
aba1, aba2 = st.tabs(["🌐 Visão Global (Radar)", "🏗️ Visão Realista (Paletes)"])

paleta = ['#1f77b4', '#2ca02c', '#ff7f0e', '#9467bd', '#8c564b']
cores_map = {a: paleta[i % len(paleta)] for i, a in enumerate(areas)}

with aba1:
    fig_macro = px.scatter_3d(df_f, x='Coluna', y='Y_Macro', z='Z_Base', color='Área_Exibicao', 
                              color_discrete_map=cores_map, hover_name='Posição no depósito', height=600)
    fig_macro.update_traces(marker=dict(symbol='square', size=3))
    fig_macro.update_layout(scene=dict(aspectmode='data'), dragmode="turntable")
    st.plotly_chart(fig_macro, use_container_width=True)

with aba2:
    corr_alvo = st.selectbox("Selecione o Corredor:", sorted(df['Corredor'].unique()))
    df_c = df_f[df_f['Corredor'] == corr_alvo]
    
    if df_c.empty: st.info("Corredor vazio.")
    else:
        # Iniciamos os agrupadores (Mesh Combiners)
        acinho = Gerador3D()    # Colunas metálicas
        longarinas = Gerador3D() # Vigas laranjas
        paletes = Gerador3D()   # Base de madeira
        cargas = Gerador3D()    # Cargas coloridas
        vencidos = Gerador3D()  # Cargas vermelhas

        max_h_total = df_c['Z_Base'].max() + 2
        
        # Lógica de desenho POR COLUNA (Evita níveis fantasmas)
        for col_id, df_col in df_c.groupby('Coluna'):
            y = df_col['Y_Micro'].iloc[0]
            
            # Desenha os Montantes (Vertical)
            acinho.add_box(col_id - 1.1, y - 0.2, 0, 0.2, 1.4, max_h_total)
            
            # Desenha as Longarinas e Cargas (Apenas onde o nível EXISTE na planilha)
            for _, row in df_col.iterrows():
                # Viga (Longarina) - Só desenha se não for o chão (Z > 0)
                if row['Z_Base'] > 0:
                    longarinas.add_box(row['Coluna']-1.1, y-0.2, row['Z_Base']-0.1, 2.2, 0.1, 0.15) # Frente
                    longarinas.add_box(row['Coluna']-1.1, y+1.1, row['Z_Base']-0.1, 2.2, 0.1, 0.15) # Fundo
                
                # Carga e Palete
                if row['Status'] == 'Ocupado':
                    cor_area = cores_map.get(row['Área_Exibicao'], 'gray')
                    paletes.add_box(row['Coluna']-0.9, y+0.1, row['Z_Base'], 1.8, 1.0, 0.15) # Madeira
                    
                    if row['Vencido']:
                        vencidos.add_box(row['Coluna']-0.85, y+0.15, row['Z_Base']+0.15, 1.7, 0.9, 1.2)
                    else:
                        cargas.add_box(row['Coluna']-0.85, y+0.15, row['Z_Base']+0.15, 1.7, 0.9, 1.2)

        fig_real = go.Figure(data=[
            acinho.build_mesh("#2c3e50", "Estrutura Vertical"),
            longarinas.build_mesh("#e67e22", "Vigas"),
            paletes.build_mesh("#8b4513", "Palete Madeira"),
            cargas.build_mesh("#3498db", "Carga OK"),
            vencidos.build_mesh("#e74c3c", "VENCIDO")
        ])

        fig_real.update_layout(scene=dict(xaxis=dict(visible=False), yaxis=dict(visible=False), 
                                         zaxis=dict(visible=False), aspectmode='data'),
                               dragmode="turntable", height=800, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig_real, use_container_width=True)

# --- 4. FICHA TÉCNICA ---
st.markdown("---")
st.markdown("### 📋 Ficha Técnica (Últimos itens filtrados)")
st.dataframe(df_f[df_f['Status'] == 'Ocupado'][['Posição no depósito', 'Produto', 'Quantidade', 'Vencimento']].head(10))