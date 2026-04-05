import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import os
import math
import requests
import urllib.request
import xml.etree.ElementTree as ET

# --- TENTATIVA DE IMPORTAR MACHINE LEARNING ---
try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Carteira Maurício | Smart Hold", page_icon="🤖", layout="wide")

# --- CSS AVANÇADO ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    .stProgress > div > div > div > div { background-color: #00fa9a; }
    .bot-message { background: rgba(0, 250, 154, 0.1); border-left: 5px solid #00fa9a; padding: 15px; border-radius: 5px; margin-bottom: 20px; font-size: 1.1em;}
    .header-mauricio { display: flex; align-items: center; background: linear-gradient(90deg, #0f2027 0%, #203a43 50%, #2c5364 100%); padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
    .news-box { border-bottom: 1px solid #333; padding: 10px 0; }
    </style>
""", unsafe_allow_html=True)

ARQUIVO_ANOTACOES = "anotacoes_mauricio.csv"

# ==========================================
# 1. LISTAS DE ATIVOS
# ==========================================
ACOES = [
    'ITUB4.SA', 'BBAS3.SA', 'BBDC4.SA', 'BBSE3.SA', 'CXSE3.SA', 
    'EGIE3.SA', 'TAEE11.SA', 'CPLE6.SA', 'SAPR11.SA', 'CMIG4.SA', 'TRPL4.SA',
    'VALE3.SA', 'PETR4.SA', 'SUZB3.SA', 'KLBN11.SA', 'GGBR4.SA',
    'WEGE3.SA', 'RADL3.SA', 'LREN3.SA', 'VIVT3.SA', 'B3SA3.SA', 'ABEV3.SA'
]

FIIS = [
    'HGLG11.SA', 'BTLG11.SA', 'XPLG11.SA', 'VISC11.SA', 'XPML11.SA', 
    'MXRF11.SA', 'KNCR11.SA', 'CPTS11.SA', 'IRDM11.SA', 'HGRU11.SA'
]

# ==========================================
# 2. MOTOR DE DADOS, MACROECONOMIA E IA
# ==========================================
@st.cache_data(ttl=86400) # Atualiza a cada 24h
def buscar_dados_macro():
    """Busca Selic e IPCA direto da API oficial do BCB"""
    try:
        res_selic = requests.get("https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json", timeout=5).json()
        selic = float(res_selic[0]['valor'])
        
        res_ipca = requests.get("https://api.bcb.gov.br/dados/serie/bcdata.sgs.13522/dados/ultimos/1?formato=json", timeout=5).json()
        ipca = float(res_ipca[0]['valor'])
        return selic, ipca
    except:
        return 10.50, 4.50

@st.cache_data(ttl=3600) # Atualiza a cada hora
def buscar_noticias():
    """Busca notícias via RSS do Google News focado na B3"""
    noticias = []
    try:
        url = "https://news.google.com/rss/search?q=ibovespa+selic+ações+economia+brasil&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        xml_data = urllib.request.urlopen(req, timeout=5).read()
        root = ET.fromstring(xml_data)
        
        for item in root.findall('./channel/item')[:5]:
            noticias.append({
                'titulo': item.find('title').text,
                'link': item.find('link').text,
                'data': item.find('pubDate').text[5:16]
            })
    except: pass
    return noticias

def aplicar_machine_learning(df):
    """Usa ML K-Means para clusterizar (agrupar) as ações com base em fundamentos"""
    if not ML_AVAILABLE or df.empty:
        df['Perfil IA'] = "🤖 IA Desativada/Sem Dados"
        return df

    # Filtra apenas ações com dados válidos para não quebrar a IA
    df_ml = df[(df['P/VP'] > 0) & (df['Preço Justo (R$)'] > 0)].copy()
    
    if len(df_ml) < 5:
        df['Perfil IA'] = "❓ Dados Insuficientes"
        return df
        
    features = ['P/VP', 'Div. Yield (%)', 'Margem Graham (%)']
    X = df_ml[features]
    
    # Padroniza a escala matemática
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Roda o Algoritmo K-Means
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    df_ml['Cluster_ID'] = kmeans.fit_predict(X_scaled)
    
    # Identifica quem é quem
    medias = df_ml.groupby('Cluster_ID')[features].mean()
    id_dividendos = medias['Div. Yield (%)'].idxmax()
    id_desconto = medias['Margem Graham (%)'].idxmax()
    
    def nomear_cluster(row):
        if row['Cluster_ID'] == id_dividendos: return "🐄 Vaca Leiteira (Foco DY)"
        elif row['Cluster_ID'] == id_desconto: return "💎 Oportunidade (Desconto)"
        else: return "⚖️ Equilíbrio / Crescimento"
        
    df_ml['Perfil IA'] = df_ml.apply(nomear_cluster, axis=1)
    
    # Mescla de volta no Dataframe Original
    df = df.merge(df_ml[['Ativo', 'Perfil IA']], on='Ativo', how='left')
    df['Perfil IA'] = df['Perfil IA'].fillna("❓ Sem Classificação")
    return df

@st.cache_data(ttl=3600)
def buscar_dados_b3(lista_tickers, tipo='acao'):
    dados = []
    barra = st.progress(0, text=f"🤖 Alpha Bot extraindo dados de {len(lista_tickers)} {tipo.upper()}s...")
    
    for i, ticker in enumerate(lista_tickers):
        try:
            info = yf.Ticker(ticker).info
            preco = info.get('currentPrice', info.get('regularMarketPrice', info.get('previousClose', 0.01)))
            if preco == 0: continue

            pvp = info.get('priceToBook', 0)
            pl = info.get('trailingPE', 0)
            dy_raw = info.get('dividendYield', 0)
            dy = (dy_raw * 100 if dy_raw and dy_raw < 1 else dy_raw) if dy_raw else 0
            
            if tipo == 'acao':
                vpa = preco / pvp if pvp and pvp > 0 else 0
                lpa = preco / pl if pl and pl > 0 else 0
                
                graham = math.sqrt(22.5 * vpa * lpa) if (vpa > 0 and lpa > 0) else 0
                margem_graham = ((graham - preco) / preco) * 100 if graham > 0 else 0

                bazin = (preco * (dy / 100)) / 0.06
                margem_bazin = ((bazin - preco) / preco) * 100 if bazin > 0 else 0

                dados.append({
                    'Ativo': ticker.replace('.SA', ''),
                    'Preço (R$)': round(preco, 2),
                    'P/VP': round(pvp, 2) if pvp else 0.0,
                    'Div. Yield (%)': round(dy, 2),
                    'Preço Justo (R$)': round(graham, 2),
                    'Margem Graham (%)': round(margem_graham, 2),
                    'Preço Teto (R$)': round(bazin, 2),
                    'Margem Bazin (%)': round(margem_bazin, 2),
                })
            elif tipo == 'fii':
                margem_pvp = ((1.0 - pvp) / pvp) * 100 if pvp and pvp > 0 else 0
                dados.append({
                    'Fundo': ticker.replace('.SA', ''),
                    'Preço (R$)': round(preco, 2),
                    'P/VP': round(pvp, 2) if pvp else 0.0,
                    'Div. Yield (%)': round(dy, 2),
                    'Desconto P/VP (%)': round(margem_pvp, 2)
                })
        except: pass
        barra.progress((i + 1) / len(lista_tickers))
    
    barra.empty()
    df_final = pd.DataFrame(dados)
    
    if tipo == 'acao' and not df_final.empty:
        df_final = aplicar_machine_learning(df_final)
        
    return df_final

# ==========================================
# 3. INTERFACE E MENU
# ==========================================
st.markdown("""
<div class="header-mauricio">
    <svg width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="#00fa9a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 15px;">
        <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
    </svg>
    <div>
        <h1 style="margin:0; color:white; font-size:2em;">Carteira Maurício | Smart Hold</h1>
        <p style="margin:0; color:#00fa9a;">Inteligência Quantitativa & Macroeconomia</p>
    </div>
</div>
""", unsafe_allow_html=True)

if not ML_AVAILABLE:
    st.sidebar.warning("⚠️ IA Desativada. Adicione 'scikit-learn' no requirements.txt.")

st.sidebar.title("🧭 Módulos")
menu = st.sidebar.radio("Navegação:", [
    "🤖 Visão Geral & Macro",
    "🎯 Calcular Aporte de Hoje",
    "📊 Radar de Valuation", 
    "📝 Diário de Bordo"
])

# Carregamento de Dados (Fica na memória rápida via Cache)
df_acoes = buscar_dados_b3(ACOES, 'acao')
df_fiis = buscar_dados_b3(FIIS, 'fii')
selic_atual, ipca_atual = buscar_dados_macro()
noticias_mercado = buscar_noticias()

if st.sidebar.button("Forçar Atualização de Preços 🔄", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# ------------------------------------------
# MÓDULO 1: VISÃO GERAL & MACROECONOMIA
# ------------------------------------------
if menu == "🤖 Visão Geral & Macro":
    st.title("Sua Reunião Matinal")
    
    # KPIs Macro
    c1, c2, c3 = st.columns(3)
    c1.metric("Taxa Selic (BCB)", f"{selic_atual}% ao ano")
    c2.metric("Inflação IPCA (12m)", f"{ipca_atual}% ao ano")
    juros_reais = round(selic_atual - ipca_atual, 2)
    c3.metric("Juros Reais (Lucro Fixo)", f"+{juros_reais}% ao ano", delta_color="normal")
    
    # Texto do Robô adaptativo
    texto_bot = f"**Fala Maurício!** Com a Selic a {selic_atual}% e inflação a {ipca_atual}%, o Brasil entrega juros reais formidáveis. "
    texto_bot += "Na renda variável, a inteligência recomenda buscar ativos que entreguem prêmios de risco reais.\n\n"
    
    boas_graham = df_acoes[(df_acoes['Margem Graham (%)'] > 15)].sort_values(by='Margem Graham (%)', ascending=False).head(2)
    bons_fiis = df_fiis[(df_fiis['P/VP'] < 1.0) & (df_fiis['Div. Yield (%)'] > selic_atual*0.7)].sort_values(by='Desconto P/VP (%)', ascending=False).head(2)

    if not boas_graham.empty:
        texto_bot += "📉 **Oportunidades de Valor:** A IA detectou margem segura em " + ", ".join([r['Ativo'] for _, r in boas_graham.iterrows()]) + ".\n"
    if not bons_fiis.empty:
        texto_bot += "🏢 **FIIs Descontados:** Fique de olho em " + ", ".join([r['Fundo'] for _, r in bons_fiis.iterrows()]) + "."
        
    st.markdown(f"<div class='bot-message'>{texto_bot}</div>", unsafe_allow_html=True)
    
    # Notícias
    st.markdown("### 📰 Giro do Mercado (Últimas Notícias)")
    if noticias_mercado:
        for n in noticias_mercado:
            st.markdown(f"<div class='news-box'>🕒 {n['data']} - <a href='{n['link']}' target='_blank' style='color:#00fa9a; text-decoration:none;'>{n['titulo']}</a></div>", unsafe_allow_html=True)
    else:
        st.write("Sem notícias no momento.")

# ------------------------------------------
# MÓDULO 2: CALCULAR APORTE (APRIMORADO COM IA)
# ------------------------------------------
elif menu == "🎯 Calcular Aporte de Hoje":
    st.title("🎯 Máquina de Aporte Inteligente")
    
    valor_aporte = st.number_input("💸 Dinheiro disponível hoje (R$):", min_value=10.0, value=300.0, step=50.0)
    estrategia = st.radio("Qual seu foco estratégico?", ["Valor (Margem de Segurança)", "Renda Passiva (Dividendos)"], horizontal=True)

    if estrategia == "Valor (Margem de Segurança)":
        filtradas = df_acoes[(df_acoes['Preço (R$)'] <= valor_aporte) & (df_acoes['Margem Graham (%)'] > 0)].copy()
        filtradas = filtradas.sort_values(by='Margem Graham (%)', ascending=False).head(4)
    else:
        filtradas = df_acoes[(df_acoes['Preço (R$)'] <= valor_aporte) & (df_acoes['Margem Bazin (%)'] > 0)].copy()
        filtradas = filtradas.sort_values(by='Div. Yield (%)', ascending=False).head(4)

    if not filtradas.empty:
        filtradas['Qtd. Máx'] = (valor_aporte // filtradas['Preço (R$)']).astype(int)
        filtradas['Custo (R$)'] = filtradas['Qtd. Máx'] * filtradas['Preço (R$)']
        
        st.success(f"Portfólio otimizado para o valor de R$ {valor_aporte:.2f}")
        
        # Mostra a tabela de forma mais elegante e com o Perfil IA
        st.dataframe(
            filtradas[['Ativo', 'Perfil IA', 'Preço (R$)', 'Qtd. Máx', 'Custo (R$)', 'Margem Graham (%)', 'Div. Yield (%)']], 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.warning("Com esse valor e filtros rígidos de proteção, não há compras claras no momento.")

# ------------------------------------------
# MÓDULO 3: RADAR DE VALUATION
# ------------------------------------------
elif menu == "📊 Radar de Valuation":
    st.title("📊 Painel Analítico Quantitativo")
    st.write("Visualização completa do mercado. A Inteligência Artificial (K-Means) agrupa os ativos para facilitar a leitura.")
    
    aba1, aba2 = st.tabs(["📈 Ações (Valuation & IA)", "🏢 FIIs (Yield & Desconto)"])
    
    with aba1:
        st.dataframe(
            df_acoes[['Ativo', 'Perfil IA', 'Preço (R$)', 'P/VP', 'Div. Yield (%)', 'Margem Graham (%)']],
            column_config={
                "Perfil IA": st.column_config.TextColumn("Veredito da IA"),
                "Margem Graham (%)": st.column_config.ProgressColumn("Margem Graham (%)", format="%f%%", min_value=0, max_value=50),
                "Div. Yield (%)": st.column_config.ProgressColumn("Div. Yield (%)", format="%f%%", min_value=0, max_value=15),
            },
            use_container_width=True, hide_index=True
        )
    with aba2:
        st.dataframe(
            df_fiis,
            column_config={
                "Desconto P/VP (%)": st.column_config.ProgressColumn("Desconto P/VP (%)", format="%f%%", min_value=0, max_value=30),
                "Div. Yield (%)": st.column_config.ProgressColumn("Div. Yield (%)", format="%f%%", min_value=0, max_value=15),
            },
            use_container_width=True, hide_index=True
        )

# ------------------------------------------
# MÓDULO 4: DIÁRIO DE BORDO
# ------------------------------------------
elif menu == "📝 Diário de Bordo":
    st.title("📝 Teses de Investimento")
    with st.form("nova_anotacao"):
        ativo_nota = st.text_input("Ativo (ex: BBAS3):").upper()
        texto_nota = st.text_area("Sua tese, motivo de compra ou anotação macro:")
        salvar = st.form_submit_button("Registrar no Banco de Dados 💾")
        
        if salvar and ativo_nota and texto_nota:
            nova_linha = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y %H:%M"), "Ativo": ativo_nota, "Anotação": texto_nota}])
            if os.path.exists(ARQUIVO_ANOTACOES):
                df_notas = pd.read_csv(ARQUIVO_ANOTACOES)
                df_notas = pd.concat([nova_linha, df_notas], ignore_index=True)
            else:
                df_notas = nova_linha
            df_notas.to_csv(ARQUIVO_ANOTACOES, index=False)
            st.success("Tese salva com sucesso!")
            
    if os.path.exists(ARQUIVO_ANOTACOES):
        df_historico = pd.read_csv(ARQUIVO_ANOTACOES)
        for _, row in df_historico.iterrows():
            with st.expander(f"📌 {row['Ativo']} - {row['Data']}"):
                st.write(row['Anotação'])
