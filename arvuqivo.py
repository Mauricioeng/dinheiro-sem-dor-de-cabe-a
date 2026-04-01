import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Terminal Alpha | Buy & Hold", page_icon="📈", layout="wide")

# Estilo CSS customizado para melhorar o visual
st.markdown("""
    <style>
    .stProgress > div > div > div > div { background-color: #4CAF50; }
    .metric-container { background-color: #1E1E1E; padding: 15px; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- LISTAS DE ATIVOS (EXPANDIDAS) ---
ACOES = [
    'ITUB4.SA', 'BBAS3.SA', 'SANB11.SA', 'BBDC4.SA', 'BPAC11.SA', # Bancos
    'EGIE3.SA', 'TAEE11.SA', 'CPLE6.SA', 'ENBR3.SA', 'ALUP11.SA', # Energia
    'SAPR11.SA', 'SBSP3.SA', 'CSMG3.SA',                          # Saneamento
    'WEGE3.SA', 'VALE3.SA', 'PETR4.SA', 'PRIO3.SA',               # Indústria/Commodities
    'RADL3.SA', 'RENT3.SA', 'LREN3.SA', 'VIVT3.SA', 'B3SA3.SA'    # Varejo/Serviços/Tech
]

FIIS = [
    'HGLG11.SA', 'BTLG11.SA', 'XPLG11.SA', 'VILG11.SA', # Logística
    'MXRF11.SA', 'KNCR11.SA', 'CPTS11.SA', 'IRDM11.SA', # Papel
    'XPML11.SA', 'VISC11.SA', 'HSML11.SA', 'MALL11.SA', # Shoppings
    'HGRU11.SA', 'KNRI11.SA', 'TGAR11.SA', 'BCFF11.SA'  # Híbridos/Agro/FoF
]

FOREX = [
    'USDBRL=X', 'EURBRL=X', 'GBPBRL=X', # Moedas vs Real
    'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', # Pares Globais
    'BTC-USD', 'ETH-USD'                # Cripto (Bônus)
]

# --- FUNÇÕES DE BUSCA DE DADOS ---
@st.cache_data(ttl=1800)
def buscar_dados_fundamentus(lista_tickers, tipo='acao'):
    dados = []
    progress_bar = st.progress(0)
    
    for i, ticker in enumerate(lista_tickers):
        try:
            ativo = yf.Ticker(ticker)
            info = ativo.info
            
            preco = info.get('currentPrice', info.get('regularMarketPrice', 0))
            pvp = info.get('priceToBook', 0)
            dy_raw = info.get('dividendYield', 0)
            dy = (dy_raw * 100 if dy_raw and dy_raw < 1 else dy_raw) if dy_raw else 0
            
            if tipo == 'acao':
                pl = info.get('trailingPE', 0)
                roe = info.get('returnOnEquity', 0)
                margem = info.get('profitMargins', 0)
                divida_pl = info.get('debtToEquity', 0)
                
                dados.append({
                    'Ativo': ticker.replace('.SA', ''),
                    'Preço (R$)': round(preco, 2) if preco else 0.0,
                    'P/L': round(pl, 2) if pl else 0.0,
                    'P/VP': round(pvp, 2) if pvp else 0.0,
                    'ROE (%)': round((roe or 0) * 100, 2),
                    'Div. Yield (%)': round(dy, 2),
                    'Margem Liq (%)': round((margem or 0) * 100, 2),
                    'Dívida/PL': round(divida_pl / 100, 2) if divida_pl else 0.0 # Ajuste comum do Yahoo
                })
            else:
                dados.append({
                    'Fundo': ticker.replace('.SA', ''),
                    'Preço (R$)': round(preco, 2) if preco else 0.0,
                    'P/VP': round(pvp, 2) if pvp else 0.0,
                    'Div. Yield (%)': round(dy, 2),
                })
        except Exception:
            pass
        progress_bar.progress((i + 1) / len(lista_tickers))
        
    progress_bar.empty()
    return pd.DataFrame(dados)

@st.cache_data(ttl=300) # Forex atualiza mais rápido (5 min)
def buscar_dados_forex(lista_pares):
    dados = []
    for par in lista_pares:
        try:
            ativo = yf.Ticker(par)
            info = ativo.info
            preco = info.get('regularMarketPrice', info.get('previousClose', 0))
            abertura = info.get('regularMarketOpen', preco)
            variacao = ((preco - abertura) / abertura) * 100 if abertura else 0
            
            nome = par.replace('=X', '').replace('-', '/')
            
            dados.append({
                'Paridade': nome,
                'Cotação Atual': round(preco, 4),
                'Variação Dia (%)': round(variacao, 2),
            })
        except:
            pass
    return pd.DataFrame(dados)

# --- MOTORES DE ACONSELHAMENTO VIRTUAL ---
def conselho_acao(linha):
    insights = []
    if 0 < linha['P/L'] <= 15: insights.append("🟢 Preço atrativo (P/L baixo)")
    elif linha['P/L'] > 20: insights.append("🔴 Múltiplos esticados")
    
    if linha['ROE (%)'] >= 12: insights.append("🟢 Alta rentabilidade (ROE > 12%)")
    
    if linha['Div. Yield (%)'] >= 6: insights.append("🟢 Boa pagadora de dividendos")
    
    if linha['Dívida/PL'] > 2: insights.append("🔴 Alavancagem alta (Dívida)")
    
    return " | ".join(insights) if insights else "🟡 Neutro / Sem destaques"

def conselho_fii(linha):
    insights = []
    if 0 < linha['P/VP'] < 0.95: insights.append("🟢 Descontado (Abaixo do VP)")
    elif 0.95 <= linha['P/VP'] <= 1.05: insights.append("🟡 Preço Justo")
    elif linha['P/VP'] > 1.05: insights.append("🔴 Sendo negociado com Ágio (Caro)")
    
    if linha['Div. Yield (%)'] >= 10: insights.append("🟢 Excelente Yield (2 dígitos)")
    return " | ".join(insights) if insights else "🟡 Analise o portfólio"

# --- INTERFACE PRINCIPAL ---
st.title("📊 Terminal Alpha | Inteligência de Mercado")
st.markdown("Análise Fundamentalista Avançada para **Buy & Hold**, **FIIs** e cotações de **Forex**.")

# Sidebar de Controles
with st.sidebar:
    st.header("⚙️ Controles")
    if st.button("Atualizar Dados do Mercado 🔄", use_container_width=True):
        st.cache_data.clear()
        
    st.markdown("---")
    st.subheader("Filtros Buy & Hold")
    filtro_pl = st.slider("P/L Máximo", 0, 50, 15)
    filtro_roe = st.slider("ROE Mínimo (%)", 0, 50, 12)
    filtro_dy = st.slider("Div. Yield Mínimo (%)", 0, 20, 6)

# Carregamento de Dados
with st.spinner("Conectando aos servidores globais..."):
    df_acoes = buscar_dados_fundamentus(ACOES, tipo='acao')
    df_fiis = buscar_dados_fundamentus(FIIS, tipo='fii')
    df_forex = buscar_dados_forex(FOREX)

    if not df_acoes.empty:
        df_acoes['Análise da IA'] = df_acoes.apply(conselho_acao, axis=1)
    if not df_fiis.empty:
        df_fiis['Análise da IA'] = df_fiis.apply(conselho_fii, axis=1)

# --- PAINEL DE INDICADORES (METRICS) ---
st.markdown("### 🌐 Cotações Globais em Tempo Real")
col1, col2, col3, col4 = st.columns(4)
try:
    if not df_forex.empty:
        usd = df_forex[df_forex['Paridade'] == 'USDBRL'].iloc[0]
        eur = df_forex[df_forex['Paridade'] == 'EURBRL'].iloc[0]
        btc = df_forex[df_forex['Paridade'] == 'BTC/USD'].iloc[0]
        col1.metric("Dólar (USD/BRL)", f"R$ {usd['Cotação Atual']}", f"{usd['Variação Dia (%)']}%")
        col2.metric("Euro (EUR/BRL)", f"R$ {eur['Cotação Atual']}", f"{eur['Variação Dia (%)']}%")
        col3.metric("Bitcoin (BTC/USD)", f"$ {btc['Cotação Atual']}", f"{btc['Variação Dia (%)']}%")
except:
    pass

# Mockup rápido para o IBOV (já que indices dão muito erro na API base)
ibov_ticker = yf.Ticker('^BVSP')
try:
    ibov_price = ibov_ticker.info.get('regularMarketPrice', 0)
    col4.metric("Ibovespa", f"{int(ibov_price):,} pts".replace(',', '.'), "")
except:
    col4.metric("Ibovespa", "N/A")

st.markdown("---")

# --- ABAS DE ANÁLISE ---
aba_acoes, aba_fiis, aba_forex, aba_estrategia = st.tabs([
    "📈 Ações (Empresas)", "🏢 FIIs (Imobiliários)", "💱 Forex & Cripto", "🎯 Top Pick: Estratégia"
])

with aba_acoes:
    st.subheader("Tabela Fundamentalista de Ações")
    # Usa st.dataframe com column_config para melhor visualização
    st.dataframe(
        df_acoes,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ROE (%)": st.column_config.ProgressColumn("ROE (%)", format="%f%%", min_value=0, max_value=40),
            "Div. Yield (%)": st.column_config.ProgressColumn("Div. Yield (%)", format="%f%%", min_value=0, max_value=20),
            "Preço (R$)": st.column_config.NumberColumn("Preço", format="R$ %.2f"),
        }
    )

with aba_fiis:
    st.subheader("Panorama de Fundos Imobiliários")
    st.dataframe(
        df_fiis,
        use_container_width=True,
        hide_index=True,
        column_config={
            "P/VP": st.column_config.NumberColumn("P/VP", format="%.2f"),
            "Div. Yield (%)": st.column_config.ProgressColumn("Div. Yield (%)", format="%f%%", min_value=0, max_value=18),
            "Preço (R$)": st.column_config.NumberColumn("Preço", format="R$ %.2f"),
        }
    )

with aba_forex:
    st.subheader("Mercado de Câmbio e Criptoativos")
    st.dataframe(
        df_forex,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Cotação Atual": st.column_config.NumberColumn("Cotação", format="%.4f"),
            "Variação Dia (%)": st.column_config.NumberColumn("Variação", format="%.2f%%")
        }
    )

with aba_estrategia:
    st.subheader("🏆 Filtro Inteligente Buy & Hold")
    st.write(f"Buscando empresas com: **P/L** até {filtro_pl} | **ROE** acima de {filtro_roe}% | **DY** acima de {filtro_dy}%")
    
    if not df_acoes.empty:
        filtro = (
            (df_acoes['P/L'] > 0) & (df_acoes['P/L'] <= filtro_pl) & 
            (df_acoes['ROE (%)'] >= filtro_roe) & 
            (df_acoes['Div. Yield (%)'] >= filtro_dy)
        )
        empresas_aprovadas = df_acoes[filtro].sort_values(by='Div. Yield (%)', ascending=False)
        
        if empresas_aprovadas.empty:
            st.warning("Nenhuma empresa atende a todos os critérios simultaneamente com os dados atuais.")
        else:
            st.success(f"**{len(empresas_aprovadas)}** empresas aprovadas na sua estratégia!")
            st.dataframe(empresas_aprovadas, use_container_width=True, hide_index=True)
            
            # Gráfico das Top Aprovadas
            fig = px.bar(
                empresas_aprovadas, x='Ativo', y='Div. Yield (%)', color='ROE (%)',
                title="Comparativo: Dividend Yield x ROE (Ativos Aprovados)",
                text_auto='.2f', color_continuous_scale='Viridis'
            )
            st.plotly_chart(fig, use_container_width=True)