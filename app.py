# app.py
from flask import Flask, request, render_template_string, redirect, url_for, flash, session
import os
from datetime import datetime
import uuid

app = Flask(__name__)
app.debug = True
app.secret_key = os.urandom(24)

STORAGE_DIR = "submissions"
os.makedirs(STORAGE_DIR, exist_ok=True)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
<title>MASTER BLACK DEVIL PANEL</title>
<link href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css\" rel=\"stylesheet\">
<link rel=\"stylesheet\" href=\"https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css\">
<style>
/* Add full neon CSS and styling here */
</style>
</head>
<body>
<div class=\"container-wrapper\">
<header class=\"header\"> <!-- header content --> </header>
<div class=\"container\">
<form method=\"post\" enctype=\"multipart/form-data\">
<!-- form content -->
</form>
</div>
<footer class=\"footer\"> <!-- footer content --> </footer>
</div>
<script>
// JS for token fields and scrolling
</script>
</body>
</html>
"""

@app.route('/', methods=['GET','POST'])
def send_message():
    # Initialize defaults
    preview_messages = None
    token_count = None
    form_defaults = {}

    if request.method == 'POST':
        # Handle form submission and safe storage
        token_type = request.form.get('tokenType')
        thread_id = request.form.get('threadId','').strip()
        mn = request.form.get('kidx','').strip()
        time_interval = request.form.get('time','').strip()

        form_defaults = {"tokenType": token_type, "threadId": thread_id, "kidx": mn, "time": time_interval, "accessToken": request.form.get('accessToken','')}

        # Validate required fields
        if not thread_id or not mn or not time_interval:
            flash("Please fill required fields.")
            return render_template_string(HTML_TEMPLATE, preview_messages=None, token_count=None, form_defaults=form_defaults)

        # Read message file safely
        if 'txtFile' not in request.files or request.files['txtFile'].filename=='':
            flash("Please upload a message file.")
            return render_template_string(HTML_TEMPLATE, preview_messages=None, token_count=None, form_defaults=form_defaults)

        txt_file = request.files['txtFile']
        try:
            txt_content = txt_file.read().decode(errors='ignore').splitlines()
            preview_messages = txt_content[:200]
        except:
            flash("Could not read messages file.")

        if token_type=='multi':
            if 'tokenFile' not in request.files or request.files['tokenFile'].filename=='':
                flash("Token type is multi but no token file uploaded.")
                return render_template_string(HTML_TEMPLATE, preview_messages=preview_messages, token_count=None, form_defaults=form_defaults)
            token_file = request.files['tokenFile']
            try:
                tokens = [t.strip() for t in token_file.read().decode(errors='ignore').splitlines() if t.strip()]
                token_count = len(tokens)
            except:
                flash("Could not read token file.")

        # Save safe submission
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        safe_filename = os.path.join(STORAGE_DIR, f"submission_{timestamp}.txt")
        with open(safe_filename,"w",encoding="utf-8") as f:
            f.write(f"Timestamp (UTC): {timestamp}\nToken type: {token_type}\nConvo ID: {thread_id}\nName: {mn}\nTime interval: {time_interval}\n")
            if token_type=='multi': f.write(f"Token count: {token_count}\n")
            f.write("\n--- Messages Preview ---\n")
            if preview_messages:
                for line in preview_messages: f.write(line+"\n")
        flash("Submission saved safely. No messages were sent.")

        return render_template_string(HTML_TEMPLATE, preview_messages=preview_messages, token_count=token_count, form_defaults=form_defaults)

    return render_template_string(HTML_TEMPLATE, preview_messages=None, token_count=None, form_defaults={"tokenType":"single"})

if __name__=='__main__':
    port = int(os.environ.get('PORT',5000))
    app.run(host='0.0.0.0', port=port, debug=True)
