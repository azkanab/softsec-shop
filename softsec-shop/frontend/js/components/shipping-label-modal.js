const cancelReturnBtn = document.getElementById('cancelReturnBtn');
const loading = document.getElementById('loadingSpinner');
const labelModal = document.getElementById('labelModal');
const labelImage = document.getElementById('labelImage');
const printSendBtn = document.getElementById('printSendBtn');
const closeModalBtn = document.getElementById('closeModalBtn');
const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

let currentOrderToken = '';
let timerInterval = null;

// Function to count elapsed time since cancellation
function startCountdownTimer(cancellationTime) {
        const returnTimer = document.getElementById('returnTimer');
        const timerDisplay = document.getElementById('timerDisplay');

        if (!returnTimer || !timerDisplay) return;

        // Show the timer
        returnTimer.style.display = 'block';

        // Clear any existing timer
        if (timerInterval) {
                clearInterval(timerInterval);
        }

        // Get cancellation time in UTC
        const cancellationDate = new Date(cancellationTime);

        // Update timer every second
        timerInterval = setInterval(() => {
                // Get current time in UTC
                const now = new Date();
                const nowUTC = new Date(now.getTime() + (now.getTimezoneOffset() * 60 * 1000));

                // Calculate time elapsed since cancellation
                const timeElapsed = nowUTC - cancellationDate;

                if (timeElapsed < 0) {
                        timerDisplay.textContent = '00:00:00';
                        return;
                }

                // Calculate hours, minutes, seconds
                const hours = Math.floor(timeElapsed / (1000 * 60 * 60));
                const minutes = Math.floor((timeElapsed % (1000 * 60 * 60)) / (1000 * 60));
                const seconds = Math.floor((timeElapsed % (1000 * 60)) / 1000);

                // Display timer
                timerDisplay.textContent = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        }, 1000);
}

if (cancelReturnBtn) {
        cancelReturnBtn.addEventListener('click', function(e) {
                e.preventDefault();
                currentOrderToken = this.getAttribute('data-token');

                loading.style.display = 'flex';

                // Call API
                fetch(`/orders/cancel_return/${currentOrderToken}`, {
                        method: 'POST',
                        headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': csrfToken
                        }
                })
                .then(response => response.json())
                .then(data => {
                        loading.style.display = 'none';
                        if (data.success) {
                                labelImage.src = data.shipping_label_url;
                                labelModal.style.display = 'flex';

                                // Start countdown timer
                                if (data.cancellation_time) {
                                        startCountdownTimer(data.cancellation_time);
                                }
                        } else {
                                alert('Error processing return. Please try again.');
                        }
                })
                .catch(error => {
                        loading.style.display = 'none';
                        console.error('Error:', error);
                        alert('Error fetching');
                });
        });
}

if (printSendBtn) {
        printSendBtn.addEventListener('click', function() {
                fetch(`/orders/send_return/${currentOrderToken}`, {
                method: 'POST',
                headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                }
                })
                .then(response => response.json())
                .then(data => {
                if (data.success) {
                        labelModal.style.display = 'none';

                        window.location.reload();
                } else {
                        alert('Error sending return. Please try again.');
                }
                })
                .catch(error => {
                        console.error('Error:', error);
                        alert('Error fetching send-return');
                });
        });
}

if (closeModalBtn) {
        closeModalBtn.addEventListener('click', function() {
                labelModal.style.display = 'none';
                window.location.reload();
        });
}

labelModal.addEventListener('click', function(e) {
        if (e.target === labelModal) {
                labelModal.style.display = 'none';
        }
});

const returnTimer = document.getElementById('returnTimer');
if (returnTimer) {
        const cancellationTime = returnTimer.getAttribute('data-cancellation-time');
        if (cancellationTime) {
                startCountdownTimer(cancellationTime);
        }
}