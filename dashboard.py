import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import smtplib
from email.message import EmailMessage
import os
import math

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Carteira Maurício | Smart Hold", page_icon="🤖", layout="wide")

# --- CSS AVANÇADO E RESPONSIVO ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    .stProgress > div > div > div > div { background-color: #00fa9a; }
    .bot-message { background: rgba(0, 250, 154, 0.1); border-left: 5px solid #00fa9a; padding: 15px; border-radius: 5px; margin-bottom: 20px; font-size: 1.1em;}
    .header-mauricio { display: flex; align-items: center; background: linear-gradient(90deg, #0f2027 0%, #203a43 50%, #2c5364 100%); padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
    </style>
""", unsafe_allow_html=True)

ARQUIVO_ANOTACOES = "anotacoes_mauricio.csv"
EMAIL_DESTINO_PADRAO = "mauriciomts99@gmail.com"

# ==========================================
# 1. LISTAS DE ATIVOS
# ==========================================
ACOES = [
    'ITUB4.SA', 'BBAS3.SA', 'SANB11.SA', 'BBDC4.SA', 'BBSE3.SA', 'CXSE3.SA', 
    'EGIE3.SA', 'TAEE11.SA', 'CPLE6.SA', 'SAPR11.SA', 'SBSP3.SA', 'CMIG4.SA', 'TRPL4.SA',
    'VALE3.SA', 'PETR4.SA', 'SUZB3.SA', 'KLBN11.SA', 'GGBR4.SA',
    'WEGE3.SA', 'RADL3.SA', 'LREN3.SA', 'VIVT3.SA', 'B3SA3.SA', 'ABEV3.SA'
]

FIIS = [
    'HGLG11.SA', 'BTLG11.SA', 'XPLG11.SA', 'VISC11.SA', 'XPML11.SA', 
    'MXRF11.SA', 'KNCR11.SA', 'CPTS11.SA', 'IRDM11.SA', 'HGRU11.SA', 'VGHF11.SA'
]

# ==========================================
# 2. MOTOR QUANTITATIVO (VALUATION GRAHAM E BAZIN)
# ==========================================
@st.cache_data(ttl=3600)
def buscar_dados_b3(lista_tickers, tipo='acao'):
    dados = []
    barra = st.progress(0, text=f"🤖 Alpha Bot analisando {len(lista_tickers)} {tipo.upper()}s...")
    
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
                # VALUATION: FÓRMULA DE GRAHAM (Preço Justo)
                # Graham = Raiz(22.5 * VPA * LPA)
                vpa = preco / pvp if pvp and pvp > 0 else 0
                lpa = preco / pl if pl and pl > 0 else 0
                
                graham = 0
                margem_graham = 0
                if vpa > 0 and lpa > 0:
                    graham = math.sqrt(22.5 * vpa * lpa)
                    margem_graham = ((graham - preco) / preco) * 100

                # VALUATION: FÓRMULA DE BAZIN (Preço Teto para 6% de DY)
                # Bazin = Dividendo Anual Pago / 0.06
                dividendo_anual = preco * (dy / 100)
                bazin = dividendo_anual / 0.06
                margem_bazin = ((bazin - preco) / preco) * 100 if bazin > 0 else 0

                dados.append({
                    'Ativo': ticker.replace('.SA', ''),
                    'Preço (R$)': round(preco, 2),
                    'P/VP': round(pvp, 2) if pvp else 0.0,
                    'P/L': round(pl, 2) if pl else 0.0,
                    'Div. Yield (%)': round(dy, 2),
                    'Preço Justo Graham (R$)': round(graham, 2),
                    'Margem Graham (%)': round(margem_graham, 2),
                    'Preço Teto Bazin (R$)': round(bazin, 2),
                    'Margem Bazin (%)': round(margem_bazin, 2),
                })
            elif tipo == 'fii':
                # FIIs avaliamos basicamente por P/VP e DY
                margem_pvp = ((1.0 - pvp) / pvp) * 100 if pvp > 0 else 0
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
    return pd.DataFrame(dados)

def gerar_briefing_diario(df_acoes, df_fiis):
    # Encontra as top 3 ações por margem de Graham e Bazin
    boas_graham = df_acoes[(df_acoes['Margem Graham (%)'] > 15)].sort_values(by='Margem Graham (%)', ascending=False).head(2)
    boas_bazin = df_acoes[(df_acoes['Margem Bazin (%)'] > 10)].sort_values(by='Div. Yield (%)', ascending=False).head(2)
    bons_fiis = df_fiis[(df_fiis['P/VP'] < 1.0) & (df_fiis['Div. Yield (%)'] > 8)].sort_values(by='Desconto P/VP (%)', ascending=False).head(2)

    hoje = datetime.now().strftime("%d/%m/%Y")
    
    texto = f"**🤖 Relatório Matinal Alpha Bot - {hoje}**\n\nFala Maurício! Analisei os {len(ACOES) + len(FIIS)} ativos da sua lista. Aqui estão os destaques de hoje:\n\n"
    
    if not boas_graham.empty:
        texto += "📉 **Ações Descontadas (Fórmula de Graham):**\n"
        for _, r in boas_graham.iterrows():
            texto += f"- **{r['Ativo']}**: Preço R$ {r['Preço (R$)']} | Preço Justo: R$ {r['Preço Justo Graham (R$)']} (*Upside de {r['Margem Graham (%)']}%*)\n"
            
    if not boas_bazin.empty:
        texto += "\n💰 **Vacas Leiteiras (Preço Teto Bazin - 6%):**\n"
        for _, r in boas_bazin.iterrows():
            texto += f"- **{r['Ativo']}**: Pagando {r['Div. Yield (%)']}% ao ano. Preço teto é R$ {r['Preço Teto Bazin (R$)']}.\n"

    if not bons_fiis.empty:
        texto += "\n🏢 **FIIs a Preço de Banana:**\n"
        for _, r in bons_fiis.iterrows():
            texto += f"- **{r['Fundo']}**: Sendo negociado a um P/VP de {r['P/VP']} (Desconto de {r['Desconto P/VP (%)']}% no patrimônio).\n"

    return texto

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
        <p style="margin:0; color:#00fa9a;">Motor Quantitativo & Valuation em Tempo Real</p>
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.title("🧭 Módulos")
menu = st.sidebar.radio("Navegação:", [
    "🤖 Resumo Diário (IA)",
    "🎯 Calcular Aporte de Hoje",
    "📊 Radar de Valuation", 
    "📝 Diário de Bordo"
])

# Carrega os dados na memória (Cache)
df_acoes = buscar_dados_b3(ACOES, 'acao')
df_fiis = buscar_dados_b3(FIIS, 'fii')

if st.sidebar.button("Forçar Atualização 🔄", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# ------------------------------------------
# MÓDULO 1: BRIEFING DIÁRIO (NOVO)
# ------------------------------------------
if menu == "🤖 Resumo Diário (IA)":
    st.title("Sua Reunião Matinal")
    if not df_acoes.empty and not df_fiis.empty:
        briefing = gerar_briefing_diario(df_acoes, df_fiis)
        st.markdown(f"<div class='bot-message'>{briefing}</div>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Ações Analisadas", len(df_acoes))
        col2.metric("Ações com Margem > 10%", len(df_acoes[df_acoes['Margem Graham (%)'] > 10]))
        col3.metric("FIIs com P/VP < 1.0", len(df_fiis[df_fiis['P/VP'] < 1.0]))

# ------------------------------------------
# MÓDULO 2: ASSISTENTE DE APORTE (INTELIGENTE)
# ------------------------------------------
elif menu == "🎯 Calcular Aporte de Hoje":
    st.title("🎯 Máquina de Aporte Eficiente")
    st.write("Digite o valor. O robô vai calcular a quantidade exata de lotes fracionários das ações com maior **Margem de Segurança** para otimizar seu dinheiro.")
    
    valor_aporte = st.number_input("💸 Dinheiro na Corretora hoje (R$):", min_value=10.0, value=300.0, step=50.0)
    estrategia = st.radio("Qual seu foco hoje?", ["Crescimento & Valor (Graham)", "Renda Passiva (Bazin / FIIs)"], horizontal=True)

    if estrategia == "Crescimento & Valor (Graham)":
        filtradas = df_acoes[(df_acoes['Preço (R$)'] <= valor_aporte) & (df_acoes['Margem Graham (%)'] > 5)].copy()
        filtradas = filtradas.sort_values(by='Margem Graham (%)', ascending=False)
        motivo = "Margem Graham (%)"
    else:
        filtradas = df_acoes[(df_acoes['Preço (R$)'] <= valor_aporte) & (df_acoes['Margem Bazin (%)'] > 0)].copy()
        filtradas = filtradas.sort_values(by='Div. Yield (%)', ascending=False)
        motivo = "Div. Yield (%)"

    if not filtradas.empty:
        st.success(f"Opções calculadas! Focando em: {estrategia}")
        
        # Otimizador de Carteira Simples
        top_3 = filtradas.head(3).copy()
        top_3['Qtd. Máx'] = (valor_aporte // top_3['Preço (R$)']).astype(int)
        top_3['Custo (R$)'] = top_3['Qtd. Máx'] * top_3['Preço (R$)']
        
        st.dataframe(
            top_3[['Ativo', 'Preço (R$)', motivo, 'Qtd. Máx', 'Custo (R$)']].style.highlight_max(subset=[motivo], color='darkgreen'),
            use_container_width=True, hide_index=True
        )
    else:
        st.warning("Com esse valor e filtros rígidos da IA, não há compras claras. Acumule caixa!")

# ------------------------------------------
# MÓDULO 3: RADAR DE VALUATION COMPLETO
# ------------------------------------------
elif menu == "📊 Radar de Valuation":
    st.title("📊 Painel de Controle Analítico")
    st.write("A tabela inteira com os cálculos matemáticos já processados.")
    
    aba1, aba2 = st.tabs(["📈 Ações (Valuation)", "🏢 FIIs (Yield & Desconto)"])
    
    with aba1:
        st.dataframe(
            df_acoes.style.background_gradient(cmap='Greens', subset=['Margem Graham (%)', 'Margem Bazin (%)', 'Div. Yield (%)']),
            use_container_width=True, hide_index=True
        )
    with aba2:
        st.dataframe(
            df_fiis.style.background_gradient(cmap='Greens', subset=['Desconto P/VP (%)', 'Div. Yield (%)']),
            use_container_width=True, hide_index=True
        )

# ------------------------------------------
# MÓDULO 4: DIÁRIO DE BORDO
# ------------------------------------------
elif menu == "📝 Diário de Bordo":
    st.title("📝 Teses de Investimento")
    
    with st.form("nova_anotacao"):
        ativo_nota = st.text_input("Ativo (ex: BBAS3):").upper()
        texto_nota = st.text_area("Tese ou Anotação:")
        salvar = st.form_submit_button("Registrar no Diário 💾")
        
        if salvar and ativo_nota and texto_nota:
            nova_linha = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y %H:%M"), "Ativo": ativo_nota, "Anotação": texto_nota}])
            if os.path.exists(ARQUIVO_ANOTACOES):
                df_notas = pd.read_csv(ARQUIVO_ANOTACOES)
                df_notas = pd.concat([nova_linha, df_notas], ignore_index=True)
            else:
                df_notas = nova_linha
            df_notas.to_csv(ARQUIVO_ANOTACOES, index=False)
            st.success("Tese salva com sucesso!")
            
    st.markdown("### 📚 Histórico")
    if os.path.exists(ARQUIVO_ANOTACOES):
        df_historico = pd.read_csv(ARQUIVO_ANOTACOES)
        for _, row in df_historico.iterrows():
            with st.expander(f"📌 {row['Ativo']} - {row['Data']}"):
                st.write(row['Anotação'])
