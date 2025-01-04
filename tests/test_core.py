import pytest
import os
import json
import shutil
from app import (
    create_workspace,
    get_workspace_history,
    delete_workspace,
    get_workspace_structure,
    get_file_size,
    read_file_in_chunks,
    is_large_file
)

def test_create_workspace(temp_workspace):
    workspace_id, workspace_path = create_workspace()
    assert os.path.exists(workspace_path)
    assert workspace_id in workspace_path

def test_get_workspace_history(temp_workspace):
    # Create a test workspace
    workspace_id, workspace_path = create_workspace()
    
    # Create a test file in the workspace
    test_file = os.path.join(workspace_path, "test.txt")
    with open(test_file, "w") as f:
        f.write("test content")
    
    history = get_workspace_history()
    assert len(history) > 0
    assert any(ws['id'] == workspace_id for ws in history)

def test_delete_workspace(temp_workspace):
    workspace_id, workspace_path = create_workspace()
    assert os.path.exists(workspace_path)
    
    delete_workspace(workspace_id)
    assert not os.path.exists(workspace_path)

def test_get_workspace_structure(temp_workspace):
    workspace_id, workspace_path = create_workspace()
    
    # Create test directory structure
    os.makedirs(os.path.join(workspace_path, "dir1"))
    os.makedirs(os.path.join(workspace_path, "dir1/subdir"))
    
    with open(os.path.join(workspace_path, "file1.txt"), "w") as f:
        f.write("test")
    with open(os.path.join(workspace_path, "dir1/file2.txt"), "w") as f:
        f.write("test")
    
    structure = get_workspace_structure(workspace_path)
    
    assert any(item["path"] == "dir1" for item in structure)
    assert any(item["path"] == "file1.txt" for item in structure)
    assert any(item["path"] == os.path.join("dir1", "file2.txt") for item in structure)

def test_file_operations(temp_workspace):
    workspace_id, workspace_path = create_workspace()
    test_file = os.path.join(workspace_path, "test.txt")
    
    # Test file creation and size
    content = "test content" * 1000
    with open(test_file, "w") as f:
        f.write(content)
    
    assert get_file_size(test_file) > 0
    assert is_large_file(test_file, threshold_mb=0.001)  # Small threshold to test
    
    # Test reading in chunks
    chunks = list(read_file_in_chunks(test_file, chunk_size=100))
    assert len(chunks) > 1
    assert "".join(chunks) == content 

def test_delete_workspace_invalid_path():
    """Test deleting workspace with invalid path"""
    with pytest.raises(Exception, match="Invalid workspace path"):
        delete_workspace("../invalid")

def test_delete_workspace_permission_error(temp_workspace, mocker):
    """Test deleting workspace with permission error"""
    workspace_id, workspace_path = create_workspace()
    
    # Mock shutil.rmtree to raise PermissionError
    mocker.patch('shutil.rmtree', side_effect=PermissionError("Permission denied"))
    
    with pytest.raises(Exception, match="Failed to delete workspace directory"):
        delete_workspace(workspace_id)

def test_delete_workspace_failed_removal(temp_workspace, mocker):
    """Test when workspace directory still exists after deletion attempt"""
    workspace_id, workspace_path = create_workspace()
    
    # Mock os.path.exists to always return True
    mocker.patch('os.path.exists', return_value=True)
    
    with pytest.raises(Exception, match="Failed to delete workspace directory"):
        delete_workspace(workspace_id) 

def test_get_file_size_nonexistent():
    """Test getting size of nonexistent file"""
    assert get_file_size("nonexistent.txt") == 0

def test_read_file_in_chunks_large_file(temp_workspace):
    """Test reading large file in chunks"""
    # Create a large test file
    workspace_id, workspace_path = create_workspace()
    test_file = os.path.join(workspace_path, "large.txt")
    content = "x" * 1024 * 1024  # 1MB of data
    
    with open(test_file, "w") as f:
        f.write(content)
    
    chunks = list(read_file_in_chunks(test_file, chunk_size=1024))
    assert len(chunks) > 1
    assert "".join(chunks) == content

def test_read_file_in_chunks_unicode(temp_workspace):
    """Test reading file with unicode characters"""
    workspace_id, workspace_path = create_workspace()
    test_file = os.path.join(workspace_path, "unicode.txt")
    content = "Hello 世界 🌍"
    
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(content)
    
    chunks = list(read_file_in_chunks(test_file))
    assert "".join(chunks) == content

def test_is_large_file_threshold(mocker):
    """Test large file threshold detection"""
    # Mock file size to be just above and below threshold
    def mock_size(size):
        return lambda x: size
    
    # Test file just below threshold (5MB)
    with mocker.patch('app.get_file_size', new=mock_size(5 * 1024 * 1024 - 1)):
        assert not is_large_file("test.txt")
    
    # Test file just above threshold
    with mocker.patch('app.get_file_size', new=mock_size(5 * 1024 * 1024 + 1)):
        assert is_large_file("test.txt") 