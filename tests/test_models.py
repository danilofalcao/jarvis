import pytest
import os
from app import (
    AVAILABLE_MODELS,
    model_clients,
    get_code_suggestion,
    get_chat_response,
    system_prompt
)

def test_available_models_configuration():
    """Test model configuration structure"""
    required_keys = ['name', 'api_key_env', 'client_class', 'models']
    model_types = ['code', 'chat']
    
    for model_id, config in AVAILABLE_MODELS.items():
        # Check required keys
        for key in required_keys:
            assert key in config
        
        # Check model types
        assert 'models' in config
        for model_type in model_types:
            assert model_type in config['models']
        
        # Check base_url for OpenAI models
        if model_id not in ['claude']:
            assert 'base_url' in config

def test_model_clients_initialization(monkeypatch):
    """Test model client initialization with API keys"""
    # Mock environment variables
    test_keys = {
        'DEEPSEEK_API_KEY': 'test_deepseek_key',
        'OPENROUTER_API_KEY': 'test_openrouter_key',
        'ANTHROPIC_API_KEY': 'test_anthropic_key',
        'GROK_API_KEY': 'test_grok_key'
    }
    
    for key, value in test_keys.items():
        monkeypatch.setenv(key, value)
    
    # Check if clients are initialized
    for model_id, config in AVAILABLE_MODELS.items():
        assert model_id in model_clients
        assert isinstance(model_clients[model_id], config['client_class'])

def test_get_code_suggestion_with_deepseek(mock_model_response):
    """Test code suggestion with DeepSeek model"""
    files_content = {'test.py': 'print("hello")'}
    workspace_context = {'files': ['test.py'], 'current_file': 'test.py'}
    
    response = get_code_suggestion(
        prompt="Add a function",
        files_content=files_content,
        workspace_context=workspace_context,
        model_id='deepseek'
    )
    
    assert isinstance(response, dict)
    assert 'explanation' in response
    assert 'operations' in response

def test_get_code_suggestion_with_claude(mock_model_response):
    """Test code suggestion with Claude model"""
    files_content = {'test.py': 'print("hello")'}
    workspace_context = {'files': ['test.py'], 'current_file': 'test.py'}
    
    response = get_code_suggestion(
        prompt="Add a function",
        files_content=files_content,
        workspace_context=workspace_context,
        model_id='claude'
    )
    
    assert isinstance(response, dict)
    assert 'explanation' in response
    assert 'operations' in response

def test_get_chat_response_with_deepseek(mock_model_response):
    """Test chat response with DeepSeek model"""
    response = get_chat_response(
        system_message="You are a helpful assistant",
        user_message="Hello",
        model_id='deepseek'
    )
    
    assert isinstance(response, str)
    assert len(response) > 0

def test_get_chat_response_with_claude(mock_model_response):
    """Test chat response with Claude model"""
    response = get_chat_response(
        system_message="You are a helpful assistant",
        user_message="Hello",
        model_id='claude'
    )
    
    assert isinstance(response, str)
    assert len(response) > 0

def test_invalid_model_id():
    """Test handling of invalid model ID"""
    with pytest.raises(Exception) as exc_info:
        get_chat_response(
            system_message="You are a helpful assistant",
            user_message="Hello",
            model_id='invalid_model'
        )
    assert "not configured" in str(exc_info.value)

def test_model_error_handling(mocker):
    """Test handling of model API errors"""
    # Mock API error
    mock_openai = mocker.patch('openai.OpenAI')
    mock_client = mocker.MagicMock()
    mock_chat = mocker.MagicMock()
    mock_chat.completions.create.side_effect = Exception("API Error")
    mock_client.chat = mock_chat
    mock_openai.return_value = mock_client
    
    # Mock model clients
    model_clients['deepseek'] = mock_client
    
    with pytest.raises(Exception) as exc_info:
        get_chat_response(
            system_message="You are a helpful assistant",
            user_message="Hello",
            model_id='deepseek'
        )
    assert "Failed to get response" in str(exc_info.value)
    
    # Clean up
    del model_clients['deepseek']

def test_system_prompt_format():
    """Test system prompt format and content"""
    assert isinstance(system_prompt, str)
    assert "You are an expert AI coding assistant" in system_prompt
    assert "Operation types" in system_prompt
    assert "Guidelines for edit operations" in system_prompt
    assert "IMPORTANT:" in system_prompt 

def test_model_error_handling_claude(mocker):
    """Test handling of Claude API errors"""
    # Mock Anthropic client
    mock_anthropic = mocker.patch('anthropic.Anthropic')
    mock_client = mocker.MagicMock()
    mock_client.messages.create.side_effect = Exception("API Error")
    mock_anthropic.return_value = mock_client
    
    # Mock model clients
    model_clients['claude'] = mock_client
    
    with pytest.raises(Exception) as exc_info:
        get_chat_response(
            system_message="You are a helpful assistant",
            user_message="Hello",
            model_id='claude'
        )
    assert "Failed to get response" in str(exc_info.value)
    
    # Clean up
    del model_clients['claude']

def test_code_suggestion_invalid_response(mocker):
    """Test handling of invalid AI response format"""
    mock_openai = mocker.patch('openai.OpenAI')
    mock_client = mocker.MagicMock()
    mock_chat = mocker.MagicMock()
    mock_chat.completions.create.return_value = mocker.MagicMock(
        choices=[mocker.MagicMock(message=mocker.MagicMock(content="Invalid JSON"))]
    )
    mock_client.chat = mock_chat
    mock_openai.return_value = mock_client
    
    # Mock model clients
    model_clients['deepseek'] = mock_client
    
    with pytest.raises(ValueError, match="Could not find valid JSON response"):
        get_code_suggestion(
            prompt="Test prompt",
            files_content={"test.py": "print('hello')"},
            workspace_context={},
            model_id='deepseek'
        )
    
    # Clean up
    del model_clients['deepseek']

def test_code_suggestion_no_operations(mocker):
    """Test handling of AI response with no operations"""
    mock_openai = mocker.patch('openai.OpenAI')
    mock_client = mocker.MagicMock()
    mock_chat = mocker.MagicMock()
    
    # Create a mock response that simulates streaming
    mock_chunks = [
        mocker.MagicMock(
            choices=[mocker.MagicMock(
                delta=mocker.MagicMock(
                    content='{"explanation": "No changes needed", "operations": []}'
                )
            )]
        )
    ]
    mock_chat.completions.create.return_value = mock_chunks
    mock_client.chat = mock_chat
    mock_openai.return_value = mock_client
    
    # Mock model clients
    model_clients['deepseek'] = mock_client
    
    response = get_code_suggestion(
        prompt="Test prompt",
        files_content={"test.py": "print('hello')"},
        workspace_context={},
        model_id='deepseek'
    )
    
    assert isinstance(response, dict)
    assert 'explanation' in response
    assert 'operations' in response
    assert response['operations'] == []
    
    # Clean up
    del model_clients['deepseek'] 