import cv2
import mss
import numpy as np
import win32gui
import subprocess
import os
import time
import sys
from flask import Flask, Response, render_template_string, request, redirect, url_for, session
from datetime import timedelta
from waitress import serve

# ==================================
# Configurações do Programa
# ==================================
NOME_APLICACAO = "Sistema de Monitoramento HUPE-UERJ"
app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'
app.permanent_session_lifetime = timedelta(minutes=20)

# Configuração de usuário e senha
USUARIOS_SENHAS = {
    "hupe": "hupe@2.0"
}

# --- Título e dimensões da janela ---
NOME_JANELA = "Câmera"
JANELA_LARGURA = 1920
JANELA_ALTURA = 1080

# --- Parâmetros de Otimização ---
# A qualidade de compressão JPEG. Valores entre 10 (mais leve) e 100 (melhor qualidade).
QUALIDADE_JPEG = 60

# O FPS máximo.
FPS_MAXIMO = 30
TEMPO_ENTRE_FRAMES = 1 / FPS_MAXIMO

def get_window_box(window_name):
    """
    Encontra e retorna as dimensões de uma janela com o nome especificado.
    """
    try:
        hwnd = win32gui.FindWindow(None, window_name)
        if hwnd:
            # Verifica se a janela existe E se ela está visível e em foco
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetForegroundWindow() == hwnd:
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                width = right - left
                height = bottom - top
                return {"left": left, "top": top, "width": width, "height": height}
    except Exception as e:
        print(f"Erro ao encontrar a janela: {e}")
    return None

def start_camera_app():
    """
    Inicia o aplicativo 'Câmera' do Windows e espera a janela aparecer.
    """
    try:
        subprocess.Popen("start microsoft.windows.camera:", shell=True)
    except Exception as e:
        print(f"Erro ao iniciar o aplicativo 'Câmera': {e}")
        return False

    # Espera até 10 segundos para a janela da câmera aparecer
    for _ in range(20):
        hwnd = win32gui.FindWindow(None, NOME_JANELA)
        if hwnd:
            # Redimensiona a janela para a proporção widescreen e a move
            win32gui.SetWindowPos(hwnd, 0, 0, 0, JANELA_LARGURA, JANELA_ALTURA, 0)
            return True
        time.sleep(0.5)
    return False

def generate_frames():
    if not start_camera_app():
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + cv2.imencode('.jpg', np.zeros((480, 640, 3)))[1].tobytes() + b'\r\n')
        return
        
    with mss.mss() as sct:
        while True:
            start_time = time.time()
            monitor = get_window_box(NOME_JANELA)
            if monitor is None:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + cv2.imencode('.jpg', np.zeros((480, 640, 3)))[1].tobytes() + b'\r\n')
            else:
                sct_img = sct.grab(monitor)
                frame = np.array(sct_img)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                frame = cv2.resize(frame, (JANELA_LARGURA, JANELA_ALTURA))
                
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, QUALIDADE_JPEG])
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            elapsed_time = time.time() - start_time
            sleep_time = TEMPO_ENTRE_FRAMES - elapsed_time
            if sleep_time > 0:
                time.sleep(sleep_time)

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'logged_in' in session:
        return redirect(url_for('index'))
    
    error = None
    if request.method == 'POST':
        if USUARIOS_SENHAS.get(request.form['username']) == request.form['password']:
            session['logged_in'] = True
            session.permanent = True
            return redirect(url_for('index'))
        else:
            error = 'Credenciais inválidas. Tente novamente.'
            
    return render_template_string("""
    <!DOCTYPE html>
    <html>
      <head>
        <title>Login</title>
        <style>
          body { font-family: 'Segoe UI', Arial, sans-serif; background-color: #f0f0f0; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
          .login-box { background-color: #fff; padding: 40px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); text-align: center; }
          h2 { color: #003366; margin-bottom: 20px; }
          input[type="text"], input[type="password"] { width: 100%; padding: 10px; margin: 8px 0; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; }
          input[type="submit"] { width: 100%; background-color: #005a8f; color: white; padding: 12px 20px; border: none; border-radius: 4px; cursor: pointer; }
          input[type="submit"]:hover { background-color: #004066; }
          .error { color: red; margin-bottom: 15px; }
        </style>
      </head>
      <body>
        <div class="login-box">
          <h2>{{ app_name }}</h2>
          {% if error %}<p class="error">{{ error }}</p>{% endif %}
          <form method="post">
            <input type="text" name="username" placeholder="Usuário" required><br>
            <input type="password" name="password" placeholder="Senha" required><br>
            <input type="submit" value="Entrar">
          </form>
        </div>
      </body>
    </html>
    """, app_name=NOME_APLICACAO, error=error)

@app.route('/index')
def index():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    return render_template_string("""
    <html>
      <head>
        <title>Desktop Stream HUPE-UERJ</title>
        <style>
          body { background-color: #000; font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 0; display: flex; flex-direction: column; justify-content: center; align-items: center; min-height: 100vh; color: white; }
          .container { text-align: center; width: 100%; max-width: 1280px; }
          h1 { color: #fff; font-size: 2.5em; margin-bottom: 10px; }
          .video-container { position: relative; width: 100%; padding-bottom: 56.25%; height: 0; }
          .video-container img { position: absolute; top: 0; left: 0; width: 100%; height: 100%; }
          .logout-link { color: #fff; text-decoration: none; font-size: 1.2em; margin-top: 20px; display: block; }
          .logout-link:hover { text-decoration: underline; }
        </style>
      </head>
      <body>
        <div class="container">
          <h1>HUPE - ROBÔ DAVINCI</h1>
          <div class="video-container">
            <img src="{{ url_for('video_feed') }}">
          </div>
          <a class="logout-link" href="{{ url_for('logout') }}">Sair</a>
        </div>
      </body>
    </html>
    """)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/video_feed')
def video_feed():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=5000, threads=8)