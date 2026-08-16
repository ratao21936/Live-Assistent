from flask import Flask, render_template, request, jsonify, Response
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time
import random
import threading
import queue
import json
import re
import os
from datetime import datetime

app = Flask(__name__)
log_queue = queue.Queue()
bot_ativo = False
driver = None
live_ativa = False
relatorio_gerado = False

TAXA_LUCRO = 0.50
MOEDA_REAL = 0.09

PRESENTES = {
    'Rosa': 1, 'Coração': 1, 'Estrela': 50, 'Foguete': 499,
    'Unicórnio': 2499, 'Coroa': 999, 'Leão': 2999, 'Diamante': 1499,
    'Universo': 4499, 'TikTok Universo': 44999
}

NIVEL_SORTEIO = {
    'Leão': {'quantidade': 3, 'premio': 5000},
    'Unicórnio': {'quantidade': 2, 'premio': 10000},
    'Coroa': {'quantidade': 1, 'premio': 50000},
    'TikTok Universo': {'quantidade': 1, 'premio': 100000},
}

live_data = {
    'inicio': datetime.now().isoformat(),
    'moedas_bruto': 0,
    'moedas_lucro': 0,
    'reais_lucro': 0,
    'total_presentes': 0,
    'presentes_por_nivel': {},
    'doadores': {},
    'sorteios_ativados': [],
    'premiados_fake': [],
    'logs_resumidos': []
}

HISTORICO_FILE = 'historico_lives.json'

def carregar_historico():
    if os.path.exists(HISTORICO_FILE):
        with open(HISTORICO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'lives': []}

def salvar_historico(historico):
    with open(HISTORICO_FILE, 'w', encoding='utf-8') as f:
        json.dump(historico, f, ensure_ascii=False, indent=2)

def adicionar_log(mensagem, tipo='info'):
    log_queue.put({'mensagem': mensagem, 'tipo': tipo, 'time': datetime.now().strftime('%H:%M:%S')})
    live_data['logs_resumidos'].append({'mensagem': mensagem, 'tipo': tipo, 'time': datetime.now().isoformat()})

def moedas_para_reais_lucro(moedas):
    bruto = moedas * MOEDA_REAL
    lucro = bruto * TAXA_LUCRO
    return lucro

def atualizar_ganhos(moedas, nick, presente_nome):
    live_data['moedas_bruto'] += moedas
    live_data['moedas_lucro'] += moedas * TAXA_LUCRO
    live_data['reais_lucro'] = live_data['moedas_lucro'] * MOEDA_REAL
    live_data['total_presentes'] += 1
    
    if nick not in live_data['doadores']:
        live_data['doadores'][nick] = 0
    live_data['doadores'][nick] += moedas
    
    if presente_nome not in live_data['presentes_por_nivel']:
        live_data['presentes_por_nivel'][presente_nome] = 0
    live_data['presentes_por_nivel'][presente_nome] += 1
    
    adicionar_log(f"💰 +{moedas} moedas ({presente_nome}) | Total: {live_data['moedas_bruto']} moedas (R$ {live_data['reais_lucro']:.2f} lucro)", 'stats')
    
    verificar_sorteio(presente_nome, nick)

def verificar_sorteio(presente_nome, nick):
    if presente_nome in NIVEL_SORTEIO:
        config = NIVEL_SORTEIO[presente_nome]
        quantidade = live_data['presentes_por_nivel'].get(presente_nome, 0)
        if quantidade >= config['quantidade']:
            ja_ativado = any(s['presente'] == presente_nome for s in live_data['sorteios_ativados'])
            if not ja_ativado:
                adicionar_log(f"🎉 SORTEIO ATIVADO! {config['quantidade']}x {presente_nome} enviados!", 'sorteio')
                live_data['sorteios_ativados'].append({
                    'presente': presente_nome,
                    'quantidade': config['quantidade'],
                    'premio': config['premio'],
                    'premiados': []
                })
                live_data['sorteios_ativados'][-1]['premiados'].append(nick)
                live_data['premiados_fake'].append(nick)

def gerar_relatorio():
    fim = datetime.now()
    inicio = datetime.fromisoformat(live_data['inicio'])
    duracao = str(fim - inicio).split('.')[0]
    
    top_doadores = sorted(live_data['doadores'].items(), key=lambda x: x[1], reverse=True)[:3]
    top_list = []
    for nick, moedas in top_doadores:
        presente = max(PRESENTES, key=lambda p: PRESENTES[p] if PRESENTES.get(p) <= moedas else 0)
        top_list.append({'nick': nick, 'presente': presente, 'moedas': moedas})
    
    relatorio = {
        'id': datetime.now().strftime('%Y-%m-%d_%H-%M'),
        'data': datetime.now().strftime('%d/%m/%Y %H:%M'),
        'duracao': duracao,
        'moedas_bruto': live_data['moedas_bruto'],
        'moedas_lucro': live_data['moedas_lucro'],
        'reais_lucro': live_data['reais_lucro'],
        'total_presentes': live_data['total_presentes'],
        'top_doadores': top_list,
        'presentes_por_nivel': live_data['presentes_por_nivel'],
        'sorteios_ativados': live_data['sorteios_ativados']
    }
    
    historico = carregar_historico()
    historico['lives'].append(relatorio)
    salvar_historico(historico)
    
    adicionar_log(f"📊 RELATÓRIO GERADO: {live_data['moedas_bruto']} moedas | R$ {live_data['reais_lucro']:.2f} lucro", 'relatorio')
    return relatorio

def movimento_humano(elemento):
    ac = ActionChains(driver)
    ac.move_to_element_with_offset(elemento, random.randint(-8, 8), random.randint(-8, 8))
    ac.pause(random.uniform(0.2, 0.8))
    ac.perform()

def digitar_como_humano(elemento, texto):
    elemento.click()
    time.sleep(random.uniform(0.2, 0.6))
    elemento.clear()
    for i, char in enumerate(texto):
        elemento.send_keys(char)
        time.sleep(random.uniform(0.08, 0.25))
        if i % random.randint(3, 5) == 0:
            time.sleep(random.uniform(0.1, 0.4))

def extrair_nick_roblox(texto):
    texto = texto.strip()
    match = re.search(r'\(?(?:nick|Nick)\s*:\s*([a-zA-Z0-9_]{3,20})\)?', texto)
    if match: return match.group(1)
    match = re.search(r'(?:nick|Nick)\s+([a-zA-Z0-9_]{3,20})', texto)
    if match: return match.group(1)
    palavras = texto.split()
    if palavras:
        ultima = palavras[-1].strip('.,!?()[]{}')
        if re.match(r'^[a-zA-Z0-9_]{3,20}$', ultima): return ultima
    match = re.search(r'\b([a-zA-Z0-9_]{3,20})\b', texto)
    if match:
        ignorar = ['roblox', 'nick', 'manda', 'por', 'favor', 'obrigado', 'gift', 'robux', 'doa', 'pra', 'voce']
        if match.group(1).lower() not in ignorar: return match.group(1)
    return None

def extrair_presente(texto):
    for nome, moedas in PRESENTES.items():
        if nome.lower() in texto.lower():
            return nome, moedas
    return None, 0

def enviar_gift(nick, valor, comentario_original):
    try:
        extensao_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Fake Robux Gift']"))
        )
        movimento_humano(extensao_btn)
        time.sleep(random.uniform(0.3, 0.9))
        extensao_btn.click()
        time.sleep(random.uniform(1.0, 2.0))

        campo_nick = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.ID, "username"))
        )
        campo_nick.click()
        campo_nick.clear()
        campo_nick.send_keys(comentario_original)
        time.sleep(random.uniform(0.5, 1.2))
        campo_nick.send_keys(Keys.CONTROL + 'a')
        time.sleep(random.uniform(0.2, 0.5))
        digitar_como_humano(campo_nick, nick)
        time.sleep(random.uniform(0.5, 1.5))

        campo_valor = driver.find_element(By.ID, "value")
        digitar_como_humano(campo_valor, str(valor))
        time.sleep(random.uniform(0.8, 2.0))

        botao_enviar = driver.find_element(By.ID, "sendGift")
        movimento_humano(botao_enviar)
        time.sleep(random.uniform(0.3, 0.7))
        botao_enviar.click()
        time.sleep(random.uniform(0.5, 1.0))
        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        adicionar_log(f"✅ Gift fake enviado para {nick}: {valor} robux", 'gift')
        return True
    except Exception as e:
        adicionar_log(f"❌ Erro: {e}", 'erro')
        return False

def comentar_no_chat(mensagem):
    try:
        time.sleep(random.uniform(0.5, 1.5))
        caixa_chat = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "textarea[data-e2e='live-comment-input']"))
        )
        movimento_humano(caixa_chat)
        time.sleep(random.uniform(0.2, 0.5))
        caixa_chat.click()
        digitar_como_humano(caixa_chat, mensagem)
        time.sleep(random.uniform(0.5, 1.2))
        caixa_chat.submit()
        adicionar_log(f"💬 {mensagem}", 'chat')
        return True
    except Exception as e:
        adicionar_log(f"Erro ao comentar: {e}", 'erro')
        return False

def ler_chat():
    try:
        time.sleep(random.uniform(0.5, 1.5))
        comentarios = driver.find_elements(By.CSS_SELECTOR, "div[data-e2e='live-comment-item'] span")
        resultados = []
        for c in comentarios:
            texto = c.text
            if ":" in texto:
                partes = texto.split(":", 1)
                if len(partes) == 2:
                    nick_tiktok = partes[0].strip()
                    mensagem = partes[1].strip()
                    presente_nome, moedas = extrair_presente(mensagem)
                    if presente_nome:
                        atualizar_ganhos(moedas, nick_tiktok, presente_nome)
                        adicionar_log(f"🎁 {nick_tiktok} enviou {presente_nome} (+{moedas} moedas)", 'presente')
                    nick_roblox = extrair_nick_roblox(mensagem)
                    if nick_roblox:
                        resultados.append({
                            'nick_roblox': nick_roblox,
                            'nick_tiktok': nick_tiktok,
                            'mensagem_original': mensagem
                        })
        return resultados
    except Exception as e:
        return []

def verificar_live_ativa():
    try:
        elementos = driver.find_elements(By.CSS_SELECTOR, "[data-e2e='live-ended-text'], .live-ended-message")
        if elementos:
            return False
        driver.find_element(By.CSS_SELECTOR, "textarea[data-e2e='live-comment-input']")
        return True
    except:
        return False

def iniciar_bot(live_url):
    global driver, bot_ativo, live_ativa, relatorio_gerado
    try:
        adicionar_log("🚀 Iniciando navegador...", 'info')
        options = Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--window-size=1280,720")
        
        driver = webdriver.Chrome(options=options)
        driver.get(live_url)
        adicionar_log(f"📺 Acessando live...", 'info')
        
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-e2e='live-comment-item']"))
        )
        adicionar_log("✅ Live carregada! Monitorando...", 'info')
        
        ja_premiados = []
        live_ativa = True
        relatorio_gerado = False
        
        while bot_ativo and live_ativa:
            if not verificar_live_ativa():
                adicionar_log("🔴 Live encerrada detectada!", 'info')
                live_ativa = False
                break
            
            resultados = ler_chat()
            disponiveis = [r for r in resultados if r['nick_roblox'] not in ja_premiados]
            
            for sorteio in live_data['sorteios_ativados']:
                for premiado in sorteio['premiados']:
                    if premiado not in ja_premiados:
                        disponiveis.append({'nick_roblox': premiado, 'nick_tiktok': premiado, 'mensagem_original': ''})
            
            if disponiveis:
                escolhido = random.choice(disponiveis)
                nick = escolhido['nick_roblox']
                mensagem_original = escolhido.get('mensagem_original', nick)
                
                adicionar_log(f"🎯 Sorteado: {nick}", 'sorteio')
                time.sleep(random.randint(2, 5))
                valor = random.choice([1000, 2500, 5000, 7500, 10000])
                
                if enviar_gift(nick, valor, mensagem_original):
                    comentar_no_chat(f"@{nick} ganhou {valor} robux! 🎉")
                    ja_premiados.append(nick)
                    if len(ja_premiados) > 50:
                        ja_premiados = ja_premiados[-50:]
                
                espera = random.randint(5, 12)
                for _ in range(espera):
                    if not bot_ativo or not live_ativa:
                        break
                    time.sleep(1)
            else:
                time.sleep(3)
        
        if not live_ativa and not relatorio_gerado:
            relatorio_gerado = True
            relatorio = gerar_relatorio()
            adicionar_log(f"📊 Relatório salvo! Lucro: R$ {relatorio['reais_lucro']:.2f}", 'relatorio')
            
    except Exception as e:
        adicionar_log(f"❌ Erro crítico: {e}", 'erro')
    finally:
        if driver:
            driver.quit()
        adicionar_log("🛑 Bot finalizado.", 'info')
        bot_ativo = False

@app.route('/')
def index():
    historico = carregar_historico()
    return render_template('index.html', historico=historico)

@app.route('/iniciar', methods=['POST'])
def iniciar():
    global bot_ativo, live_data
    if bot_ativo:
        return jsonify({'status': 'ja_rodando'})
    data = request.get_json()
    live_url = data.get('live_url')
    if not live_url:
        return jsonify({'status': 'erro', 'msg': 'URL da live é obrigatória'})
    
    live_data = {
        'inicio': datetime.now().isoformat(),
        'moedas_bruto': 0,
        'moedas_lucro': 0,
        'reais_lucro': 0,
        'total_presentes': 0,
        'presentes_por_nivel': {},
        'doadores': {},
        'sorteios_ativados': [],
        'premiados_fake': [],
        'logs_resumidos': []
    }
    
    bot_ativo = True
    thread = threading.Thread(target=iniciar_bot, args=(live_url,))
    thread.daemon = True
    thread.start()
    return jsonify({'status': 'ok'})

@app.route('/parar', methods=['POST'])
def parar():
    global bot_ativo, live_ativa, relatorio_gerado
    bot_ativo = False
    live_ativa = False
    return jsonify({'status': 'ok'})

@app.route('/logs')
def logs():
    def generate():
        while True:
            try:
                log = log_queue.get(timeout=1)
                yield f"data: {json.dumps(log)}\n\n"
            except:
                continue
    return Response(generate(), mimetype='text/event-stream')

@app.route('/live_data')
def get_live_data():
    return jsonify({
        'moedas_bruto': live_data['moedas_bruto'],
        'moedas_lucro': live_data['moedas_lucro'],
        'reais_lucro': live_data['reais_lucro'],
        'total_presentes': live_data['total_presentes'],
        'doadores': live_data['doadores'],
        'sorteios_ativados': live_data['sorteios_ativados'],
        'premiados_fake': live_data['premiados_fake']
    })

@app.route('/historico')
def get_historico():
    return jsonify(carregar_historico())

if __name__ == '__main__':
    app.run(debug=True, threaded=True, host='0.0.0.0', port=5000)
