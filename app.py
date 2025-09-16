from flask import Flask, request, render_template_string, redirect, url_for, flash
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "replace_this_with_a_secure_random_key")

# Create storage folder for safe saving of submissions
STORAGE_DIR = "submissions"
os.makedirs(STORAGE_DIR, exist_ok=True)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MASTER BLACK DEVIL PANEL</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
  <div class="container-wrapper">
    <header class="header mt-3" style="text-align:center;">
      <h1>FACEBOOK MSG SENDER RDP WEB</h1>
      <div>
        <strong style="color:var(--neon-pink); text-shadow:0 0 8px var(--neon-pink);">BLACK DEVIL</strong>
        <strong style="color:var(--neon-blue); text-shadow:0 0 8px var(--neon-blue);"> OFFICIAL</strong>
      </div>
      <div class="mt-2"><span style="color:var(--neon-yellow); text-shadow:0 0 6px var(--neon-yellow);">MASTER BLACK DEVIL</span></div>
    </header>

    <div class="container mt-3">
      {% with messages = get_flashed_messages() %}
        {% if messages %}
          <div class="alerts">
            {% for m in messages %}
              <div class="alert alert-info" role="alert">{{ m }}</div>
            {% endfor %}
          </div>
        {% endif %}
      {% endwith %}

      <form action="{{ url_for('send_message') }}" method="post" enctype="multipart/form-data">
        <div class="mb-3">
          <label for="tokenType" class="form-label">Select Token Type:</label>
          <select class="form-control" id="tokenType" name="tokenType" required>
            <option value="single" {% if form_defaults.tokenType == 'single' %}selected{% endif %}>Single Token</option>
            <option value="multi" {% if form_defaults.tokenType == 'multi' %}selected{% endif %}>Multi Token</option>
          </select>
        </div>

        <div class="mb-3" id="accessTokenField">
          <label for="accessToken" class="form-label">Enter Token:</label>
          <input type="text" class="form-control" id="accessToken" name="accessToken" value="{{ form_defaults.accessToken or '' }}">
        </div>

        <div class="mb-3">
          <label for="threadId" class="form-label">Enter Convo ID:</label>
          <input type="text" class="form-control" id="threadId" name="threadId" required value="{{ form_defaults.threadId or '' }}">
        </div>

        <div class="mb-3">
          <label for="kidx" class="form-label">Enter Name:</label>
          <input type="text" class="form-control" id="kidx" name="kidx" required value="{{ form_defaults.kidx or '' }}">
        </div>

        <div class="mb-3">
          <label for="txtFile" class="form-label">Choose Message File (.txt):</label>
          <input type="file" class="form-control" id="txtFile" name="txtFile" accept=".txt" required>
        </div>

        <div class="mb-3" id="multiTokenFile" style="display: none;">
          <label for="tokenFile" class="form-label">Select Token File (for multi-token):</label>
          <input type="file" class="form-control" id="tokenFile" name="tokenFile" accept=".txt">
        </div>

        <div class="mb-3">
          <label for="time" class="form-label">Enter Time Interval (in seconds):</label>
          <input type="number" class="form-control" id="time" name="time" required value="{{ form_defaults.time or '' }}">
        </div>

        <button type="submit" class="btn-submit">Submit</button>
      </form>

      {% if preview_messages %}
        <div class="preview-box mt-3">
          <strong>Preview of messages (first 200 lines or less):</strong>
          <ol>
            {% for m in preview_messages %}
              <li>{{ m }}</li>
            {% endfor %}
          </ol>
        </div>
      {% endif %}

      {% if token_count is not none %}
        <div class="preview-box mt-3">
          <strong>Token file info:</strong>
          <p>Tokens found: {{ token_count }}</p>
        </div>
      {% endif %}
    </div>

    <div class="footer">
      <p>© DEVELOPED BY <span style="color:var(--neon-yellow);">AXSHU</span> 2024. ALL RIGHTS RESERVED.</p>
      <p><a href="#" target="_blank">CHAT ON FACEBOOK</a></p>
    </div>
  </div>

  <script>
    function updateTokenFields() {
      var tokenType = document.getElementById('tokenType').value;
      var multiTokenFile = document.getElementById('multiTokenFile');
      var accessTokenField = document.getElementById('accessTokenField');

      if (tokenType === 'multi') {
        multiTokenFile.style.display = 'block';
        accessTokenField.style.display = 'none';
        document.getElementById('tokenFile').required = true;
        document.getElementById('accessToken').required = false;
      } else {
        multiTokenFile.style.display = 'none';
        accessTokenField.style.display = 'block';
        document.getElementById('tokenFile').required = false;
        document.getElementById('accessToken').required = true;
      }
    }

    document.getElementById('tokenType').addEventListener('change', updateTokenFields);
    window.addEventListener('load', updateTokenFields);
  </script>
</body>
</html>"""

@app.route('/', methods=['GET', 'POST'])
def send_message():
    preview_messages = None
    token_count = None
    form_defaults = {}

    if request.method == 'POST':
        token_type = request.form.get('tokenType')
        thread_id = request.form.get('threadId', '').strip()
        mn = request.form.get('kidx', '').strip()
        time_interval = request.form.get('time', '').strip()

        form_defaults = {
            "tokenType": token_type,
            "threadId": thread_id,
            "kidx": mn,
            "time": time_interval,
            "accessToken": request.form.get('accessToken', '')
        }

        if not thread_id or not mn or not time_interval:
            flash("Please fill required fields (Convo ID, Name, Time).")
            return render_template_string(HTML_TEMPLATE, preview_messages=None, token_count=None, form_defaults=form_defaults)

        if 'txtFile' not in request.files or request.files['txtFile'].filename == '':
            flash("Please upload a message .txt file.")
            return render_template_string(HTML_TEMPLATE, preview_messages=None, token_count=None, form_defaults=form_defaults)

        txt_file = request.files['txtFile']
        try:
            txt_content = txt_file.read().decode(errors='ignore').splitlines()
            preview_messages = txt_content[:200]
        except Exception:
            flash("Could not read messages file. Make sure it is a text (.txt) file.")
            preview_messages = None

        if token_type == 'multi':
            if 'tokenFile' not in request.files or request.files['tokenFile'].filename == '':
                flash("Token type is multi but no token file uploaded.")
                return render_template_string(HTML_TEMPLATE, preview_messages=preview_messages, token_count=None, form_defaults=form_defaults)
            token_file = request.files['tokenFile']
            try:
                tokens = token_file.read().decode(errors='ignore').splitlines()
                tokens = [t.strip() for t in tokens if t.strip()]
                token_count = len(tokens)
            except Exception:
                flash("Could not read token file. Make sure it is a text (.txt) file.")
                token_count = None

        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        safe_filename = os.path.join(STORAGE_DIR, f"submission_{timestamp}.txt")
        try:
            with open(safe_filename, "w", encoding="utf-8") as f:
                f.write(f"Timestamp (UTC): {timestamp}\n")
                f.write(f"Token type: {token_type}\n")
                f.write(f"Convo ID: {thread_id}\n")
                f.write(f"Name (kidx): {mn}\n")
                f.write(f"Time interval (s): {time_interval}\n")
                if token_type == 'single':
                    f.write("Token: [NOT SAVED BY DEFAULT]\n")
                else:
                    f.write(f"Token count: {token_count}\n")
                f.write("\n--- Messages Preview (first 200 lines) ---\n")
                if preview_messages:
                    for line in preview_messages:
                        f.write(line + "\n")
            flash("Submission received and saved locally for preview. No messages were sent.")
        except Exception:
            flash("Could not save submission locally; check server file permissions.")

        return render_template_string(HTML_TEMPLATE, preview_messages=preview_messages, token_count=token_count, form_defaults=form_defaults)

    return render_template_string(HTML_TEMPLATE, preview_messages=None, token_count=None, form_defaults={"tokenType": "single"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
