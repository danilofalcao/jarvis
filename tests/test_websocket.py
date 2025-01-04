import pytest
from flask_socketio import SocketIOTestClient
from app import socketio, app

@pytest.fixture
def socket_client(client):
    return SocketIOTestClient(app, socketio)

def test_socket_connection(socket_client):
    """Test WebSocket connection"""
    assert socket_client.is_connected()

def test_changes_applied_event(socket_client, temp_workspace):
    """Test changes_applied event emission"""
    workspace_id = 'test_workspace'
    modified_files = ['test.txt', 'dir1/test2.txt']
    
    # Emit the event
    socketio.emit('changes_applied', {
        'workspace_id': workspace_id,
        'modified_files': modified_files
    })
    
    # Get the received event
    received = socket_client.get_received()
    assert len(received) > 0
    assert received[0]['name'] == 'changes_applied'
    assert received[0]['args'][0]['workspace_id'] == workspace_id
    assert received[0]['args'][0]['modified_files'] == modified_files

def test_socket_error_handling(socket_client):
    """Test WebSocket error handling"""
    # Test with invalid event data
    socketio.emit('changes_applied', {})  # Empty data instead of None
    received = socket_client.get_received()
    assert len(received) == 1  # Event is still emitted but with empty data
    assert received[0]['name'] == 'changes_applied'
    assert len(received[0]['args']) == 1
    assert isinstance(received[0]['args'][0], dict)
    assert 'workspace_id' not in received[0]['args'][0]
    assert 'modified_files' not in received[0]['args'][0]

def test_multiple_clients(client):
    """Test multiple WebSocket clients"""
    client1 = SocketIOTestClient(app, socketio)
    client2 = SocketIOTestClient(app, socketio)
    
    assert client1.is_connected()
    assert client2.is_connected()
    
    # Emit event
    workspace_id = 'test_workspace'
    modified_files = ['test.txt']
    socketio.emit('changes_applied', {
        'workspace_id': workspace_id,
        'modified_files': modified_files
    })
    
    # Check both clients received the event
    for client in [client1, client2]:
        received = client.get_received()
        assert len(received) > 0
        assert received[0]['name'] == 'changes_applied'
        assert received[0]['args'][0]['workspace_id'] == workspace_id
        assert received[0]['args'][0]['modified_files'] == modified_files

def test_socket_disconnect(socket_client):
    """Test WebSocket disconnection"""
    assert socket_client.is_connected()
    socket_client.disconnect()
    assert not socket_client.is_connected() 

def test_socket_status_events(socket_client):
    """Test status event emission"""
    # Test different status messages
    messages = [
        {'message': 'Creating new workspace...', 'step': 0},
        {'message': 'Reading workspace files...', 'step': 1},
        {'message': 'Processing AI response...', 'step': 3},
        {'message': 'Ready for review', 'step': 5}
    ]
    
    for msg in messages:
        socketio.emit('status', msg)
        received = socket_client.get_received()
        assert len(received) > 0
        assert received[0]['name'] == 'status'
        assert received[0]['args'][0] == msg

def test_socket_progress_events(socket_client):
    """Test progress event emission"""
    progress_data = {'message': 'Received 100 tokens...', 'tokens': 100}
    socketio.emit('progress', progress_data)
    
    received = socket_client.get_received()
    assert len(received) > 0
    assert received[0]['name'] == 'progress'
    assert received[0]['args'][0] == progress_data

def test_socket_error_events(socket_client):
    """Test error event emission"""
    error_data = {'message': 'Test error', 'step': -1}
    socketio.emit('error', error_data)
    
    received = socket_client.get_received()
    assert len(received) > 0
    assert received[0]['name'] == 'error'
    assert received[0]['args'][0] == error_data

def test_socket_reconnection(socket_client):
    """Test socket reconnection handling"""
    # Simulate disconnect
    socket_client.disconnect()
    assert not socket_client.is_connected()
    
    # Reconnect
    socket_client.connect()
    assert socket_client.is_connected()
    
    # Test event after reconnection
    socketio.emit('status', {'message': 'Test after reconnect', 'step': 1})
    received = socket_client.get_received()
    assert len(received) > 0
    assert received[0]['args'][0]['message'] == 'Test after reconnect' 