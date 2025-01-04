import pytest
import json
import os

def test_index_route(client):
    response = client.get('/')
    assert response.status_code == 200

def test_create_workspace_api(client):
    response = client.post('/workspace/create')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'workspace_id' in data
    assert 'workspace_dir' in data
    assert 'status' in data
    assert data['status'] == 'success'

def test_workspace_history_api(client, temp_workspace):
    # Create a test workspace first
    client.post('/workspace/create')
    
    response = client.get('/workspace/history')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'status' in data
    assert data['status'] == 'success'
    assert 'history' in data
    assert isinstance(data['history'], list)

def test_workspace_structure_api(client, temp_workspace):
    # Create a workspace
    create_response = client.post('/workspace/create')
    workspace_data = json.loads(create_response.data)
    
    response = client.post('/workspace/structure', json={
        'workspace_id': workspace_data['workspace_id'],
        'workspace_dir': workspace_data['workspace_dir']
    })
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'status' in data
    assert data['status'] == 'success'
    assert isinstance(data['structure'], list)

def test_workspace_structure_api_invalid_dir(client):
    """Test workspace structure API with invalid directory"""
    response = client.post('/workspace/structure', json={
        'workspace_id': 'invalid',
        'workspace_dir': '/invalid/path'
    })
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data

def test_process_prompt_api(client, temp_workspace, mock_model_response):
    # Create a workspace
    create_response = client.post('/workspace/create')
    workspace_data = json.loads(create_response.data)
    
    response = client.post('/process', json={
        'prompt': 'Create a test file',
        'workspace_id': workspace_data['workspace_id'],
        'model_id': 'deepseek',
        'workspace_dir': workspace_data['workspace_dir']
    })
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'status' in data
    assert data['status'] == 'success'
    assert 'explanation' in data
    assert 'operations' in data

def test_process_prompt_api_missing_prompt(client, temp_workspace):
    """Test process prompt API with missing prompt"""
    create_response = client.post('/workspace/create')
    workspace_data = json.loads(create_response.data)
    
    response = client.post('/process', json={
        'workspace_id': workspace_data['workspace_id'],
        'model_id': 'deepseek',
        'workspace_dir': workspace_data['workspace_dir']
    })
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'status' in data
    assert data['status'] == 'error'
    assert 'message' in data
    assert 'No prompt provided' in data['message']

def test_process_prompt_api_invalid_model(client, temp_workspace):
    """Test process prompt API with invalid model"""
    create_response = client.post('/workspace/create')
    workspace_data = json.loads(create_response.data)
    
    response = client.post('/process', json={
        'prompt': 'Create a test file',
        'workspace_id': workspace_data['workspace_id'],
        'model_id': 'invalid_model',
        'workspace_dir': workspace_data['workspace_dir']
    })
    assert response.status_code == 500
    data = json.loads(response.data)
    assert 'status' in data
    assert data['status'] == 'error'
    assert 'message' in data
    assert 'not configured' in data['message']

def test_chat_api(client, mock_model_response):
    # Create a workspace first
    create_response = client.post('/workspace/create')
    workspace_data = json.loads(create_response.data)
    
    response = client.post('/chat', json={
        'prompt': 'Hello',
        'model_id': 'deepseek',
        'workspace_dir': workspace_data['workspace_dir'],
        'attachments': []
    })
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'status' in data
    assert data['status'] == 'success'
    assert 'response' in data

def test_chat_api_missing_prompt(client, temp_workspace):
    """Test chat API with missing prompt"""
    create_response = client.post('/workspace/create')
    workspace_data = json.loads(create_response.data)
    
    response = client.post('/chat', json={
        'model_id': 'deepseek',
        'workspace_dir': workspace_data['workspace_dir'],
        'attachments': []
    })
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data

def test_chat_api_invalid_workspace(client):
    """Test chat API with invalid workspace"""
    response = client.post('/chat', json={
        'prompt': 'Hello',
        'model_id': 'deepseek',
        'workspace_dir': '/invalid/path',
        'attachments': []
    })
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data

def test_chat_api_with_attachments(client, mock_model_response, temp_workspace):
    """Test chat API with file attachments"""
    create_response = client.post('/workspace/create')
    workspace_data = json.loads(create_response.data)
    
    response = client.post('/chat', json={
        'prompt': 'Hello',
        'model_id': 'deepseek',
        'workspace_dir': workspace_data['workspace_dir'],
        'attachments': [
            {
                'name': 'test.txt',
                'content': 'test content'
            }
        ]
    })
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'status' in data
    assert data['status'] == 'success'
    assert 'response' in data

def test_models_api(client):
    response = client.get('/models')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'status' in data
    assert data['status'] == 'success'
    assert 'models' in data
    assert isinstance(data['models'], list)

def test_file_operations_api(client, temp_workspace):
    # Create a workspace
    create_response = client.post('/workspace/create')
    workspace_data = json.loads(create_response.data)
    workspace_id = workspace_data['workspace_id']
    workspace_dir = workspace_data['workspace_dir']
    
    # Create a test file
    test_file_path = os.path.join(workspace_dir, 'test.txt')
    with open(test_file_path, 'w') as f:
        f.write('test content')
    
    # Test file content retrieval
    response = client.post('/workspace/file', json={
        'workspace_id': workspace_id,
        'file_path': 'test.txt',
        'workspace_dir': workspace_dir
    })
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'status' in data
    assert data['status'] == 'success'
    assert 'content' in data
    assert data['content'] == 'test content'

def test_file_operations_api_invalid_file(client, temp_workspace):
    """Test file operations API with invalid file"""
    create_response = client.post('/workspace/create')
    workspace_data = json.loads(create_response.data)
    
    response = client.post('/workspace/file', json={
        'workspace_id': workspace_data['workspace_id'],
        'file_path': 'nonexistent.txt',
        'workspace_dir': workspace_data['workspace_dir']
    })
    assert response.status_code == 404
    data = json.loads(response.data)
    assert 'status' in data
    assert data['status'] == 'error'
    assert 'message' in data
    assert 'not found' in data['message'].lower()

def test_file_operations_api_invalid_workspace(client):
    """Test file operations API with invalid workspace"""
    response = client.post('/workspace/file', json={
        'workspace_id': 'invalid',
        'file_path': 'test.txt',
        'workspace_dir': '/invalid/path'
    })
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'status' in data
    assert data['status'] == 'error'
    assert 'message' in data
    assert 'invalid' in data['message'].lower()

def test_apply_changes_api(client, temp_workspace):
    # Create a workspace
    create_response = client.post('/workspace/create')
    workspace_data = json.loads(create_response.data)
    
    # Test applying changes
    response = client.post('/apply_changes', json={
        'workspace_dir': workspace_data['workspace_dir'],
        'operations': [{
            'type': 'create_file',
            'path': 'test.txt',
            'content': 'test content'
        }]
    })
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'status' in data
    assert data['status'] == 'success'
    assert 'structure' in data
    
    # Verify file was created
    test_file_path = os.path.join(workspace_data['workspace_dir'], 'test.txt')
    assert os.path.exists(test_file_path)
    with open(test_file_path, 'r') as f:
        assert f.read().strip() == 'test content'

def test_apply_changes_api_missing_params(client):
    """Test apply changes API with missing parameters"""
    response = client.post('/apply_changes', json={})
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data

def test_apply_changes_api_invalid_workspace(client):
    """Test apply changes API with invalid workspace"""
    response = client.post('/apply_changes', json={
        'workspace_dir': '/invalid/path',
        'operations': []
    })
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data

def test_static_files(client):
    """Test static file serving"""
    response = client.get('/logo.svg')
    assert response.status_code == 200
    assert response.mimetype == 'image/svg+xml'
    
    response = client.get('/favicon.png')
    assert response.status_code == 200
    assert response.mimetype == 'image/svg+xml' 