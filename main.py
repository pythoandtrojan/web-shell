#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import socket
import threading
import subprocess
import json
import base64
import time
import random
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import html
import cgi

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = ''
    class Style:
        BRIGHT = RESET_ALL = ''

# Configurações
ADMIN_PASSWORD = "erik2008"
SERVER_IP = "0.0.0.0"
SERVER_PORT = 8080
WEB_PORT = 80

class WebTerminalHandler(BaseHTTPRequestHandler):
    sessions = {}
    current_dir = os.getcwd()
    
    def do_GET(self):
        try:
            path = urlparse(self.path).path
            
            # Verificar sessão
            session_id = self.get_session_id()
            if path != '/login' and not self.is_authenticated(session_id):
                self.redirect_login()
                return
            
            if path == '/':
                self.serve_main_page(session_id)
            elif path == '/login':
                self.serve_login_page()
            elif path == '/logout':
                self.logout(session_id)
            elif path == '/api/command':
                self.handle_command_api()
            elif path == '/api/files':
                self.handle_files_api()
            elif path == '/api/download':
                self.handle_download_api()
            elif path == '/api/upload':
                self.handle_upload_api()
            elif path.startswith('/static/'):
                self.serve_static_file(path)
            else:
                self.send_error(404)
                
        except Exception as e:
            self.send_error(500, str(e))
    
    def do_POST(self):
        try:
            path = urlparse(self.path).path
            
            if path == '/login':
                self.handle_login()
            elif path == '/api/command':
                self.handle_command_api()
            elif path == '/api/upload':
                self.handle_upload_api()
            else:
                self.send_error(404)
                
        except Exception as e:
            self.send_error(500, str(e))
    
    def get_session_id(self):
        cookies = self.headers.get('Cookie', '')
        for cookie in cookies.split(';'):
            if 'session_id' in cookie:
                return cookie.split('=')[1].strip()
        return None
    
    def is_authenticated(self, session_id):
        return session_id in self.sessions and self.sessions[session_id]['authenticated']
    
    def create_session(self):
        session_id = hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]
        self.sessions[session_id] = {
            'authenticated': True,
            'created': time.time()
        }
        return session_id
    
    def logout(self, session_id):
        if session_id in self.sessions:
            del self.sessions[session_id]
        self.redirect_login()
    
    def redirect_login(self):
        self.send_response(302)
        self.send_header('Location', '/login')
        self.end_headers()
    
    def handle_login(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode()
        params = parse_qs(post_data)
        
        password = params.get('password', [''])[0]
        
        if password == ADMIN_PASSWORD:
            session_id = self.create_session()
            self.send_response(302)
            self.send_header('Location', '/')
            self.send_header('Set-Cookie', f'session_id={session_id}; Path=/; HttpOnly')
            self.end_headers()
        else:
            self.serve_login_page(error="Senha incorreta!")
    
    def serve_login_page(self, error=None):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Login - Shell Reverso</title>
            <style>
                body {{
                    background: #0d1117;
                    color: #c9d1d9;
                    font-family: 'Courier New', monospace;
                    margin: 0;
                    padding: 20px;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                }}
                .login-container {{
                    background: #161b22;
                    padding: 40px;
                    border-radius: 10px;
                    border: 1px solid #30363d;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                    width: 300px;
                }}
                h1 {{
                    color: #58a6ff;
                    text-align: center;
                    margin-bottom: 30px;
                }}
                input[type="password"] {{
                    width: 100%;
                    padding: 12px;
                    margin: 10px 0;
                    background: #0d1117;
                    border: 1px solid #30363d;
                    color: #c9d1d9;
                    border-radius: 5px;
                    outline: none;
                }}
                input[type="password"]:focus {{
                    border-color: #58a6ff;
                }}
                button {{
                    width: 100%;
                    padding: 12px;
                    background: #238636;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    font-weight: bold;
                }}
                button:hover {{
                    background: #2ea043;
                }}
                .error {{
                    color: #f85149;
                    text-align: center;
                    margin-top: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="login-container">
                <h1>🔐 Acesso Restrito</h1>
                <form method="POST">
                    <input type="password" name="password" placeholder="Senha de administrador" required>
                    <button type="submit">Acessar</button>
                </form>
                {f'<div class="error">{error}</div>' if error else ''}
            </div>
        </body>
        </html>
        '''
        self.wfile.write(html_content.encode())
    
    def serve_main_page(self, session_id):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        html_content = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Terminal Web - Shell Reverso</title>
            <style>
                :root {
                    --bg-primary: #0d1117;
                    --bg-secondary: #161b22;
                    --border: #30363d;
                    --text-primary: #c9d1d9;
                    --text-secondary: #8b949e;
                    --accent: #58a6ff;
                    --success: #3fb950;
                    --error: #f85149;
                }
                
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }
                
                body {
                    background: var(--bg-primary);
                    color: var(--text-primary);
                    font-family: 'Fira Code', 'Courier New', monospace;
                    line-height: 1.6;
                }
                
                .container {
                    display: grid;
                    grid-template-columns: 250px 1fr;
                    grid-template-rows: 60px 1fr 200px;
                    grid-template-areas: 
                        "header header"
                        "sidebar terminal"
                        "sidebar input";
                    height: 100vh;
                }
                
                .header {
                    grid-area: header;
                    background: var(--bg-secondary);
                    border-bottom: 1px solid var(--border);
                    padding: 0 20px;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                }
                
                .sidebar {
                    grid-area: sidebar;
                    background: var(--bg-secondary);
                    border-right: 1px solid var(--border);
                    padding: 20px;
                    overflow-y: auto;
                }
                
                .terminal {
                    grid-area: terminal;
                    background: var(--bg-primary);
                    padding: 20px;
                    overflow-y: auto;
                    font-family: 'Fira Code', monospace;
                }
                
                .input-area {
                    grid-area: input;
                    background: var(--bg-secondary);
                    border-top: 1px solid var(--border);
                    padding: 15px;
                }
                
                .command-input {
                    width: 100%;
                    padding: 12px;
                    background: var(--bg-primary);
                    border: 1px solid var(--border);
                    color: var(--text-primary);
                    border-radius: 5px;
                    font-family: 'Fira Code', monospace;
                    outline: none;
                }
                
                .command-input:focus {
                    border-color: var(--accent);
                }
                
                .file-list {
                    list-style: none;
                }
                
                .file-item {
                    padding: 8px;
                    margin: 5px 0;
                    background: var(--bg-primary);
                    border-radius: 5px;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }
                
                .file-item:hover {
                    background: #1c2128;
                }
                
                .file-icon {
                    width: 16px;
                    height: 16px;
                }
                
                .terminal-line {
                    margin-bottom: 5px;
                }
                
                .command {
                    color: var(--accent);
                }
                
                .output {
                    color: var(--text-primary);
                }
                
                .error {
                    color: var(--error);
                }
                
                .success {
                    color: var(--success);
                }
                
                .btn {
                    padding: 8px 16px;
                    background: var(--accent);
                    color: white;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    margin: 5px;
                }
                
                .btn:hover {
                    opacity: 0.9;
                }
                
                .section {
                    margin-bottom: 20px;
                }
                
                .section-title {
                    color: var(--accent);
                    margin-bottom: 10px;
                    font-weight: bold;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🖥️ Terminal Web - Shell Reverso</h1>
                    <div>
                        <span id="current-dir"></span>
                        <a href="/logout" class="btn">Sair</a>
                    </div>
                </div>
                
                <div class="sidebar">
                    <div class="section">
                        <div class="section-title">📁 Sistema de Arquivos</div>
                        <div id="file-explorer"></div>
                    </div>
                    
                    <div class="section">
                        <div class="section-title">⚡ Comandos Rápidos</div>
                        <button class="btn" onclick="executeCommand('pwd')">pwd</button>
                        <button class="btn" onclick="executeCommand('ls -la')">ls -la</button>
                        <button class="btn" onclick="executeCommand('whoami')">whoami</button>
                        <button class="btn" onclick="executeCommand('uname -a')">uname -a</button>
                    </div>
                    
                    <div class="section">
                        <div class="section-title">📤 Upload/Download</div>
                        <input type="file" id="file-upload" style="display: none;">
                        <button class="btn" onclick="document.getElementById('file-upload').click()">Upload File</button>
                    </div>
                </div>
                
                <div class="terminal" id="terminal-output">
                    <div class="terminal-line success">✅ Conectado ao shell remoto</div>
                    <div class="terminal-line">Digite "help" para ver comandos disponíveis</div>
                </div>
                
                <div class="input-area">
                    <input type="text" class="command-input" id="command-input" 
                           placeholder="Digite seu comando..." onkeypress="handleKeyPress(event)">
                </div>
            </div>

            <script>
                let currentDirectory = '/';
                
                function executeCommand(command) {
                    if (!command.trim()) return;
                    
                    // Adicionar comando ao terminal
                    addTerminalLine('$ ' + command, 'command');
                    
                    // Enviar comando para o servidor
                    fetch('/api/command', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ command: command })
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            addTerminalLine(data.output, 'output');
                            if (data.current_dir) {
                                currentDirectory = data.current_dir;
                                document.getElementById('current-dir').textContent = currentDirectory;
                            }
                            updateFileExplorer();
                        } else {
                            addTerminalLine('Erro: ' + data.error, 'error');
                        }
                    })
                    .catch(error => {
                        addTerminalLine('Erro de conexão: ' + error, 'error');
                    });
                    
                    // Limpar input
                    document.getElementById('command-input').value = '';
                }
                
                function handleKeyPress(event) {
                    if (event.key === 'Enter') {
                        executeCommand(document.getElementById('command-input').value);
                    }
                }
                
                function addTerminalLine(text, type) {
                    const terminal = document.getElementById('terminal-output');
                    const line = document.createElement('div');
                    line.className = 'terminal-line ' + type;
                    line.textContent = text;
                    terminal.appendChild(line);
                    terminal.scrollTop = terminal.scrollHeight;
                }
                
                function updateFileExplorer() {
                    fetch('/api/files?path=' + encodeURIComponent(currentDirectory))
                        .then(response => response.json())
                        .then(data => {
                            const explorer = document.getElementById('file-explorer');
                            explorer.innerHTML = '';
                            
                            data.files.forEach(file => {
                                const item = document.createElement('div');
                                item.className = 'file-item';
                                item.innerHTML = `
                                    <span class="file-icon">${file.is_dir ? '📁' : '📄'}</span>
                                    <span>${file.name}</span>
                                `;
                                item.onclick = () => {
                                    if (file.is_dir) {
                                        executeCommand('cd "' + file.name + '" && pwd');
                                    }
                                };
                                explorer.appendChild(item);
                            });
                        });
                }
                
                // Inicializar
                document.addEventListener('DOMContentLoaded', function() {
                    updateFileExplorer();
                    executeCommand('pwd');
                    document.getElementById('command-input').focus();
                    
                    // Configurar upload
                    document.getElementById('file-upload').addEventListener('change', function(e) {
                        const file = e.target.files[0];
                        if (file) {
                            const formData = new FormData();
                            formData.append('file', file);
                            
                            fetch('/api/upload', {
                                method: 'POST',
                                body: formData
                            })
                            .then(response => response.json())
                            .then(data => {
                                if (data.success) {
                                    addTerminalLine('✅ Arquivo enviado: ' + data.filename, 'success');
                                    updateFileExplorer();
                                } else {
                                    addTerminalLine('❌ Erro no upload: ' + data.error, 'error');
                                }
                            });
                        }
                    });
                });
            </script>
        </body>
        </html>
        '''
        self.wfile.write(html_content.encode())
    
    def handle_command_api(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode())
        
        command = data.get('command', '')
        result = self.execute_command(command)
        
        response = {
            'success': True,
            'output': result,
            'current_dir': self.current_dir
        }
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
    
    def handle_files_api(self):
        query = urlparse(self.path).query
        params = parse_qs(query)
        path = params.get('path', [self.current_dir])[0]
        
        try:
            files = []
            if os.path.exists(path):
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    files.append({
                        'name': item,
                        'is_dir': os.path.isdir(item_path),
                        'size': os.path.getsize(item_path) if not os.path.isdir(item_path) else 0
                    })
            
            response = {'success': True, 'files': files}
            
        except Exception as e:
            response = {'success': False, 'error': str(e)}
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
    
    def handle_download_api(self):
        query = urlparse(self.path).query
        params = parse_qs(query)
        file_path = params.get('file', [''])[0]
        
        if os.path.exists(file_path) and os.path.isfile(file_path):
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(file_path)}"')
            self.end_headers()
            
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, "File not found")
    
    def handle_upload_api(self):
        try:
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={'REQUEST_METHOD': 'POST'}
            )
            
            file_item = form['file']
            if file_item.file:
                filename = os.path.join(self.current_dir, file_item.filename)
                with open(filename, 'wb') as f:
                    f.write(file_item.file.read())
                
                response = {'success': True, 'filename': filename}
            else:
                response = {'success': False, 'error': 'No file uploaded'}
                
        except Exception as e:
            response = {'success': False, 'error': str(e)}
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
    
    def execute_command(self, command):
        try:
            if command.startswith('cd '):
                new_dir = command[3:].strip()
                if new_dir:
                    os.chdir(new_dir)
                    self.current_dir = os.getcwd()
                return f"Diretório alterado para: {self.current_dir}"
            
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                cwd=self.current_dir
            )
            
            stdout, stderr = process.communicate()
            result = stdout.decode('utf-8', errors='ignore') + stderr.decode('utf-8', errors='ignore')
            return result.strip() or "Comando executado (sem output)"
            
        except Exception as e:
            return f"Erro: {str(e)}"
    
    def serve_static_file(self, path):
        # Implementar se necessário para arquivos estáticos
        self.send_error(404)

class TerminalPanel:
    def __init__(self):
        self.server = None
        self.web_thread = None
        self.running = False
        
    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_banner(self):
        banner = f"""
{Fore.CYAN}
╔══════════════════════════════════════════════════════════════╗
║{Fore.MAGENTA}          🎯 SHELL REVERSO - TERMINAL WEB{Fore.CYAN}               ║
║                                                              ║
║{Fore.YELLOW}    IP: {SERVER_IP:<15} Porta: {WEB_PORT:<10}{Fore.CYAN}            ║
║{Fore.YELLOW}    Senha Admin: {ADMIN_PASSWORD:<10}{Fore.CYAN}                    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
{Style.RESET_ALL}
"""
        print(banner)
    
    def start_web_server(self):
        try:
            self.server = HTTPServer((SERVER_IP, WEB_PORT), WebTerminalHandler)
            print(f"{Fore.GREEN}✅ Servidor web iniciado em http://{SERVER_IP}:{WEB_PORT}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}📋 Use a senha: {ADMIN_PASSWORD} para acessar o painel{Style.RESET_ALL}")
            self.running = True
            self.server.serve_forever()
        except Exception as e:
            print(f"{Fore.RED}❌ Erro ao iniciar servidor: {e}{Style.RESET_ALL}")
    
    def show_menu(self):
        while True:
            self.clear_screen()
            self.print_banner()
            
            print(f"{Fore.CYAN}╔══════════════════════════════════════════════════════════════╗")
            print(f"║{Fore.WHITE}                       MENU PRINCIPAL{Fore.CYAN}                       ║")
            print(f"╠══════════════════════════════════════════════════════════════╣")
            print(f"║{Fore.GREEN} 1.{Fore.WHITE} Iniciar Servidor Web (Porta {WEB_PORT}){Fore.CYAN}                  ║")
            print(f"║{Fore.GREEN} 2.{Fore.WHITE} Configurar IP/Porta{Fore.CYAN}                               ║")
            print(f"║{Fore.GREEN} 3.{Fore.WHITE} Testar Conexão{Fore.CYAN}                                    ║")
            print(f"║{Fore.GREEN} 4.{Fore.WHITE} Sair{Fore.CYAN}                                              ║")
            print(f"╚══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}")
            
            choice = input(f"\n{Fore.YELLOW}➤ Selecione uma opção: {Style.RESET_ALL}").strip()
            
            if choice == '1':
                self.start_server()
            elif choice == '2':
                self.configure_settings()
            elif choice == '3':
                self.test_connection()
            elif choice == '4':
                self.clean_exit()
                break
            else:
                print(f"{Fore.RED}❌ Opção inválida!{Style.RESET_ALL}")
                time.sleep(1)
    
    def start_server(self):
        if self.web_thread and self.web_thread.is_alive():
            print(f"{Fore.YELLOW}⚠️  Servidor já está em execução!{Style.RESET_ALL}")
            time.sleep(2)
            return
        
        self.web_thread = threading.Thread(target=self.start_web_server, daemon=True)
        self.web_thread.start()
        
        print(f"{Fore.GREEN}🚀 Iniciando servidor...{Style.RESET_ALL}")
        time.sleep(2)
        
        print(f"\n{Fore.CYAN}╔══════════════════════════════════════════════════════════════╗")
        print(f"║{Fore.WHITE}                 SERVIDOR EM EXECUÇÃO{Fore.CYAN}                     ║")
        print(f"╠══════════════════════════════════════════════════════════════╣")
        print(f"║{Fore.YELLOW} URL: {Fore.WHITE}http://{SERVER_IP}:{WEB_PORT}{Fore.CYAN}                          ║")
        print(f"║{Fore.YELLOW} Senha: {Fore.WHITE}{ADMIN_PASSWORD}{Fore.CYAN}                                   ║")
        print(f"║{Fore.YELLOW} Pressione Enter para voltar ao menu{Fore.CYAN}                   ║")
        print(f"╚══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}")
        input()
    
    def configure_settings(self):
        global SERVER_IP, WEB_PORT, ADMIN_PASSWORD
        
        self.clear_screen()
        print(f"{Fore.CYAN}╔══════════════════════════════════════════════════════════════╗")
        print(f"║{Fore.WHITE}                   CONFIGURAÇÕES{Fore.CYAN}                            ║")
        print(f"╠══════════════════════════════════════════════════════════════╣")
        
        print(f"║{Fore.YELLOW} IP atual: {Fore.WHITE}{SERVER_IP}{Fore.CYAN}                                      ║")
        new_ip = input(f"║{Fore.GREEN} Novo IP (Enter para manter): {Style.RESET_ALL}").strip()
        if new_ip:
            SERVER_IP = new_ip
        
        print(f"║{Fore.YELLOW} Porta atual: {Fore.WHITE}{WEB_PORT}{Fore.CYAN}                                   ║")
        new_port = input(f"║{Fore.GREEN} Nova Porta (Enter para manter): {Style.RESET_ALL}").strip()
        if new_port and new_port.isdigit():
            WEB_PORT = int(new_port)
        
        print(f"║{Fore.YELLOW} Senha atual: {Fore.WHITE}{ADMIN_PASSWORD}{Fore.CYAN}                               ║")
        new_pass = input(f"║{Fore.GREEN} Nova Senha (Enter para manter): {Style.RESET_ALL}").strip()
        if new_pass:
            ADMIN_PASSWORD = new_pass
        
        print(f"{Fore.CYAN}╚══════════════════════════════════════════════════════════════╝")
        print(f"{Fore.GREEN}✅ Configurações atualizadas!{Style.RESET_ALL}")
        time.sleep(2)
    
    def test_connection(self):
        print(f"{Fore.CYAN}🧪 Testando conexão...{Style.RESET_ALL}")
        time.sleep(1)
        
        try:
            # Testar se a porta está disponível
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((SERVER_IP, WEB_PORT))
            sock.close()
            
            if result == 0:
                print(f"{Fore.RED}❌ Porta {WEB_PORT} já está em uso!{Style.RESET_ALL}")
            else:
                print(f"{Fore.GREEN}✅ Porta {WEB_PORT} disponível{Style.RESET_ALL}")
                
        except Exception as e:
            print(f"{Fore.RED}❌ Erro no teste: {e}{Style.RESET_ALL}")
        
        time.sleep(2)
    
    def clean_exit(self):
        print(f"{Fore.YELLOW}🔄 Encerrando...{Style.RESET_ALL}")
        if self.server:
            self.server.shutdown()
        time.sleep(1)

def main():
    try:
        panel = TerminalPanel()
        panel.show_menu()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}👋 Encerrado pelo usuário{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}💥 Erro crítico: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
