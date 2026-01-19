from flask import Flask, request, jsonify, render_template, session, redirect, url_for # Adicione session, redirect e url_for
from flask_cors import CORS
import sqlite3
import os
from engine_ia import EngineIA 

app = Flask(__name__)
CORS(app)
# 1. Inicializa a IA (mantenha fora das rotas para carregar uma vez só)
ia_engine = EngineIA().inicializar_sistema()
app.secret_key = 'Mindhub@1417!' # DEFINA UMA CHAVE AQUI


@app.route('/')
def index():
    return render_template('login.html')

@app.route('/ia')
def ia_page():
    # VERIFICAÇÃO: Se não houver 'usuario' na sessão, manda de volta pro login
    if 'usuario' not in session:
        return redirect(url_for('index'))
    return render_template('chat.html')

@app.route('/login', methods=['POST'])
def login_endpoint():
    dados = request.json
    usuario = validar_no_db(dados.get('email'), dados.get('senha'))
    
    if usuario:
        # SALVA O USUÁRIO NA SESSÃO
        session['usuario'] = usuario[0] 
        return jsonify({"status": "sucesso", "role": usuario[1]}), 200
        
    return jsonify({"status": "erro", "mensagem": "Credenciais inválidas"}), 401

@app.route('/logout')
def logout():
    session.pop('usuario', None) # Limpa a sessão
    return redirect(url_for('index'))

@app.route('/perguntar', methods=['POST'])
def perguntar():
    if 'usuario' not in session:
        return jsonify({"erro": "Acesso negado"}), 403
    
    dados = request.json
    pergunta = dados.get('mensagem')
    res = ia_engine.invoke({"question": pergunta}) 
    return jsonify({"resposta": res["answer"]})

esta_atualizando = False

@app.route('/status-atualizacao')
def status_atualizacao():
    return jsonify({"atualizando": esta_atualizando})

@app.route('/forçar-atualizacao', methods=['POST'])
def forcar_atualizacao():
    global ia_engine, esta_atualizando
    esta_atualizando = True
    try:
        ia_engine = EngineIA().inicializar_sistema()
        return jsonify({"status": "sucesso"})
    finally:
        esta_atualizando = False

def validar_no_db(email, senha):
    try:
        conn = sqlite3.connect('usuarios.db')
        cursor = conn.cursor()
        cursor.execute("SELECT email, role FROM usuarios WHERE email=? AND senha=?", (email, senha))
        usuario = cursor.fetchone()
        conn.close()
        return usuario
    except sqlite3.OperationalError:
        return None

# 3. O COMANDO DE INICIAR O SERVIDOR DEVE SER O ÚLTIMO
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)