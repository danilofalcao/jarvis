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
import sqlite3
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

# Set up database
DB_PATH = os.path.join(WORKSPACE_ROOT, 'history.db')

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    return conn

def init_db():
    """Initialize SQLite database for history tracking"""
    with get_db() as conn:
        c = conn.cursor()
        # Create workspaces table
        c.execute('''CREATE TABLE IF NOT EXISTS workspaces
                    (id TEXT PRIMARY KEY,
                     path TEXT NOT NULL,
                     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Create file_history table
        c.execute('''CREATE TABLE IF NOT EXISTS file_history
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     workspace_id TEXT NOT NULL,
                     file_path TEXT NOT NULL,
                     content TEXT NOT NULL,
                     explanation TEXT,
                     timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                     FOREIGN KEY(workspace_id) REFERENCES workspaces(id))''')
        conn.commit()

def create_workspace():
    """Create a new workspace directory"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    workspace_id = timestamp
    workspace_path = os.path.join(WORKSPACE_ROOT, workspace_id)
    os.makedirs(workspace_path, exist_ok=True)
    
    # Record in database
    with get_db() as conn:
        c = conn.cursor()
        c.execute('INSERT INTO workspaces (id, path) VALUES (?, ?)',
                 (workspace_id, workspace_path))
        conn.commit()
    
    return workspace_id, workspace_path

def get_workspace_history():
    """Get list of all workspaces with their history"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT w.id, w.path, w.created_at FROM workspaces w ORDER BY w.created_at DESC')
        workspaces = [dict(row) for row in c.fetchall()]
        
        # Count actual files in each workspace directory
        for workspace in workspaces:
            file_count = 0
            workspace_path = workspace['path']
            if os.path.exists(workspace_path):
                for root, _, files in os.walk(workspace_path):
                    # Exclude database files and hidden files
                    file_count += sum(1 for f in files if not f.endswith('.db') and not f.startswith('.'))
            workspace['file_count'] = file_count
            
        return workspaces

def record_file_change(workspace_id, file_path, content, explanation):
    """Record file change in history"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO file_history 
                    (workspace_id, file_path, content, explanation)
                    VALUES (?, ?, ?, ?)''',
                 (workspace_id, file_path, content, explanation))
        conn.commit()

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
            full_path = os.path.join(rel_path, dir_name)
            structure.append({
                'type': 'directory',
                'path': full_path,
                'name': dir_name
            })
            
        # Add files
        for file_name in files:
            if not file_name.endswith('.db'):  # Skip database files
                full_path = os.path.join(rel_path, file_name)
                structure.append({
                    'type': 'file',
                    'path': full_path,
                    'name': file_name
                })
    
    return sorted(structure, key=lambda x: (x['type'] == 'file', x['path']))

def reconstruct_json_from_stream(chunks):
    """Reconstruct JSON from streamed chunks"""
    # Join all chunks
    full_text = ''.join(chunk for chunk in chunks if isinstance(chunk, str))
    
    # Try to find complete JSON object
    json_start = full_text.find('{')
    json_end = full_text.rfind('}') + 1
    
    if json_start == -1 or json_end <= json_start:
        raise Exception("No complete JSON object found in response")
    
    # Extract the JSON part
    json_text = full_text[json_start:json_end]
    
    # Clean up the JSON
    # Fix string escaping issues
    json_text = re.sub(r'(?<!\\)"([^"]*?)(?<!\\)"(?=:)', r'"\1"', json_text)  # Fix key quotes
    json_text = re.sub(r':\s*"([^"]*?)(?<!\\)"(?=,|})', r':"\1"', json_text)  # Fix value quotes
    
    # Handle multiline strings properly
    def escape_multiline(match):
        content = match.group(1)
        # Escape newlines and quotes
        content = content.replace('\n', '\\n').replace('"', '\\"')
        return f'"{content}"'
    
    json_text = re.sub(r'"((?:[^"\\]|\\.|\n)*)"', escape_multiline, json_text)
    
    # Remove any control characters
    json_text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', json_text)
    
    # Fix common JSON formatting issues
    json_text = re.sub(r',\s*}$', '}', json_text)  # Remove trailing comma before }
    json_text = re.sub(r',\s*]$', ']', json_text)  # Remove trailing comma before ]
    json_text = re.sub(r'(?<=\{|\[|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'"\1":', json_text)  # Quote unquoted keys
    
    try:
        # Try to parse the cleaned JSON
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {str(e)}")
        print(f"Problematic JSON: {json_text}")
        
        # Try one more time with a more aggressive cleaning
        try:
            # Replace problematic characters in string values
            json_text = re.sub(r':\s*"([^"]*)"', lambda m: f':{json.dumps(m.group(1))}', json_text)
            return json.loads(json_text)
        except json.JSONDecodeError as e2:
            print(f"Second attempt failed: {str(e2)}")
            raise

def process_streamed_response(response_chunks, files_content):
    """Process streamed response chunks and handle file comparisons"""
    # Join all chunks
    full_text = ''.join(chunk for chunk in response_chunks if isinstance(chunk, str))
    
    try:
        # First try to parse the entire response as JSON
        try:
            result = json.loads(full_text)
            if isinstance(result, dict) and 'operations' in result:
                return result
        except:
            pass
        
        # Try to find JSON in code blocks
        json_matches = re.finditer(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', full_text)
        for match in json_matches:
            try:
                json_str = match.group(1).strip()
                result = json.loads(json_str)
                if isinstance(result, dict) and 'operations' in result:
                    return result
            except:
                continue
        
        # Try to find any JSON object in the response
        json_matches = re.finditer(r'\{[\s\S]*?\}', full_text)
        for match in json_matches:
            try:
                json_str = match.group(0).strip()
                result = json.loads(json_str)
                if isinstance(result, dict) and 'operations' in result:
                    return result
            except:
                continue
        
        print(f"Failed to parse response. Preview:\n{full_text[:1000]}")
        raise Exception("No valid JSON object found in response")
    except Exception as e:
        print(f"Error processing response: {str(e)}")
        raise

def clean_json_text(json_text):
    """Clean and format JSON text for parsing"""
    # First, normalize line endings and remove any null bytes
    json_text = json_text.replace('\0', '').replace('\r\n', '\n').replace('\r', '\n')
    
    # Handle multiline strings properly
    def escape_multiline(match):
        content = match.group(1)
        # Escape special characters
        content = content.replace('\\', '\\\\')  # Must be first
        content = content.replace('\n', '\\n')
        content = content.replace('\t', '\\t')
        content = content.replace('"', '\\"')
        return f'"{content}"'
    
    # Fix string values, handling both single and multiline
    json_text = re.sub(r'"((?:[^"\\]|\\.|\n)*)"', escape_multiline, json_text)
    
    # Remove any control characters except newlines and tabs
    json_text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', json_text)
    
    # Fix common JSON formatting issues
    json_text = re.sub(r',\s*}$', '}', json_text)  # Remove trailing comma before }
    json_text = re.sub(r',\s*]$', ']', json_text)  # Remove trailing comma before ]
    json_text = re.sub(r'(?<=\{|\[|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'"\1":', json_text)  # Quote unquoted keys
    
    return json_text

def generate_diff(current_content, new_content, file_path):
    """Generate a clean diff between current and new content"""
    current_lines = current_content.splitlines()
    new_lines = new_content.splitlines()
    
    diff_lines = list(difflib.unified_diff(
        current_lines,
        new_lines,
        fromfile=f'a/{file_path}',
        tofile=f'b/{file_path}',
        lineterm=''
    ))
    
    return '\n'.join(diff_lines)

def get_code_suggestion(prompt, files_content=None, workspace_context=None, model_id='deepseek'):
    """Get code suggestions from the selected AI model"""
    if model_id not in model_clients:
        raise Exception(f"Model {model_id} is not configured. Please check your API keys.")
        
    client = model_clients[model_id]
    model_config = AVAILABLE_MODELS[model_id]
    
    try:
        socketio.emit('status', {'message': 'Analyzing files...', 'step': 1})
        print("\n=== Step 1: Analyzing files ===")
        # First send all files to AI for analysis
        files_list = []
        for file_path, content in files_content.items():
            files_list.append(f"File: {file_path}\nContent:\n{content}\n")
        
        analysis_prompt = f"""Based on this request: {prompt}

Here are all the files in the workspace:

{chr(10).join(files_list)}

Analyze these files and determine:
1. Which files need to be modified
2. What specific changes are needed in each file
3. Whether any new files need to be created
4. Whether any files need to be deleted

Return a JSON object with the operations needed. Only include files that actually need changes.
Do not include files in the operations if they don't need modifications.

IMPORTANT: Return the JSON object directly, not inside a code block."""

        socketio.emit('status', {'message': 'Sending request to AI...', 'step': 2})
        print("\nSending analysis request...")
        
        if model_id == 'qwen':
            try:
                # Try streaming first
                response = client.chat.completions.create(
                    model=model_config['models']['code'],
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": analysis_prompt}
                    ],
                    stream=True,
                    max_tokens=4000,
                    temperature=0.7,
                    http_referer="https://github.com/danilofalcao",
                    x_title="J.A.R.V.I.S."
                )
                
                response_chunks = []
                tokens_received = 0
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        response_chunks.append(content)
                        tokens_received += len(content.split())
                        socketio.emit('progress', {
                            'message': f'Received {tokens_received} tokens...',
                            'tokens': tokens_received
                        })
                
                full_text = ''.join(response_chunks)
                
            except Exception as qwen_error:
                print(f"Qwen streaming error, trying non-streaming: {str(qwen_error)}")
                # Fallback to non-streaming request
                response = client.chat.completions.create(
                    model=model_config['models']['code'],
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": analysis_prompt}
                    ],
                    stream=False,
                    max_tokens=4000,
                    temperature=0.7,
                    http_referer="https://github.com/danilofalcao",
                    x_title="J.A.R.V.I.S."
                )
                
                if response.choices and response.choices[0].message.content:
                    full_text = response.choices[0].message.content
                else:
                    print("Qwen response failed, falling back to DeepSeek")
                    return get_code_suggestion(prompt, files_content, workspace_context, "deepseek")

        elif model_id == 'codestral-mamba':
            try:
                # Try streaming first
                response = client.chat.completions.create(
                    model=model_config['models']['code'],
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": analysis_prompt}
                    ],
                    stream=True,
                    max_tokens=4000,
                    temperature=0.7
                )
                
                response_chunks = []
                tokens_received = 0
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        response_chunks.append(content)
                        tokens_received += len(content.split())
                        socketio.emit('progress', {
                            'message': f'Received {tokens_received} tokens...',
                            'tokens': tokens_received
                        })
                
                full_text = ''.join(response_chunks)
                
            except Exception as codestral_error:
                print(f"Codestral-Mamba streaming error, trying non-streaming: {str(codestral_error)}")
                # Fallback to non-streaming request
                response = client.chat.completions.create(
                    model=model_config['models']['code'],
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": analysis_prompt}
                    ],
                    stream=False,
                    max_tokens=4000,
                    temperature=0.7
                )
                
                if response.choices and response.choices[0].message.content:
                    full_text = response.choices[0].message.content
                else:
                    print("Codestral-Mamba response failed, falling back to DeepSeek")
                    return get_code_suggestion(prompt, files_content, workspace_context, "deepseek")

        elif model_id == 'claude':
            response = client.messages.create(
                model=model_config['models']['code'],
                system=system_prompt,
                messages=[{"role": "user", "content": analysis_prompt}],
                temperature=0.7,
                max_tokens=4096
            )
            # Claude doesn't need streaming for this use case
            response_chunks = [response.content[0].text]
            full_text = ''.join(response_chunks)
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": analysis_prompt}
            ]
            
            response = client.chat.completions.create(
                model=model_config['models']['code'],
                messages=messages,
                temperature=0.7,
                stream=True
            )
            
            response_chunks = []
            tokens_received = 0
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    response_chunks.append(content)
                    tokens_received += len(content.split())
                    socketio.emit('progress', {
                        'message': f'Received {tokens_received} tokens...',
                        'tokens': tokens_received
                    })
            full_text = ''.join(response_chunks)
        
        socketio.emit('status', {'message': 'Processing AI response...', 'step': 3})
        print("\n=== Step 2: Processing response ===")
        print("\nFull response length:", len(full_text))
        print("\nFirst 500 chars:", full_text[:500])
        
        # Try to parse the response in different ways
        result = None
        try:
            # First try direct JSON parsing
            result = json.loads(full_text)
            if isinstance(result, dict) and 'operations' in result:
                return result
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from code blocks
        if not result:
            matches = re.finditer(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', full_text)
            for match in matches:
                try:
                    json_str = match.group(1).strip()
                    result = json.loads(json_str)
                    if isinstance(result, dict) and 'operations' in result:
                        return result
                except:
                    continue
        
        # Try to find any JSON object
        if not result:
            matches = re.finditer(r'\{[\s\S]*?\}', full_text)
            for match in matches:
                try:
                    json_str = match.group(0).strip()
                    result = json.loads(json_str)
                    if isinstance(result, dict) and 'operations' in result:
                        return result
                except:
                    continue
        
        if not result:
            raise ValueError("Could not find valid JSON response")
        
        return result
        
    except Exception as e:
        socketio.emit('status', {'message': f'Error: {str(e)}', 'step': -1})
        print(f"\nError getting code suggestion: {str(e)}")
        raise

def get_workspace_context(workspace_dir):
    """Get a description of the workspace context"""
    structure = get_workspace_structure(workspace_dir)
    files_content = get_existing_files(workspace_dir)
    
    context = "Workspace Structure:\n"
    for item in structure:
        prefix = "📁 " if item['type'] == 'directory' else " "
        context += f"{prefix}{item['path']}\n"
    
    context += "\nFile Relationships and Dependencies:\n"
    # Analyze imports and dependencies
    dependencies = analyze_dependencies(files_content)
    for file, deps in dependencies.items():
        if deps:
            context += f"{file} depends on: {', '.join(deps)}\n"
    
    return context

def analyze_dependencies(files_content):
    """Analyze file dependencies based on imports and references"""
    dependencies = {}
    import_patterns = {
        '.py': ['import ', 'from '],
        '.js': ['import ', 'require('],
        '.html': ['<script src=', '<link href='],
    }
    
    for file_path, content in files_content.items():
        ext = os.path.splitext(file_path)[1]
        deps = set()
        
        if ext in import_patterns:
            lines = content.split('\n')
            for line in lines:
                for pattern in import_patterns[ext]:
                    if pattern in line:
                        # Extract dependency name (simplified)
                        dep = line.split(pattern)[-1].split()[0].strip('"\';')
                        deps.add(dep)
        
        dependencies[file_path] = deps
    
    return dependencies


def apply_changes(suggestions, workspace_dir):
    """Apply code changes based on the operations in the response"""
    try:
        modified_files = {}
        
        # Validate workspace directory
        if not os.path.exists(workspace_dir) or not os.path.isdir(workspace_dir):
            raise ValueError('Invalid workspace directory')
            
        # Get the explanation for the overall changes
        overall_explanation = suggestions.get('explanation', 'Changes requested by user')
        
        # Validate operations
        if not isinstance(suggestions.get('operations'), list):
            raise ValueError('Invalid operations format')
        
        # Process each operation
        for operation in suggestions.get('operations', []):
            op_type = operation.get('type')
            path = operation.get('path')
            if not path:
                continue
                
            full_path = os.path.join(workspace_dir, path)
            rel_path = os.path.relpath(full_path, workspace_dir)
            
            if op_type == 'remove_directory':
                if os.path.exists(full_path) and os.path.isdir(full_path):
                    recursive = operation.get('recursive', False)
                    if recursive:
                        shutil.rmtree(full_path)
                    else:
                        os.rmdir(full_path)
                        
            elif op_type == 'remove_file':
                if os.path.exists(full_path):
                    os.remove(full_path)
                    
            elif op_type == 'rename_file':
                new_path = operation.get('new_path')
                if new_path and os.path.exists(full_path):
                    new_full_path = os.path.join(workspace_dir, new_path)
                    os.makedirs(os.path.dirname(new_full_path), exist_ok=True)
                    os.rename(full_path, new_full_path)
                    
            elif op_type in ['create_file', 'edit_file']:
                explanation = operation.get('explanation', '')
                
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                # Get current content if file exists
                current_content = ''
                if os.path.exists(full_path):
                    with open(full_path, 'r', encoding='utf-8') as f:
                        current_content = f.read()
                
                # Determine new content
                if op_type == 'create_file':
                    new_content = operation.get('content', '')
                else:  # edit_file
                    if 'changes' in operation:
                        # Apply each change in sequence
                        new_content = current_content
                        for change in operation['changes']:
                            old_text = change.get('old', '')
                            new_text = change.get('new', '')
                            new_content = new_content.replace(old_text, new_text)
                    else:
                        new_content = operation.get('content', current_content)
                
                # Ensure content ends with newline
                if new_content and not new_content.endswith('\n'):
                    new_content += '\n'
                
                # Write the content
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                # Generate diff
                if current_content:
                    print(f"Generating diff for modified file: {rel_path}")
                    current_lines = current_content.splitlines()
                    new_lines = new_content.splitlines()
                    
                    diff_lines = list(difflib.unified_diff(
                        current_lines,
                        new_lines,
                        fromfile=f'a/{rel_path}',
                        tofile=f'b/{rel_path}',
                        lineterm=''
                    ))
                    
                    if not diff_lines and current_content != new_content:
                        diff_lines = [
                            f'--- a/{rel_path}',
                            f'+++ b/{rel_path}',
                            f'@@ -1,{len(current_lines)} +1,{len(new_lines)} @@'
                        ]
                        for line in current_lines:
                            diff_lines.append('-' + line)
                        for line in new_lines:
                            diff_lines.append('+' + line)
                else:
                    print(f"Generating diff for new file: {rel_path}")
                    new_lines = new_content.splitlines()
                    diff_lines = [
                        f'--- /dev/null',
                        f'+++ b/{rel_path}',
                        f'@@ -0,0 +1,{len(new_lines)} @@'
                    ]
                    diff_lines.extend('+' + line for line in new_lines)
                
                diff = '\n'.join(diff_lines)
                
                # Store the file info
                modified_files[rel_path] = {
                    'content': new_content,
                    'explanation': explanation,
                    'diff': diff,
                    'is_new': not os.path.exists(full_path) or op_type == 'create_file'
                }
        
        return modified_files
        
    except Exception as e:
        raise Exception(f"Failed to apply changes: {str(e)}")

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

def delete_workspace(workspace_id):
    """Delete a workspace and its records from database"""
    try:
        with get_db() as conn:
            c = conn.cursor()
            
            # Get workspace path first
            c.execute('SELECT path FROM workspaces WHERE id = ?', (workspace_id,))
            result = c.fetchone()
            if not result:
                raise Exception("Workspace not found")
            
            workspace_path = result['path']
            
            # Delete directory first
            if os.path.exists(workspace_path):
                shutil.rmtree(workspace_path)
            
            # Then delete from database
            c.execute('DELETE FROM file_history WHERE workspace_id = ?', (workspace_id,))
            c.execute('DELETE FROM workspaces WHERE id = ?', (workspace_id,))
            conn.commit()
            
            return True
    except Exception as e:
        # If database deletion fails but directory was deleted, try to recreate empty directory
        if not os.path.exists(workspace_path):
            try:
                os.makedirs(workspace_path)
            except:
                pass
        raise Exception(f"Failed to delete workspace: {str(e)}")

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
        # Get current workspace path
        with get_db() as conn:
            c = conn.cursor()
            c.execute('SELECT path FROM workspaces WHERE id = ?', (workspace_id,))
            result = c.fetchone()
            
            if not result:
                return jsonify({
                    'status': 'error',
                    'message': 'Workspace not found'
                }), 404
            
            old_path = result['path']
            new_path = os.path.join(WORKSPACE_ROOT, new_name)
            
            # Check if new name already exists
            if os.path.exists(new_path):
                return jsonify({
                    'status': 'error',
                    'message': 'A workspace with this name already exists'
                }), 400
            
            # Rename directory
            os.rename(old_path, new_path)
            
            # Update database
            c.execute('UPDATE workspaces SET id = ?, path = ? WHERE id = ?',
                     (new_name, new_path, workspace_id))
            conn.commit()
            
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
        
        # Record changes in history
        workspace_id = os.path.basename(workspace_dir)
        for file_path, file_data in modified_files.items():
            record_file_change(
                workspace_id,
                file_path,
                file_data['content'],
                file_data['explanation']
            )
        
        structure = get_workspace_structure(workspace_dir)
        
        # Notify all clients about the changes
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
    # Initialize database before starting the app
    init_db()
    
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
