import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, jsonify, send_from_directory
import os
from dotenv import load_dotenv
from openai import OpenAI
from anthropic import Anthropic
import json
import shutil
from pathlib import Path
from datetime import datetime
import difflib
import re
from flask_socketio import SocketIO, emit

# Model configurations
AVAILABLE_MODELS = {
    'deepseek': {
        'name': 'DeepSeek V3',
        'api_key_env': 'DEEPSEEK_API_KEY',
        'client_class': OpenAI,
        'base_url': 'https://api.deepseek.com',
        'models': {
            'code': 'deepseek-coder',
            'chat': 'deepseek-chat'
        }
    },
    'grok': {
        'name': 'Grok 2',
        'api_key_env': 'GROK_API_KEY',
        'client_class': OpenAI,
        'base_url': 'https://api.x.ai/v1',
        'models': {
            'code': 'grok-2-latest',
            'chat': 'grok-2-latest'
        }
    },
    'qwen': {
        'name': 'Qwen 2.5 Coder',
        'api_key_env': 'OPENROUTER_API_KEY',
        'client_class': OpenAI,
        'base_url': 'https://openrouter.ai/api/v1',
        'models': {
            'code': 'qwen/qwen-2.5-coder-32b-instruct',
            'chat': 'qwen/qwen-2.5-coder-32b-instruct'
        }
    },
    'codestral-mamba': {
        'name': 'Codestral Mamba',
        'api_key_env': 'OPENROUTER_API_KEY',
        'client_class': OpenAI,
        'base_url': 'https://openrouter.ai/api/v1',
        'models': {
            'code': 'mistralai/codestral-mamba',
            'chat': 'mistralai/codestral-mamba'
        }
    },
    'claude': {
        'name': 'Claude 3.5 Sonnet',
        'api_key_env': 'ANTHROPIC_API_KEY',
        'client_class': Anthropic,
        'models': {
            'code': 'claude-3-5-sonnet-20241022',
            'chat': 'claude-3-5-sonnet-20241022'
        }
    }
}

# System prompt for code generation
system_prompt = """You are an expert AI coding assistant. Your task is to help users with any coding-related request.

IMPORTANT: Before suggesting any changes:
1. ALWAYS read the current content of the file first
2. Analyze the content to understand the current state
3. Only specify the exact changes needed
4. Do not include unchanged content

Your responses must be formatted as a valid JSON object with this structure:
{
    "explanation": "Brief explanation of what you will do",
    "operations": [
        {
            "type": "edit_file",
            "path": "relative/path",
            "changes": [
                {
                    "old": "text to replace",
                    "new": "replacement text"
                }
            ],
            "explanation": "why this change is needed"
        }
    ]
}

Operation types can include but are not limited to:
- create_file: Create a new file (requires complete content)
- edit_file: Specify only the changes needed
- remove_file: Delete a file
- rename_file: Rename/move a file (requires new_path)
- remove_directory: Delete a directory (requires recursive boolean)

Guidelines for edit operations:
1. First read and analyze the existing file
2. For modifying content:
   - Only specify the exact text to change
   - Use the "changes" array to list each modification
   - Keep the original style and indentation
3. For removing content:
   - Specify the exact text to remove
   - Keep everything else exactly the same
4. For adding content:
   - Specify where to add the new content
   - Match the file's existing style

IMPORTANT:
- ALWAYS read the file content first
- ONLY specify the changes needed
- NEVER return unchanged content
- ALWAYS preserve the file's existing style and formatting

Respond with a single, valid JSON object."""

# Initialize clients for each model
model_clients = {}
for model_id, config in AVAILABLE_MODELS.items():
    api_key = os.getenv(config['api_key_env'])
    if api_key:
        client_kwargs = {'api_key': api_key}
        # Add base_url if specified
        if 'base_url' in config:
            client_kwargs['base_url'] = config['base_url']
        
        model_clients[model_id] = config['client_class'](**client_kwargs)

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management
socketio = SocketIO(app, cors_allowed_origins="*")
load_dotenv()

# Set up workspace directory
WORKSPACE_ROOT = os.path.join(os.getcwd(), 'workspaces')
os.makedirs(WORKSPACE_ROOT, exist_ok=True)

def create_workspace():
    """Create a new workspace directory"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    workspace_id = timestamp
    workspace_path = os.path.join(WORKSPACE_ROOT, workspace_id)
    os.makedirs(workspace_path, exist_ok=True)
    return workspace_id, workspace_path

def get_workspace_history():
    """Get list of all workspaces with their history"""
    workspaces = []
    
    # List all directories in WORKSPACE_ROOT
    for item in os.listdir(WORKSPACE_ROOT):
        workspace_path = os.path.join(WORKSPACE_ROOT, item)
        if os.path.isdir(workspace_path):
            # Get directory creation time
            created_at = datetime.fromtimestamp(os.path.getctime(workspace_path))
            
            # Count files in workspace
            file_count = 0
            for root, _, files in os.walk(workspace_path):
                # Exclude hidden files
                file_count += sum(1 for f in files if not f.startswith('.'))
            
            workspaces.append({
                'id': item,
                'path': workspace_path,
                'created_at': created_at.isoformat(),
                'file_count': file_count
            })
    
    # Sort by creation time, newest first
    return sorted(workspaces, key=lambda x: x['created_at'], reverse=True)

def delete_workspace(workspace_id):
    """Delete a workspace"""
    try:
        workspace_path = os.path.join(WORKSPACE_ROOT, workspace_id)
        
        # Verify the path is within WORKSPACE_ROOT for safety
        if not os.path.abspath(workspace_path).startswith(os.path.abspath(WORKSPACE_ROOT)):
            raise Exception("Invalid workspace path")
        
        # Delete directory
        try:
            if os.path.exists(workspace_path):
                shutil.rmtree(workspace_path, ignore_errors=False)
            if os.path.exists(workspace_path):
                raise Exception("Failed to delete workspace directory")
        except Exception as e:
            raise Exception(f"Failed to delete workspace directory: {str(e)}")
        
        return True
    except Exception as e:
        raise Exception(f"Failed to delete workspace: {str(e)}")

def get_workspace_structure(workspace_dir):
    """Get the folder structure of the workspace"""
    structure = []
    
    for root, dirs, files in os.walk(workspace_dir):
        # Get relative path
        rel_path = os.path.relpath(root, workspace_dir)
        if rel_path == '.':
            rel_path = ''
            
        # Add directories
        for dir_name in dirs:
            if not dir_name.startswith('.'):  # Skip hidden directories
                full_path = os.path.join(rel_path, dir_name)
                structure.append({
                    'type': 'directory',
                    'path': full_path,
                    'name': dir_name
                })
            
        # Add files
        for file_name in files:
            if not file_name.startswith('.'):  # Skip hidden files
                full_path = os.path.join(rel_path, file_name)
                structure.append({
                    'type': 'file',
                    'path': full_path,
                    'name': file_name
                })
    
    return sorted(structure, key=lambda x: (x['type'] == 'file', x['path']))

def get_file_size(file_path):
    """Get the size of a file in bytes"""
    try:
        return os.path.getsize(file_path)
    except OSError:
        return 0

def read_file_in_chunks(file_path, chunk_size=8192):
    """Generator to read a file in chunks"""
    with open(file_path, 'r', encoding='utf-8') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk

def is_large_file(file_path, threshold_mb=5):
    """Check if a file is considered large (default threshold: 5MB)"""
    return get_file_size(file_path) > (threshold_mb * 1024 * 1024)

def get_file_preview(file_path, max_lines=1000):
    """Get a preview of a large file (first max_lines lines)"""
    preview_lines = []
    try:
        # First try UTF-8
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i >= max_lines:
                        preview_lines.append('... (file truncated, too large to display completely)')
                        break
                    preview_lines.append(line.rstrip('\n'))
        except UnicodeDecodeError:
            # If UTF-8 fails, try to detect if it's a binary file
            with open(file_path, 'rb') as f:
                is_binary = False
                try:
                    chunk = f.read(1024)
                    if b'\x00' in chunk:
                        is_binary = True
                    # Try to decode as latin-1 which can handle all byte values
                    text = chunk.decode('latin-1')
                    if any(ord(c) < 32 and c not in '\r\n\t' for c in text):
                        is_binary = True
                except:
                    is_binary = True
                
                if is_binary:
                    return "[Binary file] - Cannot display content"
                
                # If not binary, try reading with latin-1 encoding
                f.seek(0)
                with open(file_path, 'r', encoding='latin-1') as f:
                    for i, line in enumerate(f):
                        if i >= max_lines:
                            preview_lines.append('... (file truncated, too large to display completely)')
                            break
                        preview_lines.append(line.rstrip('\n'))
        
        return '\n'.join(preview_lines)
    except Exception as e:
        return f"Error reading file: {str(e)}"

def get_existing_files(workspace_dir):
    """Get content of existing files in workspace"""
    # Validate workspace directory
    if not os.path.exists(workspace_dir) or not os.path.isdir(workspace_dir):
        raise ValueError('Invalid workspace directory')
        
    # Set maximum file size (50MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024
    
    files_content = {}
    for root, _, files in os.walk(workspace_dir):
        for file in files:
            # Skip database, hidden files, and common binary formats
            if (not file.endswith('.db') and 
                not file.startswith('.') and 
                not file.endswith(('.pyc', '.pyo', '.pyd', '.so', '.dll', '.exe', '.bin'))):
                
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, workspace_dir)
                try:
                    # Get file size
                    file_size = os.path.getsize(file_path)
                    if file_size > MAX_FILE_SIZE:
                        print(f"Warning: Skipping large file {rel_path} ({file_size} bytes)")
                        continue
                        
                    # Check if it's a large file
                    if is_large_file(file_path):
                        # For large files, only get a preview
                        preview = get_file_preview(file_path)
                        if preview.startswith('[Binary file]'):
                            continue  # Skip binary files
                        files_content[rel_path] = preview
                    else:
                        # Try UTF-8 first
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                        except UnicodeDecodeError:
                            # Check if binary
                            with open(file_path, 'rb') as f:
                                chunk = f.read(1024)
                                if b'\x00' in chunk:
                                    continue  # Skip binary files
                                
                                # Try latin-1 as fallback
                                try:
                                    with open(file_path, 'r', encoding='latin-1') as f:
                                        content = f.read()
                                except:
                                    continue  # Skip if still can't read
                                
                        files_content[rel_path] = content
                except Exception as e:
                    print(f"Warning: Could not read file {file_path}: {e}")
                    continue
    return files_content

@app.route('/')
def index():
    return render_template('base.html')

@app.route('/workspace/create', methods=['POST'])
def create_new_workspace():
    try:
        workspace_id, workspace_dir = create_workspace()
        structure = get_workspace_structure(workspace_dir)
        return jsonify({
            'status': 'success',
            'workspace_id': workspace_id,
            'workspace_dir': workspace_dir,
            'structure': structure
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/workspace/history', methods=['GET'])
def get_history():
    try:
        history = get_workspace_history()
        return jsonify({
            'status': 'success',
            'history': history
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/workspace/structure', methods=['POST'])
def get_structure():
    try:
        data = request.json
        workspace_dir = data.get('workspace_dir')
        
        if not workspace_dir or not os.path.exists(workspace_dir):
            return jsonify({'error': 'Invalid workspace directory'}), 400
            
        structure = get_workspace_structure(workspace_dir)
        return jsonify({
            'status': 'success',
            'structure': structure
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/process', methods=['POST'])
def process_prompt():
    try:
        data = request.json
        prompt = data.get('prompt')
        workspace_dir = data.get('workspace_dir')
        model_id = data.get('model_id', 'deepseek')
        attachments = data.get('attachments', [])
        
        print(f"\nReceived request with {len(attachments)} attachments:")
        for attachment in attachments:
            print(f"- Attachment: {attachment['name']}")
            print(f"  Content length: {len(attachment['content'])} characters")
        
        if not prompt:
            return jsonify({'status': 'error', 'message': 'No prompt provided'}), 400
            
        if not workspace_dir:
            socketio.emit('status', {'message': 'Creating new workspace...', 'step': 0})
            _, workspace_dir = create_workspace()
        elif not os.path.exists(workspace_dir):
            return jsonify({'status': 'error', 'message': 'Invalid workspace directory'}), 400
        
        # First get all existing files content
        socketio.emit('status', {'message': 'Reading workspace files...', 'step': 1})
        print(f"Reading files from workspace: {workspace_dir}")
        files_content = get_existing_files(workspace_dir)
        print(f"Found {len(files_content)} readable files")
        
        # Add attachment contents to the context
        attachment_context = ""
        if attachments:
            print("\nProcessing attachments for context:")
            attachment_context = "\nAttached files for context:\n\n"
            for attachment in attachments:
                print(f"- Adding {attachment['name']} to context")
                attachment_context += f"File: {attachment['name']}\nContent:\n{attachment['content']}\n\n"
        
        # Combine prompt with attachments
        full_prompt = f"{prompt}\n\n{attachment_context}" if attachments else prompt
        print("\nFinal prompt with attachments:")
        print("---")
        print(full_prompt)
        print("---")
        
        print("Getting workspace context...")
        workspace_context = get_workspace_context(workspace_dir)
        
        print(f"Getting suggestions from AI model: {model_id}")
        # Get suggestions from AI, passing the file contents
        suggestions = get_code_suggestion(full_prompt, files_content, workspace_context, model_id)
        
        print("AI Response:", json.dumps(suggestions, indent=2))
        
        # Validate suggestions format
        if not isinstance(suggestions, dict):
            return jsonify({
                'status': 'error',
                'message': 'Invalid response format from AI model'
            }), 500
        
        # Don't apply changes yet, just return the suggestions for approval
        if not suggestions.get('operations'):
            return jsonify({
                'status': 'error',
                'message': 'No changes suggested by the AI'
            }), 400
        
        socketio.emit('status', {'message': 'Preparing changes...', 'step': 4})
        print("Getting workspace structure...")
        structure = get_workspace_structure(workspace_dir)
        
        # Process each operation and generate diffs
        print("Generating diffs for operations...")
        for operation in suggestions.get('operations', []):
            if operation.get('type') == 'edit_file':
                file_path = operation.get('path')
                if file_path in files_content:
                    current_content = files_content[file_path]
                    
                    # If we have a changes array, apply each change
                    if 'changes' in operation:
                        new_content = current_content
                        for change in operation['changes']:
                            old_text = change.get('old', '')
                            new_text = change.get('new', '')
                            if old_text in new_content:  # Only replace if old text exists
                                new_content = new_content.replace(old_text, new_text)
                        operation['content'] = new_content
                        
                        # Generate diff directly from strings
                        current_lines = current_content.splitlines()
                        new_lines = new_content.splitlines()
                        
                        diff_lines = list(difflib.unified_diff(
                            current_lines,
                            new_lines,
                            fromfile=f'a/{file_path}',
                            tofile=f'b/{file_path}',
                            lineterm=''
                        ))
                        
                        if diff_lines:  # Only include diff if there are actual changes
                            operation['diff'] = '\n'.join(diff_lines)
                        else:
                            # If no changes were made, mark this operation for removal
                            operation['no_changes'] = True
        
        # Remove operations that didn't result in any changes
        suggestions['operations'] = [op for op in suggestions['operations'] 
                                  if not op.get('no_changes', False)]
        
        if not suggestions['operations']:
            return jsonify({
                'status': 'error',
                'message': 'No valid changes to apply'
            }), 400
        
        socketio.emit('status', {'message': 'Ready for review', 'step': 5})
        return jsonify({
            'status': 'success',
            'explanation': suggestions.get('explanation', ''),
            'operations': suggestions.get('operations', []),
            'workspace_dir': workspace_dir,
            'structure': structure,
            'requires_approval': True
        })
            
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error in process endpoint:\n{error_trace}")
        return jsonify({
            'status': 'error',
            'message': f"Request processing error: {str(e)}",
            'trace': error_trace if app.debug else None
        }), 500

@app.route('/workspace/delete', methods=['POST'])
def delete_workspace_endpoint():
    try:
        data = request.json
        workspace_id = data.get('workspace_id')
        
        if not workspace_id:
            return jsonify({'error': 'No workspace ID provided'}), 400
            
        delete_workspace(workspace_id)
        return jsonify({
            'status': 'success',
            'message': 'Workspace deleted successfully'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/workspace/file', methods=['POST'])
def get_file_content():
    try:
        data = request.json
        workspace_dir = data.get('workspace_dir')
        file_path = data.get('file_path')
        
        if not workspace_dir or not file_path:
            return jsonify({'error': 'Missing workspace_dir or file_path'}), 400
            
        # Validate file path to prevent directory traversal
        if '..' in file_path or file_path.startswith('/'):
            return jsonify({'error': 'Invalid file path'}), 400
            
        # Ensure the file is within the workspace
        full_path = os.path.abspath(os.path.join(workspace_dir, file_path))
        if not full_path.startswith(os.path.abspath(workspace_dir)):
            return jsonify({'error': 'File path not within workspace'}), 400
            
        full_path = os.path.join(workspace_dir, file_path)
        if not os.path.exists(full_path):
            return jsonify({
                'status': 'success',
                'content': ''  # Return empty content for new files
            })
        
        # Check if it's a large file
        if is_large_file(full_path):
            preview_content = get_file_preview(full_path)
            return jsonify({
                'status': 'success',
                'content': preview_content,
                'truncated': True,
                'file_size': get_file_size(full_path)
            })
        
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        return jsonify({
            'status': 'success',
            'content': content,
            'truncated': False,
            'file_size': get_file_size(full_path)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/workspace/rename', methods=['POST'])
def rename_workspace():
    """Rename a workspace"""
    data = request.json
    workspace_id = data.get('workspace_id')
    new_name = data.get('new_name')
    
    if not workspace_id or not new_name:
        return jsonify({
            'status': 'error',
            'message': 'Missing workspace_id or new_name'
        }), 400
    
    try:
        old_path = os.path.join(WORKSPACE_ROOT, workspace_id)
        new_path = os.path.join(WORKSPACE_ROOT, new_name)
        
        # Check if source exists and target doesn't
        if not os.path.exists(old_path):
            return jsonify({
                'status': 'error',
                'message': 'Workspace not found'
            }), 404
            
        if os.path.exists(new_path):
            return jsonify({
                'status': 'error',
                'message': 'A workspace with this name already exists'
            }), 400
        
        # Rename directory
        os.rename(old_path, new_path)
        
        return jsonify({
            'status': 'success',
            'message': 'Workspace renamed successfully',
            'new_path': new_path
        })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        prompt = data.get('prompt')
        workspace_dir = data.get('workspace_dir')
        model_id = data.get('model_id', 'deepseek')
        attachments = data.get('attachments', [])
        
        print(f"\nReceived chat request with {len(attachments)} attachments:")
        for attachment in attachments:
            print(f"- Attachment: {attachment['name']}")
            print(f"  Content length: {len(attachment['content'])} characters")
        
        if not prompt:
            return jsonify({'error': 'No prompt provided'}), 400
            
        if not workspace_dir or not os.path.exists(workspace_dir):
            return jsonify({'error': 'Invalid workspace directory'}), 400
        
        workspace_context = get_workspace_context(workspace_dir)
        
        # Add attachment contents to the context
        if attachments:
            print("\nProcessing attachments for chat context:")
            workspace_context += "\n\nAttached files:\n\n"
            for attachment in attachments:
                print(f"- Adding {attachment['name']} to context")
                workspace_context += f"File: {attachment['name']}\nContent:\n{attachment['content']}\n\n"
        
        print("\nFinal context with attachments:")
        print("---")
        print(workspace_context)
        print("---")
        
        system_message = f"""You are a helpful AI assistant powered by {AVAILABLE_MODELS[model_id]['name']} that can discuss the code in the workspace.
Current workspace contains the following files:
{workspace_context}

Please provide helpful responses about the code and files in this workspace."""

        response = get_chat_response(system_message, prompt, model_id)
        
        return jsonify({
            'status': 'success',
            'response': response
        })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def get_chat_response(system_message, user_message, model_id='deepseek'):
    """Get a chat response from the selected AI model"""
    if model_id not in model_clients:
        raise Exception(f"Model {model_id} is not configured. Please check your API keys.")
        
    client = model_clients[model_id]
    model_config = AVAILABLE_MODELS[model_id]
    
    try:
        if model_id == 'claude':
            response = client.messages.create(
                model=model_config['models']['chat'],
                system=system_message,
                messages=[{
                    "role": "user",
                    "content": user_message
                }],
                temperature=0.7,
                max_tokens=2048
            )
            text = response.content[0].text
        else:
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ]
            
            response = client.chat.completions.create(
                model=model_config['models']['chat'],
                messages=messages,
                temperature=0.7,
            )
            text = response.choices[0].message.content

        # Split text into code blocks and regular text
        parts = text.split('```')
        formatted_parts = []
        
        for i, part in enumerate(parts):
            if i % 2 == 0:  # Regular text
                # Replace newlines with <br> in regular text
                formatted_parts.append(part.replace('\n', '<br>'))
            else:  # Code block
                # Extract language if specified
                if '\n' in part:
                    lang, code = part.split('\n', 1)
                    # Preserve indentation and line breaks in code
                    formatted_code = code.replace('\n', '<br>').replace(' ', '&nbsp;')
                    formatted_parts.append(f'<pre><code class="language-{lang.strip()}">{formatted_code}</code></pre>')
                else:
                    # Single line code block
                    formatted_parts.append(f'<pre><code>{part.replace(" ", "&nbsp;")}</code></pre>')
        
        return ''.join(formatted_parts)
        
    except Exception as e:
        print(f"Error getting chat response: {e}")
        raise Exception(f"Failed to get response from {model_config['name']}")

@app.route('/models', methods=['GET'])
def get_available_models():
    """Get list of available and configured models"""
    configured_models = []
    for model_id, config in AVAILABLE_MODELS.items():
        if model_id in model_clients:
            configured_models.append({
                'id': model_id,
                'name': config['name']
            })
    return jsonify({
        'status': 'success',
        'models': configured_models
    })

@app.route('/logo.svg')
def serve_logo():
    return send_from_directory('static', 'logo.svg', mimetype='image/svg+xml')

@app.route('/favicon.png')
def serve_favicon():
    return send_from_directory('static', 'favicon.svg', mimetype='image/svg+xml')

@app.route('/apply_changes', methods=['POST'])
def apply_approved_changes():
    try:
        data = request.json
        workspace_dir = data.get('workspace_dir')
        operations = data.get('operations')
        
        if not workspace_dir or not operations:
            return jsonify({'error': 'Missing workspace_dir or operations'}), 400
            
        if not os.path.exists(workspace_dir):
            return jsonify({'error': 'Invalid workspace directory'}), 400
        
        # Apply the changes
        modified_files = apply_changes({
            'operations': operations
        }, workspace_dir)
        
        structure = get_workspace_structure(workspace_dir)
        
        # Notify all clients about the changes
        workspace_id = os.path.basename(workspace_dir)
        socketio.emit('changes_applied', {
            'workspace_id': workspace_id,
            'modified_files': list(modified_files.keys())
        })
        
        return jsonify({
            'status': 'success',
            'message': 'Changes applied successfully',
            'structure': structure
        })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.context_processor
def utility_processor():
    """Add utility functions to template context"""
    return {
        'cache_buster': str(int(datetime.now().timestamp()))
    }

if __name__ == '__main__':
    # Watch static and template directories for changes
    extra_files = []
    for root, dirs, files in os.walk('static'):
        for file in files:
            path = os.path.join(root, file)
            extra_files.append(path)
    
    for root, dirs, files in os.walk('templates'):
        for file in files:
            path = os.path.join(root, file)
            extra_files.append(path)
    
    # Run with eventlet server and reloader enabled
    socketio.run(
        app,
        debug=True,
        extra_files=extra_files,
        host='0.0.0.0',
        port=5000
    ) 
