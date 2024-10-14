document.addEventListener('DOMContentLoaded', () => {
    const socket = io();
    const chatContainer = document.getElementById('chat-container');
    const messageForm = document.getElementById('message-form');
    const messageInput = document.getElementById('message-input');

    // Get username and room from URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const username = urlParams.get('username');
    const room = urlParams.get('room') || 'general';

    // Join the chat room
    socket.emit('join', { username, room });

    // Handle incoming messages
    socket.on('message', (data) => {
        const messageElement = document.createElement('div');
        messageElement.textContent = `${data.username}: ${data.message}`;
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

        if (data.msg.includes('not verified')) {
            messageForm.style.display = 'none';
            const verifyMessage = document.createElement('div');
            verifyMessage.textContent = 'Please check your email to verify your account before joining the chat.';
            verifyMessage.classList.add('alert', 'alert-warning', 'mt-3');
            document.body.appendChild(verifyMessage);
        }
    });

    // Send message
    messageForm.addEventListener('submit', (e) => {
        e.preventDefault();
        if (messageInput.value.trim()) {
            socket.emit('message', { username, room, message: messageInput.value });
            messageInput.value = '';
        }
    });

    // Handle page unload
    window.addEventListener('beforeunload', () => {
        socket.emit('leave', { username, room });
    });
});
