document.addEventListener('DOMContentLoaded', function() {
    // Sistema de abas
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabId = button.getAttribute('data-tab');
            
            // Ativar aba
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabPanes.forEach(pane => pane.classList.remove('active'));
            
            button.classList.add('active');
            document.getElementById(tabId).classList.add('active');
            
            // Carregar arquivos se for a aba de explorador
            if (tabId === 'files') {
                loadFiles();
            }
        });
    });
    
    // Login form
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            const password = formData.get('password');
            
            fetch('/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `password=${encodeURIComponent(password)}`
            })
            .then(response => response.json())
            .then(data => {
                const messageEl = document.getElementById('loginMessage');
                if (data.success) {
                    messageEl.textContent = 'Login realizado com sucesso!';
                    messageEl.className = 'message success';
                    setTimeout(() => {
                        window.location.href = '/';
                    }, 1000);
                } else {
                    messageEl.textContent = data.error || 'Erro no login';
                    messageEl.className = 'message error';
                }
            })
            .catch(error => {
                document.getElementById('loginMessage').textContent = 'Erro de conexão';
                document.getElementById('loginMessage').className = 'message error';
            });
        });
    }
    
    // Logout
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function() {
            document.cookie = 'auth=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
            window.location.href = '/login';
        });
    }
    
    // Terminal functionality
    const terminalOutput = document.getElementById('terminalOutput');
    const commandInput = document.getElementById('commandInput');
    
    if (commandInput) {
        commandInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                const command = this.value.trim();
                if (command) {
                    // Adicionar comando ao output
                    addToTerminal(`$ ${command}\n`);
                    
                    // Enviar comando para o servidor
                    fetch('/command', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ command: command })
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            addToTerminal(data.output);
                        } else {
                            addToTerminal(`Erro: ${data.output}`);
                        }
                    })
                    .catch(error => {
                        addToTerminal(`Erro de conexão: ${error}`);
                    });
                    
                    // Limpar input
                    this.value = '';
                }
            }
        });
        
        // Comandos rápidos
        document.querySelectorAll('.quick-commands button').forEach(button => {
            button.addEventListener('click', function() {
                const command = this.getAttribute('data-command');
                commandInput.value = command;
                commandInput.focus();
            });
        });
    }
    
    function addToTerminal(text) {
        terminalOutput.textContent += text;
        terminalOutput.scrollTop = terminalOutput.scrollHeight;
    }
    
    // File explorer functionality
    function loadFiles(path = '') {
        const fileList = document.getElementById('fileList');
        const currentPath = document.getElementById('currentPath');
        
        fileList.innerHTML = '<div class="loading">Carregando...</div>';
        
        fetch(`/files/${path}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                fileList.innerHTML = `<div class="message error">${data.error}</div>`;
                return;
            }
            
            currentPath.textContent = data.current_path || '/';
            
            let html = '';
            
            // Diretórios primeiro
            if (data.directories && data.directories.length > 0) {
                data.directories.forEach(dir => {
                    html += `
                        <div class="dir-item" data-path="${dir.path}">
                            <span>📁 ${dir.name}</span>
                            <span>&gt;</span>
                        </div>
                    `;
                });
            }
            
            // Arquivos
            if (data.files && data.files.length > 0) {
                data.files.forEach(file => {
                    const size = formatFileSize(file.size);
                    html += `
                        <div class="file-item" data-path="${file.path}">
                            <span>📄 ${file.name}</span>
                            <span>${size}</span>
                        </div>
                    `;
                });
            }
            
            if (html === '') {
                html = '<div class="message">Nenhum arquivo ou diretório encontrado</div>';
            }
            
            fileList.innerHTML = html;
            
            // Adicionar eventos aos itens
            document.querySelectorAll('.dir-item').forEach(item => {
                item.addEventListener('click', function() {
                    const path = this.getAttribute('data-path');
                    loadFiles(path);
                });
            });
            
            document.querySelectorAll('.file-item').forEach(item => {
                item.addEventListener('click', function() {
                    // Selecionar/deselecionar arquivo
                    const isSelected = this.classList.contains('selected');
                    document.querySelectorAll('.file-item').forEach(i => i.classList.remove('selected'));
                    
                    if (!isSelected) {
                        this.classList.add('selected');
                        document.getElementById('downloadBtn').disabled = false;
                    } else {
                        document.getElementById('downloadBtn').disabled = true;
                    }
                });
            });
            
            // Botão de download
            document.getElementById('downloadBtn').addEventListener('click', function() {
                const selected = document.querySelector('.file-item.selected');
                if (selected) {
                    const filePath = selected.getAttribute('data-path');
                    window.open(`/download/${filePath}`, '_blank');
                }
            });
        })
        .catch(error => {
            fileList.innerHTML = `<div class="message error">Erro ao carregar arquivos: ${error}</div>`;
        });
    }
    
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    // Upload functionality
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const fileInput = document.getElementById('fileInput');
            if (!fileInput.files.length) {
                showUploadMessage('Nenhum arquivo selecionado', 'error');
                return;
            }
            
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            
            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showUploadMessage(data.message, 'success');
                    fileInput.value = '';
                } else {
                    showUploadMessage(data.error, 'error');
                }
            })
            .catch(error => {
                showUploadMessage('Erro no upload: ' + error, 'error');
            });
        });
    }
    
    function showUploadMessage(message, type) {
        const messageEl = document.getElementById('uploadMessage');
        messageEl.textContent = message;
        messageEl.className = `message ${type}`;
        
        setTimeout(() => {
            messageEl.textContent = '';
            messageEl.className = 'message';
        }, 3000);
    }
});
