import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import streamlit.components.v1 as components

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Terminal Alpha | Buy & Hold", page_icon="🏢", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stProgress > div > div > div > div { background-color: #00fa9a; }
    .metric-card { background-color: #1e1e1e; padding: 15px; border-radius: 8px; border: 1px solid #333; text-align: center; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 1. LISTAS DE ATIVOS (SUA CARTEIRA / RADAR)
# ==========================================
ACOES = [
    'ITUB4.SA', 'BBAS3.SA', 'SANB11.SA', 'BBDC4.SA', 'BPAC11.SA',
    'EGIE3.SA', 'TAEE11.SA', 'CPLE6.SA', 'ENBR3.SA', 'ALUP11.SA',
    'SAPR11.SA', 'SBSP3.SA', 'CSMG3.SA',
    'WEGE3.SA', 'VALE3.SA', 'PETR4.SA', 'PRIO3.SA', 'B3SA3.SA',
    'RADL3.SA', 'RENT3.SA', 'LREN3.SA', 'VIVT3.SA', 'SUZB3.SA'
]

FIIS = [
    'HGLG11.SA', 'BTLG11.SA', 'XPLG11.SA', 'VILG11.SA',
    'MXRF11.SA', 'KNCR11.SA', 'CPTS11.SA', 'IRDM11.SA',
    'XPML11.SA', 'VISC11.SA', 'HSML11.SA', 'MALL11.SA',
    'HGRU11.SA', 'KNRI11.SA', 'TGAR11.SA', 'BCFF11.SA'
]

# ==========================================
# 2. MOTOR FUNDAMENTALISTA (EXTRAÇÃO DE DADOS)
# ==========================================
@st.cache_data(ttl=3600) # Cache de 1 hora (Buy & Hold não exige zero delay)
def buscar_dados_b3(lista_tickers, tipo='acao'):
    dados = []
    barra = st.progress(0, text=f"Analisando fundamentos de {tipo.upper()}...")
    
    for i, ticker in enumerate(lista_tickers):
        try:
            info = yf.Ticker(ticker).info
            preco = info.get('currentPrice', info.get('regularMarketPrice', info.get('previousClose', 0)))
            pvp = info.get('priceToBook', 0)
            dy_raw = info.get('dividendYield', 0)
            dy = (dy_raw * 100 if dy_raw and dy_raw < 1 else dy_raw) if dy_raw else 0
            
            if tipo == 'acao':
                pl = info.get('trailingPE', 0)
                roe = info.get('returnOnEquity', 0)
                margem = info.get('profitMargins', 0)
                dados.append({
                    'Ativo': ticker.replace('.SA', ''),
                    'Preço (R$)': round(preco, 2),
                    'P/L': round(pl, 2) if pl else 0.0,
                    'P/VP': round(pvp, 2) if pvp else 0.0,
                    'ROE (%)': round((roe or 0) * 100, 2),
                    'Mrg. Líquida (%)': round((margem or 0) * 100, 2),
                    'Div. Yield (%)': round(dy, 2),
                })
            elif tipo == 'fii':
                dados.append({
                    'Fundo': ticker.replace('.SA', ''),
                    'Preço (R$)': round(preco, 2),
                    'P/VP': round(pvp, 2) if pvp else 0.0,
                    'Div. Yield (%)': round(dy, 2),
                })
        except: pass
        barra.progress((i + 1) / len(lista_tickers))
    
    barra.empty()
    return pd.DataFrame(dados)

def conselho_acao(linha):
    insights = []
    if 0 < linha['P/L'] <= 10: insights.append("🟢 P/L Muito Descontado")
    elif 10 < linha['P/L'] <= 15: insights.append("🟡 P/L Justo")
    elif linha['P/L'] > 20: insights.append("🔴 Caro (Múltiplo Alto)")
    
    if linha['ROE (%)'] >= 15: insights.append("🟢 Excelente Gestão (ROE)")
    if linha['Div. Yield (%)'] >= 6: insights.append("🟢 Vaca Leiteira (DY)")
    if linha['P/VP'] < 1.0 and linha['P/L'] > 0: insights.append("🔥 Abaixo do Valor Patrimonial")
    
    return " | ".join(insights) if insights else "⚪ Neutro"

def conselho_fii(linha):
    insights = []
    if 0 < linha['P/VP'] < 0.95: insights.append("🟢 Muito Descontado")
    elif 0.95 <= linha['P/VP'] <= 1.05: insights.append("🟡 Preço Justo")
    elif linha['P/VP'] > 1.05: insights.append("🔴 Muito Ágio (Caro)")
    
    if linha['Div. Yield (%)'] >= 10: insights.append("🟢 Alto Rendimento (Atenção ao risco)")
    elif 7 <= linha['Div. Yield (%)'] < 10: insights.append("🟢 Rendimento Sólido")
    
    return " | ".join(insights) if insights else "⚪ Analise o portfólio"

# ==========================================
# 3. TRADINGVIEW WIDGET
# ==========================================
def grafico_tradingview(simbolo, tempo="D", altura=500):
    tv_symbol = f"BMFBOVESPA:{simbolo.replace('.SA', '')}"
    html = f"""
    <div class="tradingview-widget-container">
      <div id="tv_{tempo}_{tv_symbol}"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {{
      "width": "100%", "height": {altura}, "symbol": "{tv_symbol}", "interval": "{tempo}",
      "timezone": "America/Sao_Paulo", "theme": "dark", "style": "1", "locale": "br",
      "enable_publishing": false, "allow_symbol_change": true, "container_id": "tv_{tempo}_{tv_symbol}"
      }});
      </script>
    </div>
    """
    components.html(html, height=altura)

# ==========================================
# 4. MENU LATERAL
# ==========================================
st.sidebar.title("🧭 Alpha Buy & Hold")
menu = st.sidebar.radio("Navegação:", [
    "📊 Radar de Dividendos", 
    "🎯 Filtro Mágico (Screener)",
    "🔍 Dossiê do Ativo"
])

st.sidebar.markdown("---")
if st.sidebar.button("Atualizar Dados da B3 🔄", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# ==========================================
# MÓDULO 1: RADAR DE DIVIDENDOS (VISÃO GERAL)
# ==========================================
if menu == "📊 Radar de Dividendos":
    st.title("📊 Painel Geral da Carteira B3")
    st.write("Acompanhe os múltiplos e indicadores das empresas da sua Watchlist.")
    
    aba1, aba2 = st.tabs(["🏢 Ações (Empresas)", "🏘️ FIIs (Imóveis e Papel)"])
    
    with aba1:
        df_acoes = buscar_dados_b3(ACOES, 'acao')
        if not df_acoes.empty:
            df_acoes['Avaliação da IA'] = df_acoes.apply(conselho_acao, axis=1)
            st.dataframe(
                df_acoes, use_container_width=True, hide_index=True,
                column_config={
                    "ROE (%)": st.column_config.ProgressColumn(format="%.2f%%", min_value=0, max_value=30),
                    "Mrg. Líquida (%)": st.column_config.ProgressColumn(format="%.2f%%", min_value=0, max_value=30),
                    "Div. Yield (%)": st.column_config.ProgressColumn(format="%.2f%%", min_value=0, max_value=15)
                }
            )
            
    with aba2:
        df_fiis = buscar_dados_b3(FIIS, 'fii')
        if not df_fiis.empty:
            df_fiis['Avaliação da IA'] = df_fiis.apply(conselho_fii, axis=1)
            st.dataframe(
                df_fiis, use_container_width=True, hide_index=True,
                column_config={
                    "Div. Yield (%)": st.column_config.ProgressColumn(format="%.2f%%", min_value=0, max_value=15),
                    "P/VP": st.column_config.NumberColumn(format="%.2f")
                }
            )

# ==========================================
# MÓDULO 2: FILTRO MÁGICO (AUTOMAÇÃO DE ESCOLHA)
# ==========================================
elif menu == "🎯 Filtro Mágico (Screener)":
    st.title("🎯 Automação de Stock Picking")
    st.info("Defina seus critérios de Value Investing. O robô varrerá sua lista e mostrará apenas as ações que cumprem as regras.")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: max_pl = st.slider("P/L Máximo (Barateza)", 5, 30, 15)
    with col2: max_pvp = st.slider("P/VP Máximo (Desconto)", 0.5, 5.0, 2.0, 0.1)
    with col3: min_roe = st.slider("ROE Mínimo % (Eficiência)", 0, 30, 10)
    with col4: min_dy = st.slider("Yield Mínimo % (Renda)", 0, 15, 6)
    
    st.markdown("---")
    
    df_acoes = buscar_dados_b3(ACOES, 'acao')
    if not df_acoes.empty:
        # Filtro Matemático
        filtradas = df_acoes[
            (df_acoes['P/L'] > 0) & # Ignora empresas dando prejuízo
            (df_acoes['P/L'] <= max_pl) & 
            (df_acoes['P/VP'] <= max_pvp) & 
            (df_acoes['ROE (%)'] >= min_roe) & 
            (df_acoes['Div. Yield (%)'] >= min_dy)
        ].sort_values(by='Div. Yield (%)', ascending=False)
        
        if not filtradas.empty:
            st.success(f"Encontramos {len(filtradas)} ações que batem exatamente com a sua estratégia!")
            st.dataframe(filtradas, use_container_width=True, hide_index=True)
        else:
            st.warning("Nenhuma ação da sua lista atende a critérios tão rígidos neste momento. Tente afrouxar os filtros.")

# ==========================================
# MÓDULO 3: DOSSIÊ DO ATIVO
# ==========================================
elif menu == "🔍 Dossiê do Ativo":
    st.title("🔍 Raio-X Fundamentalista")
    
    ticker_input = st.text_input("Digite o código B3 (ex: PETR4, ITUB4, HGLG11):", "WEGE3").upper().replace('.SA', '')
    ticker_completo = f"{ticker_input}.SA"
    
    if ticker_input:
        with st.spinner(f"Abrindo livros de {ticker_input}..."):
            ativo = yf.Ticker(ticker_completo)
            info = ativo.info
            
            if 'regularMarketPrice' in info or 'currentPrice' in info or 'previousClose' in info:
                nome_empresa = info.get('longName', ticker_input)
                preco_atual = info.get('currentPrice', info.get('regularMarketPrice', info.get('previousClose', 0)))
                
                # Links Externos Úteis
                is_fii = len(ticker_input) == 6 and (ticker_input.endswith('11') or ticker_input.endswith('12'))
                url_status = f"https://statusinvest.com.br/fundos-imobiliarios/{ticker_input.lower()}" if is_fii else f"https://statusinvest.com.br/acoes/{ticker_input.lower()}"
                url_investidor = f"https://investidor10.com.br/{'fundos-imobiliarios' if is_fii else 'acoes'}/{ticker_input.lower()}"
                
                st.markdown(f"### 🏢 {nome_empresa} | [🔗 StatusInvest]({url_status}) | [🔗 Investidor10]({url_investidor})")

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Preço Atual", f"R$ {preco_atual:.2f}")
                c2.metric("P/VP", f"{info.get('priceToBook', 'N/A')}")
                c3.metric("Div. Yield", f"{round(info.get('dividendYield', 0) * 100, 2) if info.get('dividendYield') else 0}%")
                
                # FIIs não têm P/L tradicional
                if not is_fii:
                    c4.metric("P/L", f"{round(info.get('trailingPE', 0), 2) if info.get('trailingPE') else 'N/A'}")
                else:
                    c4.metric("Mínima 52 sem.", f"R$ {info.get('fiftyTwoWeekLow', 0):.2f}")
                
                st.markdown("---")
                st.markdown("### 📊 Comportamento de Longo Prazo (Gráfico Mensal/Semanal)")
                # Gráfico Semanal (W) é muito melhor para Buy & Hold do que diário (D)
                grafico_tradingview(ticker_completo, "W", 450)
                
                st.markdown("---")
                col_esq, col_dir = st.columns([1, 1])
                
                with col_esq:
                    st.markdown("### ⚙️ Fundamentos da Empresa")
                    st.write(f"- **Setor:** {info.get('sector', 'Fundo Imobiliário' if is_fii else 'N/A')}")
                    if not is_fii:
                        st.write(f"- **Margem Líquida:** {round(info.get('profitMargins', 0) * 100, 2) if info.get('profitMargins') else 'N/A'}%")
                        st.write(f"- **ROE:** {round(info.get('returnOnEquity', 0) * 100, 2) if info.get('returnOnEquity') else 'N/A'}%")
                        st.write(f"- **Dívida / Patrimônio:** {info.get('debtToEquity', 'N/A')}")
                    st.write(f"- **Valor de Mercado:** R$ {info.get('marketCap', 'N/A'):,}".replace(',', '.'))
                    
                    resumo = info.get('longBusinessSummary', "Resumo não disponível para este ativo.")
                    st.info(resumo[:800] + "..." if len(resumo) > 800 else resumo)

                with col_dir:
                    st.markdown("### 📰 Últimas Notícias Corporativas")
                    noticias = ativo.news
                    if noticias:
                        for n in noticias[:4]:
                            titulo, link = n.get('title', 'Sem título'), n.get('link', '#')
                            timestamp = n.get('providerPublishTime')
                            data_pub = datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y') if timestamp else ""
                            st.write(f"📅 {data_pub} — [{titulo}]({link})")
                            st.divider()
                    else: st.write("Nenhuma notícia recente no radar.")
            else: st.error("Ativo não encontrado. Verifique se digitou corretamente (sem o .SA).")
