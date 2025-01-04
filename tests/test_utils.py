import pytest
import os
from app import (
    get_workspace_context,
    analyze_dependencies,
    apply_changes,
    get_existing_files,
    get_file_preview,
    is_large_file,
    create_workspace
)

def test_get_workspace_context(temp_workspace):
    # Create test files
    test_file = os.path.join(temp_workspace, "test.py")
    with open(test_file, "w") as f:
        f.write("print('hello')")
    
    context = get_workspace_context(temp_workspace)
    assert isinstance(context, str)
    assert 'test.py' in context

def test_analyze_dependencies():
    files_content = {
        'main.py': 'import os\nimport sys\nfrom utils import helper',
        'utils.py': 'import json\nfrom datetime import datetime',
        'test.py': 'import pytest\nfrom main import function'
    }
    
    deps = analyze_dependencies(files_content)
    assert isinstance(deps, dict)
    assert 'main.py' in deps
    assert 'os' in deps['main.py']
    assert 'sys' in deps['main.py']
    assert 'utils' in deps['main.py']

def test_apply_changes(temp_workspace):
    suggestions = {
        'explanation': 'Test changes',
        'operations': [
            {
                'type': 'create_file',
                'path': 'test.txt',
                'content': 'test content'
            },
            {
                'type': 'create_file',
                'path': 'dir1/test2.txt',
                'content': 'test content 2'
            }
        ]
    }
    
    result = apply_changes(suggestions, temp_workspace)
    assert isinstance(result, dict)
    assert 'test.txt' in result
    assert 'dir1/test2.txt' in result
    assert result['test.txt']['is_new']
    assert result['dir1/test2.txt']['is_new']
    assert result['test.txt']['content'].strip() == 'test content'
    assert result['dir1/test2.txt']['content'].strip() == 'test content 2'
    
    # Verify files were created
    assert os.path.exists(os.path.join(temp_workspace, 'test.txt'))
    assert os.path.exists(os.path.join(temp_workspace, 'dir1/test2.txt'))

def test_get_existing_files(temp_workspace):
    # Create test files
    os.makedirs(os.path.join(temp_workspace, 'dir1'))
    with open(os.path.join(temp_workspace, 'test1.txt'), 'w') as f:
        f.write('test1')
    with open(os.path.join(temp_workspace, 'dir1/test2.txt'), 'w') as f:
        f.write('test2')
    
    files = get_existing_files(temp_workspace)
    assert isinstance(files, dict)
    assert 'test1.txt' in files
    assert 'dir1/test2.txt' in files
    assert files['test1.txt'] == 'test1'
    assert files['dir1/test2.txt'] == 'test2'

def test_apply_changes_with_invalid_operation(temp_workspace):
    suggestions = {
        'explanation': 'Test invalid operation',
        'operations': [
            {
                'type': 'invalid_operation',
                'path': 'test.txt',
                'content': 'test content'
            }
        ]
    }
    
    result = apply_changes(suggestions, temp_workspace)
    assert isinstance(result, dict)
    assert len(result) == 0  # Empty dict for invalid operation

def test_apply_changes_with_file_modifications(temp_workspace):
    # Create initial file
    test_file = os.path.join(temp_workspace, 'test.txt')
    with open(test_file, 'w') as f:
        f.write('initial content')
    
    suggestions = {
        'explanation': 'Modify existing file',
        'operations': [
            {
                'type': 'edit_file',
                'path': 'test.txt',
                'changes': [
                    {
                        'old': 'initial content',
                        'new': 'modified content'
                    }
                ]
            }
        ]
    }
    
    result = apply_changes(suggestions, temp_workspace)
    assert isinstance(result, dict)
    assert 'test.txt' in result
    assert not result['test.txt']['is_new']
    assert result['test.txt']['content'].strip() == 'modified content'
    
    # Verify file was modified
    with open(test_file, 'r') as f:
        content = f.read()
    assert content.strip() == 'modified content' 

def test_get_file_preview_binary(temp_workspace):
    """Test file preview with binary file"""
    binary_file = os.path.join(temp_workspace, "test.bin")
    
    # Create a binary file
    with open(binary_file, "wb") as f:
        f.write(b"\x00\x01\x02\x03")
    
    preview = get_file_preview(binary_file)
    assert "[Binary file]" in preview

def test_get_file_preview_large_file(temp_workspace):
    """Test file preview with large file"""
    large_file = os.path.join(temp_workspace, "large.txt")
    
    # Create a file with more than max_lines lines
    with open(large_file, "w") as f:
        for i in range(1100):  # More than default max_lines (1000)
            f.write(f"Line {i}\n")
    
    preview = get_file_preview(large_file)
    assert "file truncated" in preview

def test_get_file_preview_unicode(temp_workspace):
    """Test file preview with unicode content"""
    unicode_file = os.path.join(temp_workspace, "unicode.txt")
    content = "Hello 世界 🌍\nTest unicode support"
    
    with open(unicode_file, "w", encoding="utf-8") as f:
        f.write(content)
    
    preview = get_file_preview(unicode_file)
    assert "世界" in preview
    assert "🌍" in preview

def test_get_file_preview_encoding_fallback(temp_workspace):
    """Test file preview with different encodings"""
    test_file = os.path.join(temp_workspace, "test.txt")
    
    # Write content with latin-1 encoding
    content = bytes([i for i in range(32, 127)]).decode("latin-1")
    with open(test_file, "w", encoding="latin-1") as f:
        f.write(content)
    
    preview = get_file_preview(test_file)
    assert len(preview) > 0
    assert preview == content 