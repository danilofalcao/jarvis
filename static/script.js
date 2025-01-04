// Global Variables
let currentWorkspace = null;
let currentModel = 'deepseek';
let pendingChanges = null;
let socket = null;

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    initializeWebSocket();
    initializeModelSelection();
    loadWorkspaceHistory();
    initializeKeyboardShortcuts();
});

// WebSocket Setup
function initializeWebSocket() {
    socket = io();
    
    // Status updates
    socket.on('status', (data) => {
        updateStatus(data.message, data.step);
    });
    
    // Progress updates
    socket.on('progress', (data) => {
        updateProgress(data.message, data.tokens);
    });
    
    // Connection status
    socket.on('connect', () => {
        console.log('Connected to server');
        updateConnectionStatus(true);
    });
    
    socket.on('disconnect', () => {
        console.log('Disconnected from server');
        updateConnectionStatus(false);
    });
}

// UI Update Functions
function updateStatus(message, step) {
    const statusElement = document.getElementById('statusMessage') || createStatusElement();
    statusElement.textContent = message;
    
    // Update progress bar if exists
    const progressBar = document.getElementById('progressBar');
    if (progressBar) {
        progressBar.style.width = `${(step / 5) * 100}%`;
    }
    
    // Show error styling for negative steps
    if (step < 0) {
        statusElement.classList.add('error');
    } else {
        statusElement.classList.remove('error');
    }
}

function updateProgress(message, tokens) {
    const progressElement = document.getElementById('progressMessage') || createProgressElement();
    progressElement.textContent = message;
}

function updateConnectionStatus(connected) {
    const statusIndicator = document.getElementById('connectionStatus') || createConnectionIndicator();
    statusIndicator.className = `connection-status ${connected ? 'connected' : 'disconnected'}`;
    statusIndicator.title = connected ? 'Connected to server' : 'Disconnected from server';
}

// UI Element Creation
function createStatusElement() {
    const container = document.createElement('div');
    container.id = 'statusContainer';
    container.className = 'status-container fixed bottom-4 right-4 p-4 bg-gray-800 rounded-lg shadow-lg z-50';
    
    const message = document.createElement('div');
    message.id = 'statusMessage';
    message.className = 'text-white';
    
    const progress = document.createElement('div');
    progress.className = 'mt-2 h-2 bg-gray-700 rounded-full overflow-hidden';
    
    const bar = document.createElement('div');
    bar.id = 'progressBar';
    bar.className = 'h-full bg-blue-500 transition-all duration-300';
    bar.style.width = '0%';
    
    progress.appendChild(bar);
    container.appendChild(message);
    container.appendChild(progress);
    document.body.appendChild(container);
    
    return message;
}

function createProgressElement() {
    const container = document.createElement('div');
    container.id = 'progressContainer';
    container.className = 'progress-container fixed bottom-24 right-4 p-4 bg-gray-800 rounded-lg shadow-lg z-50';
    
    const message = document.createElement('div');
    message.id = 'progressMessage';
    message.className = 'text-white';
    
    container.appendChild(message);
    document.body.appendChild(container);
    
    return message;
}

function createConnectionIndicator() {
    const indicator = document.createElement('div');
    indicator.id = 'connectionStatus';
    indicator.className = 'connection-status';
    indicator.style.cssText = `
        position: fixed;
        top: 1rem;
        right: 1rem;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        z-index: 100;
    `;
    
    const style = document.createElement('style');
    style.textContent = `
        .connection-status.connected { background-color: #10B981; }
        .connection-status.disconnected { background-color: #EF4444; }
    `;
    document.head.appendChild(style);
    document.body.appendChild(indicator);
    
    return indicator;
}

// Model Selection
function initializeModelSelection() {
    const modelSelect = document.getElementById('modelSelect');
    modelSelect.addEventListener('change', (e) => {
        currentModel = e.target.value;
    });
    loadAvailableModels();
}

async function loadAvailableModels() {
    try {
        const response = await fetch('/models');
        const data = await response.json();

        if (data.status === 'success') {
            const modelSelect = document.getElementById('modelSelect');
            modelSelect.innerHTML = '';

            data.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.id;
                option.textContent = model.name;
                modelSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading models:', error);
    }
}

// Mode Switching
function setMode(mode) {
    const codeMode = document.getElementById('codeMode');
    const chatMode = document.getElementById('chatMode');
    const codeModeBtn = document.querySelector('[onclick="setMode(\'code\')"]');
    const chatModeBtn = document.querySelector('[onclick="setMode(\'chat\')"]');

    if (mode === 'code') {
        codeMode.classList.remove('hidden');
        chatMode.classList.add('hidden');
        codeModeBtn.classList.add('active');
        chatModeBtn.classList.remove('active');
    } else {
        chatMode.classList.remove('hidden');
        codeMode.classList.add('hidden');
        chatModeBtn.classList.add('active');
        codeModeBtn.classList.remove('active');
    }
}

// Workspace Management
async function createWorkspace() {
    showLoading();
    try {
        const response = await fetch('/workspace/create', { method: 'POST' });
        const data = await response.json();

        if (data.status === 'success') {
            currentWorkspace = data.workspace_dir;
            updateWorkspaceInfo(data.workspace_id);
            updateWorkspaceTree(data.structure);
            await loadWorkspaceHistory();
        } else {
            showError('Failed to create workspace');
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Failed to create workspace: ' + error.message);
    } finally {
        hideLoading();
    }
}

async function loadWorkspaceHistory() {
    try {
        const response = await fetch('/workspace/history');
        const data = await response.json();

        if (data.status === 'success') {
            const historyList = document.getElementById('workspaceHistory');
            historyList.innerHTML = '';

            data.history.forEach(workspace => {
                const workspaceDiv = document.createElement('div');
                workspaceDiv.className = 'workspace-item flex items-center justify-between p-3 hover:bg-gray-700 rounded-lg cursor-pointer transition-colors';
                
                const infoDiv = document.createElement('div');
                infoDiv.className = 'flex-1';
                infoDiv.onclick = () => selectWorkspace(workspace.path);
                
                const nameSpan = document.createElement('span');
                nameSpan.className = 'font-medium';
                nameSpan.textContent = workspace.id;
                
                const statsSpan = document.createElement('span');
                statsSpan.className = 'text-sm text-gray-400 block';
                statsSpan.textContent = `${workspace.file_count} files`;
                
                infoDiv.appendChild(nameSpan);
                infoDiv.appendChild(statsSpan);
                
                const actionsDiv = document.createElement('div');
                actionsDiv.className = 'flex items-center gap-2';
                
                const renameBtn = document.createElement('button');
                renameBtn.className = 'p-2 text-blue-400 hover:text-blue-300 transition-colors';
                renameBtn.innerHTML = '<i class="fas fa-edit"></i>';
                renameBtn.onclick = (e) => {
                    e.stopPropagation();
                    const newName = prompt('Enter new workspace name:', workspace.id);
                    if (newName && newName !== workspace.id) {
                        renameWorkspace(workspace.id, newName);
                    }
                };
                
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'p-2 text-red-400 hover:text-red-300 transition-colors';
                deleteBtn.innerHTML = '<i class="fas fa-trash"></i>';
                deleteBtn.onclick = (e) => {
                    e.stopPropagation();
                    if (confirm('Are you sure you want to delete this workspace?')) {
                        deleteWorkspace(workspace.id);
                    }
                };
                
                actionsDiv.appendChild(renameBtn);
                actionsDiv.appendChild(deleteBtn);
                workspaceDiv.appendChild(infoDiv);
                workspaceDiv.appendChild(actionsDiv);
                historyList.appendChild(workspaceDiv);
            });
        }
    } catch (error) {
        console.error('Error loading history:', error);
        showError('Failed to load workspace history');
    }
}

async function deleteWorkspace(workspaceId) {
    try {
        const response = await fetch('/workspace/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ workspace_id: workspaceId })
        });

        const data = await response.json();
        
        if (data.status === 'success') {
            // If the deleted workspace was the current one, clear it
            if (currentWorkspace && currentWorkspace.endsWith(workspaceId)) {
                currentWorkspace = null;
                document.getElementById('currentWorkspaceInfo').classList.add('hidden');
                document.getElementById('workspaceTree').innerHTML = '';
            }
            
            // Reload the workspace history
            loadWorkspaceHistory();
        } else {
            showError(data.message || 'Failed to delete workspace');
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Failed to delete workspace: ' + error.message);
    }
}

async function renameWorkspace(workspaceId, newName) {
    try {
        const response = await fetch('/workspace/rename', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                workspace_id: workspaceId,
                new_name: newName
            })
        });

        const data = await response.json();
        
        if (data.status === 'success') {
            // If the renamed workspace was the current one, update it
            if (currentWorkspace && currentWorkspace.endsWith(workspaceId)) {
                currentWorkspace = data.new_path;
                updateWorkspaceInfo(newName);
            }
            
            // Reload the workspace history
            loadWorkspaceHistory();
        } else {
            showError(data.message || 'Failed to rename workspace');
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Failed to rename workspace: ' + error.message);
    }
}

function createWorkspaceHistoryItem(workspace) {
    const workspaceDiv = document.createElement('div');
    workspaceDiv.className = 'flex items-center justify-between p-3 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors cursor-pointer';
    workspaceDiv.onclick = () => selectWorkspace(workspace.path);

    const info = document.createElement('div');
    info.className = 'flex-1';
    
    const name = document.createElement('div');
    name.className = 'font-medium truncate';
    name.textContent = workspace.id;
    
    const date = document.createElement('div');
    date.className = 'text-sm text-gray-400';
    date.textContent = new Date(workspace.created_at).toLocaleString();
    
    const controls = document.createElement('div');
    controls.className = 'flex items-center gap-2 ml-3';
    
    const fileCount = document.createElement('span');
    fileCount.className = 'text-sm text-gray-400';
    fileCount.textContent = `${workspace.file_count} files`;
    
    const renameBtn = createButton('fas fa-edit', 'text-gray-400 hover:text-blue-400', () => {
        const newName = prompt('Enter new workspace name:', workspace.id);
        if (newName && newName !== workspace.id) {
            renameWorkspace(workspace.id, newName);
        }
    });
    
    const deleteBtn = createButton('fas fa-trash', 'text-gray-400 hover:text-red-400', () => {
        if (confirm('Are you sure you want to delete this workspace?')) {
            deleteWorkspace(workspace.id);
        }
    });

    info.appendChild(name);
    info.appendChild(date);
    controls.appendChild(fileCount);
    controls.appendChild(renameBtn);
    controls.appendChild(deleteBtn);
    workspaceDiv.appendChild(info);
    workspaceDiv.appendChild(controls);

    return workspaceDiv;
}

function createButton(iconClass, buttonClass, onClick) {
    const button = document.createElement('button');
    button.className = buttonClass + ' transition-colors';
    button.innerHTML = `<i class="${iconClass}"></i>`;
    button.onclick = (e) => {
        e.stopPropagation();
        onClick();
    };
    return button;
}

async function selectWorkspace(path) {
    currentWorkspace = path;
    updateWorkspaceInfo(path.split('/').pop());
    
    try {
        const response = await fetch('/workspace/structure', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ workspace_dir: path })
        });
        
        const data = await response.json();
        if (data.status === 'success') {
            updateWorkspaceTree(data.structure);
        } else {
            showError('Failed to load workspace structure');
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Failed to load workspace structure: ' + error.message);
    }
}

function updateWorkspaceInfo(id) {
    const info = document.getElementById('currentWorkspaceInfo');
    const name = document.getElementById('currentWorkspaceName');
    info.classList.remove('hidden');
    name.textContent = id;
}

// File Tree Management
function updateWorkspaceTree(structure) {
    const treeContainer = document.getElementById('workspaceTree');
    treeContainer.innerHTML = '';
    buildTree(structure, treeContainer);
}

function buildTree(items, container, path = '') {
    // Sort items by type (directories first) and name
    const sortedItems = items.sort((a, b) => {
        if (a.type !== b.type) {
            return a.type === 'directory' ? -1 : 1;
        }
        return a.name.localeCompare(b.name);
    });

    // Get unique top-level items for current path
    const currentLevelItems = sortedItems.filter(item => {
        const relativePath = item.path.replace(path ? path + '/' : '', '');
        return !relativePath.includes('/');
    });

    // Process directories first
    currentLevelItems.forEach(item => {
        const itemDiv = createTreeItem(item);
        container.appendChild(itemDiv);

        if (item.type === 'directory') {
            const contentDiv = document.createElement('div');
            contentDiv.className = 'directory-content';
            contentDiv.style.display = 'none';

            // Get children for this directory
            const children = sortedItems.filter(child => 
                child.path.startsWith(item.path + '/') &&
                child.path !== item.path
            );

            if (children.length > 0) {
                buildTree(children, contentDiv, item.path);
                container.appendChild(contentDiv);

                itemDiv.onclick = (e) => {
                    e.stopPropagation();
                    const icon = itemDiv.querySelector('i');
                    if (contentDiv.style.display === 'none') {
                        contentDiv.style.display = 'block';
                        icon.className = 'fas fa-folder-open';
                    } else {
                        contentDiv.style.display = 'none';
                        icon.className = 'fas fa-folder';
                    }
                };
            }
        }
    });
}

function createTreeItem(item) {
    const itemDiv = document.createElement('div');
    itemDiv.className = 'file-tree-item';
    
    const icon = document.createElement('i');
    icon.className = item.type === 'directory' ? 'fas fa-folder' : getFileIcon(item.name);
    
    const name = document.createElement('span');
    name.textContent = item.name;
    name.className = 'flex-1 truncate';
    
    itemDiv.appendChild(icon);
    itemDiv.appendChild(name);
    
    if (item.type === 'file') {
        itemDiv.onclick = (e) => {
            e.stopPropagation();
            showFileContent(item.path);
        };
        // Add hover effect for files
        itemDiv.classList.add('hover:bg-gray-700', 'cursor-pointer');
    }
    
    return itemDiv;
}

function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const iconMap = {
        'js': 'fab fa-js text-yellow-400',
        'py': 'fab fa-python text-blue-400',
        'html': 'fab fa-html5 text-orange-500',
        'css': 'fab fa-css3-alt text-blue-500',
        'json': 'fas fa-code text-green-400',
        'md': 'fas fa-file-alt text-purple-400',
        'txt': 'fas fa-file-alt text-gray-400',
        'yml': 'fas fa-file-code text-red-400',
        'yaml': 'fas fa-file-code text-red-400'
    };
    return iconMap[ext] || 'fas fa-file text-blue-400';
}

// Code Generation
async function processPrompt() {
    if (!validateWorkspace()) return;

    const promptInput = document.getElementById('promptInput');
    const prompt = promptInput.value.trim();
    
    if (!prompt) {
        showError('Please enter a prompt');
        return;
    }

    // Collect attachments
    const attachments = [];
    document.querySelectorAll('#codeAttachments > div').forEach(div => {
        attachments.push({
            name: div.querySelector('span').textContent,
            content: div.dataset.content // Get the stored file content
        });
    });

    showLoading();
    try {
        const response = await fetch('/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt: prompt,
                workspace_dir: currentWorkspace,
                model_id: document.getElementById('modelSelect').value,
                attachments: attachments
            })
        });

        const data = await response.json();
        
        if (data.status === 'error') {
            showError(data.message || 'No changes to apply');
            return;
        }

        currentWorkspace = data.workspace_dir;
        if (data.structure) {
            updateWorkspaceTree(data.structure);
        }
        if (data.requires_approval) {
            showApprovalModal(data);
        }

    } catch (error) {
        console.error('Error:', error);
        showError('Failed to process prompt: ' + error.message);
    } finally {
        hideLoading();
    }
}

// Chat Functionality
async function sendChatMessage() {
    if (!validateWorkspace()) return;

    const chatInput = document.getElementById('chatInput');
    const message = chatInput.value.trim();
    
    if (!message) {
        showError('Please enter a message');
        return;
    }

    // Collect attachments
    const attachments = [];
    document.querySelectorAll('#chatAttachments > div').forEach(div => {
        attachments.push({
            name: div.querySelector('span').textContent,
            content: div.dataset.content // Get the stored file content
        });
    });

    // Append user message first
    appendChatMessage(message, 'user');
    chatInput.value = '';

    // Show loading indicator
    const loadingMessage = appendChatMessage('<i class="fas fa-spinner fa-spin"></i> Thinking...', 'assistant', true);
    
    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt: message,
                workspace_dir: currentWorkspace,
                model_id: document.getElementById('modelSelect').value,
                attachments: attachments
            })
        });

        const data = await response.json();
        
        // Remove loading message
        loadingMessage.remove();

        if (data.status === 'success') {
            const formattedResponse = formatChatResponse(data.response);
            appendChatMessage(formattedResponse, 'assistant', true);
        } else {
            appendErrorMessage(data.message || 'Failed to get response');
        }
    } catch (error) {
        console.error('Error:', error);
        loadingMessage.remove();
        appendErrorMessage('Error: ' + error.message);
    }
}

function clearChatHistory() {
    if (confirm('Are you sure you want to clear the chat history?')) {
        const chatHistory = document.getElementById('chatHistory');
        if (chatHistory) {
            chatHistory.innerHTML = '';
            // Add a system message to indicate the chat was cleared
            appendChatMessage('Chat history has been cleared.', 'assistant', true);
        }
    }
}

function formatChatResponse(text) {
    // Configure marked options
    marked.setOptions({
        breaks: true,  // Convert line breaks
        gfm: true,     // Use GitHub Flavored Markdown
        headerIds: false,
        mangle: false
    });

    // Split text into code blocks and regular text
    const parts = text.split('```');
    const formattedParts = [];
    
    for (let i = 0; i < parts.length; i++) {
        if (i % 2 === 0) {
            // Regular text: convert markdown to HTML
            let regularText = parts[i].trim();
            if (regularText) {
                regularText = marked.parse(regularText);
                regularText = regularText.replace(/\s+$/, '');
                formattedParts.push(regularText);
            }
        } else {
            // Code block: preserve original formatting
            let code = parts[i];
            let language = '';
            
            // Check if language is specified
            const firstLineBreak = code.indexOf('\n');
            if (firstLineBreak !== -1) {
                language = code.substring(0, firstLineBreak).trim();
                code = code.substring(firstLineBreak + 1);
            }
            
            // Clean up code: remove extra newlines and spaces
            code = code.trim()
                .replace(/\n\s*\n/g, '\n') // Remove empty lines
                .replace(/[ \t]+$/gm, '') // Remove trailing spaces from each line
                .replace(/^\s+|\s+$/g, ''); // Remove leading/trailing spaces
            
            // Preserve original formatting
            code = code
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');

            formattedParts.push(`<pre class="bg-gray-800 p-4 rounded-lg overflow-x-auto font-mono text-sm"><code class="language-${language}">${code}</code></pre>`);
        }
    }
    
    // Join parts and clean up
    let result = formattedParts.join('');
    
    // Clean up any remaining unwanted tags or spaces
    result = result.replace(/\s*<br\s*\/?>\s*<br\s*\/?>\s*/g, '<br>');
    result = result.replace(/\s*<br\s*\/?>\s*<\/p>/g, '</p>');
    result = result.replace(/<p>\s*<br\s*\/?>\s*/g, '<p>');
    result = result.replace(/\s+$/g, '');
    result = result.replace(/<\/pre>\s+<p>/g, '</pre><p>');
    result = result.replace(/<\/p>\s+<pre>/g, '</p><pre>');
    
    return result;
}

function appendChatMessage(content, type, isHtml = false) {
    const chatHistory = document.getElementById('chatHistory');
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${type} mb-4 p-4 rounded ${type === 'user' ? 'bg-blue-900' : 'bg-gray-800'}`;
    
    if (isHtml) {
        messageDiv.innerHTML = content;
    } else {
        messageDiv.textContent = content;
    }
    
    chatHistory.appendChild(messageDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    return messageDiv;
}

function appendErrorMessage(message) {
    appendChatMessage(`<span class="text-red-500">${message}</span>`, 'assistant', true);
}

// Modal Management
function showApprovalModal(data) {
    const modal = document.getElementById('approvalModal');
    const preview = document.getElementById('changesPreview');
    const footer = modal.querySelector('.modal-footer > div');
    
    // Clear previous content
    preview.innerHTML = '';
    footer.innerHTML = '';
    
    // Show modal immediately
    modal.classList.remove('hidden');
    
    // Process and display each operation immediately
    data.operations.forEach(operation => {
        const container = document.createElement('div');
        container.className = 'mb-8 p-4 bg-gray-900 rounded-lg';
        
        appendOperationHeader(container, operation);
        appendOperationContent(container, operation);
        preview.appendChild(container);
    });
    
    // Add modal buttons
    appendModalButtons(footer, data.operations);
    
    // Initialize any CodeMirror instances
    preview.querySelectorAll('pre code').forEach(block => {
        const mode = block.className.replace('language-', '');
        CodeMirror.fromTextArea(block, {
            mode: mode,
            theme: 'monokai',
            readOnly: true,
            lineNumbers: true,
            matchBrackets: true,
            styleActiveLine: true,
            scrollbarStyle: 'overlay',
            viewportMargin: Infinity,
            lineWrapping: true
        });
    });
}

function appendOperationContent(container, operation) {
    if (operation.type === 'file_edit') {
        const diffContainer = document.createElement('div');
        diffContainer.className = 'mt-4 bg-gray-800 rounded p-4 overflow-x-auto';
        appendDiffView(diffContainer, operation.diff);
        container.appendChild(diffContainer);
    } else if (operation.type === 'file_create') {
        const codeContainer = document.createElement('div');
        codeContainer.className = 'mt-4 bg-gray-800 rounded p-4';
        appendCodeEditor(codeContainer, operation);
        container.appendChild(codeContainer);
    }
}

function appendDiffView(container, diff) {
    const pre = document.createElement('pre');
    const code = document.createElement('textarea');
    code.className = 'language-diff';
    code.value = diff;
    pre.appendChild(code);
    container.appendChild(pre);
}

function appendCodeEditor(container, operation) {
    const pre = document.createElement('pre');
    const code = document.createElement('textarea');
    code.className = `language-${getLanguageMode(operation.path)}`;
    code.value = operation.content;
    pre.appendChild(code);
    container.appendChild(pre);
}

function appendOperationHeader(container, operation) {
    const headerDiv = document.createElement('div');
    headerDiv.className = 'flex items-center gap-3 mb-4';

    const icon = document.createElement('i');
    icon.className = 'fas fa-2x ' + getOperationIcon(operation.type);

    const titleDiv = document.createElement('div');
    const title = document.createElement('h3');
    title.className = 'text-lg font-medium';
    title.textContent = formatOperationTitle(operation);

    const subtitle = document.createElement('p');
    subtitle.className = 'text-sm text-gray-400';
    subtitle.textContent = operation.explanation || '';

    titleDiv.appendChild(title);
    titleDiv.appendChild(subtitle);
    headerDiv.appendChild(icon);
    headerDiv.appendChild(titleDiv);
    container.appendChild(headerDiv);
}

function getOperationIcon(type) {
    const icons = {
        'create_file': 'fa-file-plus text-green-500',
        'edit_file': 'fa-file-edit text-blue-500',
        'remove_file': 'fa-file-minus text-red-500'
    };
    return icons[type] || 'fa-file text-gray-500';
}

function formatOperationTitle(operation) {
    return `${operation.type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}: ${operation.path}`;
}

function appendModalButtons(footer, operations) {
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn btn-secondary';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.onclick = hideModal;

    const applyBtn = document.createElement('button');
    applyBtn.className = 'btn btn-primary';
    applyBtn.innerHTML = '<i class="fas fa-check mr-2"></i>Apply Changes';
    applyBtn.onclick = () => applyChanges(operations);

    footer.appendChild(cancelBtn);
    footer.appendChild(applyBtn);
}

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Utility Functions
function showLoading(message = 'Processing...') {
    const loadingOverlay = document.getElementById('loadingOverlay');
    const loadingText = document.getElementById('loadingText');
    loadingOverlay.classList.remove('hidden');
    loadingText.textContent = message;
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.add('hidden');
}

function hideModal() {
    document.getElementById('approvalModal').classList.add('hidden');
    
    // Clear status message
    const statusContainer = document.getElementById('statusContainer');
    if (statusContainer) {
        statusContainer.remove();
    }
    
    // Clear progress message
    const progressContainer = document.getElementById('progressContainer');
    if (progressContainer) {
        progressContainer.remove();
    }
}

function showError(message) {
    alert(message);
}

function validateWorkspace() {
    if (!currentWorkspace) {
        showError('Please create or select a workspace first');
        return false;
    }
    return true;
}

function getLanguageMode(filePath) {
    const ext = filePath.split('.').pop().toLowerCase();
    const modeMap = {
        'js': 'javascript',
        'py': 'python',
        'html': 'xml',
        'css': 'css',
        'json': 'javascript',
        'md': 'markdown',
        'yaml': 'yaml',
        'yml': 'yaml'
    };
    return modeMap[ext] || 'plaintext';
}

async function applyChanges(operations) {
    showLoading('Applying changes...');
    hideModal();

    try {
        const response = await fetch('/apply_changes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                workspace_dir: currentWorkspace,
                operations: operations
            })
        });

        const data = await response.json();
        
        if (data.status === 'success') {
            if (data.structure) {
                updateWorkspaceTree(data.structure);
            }
        } else {
            showError(data.message || 'Failed to apply changes');
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Failed to apply changes: ' + error.message);
    } finally {
        hideLoading();
    }
}

// File Viewing
async function showFileContent(filePath) {
    const modal = document.getElementById('approvalModal');
    const preview = document.getElementById('changesPreview');
    const modalTitle = modal.querySelector('.modal-header h2');
    const modalFooter = modal.querySelector('.modal-footer .flex');

    modalTitle.textContent = 'File Content';
    preview.innerHTML = '<div class="text-center p-4"><i class="fas fa-spinner fa-spin mr-2"></i>Loading file...</div>';
    modalFooter.innerHTML = '';
    modal.classList.remove('hidden');

    try {
        const response = await fetch('/workspace/file', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                workspace_dir: currentWorkspace,
                file_path: filePath
            })
        });

        const data = await response.json();
        
        if (data.status === 'success') {
            preview.innerHTML = '';

            // File info header with size information
            const fileInfo = document.createElement('div');
            fileInfo.className = 'flex items-center gap-3 mb-6 p-4 bg-gray-700 rounded-lg';
            
            const fileSize = formatFileSize(data.file_size);
            const truncatedWarning = data.truncated 
                ? `<p class="text-yellow-400 text-sm mt-1">File is large (${fileSize}). Showing preview of first 1000 lines.</p>` 
                : `<p class="text-gray-400 text-sm mt-1">File size: ${fileSize}</p>`;
            
            fileInfo.innerHTML = `
                <i class="${getFileIcon(filePath)} text-xl"></i>
                <div>
                    <h3 class="text-lg font-medium">${filePath.split('/').pop()}</h3>
                    <p class="text-sm text-gray-400">${filePath}</p>
                    ${truncatedWarning}
                </div>
            `;
            preview.appendChild(fileInfo);

            // Code content
            const codeDiv = document.createElement('div');
            codeDiv.className = 'bg-gray-900 rounded-lg p-4 font-mono text-sm whitespace-pre overflow-x-auto';
            
            // Clean up the content
            let code = data.content.trim()
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
                
            // Get language for syntax highlighting
            const language = getLanguageMode(filePath);
            codeDiv.innerHTML = `<code class="language-${language}">${code}</code>`;
            preview.appendChild(codeDiv);

            // Add close button
            const closeBtn = document.createElement('button');
            closeBtn.className = 'btn btn-secondary';
            closeBtn.textContent = 'Close';
            closeBtn.onclick = hideModal;
            modalFooter.appendChild(closeBtn);
        } else {
            preview.innerHTML = '<div class="text-center text-red-500 p-4">Failed to load file content</div>';
        }
    } catch (error) {
        console.error('Error:', error);
        preview.innerHTML = `<div class="text-center text-red-500 p-4">Error loading file: ${error.message}</div>`;
    }
}

function formatFileSize(bytes) {
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;
    
    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex++;
    }
    
    return `${size.toFixed(1)} ${units[unitIndex]}`;
}

// Keyboard Shortcuts
function initializeKeyboardShortcuts() {
    // Code generation shortcut
    const promptInput = document.getElementById('promptInput');
    promptInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            processPrompt();
        }
    });

    // Chat shortcut
    const chatInput = document.getElementById('chatInput');
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            sendChatMessage();
        }
    });
}

// File attachment handling
async function handleFileAttachment(fileInput, attachmentsContainer) {
    const files = Array.from(fileInput.files);
    attachmentsContainer.innerHTML = '';
    
    for (const file of files) {
        try {
            const content = await extractFileContent(file);
            if (content) {
                addAttachmentToContainer(file.name, content, attachmentsContainer, getFileType(file));
            }
        } catch (error) {
            console.error('Error processing file:', error);
            showError(`Error processing ${file.name}: ${error.message}`);
        }
    }
}

async function extractFileContent(file) {
    const reader = new FileReader();

    // Helper function to wrap FileReader in a promise
    const readFile = (method) => {
        return new Promise((resolve, reject) => {
            reader.onerror = () => reject(new Error('Failed to read file'));
            reader.onload = () => resolve(reader.result);
            method.call(reader, file);
        });
    };

    try {
        switch (true) {
            // PDF Files
            case file.type === 'application/pdf':
                const arrayBuffer = await readFile(reader.readAsArrayBuffer);
                const pdf = await pdfjsLib.getDocument(new Uint8Array(arrayBuffer)).promise;
                let pdfText = '';
                for (let i = 1; i <= pdf.numPages; i++) {
                    const page = await pdf.getPage(i);
                    const textContent = await page.getTextContent();
                    pdfText += textContent.items.map(item => item.str).join(' ') + '\n';
                }
                return pdfText;

            // Word Documents
            case file.type.includes('word') || file.type.includes('openxmlformats-officedocument.wordprocessingml'):
                const docArrayBuffer = await readFile(reader.readAsArrayBuffer);
                const result = await mammoth.extractRawText({ arrayBuffer: docArrayBuffer });
                return result.value;

            // Excel Files
            case file.type.includes('excel') || file.type.includes('spreadsheetml'):
                const excelData = await readFile(reader.readAsArrayBuffer);
                const workbook = XLSX.read(excelData, { type: 'array' });
                let excelText = '';
                workbook.SheetNames.forEach(sheetName => {
                    const sheet = workbook.Sheets[sheetName];
                    excelText += `Sheet: ${sheetName}\n${XLSX.utils.sheet_to_string(sheet)}\n\n`;
                });
                return excelText;

            // Images (OCR)
            case file.type.startsWith('image/'):
                const imageUrl = await readFile(reader.readAsDataURL);
                const worker = await Tesseract.createWorker('eng');
                const { data: { text } } = await worker.recognize(imageUrl);
                await worker.terminate();
                return text;

            // Markdown (Enhanced)
            case file.name.endsWith('.md'):
                const mdContent = await readFile(reader.readAsText);
                const parsed = marked.parse(mdContent, {
                    gfm: true,
                    breaks: true,
                    headerIds: false
                });
                // Strip HTML tags for context
                return parsed.replace(/<[^>]*>/g, ' ');

            // Text and Code Files
            case file.type.startsWith('text/') || 
                 file.type === 'application/json' ||
                 file.name.match(/\.(txt|js|py|java|c|cpp|h|hpp|cs|html|css|json|yml|yaml|xml|sql|sh|bash|r|rb|php|go|rust|swift)$/i):
                return await readFile(reader.readAsText);

            // Default: Try as text
            default:
                if (file.size > 10 * 1024 * 1024) { // 10MB limit for unknown files
                    throw new Error('File too large for unknown type');
                }
                return await readFile(reader.readAsText);
        }
    } catch (error) {
        throw new Error(`Failed to process ${file.name}: ${error.message}`);
    }
}

function getFileType(file) {
    if (file.type === 'application/pdf') return 'pdf';
    if (file.type.includes('word')) return 'word';
    if (file.type.includes('excel')) return 'excel';
    if (file.type.startsWith('image/')) return 'image';
    if (file.name.endsWith('.md')) return 'markdown';
    return 'text';
}

function addAttachmentToContainer(fileName, content, container, type) {
    const fileDiv = document.createElement('div');
    fileDiv.className = 'flex items-center justify-between bg-gray-700 p-2 rounded mb-2';
    fileDiv.dataset.content = content;
    
    const iconMap = {
        'pdf': 'fa-file-pdf text-red-500',
        'word': 'fa-file-word text-blue-500',
        'excel': 'fa-file-excel text-green-500',
        'image': 'fa-file-image text-purple-500',
        'markdown': 'fa-file-alt text-blue-400',
        'text': 'fa-file-code text-blue-500'
    };
    
    const iconClass = iconMap[type] || 'fa-file text-gray-500';
    
    fileDiv.innerHTML = `
        <div class="flex items-center gap-2">
            <i class="fas ${iconClass}"></i>
            <span class="text-sm">${fileName}</span>
            <span class="text-xs text-gray-400">(${formatFileSize(new Blob([content]).size)})</span>
        </div>
        <div class="flex items-center gap-2">
            <button onclick="previewAttachment(this.parentElement.parentElement)" class="text-gray-400 hover:text-blue-500" title="Preview">
                <i class="fas fa-eye"></i>
            </button>
            <button onclick="this.parentElement.parentElement.remove()" class="text-gray-400 hover:text-red-500" title="Remove">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    container.appendChild(fileDiv);
}

function formatFileSize(bytes) {
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;
    
    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex++;
    }
    
    return `${size.toFixed(1)} ${units[unitIndex]}`;
}

function previewAttachment(attachmentDiv) {
    const fileName = attachmentDiv.querySelector('span').textContent;
    const content = attachmentDiv.dataset.content;
    
    const modal = document.getElementById('approvalModal');
    const preview = document.getElementById('changesPreview');
    const modalTitle = modal.querySelector('.modal-header h2');
    const footer = modal.querySelector('.modal-footer .flex');
    
    modalTitle.textContent = `Preview: ${fileName}`;
    preview.innerHTML = '';
    footer.innerHTML = '';
    
    const previewContent = document.createElement('div');
    previewContent.className = 'bg-gray-900 p-4 rounded-lg';
    
    if (fileName.endsWith('.pdf')) {
        // Format PDF content for readability
        const formattedContent = content
            .split('\n')
            .filter(line => line.trim())
            .join('\n\n');
        previewContent.innerHTML = `<pre class="whitespace-pre-wrap font-mono text-sm">${formattedContent}</pre>`;
    } else {
        // For text files, use CodeMirror
        const editorDiv = document.createElement('div');
        editorDiv.style.height = '500px';
        
        const textarea = document.createElement('textarea');
        textarea.value = content;
        previewContent.appendChild(textarea);
        
        CodeMirror.fromTextArea(textarea, {
            mode: getLanguageMode(fileName),
            theme: 'monokai',
            lineNumbers: true,
            readOnly: true,
            viewportMargin: Infinity
        });
    }
    
    preview.appendChild(previewContent);
    
    const closeBtn = document.createElement('button');
    closeBtn.className = 'btn btn-secondary';
    closeBtn.textContent = 'Close';
    closeBtn.onclick = hideModal;
    footer.appendChild(closeBtn);
    
    modal.classList.remove('hidden');
}

// Add event listeners for file inputs
document.getElementById('codeAttachment').addEventListener('change', function() {
    handleFileAttachment(this, document.getElementById('codeAttachments'));
});

document.getElementById('chatAttachment').addEventListener('change', function() {
    handleFileAttachment(this, document.getElementById('chatAttachments'));
}); 