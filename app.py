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

app = Flask(__name__)
log_queue = queue.Queue()
bot_ativo = False
driver = None

def adicionar_log(mensagem, tipo='info'):
    log_queue.put({'mensagem': mensagem, 'tipo': tipo, 'time': time.strftime('%H:%M:%S')})

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

def enviar_gift(nick, valor):
    try:
        adicionar_log(f"Abrindo extensão...", 'info')
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

        adicionar_log(f"✅ Gift enviado para {nick}: {valor} robux", 'gift')
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
        nicks = []
        for c in comentarios:
            texto = c.text
            if ":" in texto:
                nick = texto.split(":")[0].strip()
                if nick and len(nick) > 1 and not re.search(r'[\d]{6,}', nick):
                    nicks.append(nick)
        nicks_vistos = []
        for nick in nicks:
            if nick not in nicks_vistos:
                nicks_vistos.append(nick)
        return nicks_vistos
    except:
        return []

def iniciar_bot(live_url):
    global driver, bot_ativo
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
        adicionar_log("✅ Live carregada! Monitorando chat...", 'info')

        ja_premiados = []

        while bot_ativo:
            novos_nicks = ler_chat()
            disponiveis = [n for n in novos_nicks if n not in ja_premiados]

            if disponiveis:
                adicionar_log(f"📋 {len(disponiveis)} espectadores disponíveis", 'info')
                pausa = random.randint(15, 45)
                adicionar_log(f"⏳ Aguardando {pausa}s...", 'info')
                for _ in range(pausa):
                    if not bot_ativo:
                        break
                    time.sleep(1)
                if not bot_ativo:
                    break

                sorteado = random.choice(disponiveis)
                valor = random.choice([1000, 2500, 5000, 7500, 10000])
                adicionar_log(f"🎯 Sorteado: {sorteado} - {valor} robux", 'sorteio')

                if enviar_gift(sorteado, valor):
                    comentar_no_chat(f"@{sorteado} ganhou {valor} robux! 🎉 Parabéns!")
                    ja_premiados.append(sorteado)
                    if len(ja_premiados) > 50:
                        ja_premiados = ja_premiados[-50:]

                espera = random.randint(60, 180)
                adicionar_log(f"⏳ Próxima doação em {espera}s", 'info')
                for _ in range(espera):
                    if not bot_ativo:
                        break
                    time.sleep(1)
            else:
                adicionar_log("⏳ Nenhum nick novo. Aguardando...", 'info')
                time.sleep(5)

    except Exception as e:
        adicionar_log(f"❌ Erro crítico: {e}", 'erro')
    finally:
        if driver:
            driver.quit()
        adicionar_log("🛑 Bot finalizado.", 'info')
        bot_ativo = False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/iniciar', methods=['POST'])
def iniciar():
    global bot_ativo
    if bot_ativo:
        return jsonify({'status': 'ja_rodando'})
    data = request.get_json()
    live_url = data.get('live_url')
    if not live_url:
        return jsonify({'status': 'erro', 'msg': 'URL da live é obrigatória'})
    bot_ativo = True
    thread = threading.Thread(target=iniciar_bot, args=(live_url,))
    thread.daemon = True
    thread.start()
    return jsonify({'status': 'ok'})

@app.route('/parar', methods=['POST'])
def parar():
    global bot_ativo
    bot_ativo = False
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

if __name__ == '__main__':
    app.run(debug=True, threaded=True, host='0.0.0.0', port=5000)
