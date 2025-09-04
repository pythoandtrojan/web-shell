#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import subprocess
import threading
from flask import Flask, request, render_template, jsonify, send_file, abort
from colorama import Fore, Style, init

# Inicializar colorama
init(autoreset=True)

app = Flask(__name__)

# Configurações padrão
DEFAULT_CONFIG = {
    "port": 5000,
    "host": "0.0.0.0",
    "password": "erik2008",
    "upload_folder": "uploads"
}

# Carregar ou criar configuração
def load_config():
    if os.path.exists("config.json"):
        with open("config.json", "r") as f:
            return json.load(f)
    else:
        with open("config.json", "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG

def save_config(config):
    with open("config.json", "w") as f:
        json.dump(config, f, indent=4)

config = load_config()

# Garantir que a pasta de uploads existe
if not os.path.exists(config['upload_folder']):
    os.makedirs(config['upload_folder'])

app.config['UPLOAD_FOLDER'] = config['upload_folder']

# Banner simples
def show_banner():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(Fore.CYAN + r"""
     ____  _   _ ____  _     ___ ____ _____ 
    |  _ \| | | | __ )| |   |_ _/ ___| ____|
    | |_) | | | |  _ \| |    | | |   |  _|  
    |  _ <| |_| | |_) | |___ | | |___| |___ 
    |_| \_\\___/|____/|_____|___\____|_____|
    """ + Style.RESET_ALL)
    print(Fore.YELLOW + "    Reverse Web Shell Admin Panel" + Style.RESET_ALL)
    print(Fore.GREEN + "    Developed with security in mind" + Style.RESET_ALL)
    print("\n")

# Verificar autenticação
def check_auth():
    auth = request.cookies.get('auth')
    return auth == config['password']

# Página de login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == config['password']:
            response = jsonify({'success': True})
            response.set_cookie('auth', password)
            return response
        else:
            return jsonify({'success': False, 'error': 'Senha incorreta'})
    
    return render_template('login.html')

# Página principal
@app.route('/')
def index():
    if not check_auth():
        return abort(403)
    return render_template('index.html')

# Executar comando
@app.route('/command', methods=['POST'])
def run_command():
    if not check_auth():
        return abort(403)
    
    command = request.json.get('command')
    if not command:
        return jsonify({'error': 'Nenhum comando fornecido'})
    
    try:
        # Executar comando no sistema
        result = subprocess.check_output(
            command, 
            shell=True, 
            stderr=subprocess.STDOUT, 
            universal_newlines=True,
            timeout=30
        )
        return jsonify({'success': True, 'output': result})
    except subprocess.CalledProcessError as e:
        return jsonify({'success': False, 'output': e.output})
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'output': 'Comando expirado (timeout)'})
    except Exception as e:
        return jsonify({'success': False, 'output': str(e)})

# Listar arquivos e diretórios
@app.route('/files')
@app.route('/files/<path:subpath>')
def list_files(subpath=''):
    if not check_auth():
        return abort(403)
    
    base_path = os.getcwd()
    if subpath:
        target_path = os.path.join(base_path, subpath)
        # Prevenir directory traversal
        if not os.path.realpath(target_path).startswith(os.path.realpath(base_path)):
            return jsonify({'error': 'Acesso negado'})
    else:
        target_path = base_path
    
    if not os.path.exists(target_path):
        return jsonify({'error': 'Diretório não existe'})
    
    files = []
    directories = []
    
    try:
        for item in os.listdir(target_path):
            item_path = os.path.join(target_path, item)
            if os.path.isdir(item_path):
                directories.append({
                    'name': item,
                    'path': os.path.join(subpath, item) if subpath else item
                })
            else:
                files.append({
                    'name': item,
                    'size': os.path.getsize(item_path),
                    'path': os.path.join(subpath, item) if subpath else item
                })
    except PermissionError:
        return jsonify({'error': 'Permissão negada para acessar este diretório'})
    
    return jsonify({
        'current_path': subpath,
        'files': files,
        'directories': directories
    })

# Download de arquivo
@app.route('/download/<path:filepath>')
def download_file(filepath):
    if not check_auth():
        return abort(403)
    
    # Prevenir directory traversal
    base_path = os.getcwd()
    target_path = os.path.join(base_path, filepath)
    if not os.path.realpath(target_path).startswith(os.path.realpath(base_path)):
        return abort(403)
    
    if os.path.exists(target_path) and os.path.isfile(target_path):
        return send_file(target_path, as_attachment=True)
    else:
        return abort(404)

# Upload de arquivo
@app.route('/upload', methods=['POST'])
def upload_file():
    if not check_auth():
        return abort(403)
    
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nome de arquivo vazio'})
    
    filename = file.filename
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return jsonify({'success': True, 'message': 'Arquivo enviado com sucesso'})

# Menu interativo no terminal
def terminal_menu():
    show_banner()
    
    while True:
        print(Fore.CYAN + "\nOpções:")
        print(Fore.GREEN + "1. Iniciar servidor web")
        print(Fore.GREEN + "2. Configurar porta")
        print(Fore.GREEN + "3. Configurar host")
        print(Fore.GREEN + "4. Alterar senha")
        print(Fore.RED + "5. Sair")
        
        choice = input(Fore.YELLOW + "\nSelecione uma opção: " + Style.RESET_ALL)
        
        if choice == '1':
            print(Fore.GREEN + f"Iniciando servidor em {config['host']}:{config['port']}" + Style.RESET_ALL)
            print(Fore.YELLOW + "Acesse http://{}:{}/login para conectar".format(
                config['host'] if config['host'] != '0.0.0.0' else 'localhost', 
                config['port']
            ))
            print(Fore.RED + "Pressione Ctrl+C para parar o servidor" + Style.RESET_ALL)
            
            # Executar Flask em thread separada para não bloquear o menu
            def run_server():
                app.run(
                    host=config['host'],
                    port=config['port'],
                    debug=False,
                    threaded=True
                )
            
            server_thread = threading.Thread(target=run_server, daemon=True)
            server_thread.start()
            
            try:
                # Manter o servidor rodando
                server_thread.join()
            except KeyboardInterrupt:
                print(Fore.RED + "\nParando servidor..." + Style.RESET_ALL)
                # Não há uma maneira limpa de parar o Flask, então encerramos o programa
                os._exit(0)
                
        elif choice == '2':
            new_port = input("Nova porta (atual: {}): ".format(config['port']))
            if new_port.isdigit() and 1 <= int(new_port) <= 65535:
                config['port'] = int(new_port)
                save_config(config)
                print(Fore.GREEN + "Porta atualizada com sucesso!" + Style.RESET_ALL)
            else:
                print(Fore.RED + "Porta inválida!" + Style.RESET_ALL)
                
        elif choice == '3':
            new_host = input("Novo host (atual: {}): ".format(config['host']))
            config['host'] = new_host
            save_config(config)
            print(Fore.GREEN + "Host atualizado com sucesso!" + Style.RESET_ALL)
            
        elif choice == '4':
            new_password = input("Nova senha (atual: {}): ".format(config['password']))
            config['password'] = new_password
            save_config(config)
            print(Fore.GREEN + "Senha atualizada com sucesso!" + Style.RESET_ALL)
            
        elif choice == '5':
            print(Fore.RED + "Saindo..." + Style.RESET_ALL)
            break
            
        else:
            print(Fore.RED + "Opção inválida!" + Style.RESET_ALL)

if __name__ == '__main__':
    terminal_menu()
