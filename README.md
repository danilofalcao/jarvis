# J.A.R.V.I.S. - AI Code Assistant

J.A.R.V.I.S. is an intelligent coding assistant that leverages multiple state-of-the-art language models to help you with code generation, modifications, and technical discussions.

## Features

- **Multi-Model Support**: Choose between different AI models for your coding needs:
  - DeepSeek Coder V3
  - Grok 2
  - Qwen 2.5 Coder
  - Codestral Mamba
  - Claude 3.5 Sonnet

- **File Attachment Support**:
  - PDF files with text extraction
  - Microsoft Word documents (.docx)
  - Excel spreadsheets with sheet parsing
  - Images with OCR capabilities
  - Enhanced Markdown with GFM support
  - All major programming languages
  - Configuration files
  - Text and documentation files
  - File preview with syntax highlighting
  - Multiple file upload support
  - Progress indicators and file size display
  - Type-specific icons and preview buttons

- **Real-Time Updates**:
  - WebSocket-based notifications
  - Instant feedback for code changes
  - Real-time workspace updates
  - Automatic change notifications

- **Workspace Management**:
  - Create and manage multiple workspaces
  - View workspace history
  - Delete workspaces when no longer needed
  - Rename workspaces
  - Browse workspace file structure

- **Code Generation & Modification**:
  - Generate new code based on natural language prompts
  - Modify existing code with AI assistance
  - Preview changes before applying them
  - View diffs of proposed changes

- **Interactive Chat**:
  - Discuss code and technical concepts
  - Get explanations about existing code
  - Context-aware responses based on workspace content
  - Attach files for additional context

## Technical Stack

- **Backend**:
  - Flask web framework
  - Flask-SocketIO for WebSocket support
  - Eventlet for async operations

- **Frontend**:
  - Pure JavaScript
  - TailwindCSS for styling
  - CodeMirror for code editing
  - Socket.IO client for real-time notifications
  - PDF.js for PDF processing
  - Mammoth.js for Word documents
  - XLSX.js for Excel files
  - Tesseract.js for OCR
  - Marked and Unified.js for Markdown

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up your environment variables in `.env`:
   ```
   DEEPSEEK_API_KEY=your_deepseek_api_key
   GROK_API_KEY=your_grok_api_key
   OPENROUTER_API_KEY=your_openrouter_api_key
   ANTHROPIC_API_KEY=your_anthropic_api_key
   ```

## Usage

1. Start the server:
   ```bash
   python app.py
   ```
2. Open your browser and navigate to `http://localhost:5000`
3. Create a new workspace or select an existing one
4. Choose your preferred AI model
5. Start coding with AI assistance!

## Model Capabilities

- **DeepSeek Coder V3**: Specialized in code generation and modification
- **Grok 2**: Advanced language model for code and natural language
- **Qwen 2.5 Coder**: Specialized 32B model for code generation
- **Codestral Mamba**: High-performance model with state-of-the-art reasoning and code generation capabilities
- **Claude 3.5 Sonnet**: Advanced reasoning and code understanding

## Contributing

Contributions are welcome! Please feel free to submit pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

## Testing

The project includes a comprehensive test suite with 100% code coverage. All components are thoroughly tested to ensure reliability and stability.

### Test Categories

1. API Tests (`tests/test_api.py`)
   - Endpoint functionality
   - Request/response validation
   - Error handling
   - File operations
   - Workspace management

2. Core Tests (`tests/test_core.py`)
   - Workspace creation/deletion
   - File system operations
   - Large file handling
   - Unicode support

3. Model Tests (`tests/test_models.py`)
   - AI model configuration
   - API integration
   - Response parsing
   - Error handling
   - Streaming responses

4. Utility Tests (`tests/test_utils.py`)
   - File preview generation
   - Dependency analysis
   - Code change application
   - Binary file handling

5. WebSocket Tests (`tests/test_websocket.py`)
   - Connection management
   - Event emission
   - Multi-client support
   - Reconnection handling

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-flask pytest-cov pytest-mock

# Run all tests with coverage report
python -m pytest -v --cov=. --cov-report=term-missing

# Run specific test file
python -m pytest tests/test_api.py -v

# Run specific test
python -m pytest tests/test_api.py::test_create_workspace_api -v

# Run tests matching a pattern
python -m pytest -v -k "websocket"
```

### Test Coverage

The test suite aims for 100% code coverage, testing:
- Happy paths (successful operations)
- Error cases and edge conditions
- File system operations
- Network requests and responses
- WebSocket events and reconnection
- Binary and text file handling
- Unicode and encoding support
- Large file operations
- Model API interactions

## Special Thanks

- **Nikole Cardoso** for her invaluable contributions and support
- **Guilherme Guirro** for his expertise and guidance
- **Felipe Santos** for his dedication and insights

Their contributions have been instrumental in making J.A.R.V.I.S. better.