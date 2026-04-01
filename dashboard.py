import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import streamlit.components.v1 as components
import smtplib
from email.message import EmailMessage

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Terminal Alpha Pro", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stProgress > div > div > div > div { background-color: #00fa9a; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 1. LISTAS DE ATIVOS
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

FOREX_NIGHT = ['USDJPY=X', 'AUDUSD=X', 'NZDUSD=X', 'EURJPY=X', 'BTC-USD', 'ETH-USD']
FOREX_GERAL = ['USDBRL=X', 'EURBRL=X', 'EURUSD=X', 'BTC-USD', 'ETH-USD']

# ==========================================
# 2. FUNÇÕES DE DADOS E IA (BUY & HOLD)
# ==========================================
@st.cache_data(ttl=1800)
def buscar_dados_tabela(lista_tickers, tipo='acao'):
    dados = []
    barra = st.progress(0, text=f"Buscando dados de {tipo}...")
    
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
                dados.append({
                    'Ativo': ticker.replace('.SA', ''),
                    'Preço (R$)': round(preco, 2),
                    'P/L': round(pl, 2) if pl else 0.0,
                    'P/VP': round(pvp, 2) if pvp else 0.0,
                    'ROE (%)': round((roe or 0) * 100, 2),
                    'Div. Yield (%)': round(dy, 2),
                })
            elif tipo == 'fii':
                dados.append({
                    'Fundo': ticker.replace('.SA', ''),
                    'Preço (R$)': round(preco, 2),
                    'P/VP': round(pvp, 2) if pvp else 0.0,
                    'Div. Yield (%)': round(dy, 2),
                })
            elif tipo == 'forex':
                nome = ticker.replace('=X', '').replace('-', '/')
                dados.append({
                    'Ativo': nome,
                    'Preço Atual': round(preco, 4),
                })
        except: pass
        barra.progress((i + 1) / len(lista_tickers))
    
    barra.empty()
    return pd.DataFrame(dados)

def conselho_acao(linha):
    insights = []
    if 0 < linha['P/L'] <= 15: insights.append("🟢 P/L atrativo")
    elif linha['P/L'] > 20: insights.append("🔴 Múltiplos esticados (Caro)")
    if linha['ROE (%)'] >= 12: insights.append("🟢 Alta rentabilidade")
    if linha['Div. Yield (%)'] >= 6: insights.append("🟢 Bom pagador")
    return " | ".join(insights) if insights else "🟡 Neutro"

def conselho_fii(linha):
    insights = []
    if 0 < linha['P/VP'] < 0.95: insights.append("🟢 Descontado")
    elif 0.95 <= linha['P/VP'] <= 1.05: insights.append("🟡 Preço Justo")
    elif linha['P/VP'] > 1.05: insights.append("🔴 Fundo com Ágio")
    if linha['Div. Yield (%)'] >= 10: insights.append("🟢 Excelente Yield")
    return " | ".join(insights) if insights else "🟡 Analise o portfólio"

# ==========================================
# 3. FUNÇÕES DE TRADINGVIEW E SCALPING
# ==========================================
def grafico_tradingview(simbolo, tempo="D", altura=500):
    tv_symbol = simbolo
    if simbolo.endswith('.SA'): tv_symbol = f"BMFBOVESPA:{simbolo.replace('.SA', '')}"
    elif "=X" in simbolo: tv_symbol = f"FX_IDC:{simbolo.replace('=X', '')}"
    elif "-USD" in simbolo: tv_symbol = f"BINANCE:{simbolo.replace('-', '')}"

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

def enviar_alerta_email(remetente, senha, destinatario, ativo, sinal, preco, tp, sl):
    try:
        msg = EmailMessage()
        msg['Subject'] = f"SINAL ALPHA ⚡ {ativo} - {sinal}"
        msg['From'], msg['To'] = remetente, destinatario
        conteudo = f"Olá Trader,\n\nO Robô Alpha detectou uma oportunidade:\nAtivo: {ativo}\nSinal: {sinal}\nPreço Atual: {preco}\nAlvo (TP): {tp}\nStop Loss (SL): {sl}"
        msg.set_content(conteudo)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(remetente, senha)
            smtp.send_message(msg)
        return True
    except: return False

def analisar_scalping_avancado(ticker, volume_lotes, tempo='1m'):
    try:
        periodo = "5d" if tempo == '1m' else "1mo"
        df = yf.Ticker(ticker).history(period=periodo, interval=tempo)
        if df.empty or len(df) < 50: return None
        
        preco_atual = df['Close'].iloc[-1]
        hist_recente = df.tail(15)
        res_intra, sup_intra = hist_recente['High'].max(), hist_recente['Low'].min()
        if res_intra == sup_intra: return None
        
        vitorias = derrotas = 0
        for i in range(len(df)-65, len(df)-15):
            recorte = df.iloc[i:i+15]
            futuro = df.iloc[i+15:i+25]
            sup_teste, res_teste = recorte['Low'].min(), recorte['High'].max()
            meio_teste = (sup_teste + res_teste) / 2
            
            if recorte['Close'].iloc[-1] <= meio_teste:
                if futuro['High'].max() >= res_teste: vitorias += 1
                elif futuro['Low'].min() <= sup_teste: derrotas += 1
            else:
                if futuro['Low'].min() <= sup_teste: vitorias += 1
                elif futuro['High'].max() >= res_teste: derrotas += 1

        total_trades = vitorias + derrotas
        win_rate = (vitorias / total_trades * 100) if total_trades > 0 else 0

        multiplicador = 100000 if "=X" in ticker else 1
        moeda_lucro = "$" if "USD" in ticker else "R$"
        quantidade_real = volume_lotes * multiplicador
        margem_spread = preco_atual * 0.0003
        
        if preco_atual <= (res_intra + sup_intra) / 2:
            sinal, tp, sl = "🟢 COMPRA (LONG)", res_intra, sup_intra - margem_spread
            lucro, perda = (tp - preco_atual) * quantidade_real, (preco_atual - sl) * quantidade_real
        else:
            sinal, tp, sl = "🔴 VENDA (SHORT)", sup_intra, res_intra + margem_spread
            lucro, perda = (preco_atual - tp) * quantidade_real, (sl - preco_atual) * quantidade_real
            
        return {"sinal": sinal, "tp": tp, "sl": sl, "lucro": lucro, "perda": perda, "atual": preco_atual, "moeda": moeda_lucro, "win_rate": win_rate, "trades": total_trades}
    except: return None

# ==========================================
# 4. MENU DE NAVEGAÇÃO LATERAL
# ==========================================
st.sidebar.title("🧭 Alpha Terminal Pro")
menu = st.sidebar.radio("Selecione o Módulo:", [
    "⚡ Scalping Exness (Trading)", 
    "📊 Visão Geral (Buy & Hold)", 
    "🔍 Raio-X do Ativo",
    "📧 Configurar Alertas"
])

st.sidebar.markdown("---")
if st.sidebar.button("Limpar Cache de Dados 🔄", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# ==========================================
# MÓDULO 1: SCALPING (DAY TRADE)
# ==========================================
if menu == "⚡ Scalping Exness (Trading)":
    st.title("⚡ Exness Scalping Terminal")
    st.info("🌙 **Dica Exness:** Após as 19:30 BRT, foque em USD/JPY, AUD/USD ou Criptos para evitar spread alto.")
    
    col_busca, col_lote = st.columns([2, 1])
    with col_busca: ticker_input = st.selectbox("Par/Cripto:", FOREX_NIGHT)
    with col_lote: lote_input = st.number_input("Lote Exness (Ex: 0.05):", min_value=0.01, value=0.05, step=0.01)

    st.markdown("---")
    if ticker_input:
        with st.spinner("Sincronizando gráficos e calculando Win Rate..."):
            scalp_1m = analisar_scalping_avancado(ticker_input, lote_input, '1m')
            scalp_15m = analisar_scalping_avancado(ticker_input, lote_input, '15m')
            
            if scalp_1m and scalp_15m:
                col_1m, col_15m = st.columns(2)
                
                # PAINEL 1 MINUTO
                with col_1m:
                    st.subheader("⏱️ Gatilho (1 Minuto)")
                    st.info(f"Taxa de Acerto Hoje: **{scalp_1m['win_rate']:.1f}%** ({scalp_1m['trades']} simulações)")
                    st.markdown(f"### {scalp_1m['sinal']}")
                    c1, c2 = st.columns(2)
                    c1.metric("🎯 Alvo (TP)", f"{scalp_1m['tp']:.4f}", f"+{scalp_1m['moeda']}{scalp_1m['lucro']:.2f}")
                    c2.metric("🛑 Stop (SL)", f"{scalp_1m['sl']:.4f}", f"-{scalp_1m['moeda']}{scalp_1m['perda']:.2f}")
                    
                    if st.button("📩 Enviar Sinal 1m", key="btn1"):
                        if 'senha_app' in st.session_state and st.session_state['senha_app']:
                            enviou = enviar_alerta_email(st.session_state['email_remetente'], st.session_state['senha_app'], st.session_state['email_destino'], ticker_input, scalp_1m['sinal'], scalp_1m['atual'], scalp_1m['tp'], scalp_1m['sl'])
                            st.success("Enviado!") if enviou else st.error("Erro na senha.")
                        else: st.error("Configure o e-mail no menu.")
                    grafico_tradingview(ticker_input, "1", 300)

                # PAINEL 15 MINUTOS
                with col_15m:
                    st.subheader("🧭 Tendência (15 Minutos)")
                    st.info(f"Taxa de Acerto Recente: **{scalp_15m['win_rate']:.1f}%** ({scalp_15m['trades']} simulações)")
                    if scalp_1m['sinal'][:2] == scalp_15m['sinal'][:2]: st.success("✅ CONFLUÊNCIA! Direção alinhada.")
                    else: st.error("❌ DIVERGÊNCIA. Cuidado com falsos rompimentos.")
                    
                    st.markdown(f"### {scalp_15m['sinal']}")
                    c3, c4 = st.columns(2)
                    c3.metric("🎯 Alvo (TP)", f"{scalp_15m['tp']:.4f}", f"+{scalp_15m['moeda']}{scalp_15m['lucro']:.2f}")
                    c4.metric("🛑 Stop (SL)", f"{scalp_15m['sl']:.4f}", f"-{scalp_15m['moeda']}{scalp_15m['perda']:.2f}")
                    grafico_tradingview(ticker_input, "15", 353) # Altura ajustada para bater com o botão do outro lado
            else:
                st.warning("Dados do Yahoo Finance insuficientes no momento.")

# ==========================================
# MÓDULO 2: VISÃO GERAL (BUY & HOLD)
# ==========================================
elif menu == "📊 Visão Geral (Buy & Hold)":
    st.title("📊 Visão Geral do Mercado")
    
    col1, col2, col3 = st.columns(3)
    try:
        col1.metric("Dólar", f"R$ {yf.Ticker('USDBRL=X').info.get('regularMarketPrice', 0):.2f}")
        col2.metric("Bitcoin", f"$ {yf.Ticker('BTC-USD').info.get('regularMarketPrice', 0):,.2f}")
        col3.metric("Ibovespa", f"{int(yf.Ticker('^BVSP').info.get('regularMarketPrice', 0)):,} pts".replace(',', '.'))
    except: pass
    
    st.markdown("---")
    aba1, aba2, aba3 = st.tabs(["📈 Ações", "🏢 FIIs", "💱 Forex & Cripto"])
    
    with aba1:
        df_acoes = buscar_dados_tabela(ACOES, 'acao')
        if not df_acoes.empty:
            df_acoes['Conselho IA'] = df_acoes.apply(conselho_acao, axis=1)
            st.dataframe(df_acoes, use_container_width=True, hide_index=True,
                         column_config={"ROE (%)": st.column_config.ProgressColumn(format="%.2f%%", min_value=0, max_value=40),
                                        "Div. Yield (%)": st.column_config.ProgressColumn(format="%.2f%%", min_value=0, max_value=20)})
    with aba2:
        df_fiis = buscar_dados_tabela(FIIS, 'fii')
        if not df_fiis.empty:
            df_fiis['Conselho IA'] = df_fiis.apply(conselho_fii, axis=1)
            st.dataframe(df_fiis, use_container_width=True, hide_index=True,
                         column_config={"Div. Yield (%)": st.column_config.ProgressColumn(format="%.2f%%", min_value=0, max_value=18)})
    with aba3:
        df_forex = buscar_dados_tabela(FOREX_GERAL, 'forex')
        if not df_forex.empty: st.dataframe(df_forex, use_container_width=True, hide_index=True)

# ==========================================
# MÓDULO 3: RAIO-X DO ATIVO
# ==========================================
elif menu == "🔍 Raio-X do Ativo":
    st.title("🔍 Raio-X Profissional do Ativo")
    st.markdown("Consulte Ações da B3, FIIs, Criptos ou Forex.")
    
    ticker_input = st.text_input("Código do Ativo (ex: PETR4.SA, ITUB4.SA, BTC-USD):", "WEGE3.SA").upper()
    
    if ticker_input:
        with st.spinner(f"Coletando dossiê de {ticker_input}..."):
            ativo = yf.Ticker(ticker_input)
            info = ativo.info
            
            if 'regularMarketPrice' in info or 'currentPrice' in info or 'previousClose' in info:
                nome_empresa = info.get('longName', ticker_input)
                preco_atual = info.get('currentPrice', info.get('regularMarketPrice', info.get('previousClose', 0)))
                
                # Link StatusInvest
                if ticker_input.endswith('.SA'):
                    t_limpo = ticker_input.replace('.SA', '').lower()
                    url_status = f"https://statusinvest.com.br/fundos-imobiliarios/{t_limpo}" if (len(t_limpo) == 6 and (t_limpo.endswith('11') or t_limpo.endswith('12'))) else f"https://statusinvest.com.br/acoes/{t_limpo}"
                    st.markdown(f"### 🏢 {nome_empresa} | [🔗 Abrir no StatusInvest]({url_status})")
                else:
                    st.markdown(f"### 🏢 {nome_empresa}")

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Preço Atual", f"R$ {preco_atual:.2f}" if ".SA" in ticker_input else f"$ {preco_atual:.2f}")
                c2.metric("Máxima 52 sem.", f"{info.get('fiftyTwoWeekHigh', 0):.2f}")
                c3.metric("Mínima 52 sem.", f"{info.get('fiftyTwoWeekLow', 0):.2f}")
                c4.metric("P/VP", f"{info.get('priceToBook', 'N/A')}")
                
                st.markdown("---")
                st.markdown("### 📊 Gráfico Profissional (TradingView)")
                grafico_tradingview(ticker_input, "D", 500)
                
                st.markdown("---")
                col_esq, col_dir = st.columns([1, 1])
                
                with col_esq:
                    st.markdown("### ⚙️ Indicadores Chave")
                    st.write(f"- **Setor:** {info.get('sector', 'N/A')}")
                    st.write(f"- **P/L:** {info.get('trailingPE', 'N/A')}")
                    st.write(f"- **ROE:** {round(info.get('returnOnEquity', 0) * 100, 2) if info.get('returnOnEquity') else 'N/A'}%")
                    st.write(f"- **Valor de Mercado:** {info.get('marketCap', 'N/A'):,}".replace(',', '.'))
                    resumo = info.get('longBusinessSummary', "Resumo não disponível.")
                    st.info(resumo[:600] + "..." if len(resumo) > 600 else resumo)

                with col_dir:
                    st.markdown("### 📰 Últimas Notícias")
                    noticias = ativo.news
                    if noticias:
                        for n in noticias[:5]:
                            titulo, link, publisher = n.get('title', 'Sem título'), n.get('link', '#'), n.get('publisher', 'Desconhecido')
                            timestamp = n.get('providerPublishTime')
                            data_pub = datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M') if timestamp else "Data desconhecida"
                            
                            with st.expander(f"🗞️ {titulo}"):
                                st.caption(f"Por: {publisher} em {data_pub}")
                                st.write(f"[Ler matéria]({link})")
                    else: st.write("Nenhuma notícia recente.")
            else: st.error("Ativo não encontrado.")

# ==========================================
# MÓDULO 4: ALERTAS
# ==========================================
elif menu == "📧 Configurar Alertas":
    st.title("📧 Alertas Automáticos por E-mail")
    st.write("Configure um e-mail para receber os sinais do robô de Scalping.")
    
    st.session_state['email_remetente'] = st.text_input("Seu Gmail (Remetente):", value=st.session_state.get('email_remetente', ''))
    st.session_state['senha_app'] = st.text_input("Senha de App do Gmail:", type="password", value=st.session_state.get('senha_app', ''))
    st.session_state['email_destino'] = st.text_input("E-mail de Destino:", value=st.session_state.get('email_destino', ''))
    
    if st.button("Salvar Configurações"):
        st.success("Configurações salvas temporariamente na sessão atual!")