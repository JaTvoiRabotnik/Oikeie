document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('userForm');
    const messageDiv = document.getElementById('message');

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const name = document.getElementById('name').value.trim();
        const email = document.getElementById('email').value.trim();

        if (!name || !email) {
            showMessage('Please fill in all fields', 'danger');
            return;
        }

        if (!isValidEmail(email)) {
            showMessage('Please enter a valid email address', 'danger');
            return;
        }

        // Submit form data
        fetch('/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({
                'name': name,
                'email': email
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showMessage(data.message, 'success');
                form.reset();
            } else {
                showMessage(data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showMessage('An error occurred. Please try again later.', 'danger');
        });
    });

    function showMessage(message, type) {
        messageDiv.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
    }

    function isValidEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }
});
