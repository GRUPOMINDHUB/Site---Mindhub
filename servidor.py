from flask import Flask, request, jsonify, render_template, session, redirect, url_for # Adicione session, redirect e url_for
from flask_cors import CORS
import sqlite3
import os
from engine_ia import EngineIA 
import traceback

app = Flask(__name__)
CORS(app)
# 1. Inicializa a IA (mantenha fora das rotas para carregar uma vez só)
ia_instancia = EngineIA()
ia_engine = ia_instancia.inicializar_sistema()
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

@app.route('/executar-edicao', methods=['POST'])
def executar_edicao():
    if 'usuario' not in session:
        return jsonify({"erro": "Não autorizado"}), 403
        
    try:
        dados = request.json
        file_id = dados.get('file_id')
        nome_arquivo = dados.get('nome_arquivo')
        texto_edicao = dados.get('texto')
        
        # Tenta executar a gravação
        sucesso = ia_instancia.editar_e_salvar_no_drive(file_id, nome_arquivo, texto_edicao)
        
        if sucesso:
            return jsonify({"status": "sucesso", "mensagem": "Arquivo atualizado no Drive!"})
        else:
            # Se a função retornou False, o erro foi capturado no try/except da EngineIA
            return jsonify({"status": "erro", "mensagem": "A função de gravação falhou. Verifique os logs do sistema."}), 500

    except Exception as e:
        # Captura o erro técnico exato
        erro_detalhado = traceback.format_exc()
        print(erro_detalhado) # Imprime no terminal/Cloud Run
        return jsonify({
            "status": "erro", 
            "mensagem": str(e), 
            "detalhe": erro_detalhado
        }), 500

@app.route('/forçar-atualizacao', methods=['POST'])
def forcar_atualizacao():
    global ia_engine, ia_instancia, esta_atualizando 
    esta_atualizando = True
    try:
        ia_instancia = EngineIA() 
        ia_engine = ia_instancia.inicializar_sistema()
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