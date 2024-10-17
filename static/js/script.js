document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('userForm');
    const messageDiv = document.getElementById('message');

    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const name = document.getElementById('name')?.value.trim();
            const email = document.getElementById('email')?.value.trim();

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
    } else {
        console.error('Form element not found');
    }

    function showMessage(message, type) {
        if (messageDiv) {
            messageDiv.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
        } else {
            console.error('Message div not found');
        }
    }

    function isValidEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }

    // Add global error handler
    window.addEventListener('error', function(event) {
        console.error('Global error:', event.error);
    });
});
