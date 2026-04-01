import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import streamlit.components.v1 as components
import smtplib
from email.message import EmailMessage

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Terminal Alpha | Scalping Exness", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    .stProgress > div > div > div > div { background-color: #00fa9a; }
    </style>
""", unsafe_allow_html=True)

# --- LISTAS DE ATIVOS FOCADOS EM HORÁRIO NOTURNO (SESSÃO ASIÁTICA/CRIPTO) ---
FOREX_NIGHT =['USDJPY=X', 'AUDUSD=X', 'NZDUSD=X', 'EURJPY=X', 'BTC-USD', 'ETH-USD']

# --- FUNÇÃO DE ENVIO DE E-MAIL ---
def enviar_alerta_email(remetente, senha, destinatario, ativo, sinal, preco, tp, sl):
    try:
        msg = EmailMessage()
        msg['Subject'] = f"SINAL ALPHA ⚡ {ativo} - {sinal}"
        msg['From'] = remetente
        msg['To'] = destinatario
        
        conteudo = f"""
        Olá Trader,
        
        O Robô Alpha detectou uma oportunidade de Scalping:
        Ativo: {ativo}
        Sinal: {sinal}
        Preço Atual: {preco}
        
        Alvo (Take Profit): {tp}
        Stop Loss: {sl}
        
        Acesse sua corretora (Exness) para avaliar a entrada.
        """
        msg.set_content(conteudo)
        
        # Configuração para Gmail (Requer "Senha de App" no Google)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(remetente, senha)
            smtp.send_message(msg)
        return True
    except Exception as e:
        return False

def grafico_tradingview(simbolo, tempo="1"):
    tv_symbol = f"FX_IDC:{simbolo.replace('=X', '')}" if "=X" in simbolo else f"BINANCE:{simbolo.replace('-', '')}"
    html = f"""
    <div class="tradingview-widget-container">
      <div id="tv_{tempo}"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{"width": "100%","height": 400,"symbol": "{tv_symbol}","interval": "{tempo}","timezone": "America/Sao_Paulo","theme": "dark","style": "1","locale": "br","enable_publishing": false,"allow_symbol_change": false,"container_id": "tv_{tempo}"}});
      </script>
    </div>"""
    components.html(html, height=400)

# --- MOTOR DE SCALPING COM BACKTEST (WIN RATE) ---
def analisar_scalping_avancado(ticker, volume_lotes, tempo='1m'):
    """Analisa o gráfico e calcula a Taxa de Acerto das últimas 50 velas"""
    try:
        periodo = "5d" if tempo == '1m' else "1mo"
        hist = yf.Ticker(ticker).history(period=periodo, interval=tempo)
        if hist.empty or len(hist) < 50: return None
        
        df = hist.copy()
        preco_atual = df['Close'].iloc[-1]
        
        # Pega as últimas 15 velas para definir o canal atual
        hist_recente = df.tail(15)
        res_intra = hist_recente['High'].max()
        sup_intra = hist_recente['Low'].min()
        
        if res_intra == sup_intra: return None
        
        # --- LÓGICA DE BACKTEST (SIMULADOR DE DESEMPENHO) ---
        vitorias = 0
        derrotas = 0
        
        # Simula a estratégia nas 50 velas anteriores
        for i in range(len(df)-65, len(df)-15):
            recorte = df.iloc[i:i+15]
            sup_teste = recorte['Low'].min()
            res_teste = recorte['High'].max()
            meio_teste = (sup_teste + res_teste) / 2
            preco_entrada = recorte['Close'].iloc[-1]
            
            # Pega as próximas 10 velas para ver o que aconteceu
            futuro = df.iloc[i+15:i+25]
            
            if preco_entrada <= meio_teste: # Comprou
                tp_teste = res_teste
                sl_teste = sup_teste
                max_futuro = futuro['High'].max()
                min_futuro = futuro['Low'].min()
                if max_futuro >= tp_teste: vitorias += 1
                elif min_futuro <= sl_teste: derrotas += 1
            else: # Vendeu
                tp_teste = sup_teste
                sl_teste = res_teste
                max_futuro = futuro['High'].max()
                min_futuro = futuro['Low'].min()
                if min_futuro <= tp_teste: vitorias += 1
                elif max_futuro >= sl_teste: derrotas += 1

        total_trades = vitorias + derrotas
        win_rate = (vitorias / total_trades * 100) if total_trades > 0 else 0

        # --- LÓGICA DE LOTE EXNESS ---
        multiplicador = 100000 if "=X" in ticker else 1
        moeda_lucro = "$" if "USD" in ticker else "R$"
        quantidade_real = volume_lotes * multiplicador
        
        meio = (res_intra + sup_intra) / 2
        margem_spread = preco_atual * 0.0003 # Margem para compensar spread da Exness
        
        if preco_atual <= meio:
            sinal = "🟢 COMPRA (LONG)"
            take_profit = res_intra
            stop_loss = sup_intra - margem_spread
            lucro = (take_profit - preco_atual) * quantidade_real
            perda = (preco_atual - stop_loss) * quantidade_real
        else:
            sinal = "🔴 VENDA (SHORT)"
            take_profit = sup_intra
            stop_loss = res_intra + margem_spread
            lucro = (preco_atual - take_profit) * quantidade_real
            perda = (stop_loss - preco_atual) * quantidade_real
            
        return {
            "sinal": sinal, "tp": take_profit, "sl": stop_loss, "lucro": lucro, "perda": perda, 
            "atual": preco_atual, "moeda": moeda_lucro, "win_rate": win_rate, "trades": total_trades
        }
    except: return None

# --- INTERFACE PRINCIPAL ---
st.sidebar.title("🧭 Scalping Desk")
menu = st.sidebar.radio("Navegação:",["⚡ Terminal de Operações", "📧 Configurar Alertas"])

st.sidebar.markdown("---")
st.sidebar.info("🌙 **Dica Exness (20:00+):** Evite EUR e GBP. Foque em **USD/JPY**, **AUD/USD** ou Criptos. O spread da Exness normaliza após as 19:30 BRT.")

if menu == "📧 Configurar Alertas":
    st.title("📧 Alertas Automáticos por E-mail")
    st.write("Configure um e-mail do Gmail para receber os sinais do robô. (Necessário gerar uma 'Senha de Aplicativo' no Google).")
    
    st.session_state['email_remetente'] = st.text_input("Seu Gmail (Remetente):", value=st.session_state.get('email_remetente', ''))
    st.session_state['senha_app'] = st.text_input("Senha de App do Gmail:", type="password", value=st.session_state.get('senha_app', ''))
    st.session_state['email_destino'] = st.text_input("E-mail que vai receber os alertas:", value=st.session_state.get('email_destino', ''))
    
    if st.button("Salvar Configurações"):
        st.success("Configurações salvas na sessão atual!")

elif menu == "⚡ Terminal de Operações":
    st.title("⚡ Exness Scalping Terminal")
    
    col_busca, col_lote = st.columns([2, 1])
    with col_busca:
        ticker_input = st.selectbox("Ativo Recomendado para Sessão Noturna:", FOREX_NIGHT)
    with col_lote:
        lote_input = st.number_input("Lote (Ex: 0.01 = Micro Lote):", min_value=0.01, value=0.05, step=0.01)

    st.markdown("---")
    
    if ticker_input:
        with st.spinner("Sincronizando gráficos de 1m e 15m... calculando Win Rate..."):
            
            # --- ANÁLISE SIMULTÂNEA (1 Min e 15 Min) ---
            scalp_1m = analisar_scalping_avancado(ticker_input, lote_input, '1m')
            scalp_15m = analisar_scalping_avancado(ticker_input, lote_input, '15m')
            
            if scalp_1m and scalp_15m:
                col_1m, col_15m = st.columns(2)
                
                # PAINEL 1 MINUTO
                with col_1m:
                    st.subheader("⏱️ Gatilho (Gráfico 1 Minuto)")
                    st.info(f"O robô simulou {scalp_1m['trades']} operações hoje. **Taxa de Acerto: {scalp_1m['win_rate']:.1f}%**")
                    
                    if scalp_1m['win_rate'] > 60: st.success("🔥 Estratégia performando bem neste ativo hoje!")
                    else: st.warning("⚠️ O ativo está imprevisível no 1 minuto. Reduza a mão ou evite operar.")
                    
                    st.markdown(f"### {scalp_1m['sinal']}")
                    c1, c2 = st.columns(2)
                    c1.metric("🎯 Alvo (TP)", f"{scalp_1m['tp']:.4f}", f"Lucro: {scalp_1m['moeda']}{scalp_1m['lucro']:.2f}")
                    c2.metric("🛑 Stop (SL)", f"{scalp_1m['sl']:.4f}", f"Risco: -{scalp_1m['moeda']}{scalp_1m['perda']:.2f}")
                    
                    # Botão de Enviar E-mail
                    if st.button("📩 Enviar Sinal 1m por E-mail", key="btn1"):
                        if 'senha_app' in st.session_state and st.session_state['senha_app'] != "":
                            enviou = enviar_alerta_email(st.session_state['email_remetente'], st.session_state['senha_app'], st.session_state['email_destino'], ticker_input, scalp_1m['sinal'], scalp_1m['atual'], scalp_1m['tp'], scalp_1m['sl'])
                            if enviou: st.success("E-mail enviado!")
                            else: st.error("Erro. Verifique a senha de app.")
                        else:
                            st.error("Configure seu e-mail no menu lateral primeiro.")
                            
                    grafico_tradingview(ticker_input, "1")

                # PAINEL 15 MINUTOS
                with col_15m:
                    st.subheader("🧭 Tendência (Gráfico 15 Minutos)")
                    st.info(f"O robô simulou {scalp_15m['trades']} operações recentes. **Taxa de Acerto: {scalp_15m['win_rate']:.1f}%**")
                    
                    if scalp_1m['sinal'][:2] == scalp_15m['sinal'][:2]:
                        st.success("✅ CONFLUÊNCIA! Os gráficos de 1m e 15m apontam para a mesma direção.")
                    else:
                        st.error("❌ DIVERGÊNCIA. O 1m diz uma coisa e o 15m diz outra. Cuidado com falsos rompimentos.")
                        
                    st.markdown(f"### {scalp_15m['sinal']}")
                    c3, c4 = st.columns(2)
                    c3.metric("🎯 Alvo (TP)", f"{scalp_15m['tp']:.4f}", f"Lucro: {scalp_15m['moeda']}{scalp_15m['lucro']:.2f}")
                    c4.metric("🛑 Stop (SL)", f"{scalp_15m['sl']:.4f}", f"Risco: -{scalp_15m['moeda']}{scalp_15m['perda']:.2f}")
                    
                    if st.button("📩 Enviar Sinal 15m por E-mail", key="btn15"):
                        if 'senha_app' in st.session_state and st.session_state['senha_app'] != "":
                            enviar_alerta_email(st.session_state['email_remetente'], st.session_state['senha_app'], st.session_state['email_destino'], ticker_input, scalp_15m['sinal'], scalp_15m['atual'], scalp_15m['tp'], scalp_15m['sl'])
                            st.success("E-mail enviado!")
                        else:
                            st.error("Configure seu e-mail no menu lateral primeiro.")
                            
                    grafico_tradingview(ticker_input, "15")
            else:
                st.warning("Dados insuficientes do Yahoo Finance no momento. Tente novamente em alguns minutos.")