// Get elements
const statusBox = document.getElementById('sessionStatusBox');
const sessionInput = document.getElementById('sessionKeyInput');

// Fetch session status and update box
function checkStatus() {
    const key = sessionInput.value.trim();
    if (!key) {
        alert("Enter a session key!");
        return;
    }

    fetch(`/session/${key}`)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                statusBox.innerHTML = `<p style="color:red;">${data.error}</p>`;
                return;
            }

            let html = `<p>Status: <strong>${data.status}</strong></p>`;
            html += `<p>Messages sent logs (last 20):</p><ol>`;
            const logs = data.logs || [];
            const recentLogs = logs.slice(-20); // show last 20 logs
            recentLogs.forEach(log => {
                if (log.error) {
                    html += `<li style="color:red;">${log.message} => ERROR: ${log.error}</li>`;
                } else {
                    html += `<li>${log.message} => Status: ${log.status}</li>`;
                }
            });
            html += `</ol>`;
            statusBox.innerHTML = html;
        })
        .catch(err => {
            statusBox.innerHTML = `<p style="color:red;">Error fetching session: ${err}</p>`;
        });
}

// Perform session action: pause, resume, stop
function sessionAction(action) {
    const key = sessionInput.value.trim();
    if (!key) {
        alert("Enter a session key!");
        return;
    }

    fetch(`/session/${key}/${action}`, { method: "POST" })
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                alert(`Error: ${data.error}`);
            } else {
                alert(`Session ${action}ed. Current status: ${data.status}`);
                checkStatus();
            }
        })
        .catch(err => {
            alert(`Error performing action: ${err}`);
        });
}

// Auto-refresh status every 5 seconds
setInterval(() => {
    const key = sessionInput.value.trim();
    if (key) checkStatus();
}, 5000);
