import pytest
import os
import tempfile
import shutil
from app import app as flask_app

@pytest.fixture
def app():
    # Configure app for testing
    flask_app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'WORKSPACE_ROOT': tempfile.mkdtemp()
    })
    
    # Set test API keys
    os.environ['DEEPSEEK_API_KEY'] = 'test_key'
    os.environ['OPENROUTER_API_KEY'] = 'test_key'
    os.environ['ANTHROPIC_API_KEY'] = 'test_key'
    os.environ['GROK_API_KEY'] = 'test_key'
    
    yield flask_app
    
    # Cleanup
    shutil.rmtree(flask_app.config['WORKSPACE_ROOT'])

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def temp_workspace(app):
    workspace_path = tempfile.mkdtemp(dir=app.config['WORKSPACE_ROOT'])
    yield workspace_path
    if os.path.exists(workspace_path):
        shutil.rmtree(workspace_path)

@pytest.fixture
def mock_model_response(mocker):
    def _mock_response(content='{"explanation": "Test", "operations": []}'):
        mock_completion = mocker.MagicMock()
        mock_completion.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(
                    content=content
                )
            )
        ]
        return mock_completion
    
    # Mock OpenAI client
    mock_openai = mocker.patch('openai.OpenAI')
    mock_openai.return_value.chat.completions.create.return_value = _mock_response()
    
    # Mock Anthropic client
    mock_anthropic = mocker.patch('anthropic.Anthropic')
    mock_anthropic.return_value.messages.create.return_value = mocker.MagicMock(
        content=[mocker.MagicMock(text='{"explanation": "Test", "operations": []}')])
    
    return _mock_response 