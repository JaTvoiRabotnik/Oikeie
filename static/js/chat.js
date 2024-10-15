document.addEventListener('DOMContentLoaded', () => {
    const socket = io();
    const chatContainer = document.getElementById('chat-container');
    const messageForm = document.getElementById('message-form');
    const messageInput = document.getElementById('message-input');

    // Get handle from the data attribute
    const handle = document.getElementById('chat-container').dataset.handle;
    const room = 'general';

    // Join the chat room
    socket.emit('join', { handle, room });

    // Handle incoming messages
    socket.on('message', (data) => {
        const messageElement = document.createElement('div');
        messageElement.textContent = `${data.handle}: ${data.message}`;
        chatContainer.appendChild(messageElement);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    });

    // Handle status messages
    socket.on('status', (data) => {
        const statusElement = document.createElement('div');
        statusElement.textContent = data.msg;
        statusElement.style.fontStyle = 'italic';
        chatContainer.appendChild(statusElement);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    });

    // Send message
    messageForm.addEventListener('submit', (e) => {
        e.preventDefault();
        if (messageInput.value.trim()) {
            socket.emit('chat_message', { handle, room, message: messageInput.value });
            messageInput.value = '';
        }
    });

    // Handle page unload
    window.addEventListener('beforeunload', () => {
        socket.emit('leave', { handle, room });
    });
});
