from flask import Flask, render_template, request, jsonify
import os
import subprocess
import shutil

app = Flask(__name__, static_folder='static', template_folder='templates')

SERVERS_DIR = "servers"
if not os.path.exists(SERVERS_DIR):
    os.mkdir(SERVERS_DIR)

def tmux_exists(session_name):
    result = subprocess.run(["tmux", "has-session", "-t", session_name],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0

def tmux_create(session_name):
    if not tmux_exists(session_name):
        # Start tmux in the server root directory
        server_path = os.path.join(SERVERS_DIR, session_name)
        subprocess.run(["tmux", "new-session", "-d", "-s", session_name, f"cd {server_path} && bash"])

def tmux_kill(session_name):
    if tmux_exists(session_name):
        subprocess.run(["tmux", "kill-session", "-t", session_name])

def tmux_send(session_name, command):
    if "nano" in command:
        return False
    if "cd " in command and ("../" in command or "/" in command[3:]):
        command = "echo 'Cannot leave server root directory'"
    subprocess.run(["tmux", "send-keys", "-t", session_name, command, "Enter"])
    return True

def tmux_capture(session_name):
    if tmux_exists(session_name):
        result = subprocess.run(["tmux", "capture-pane", "-pt", session_name],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.stdout.decode()
    return ""

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/console.html")
def console():
    return render_template("console.html")

@app.route("/create_server", methods=["POST"])
def create_server():
    data = request.json
    name = data.get("name")
    if not name:
        return jsonify({"success": False, "error": "No server name"})
    
    server_path = os.path.join(SERVERS_DIR, name)
    
    if os.path.exists(server_path):
        shutil.rmtree(server_path)
    
    os.makedirs(server_path, exist_ok=True)
    
    if tmux_exists(name):
        tmux_kill(name)
    
    # Create fresh tmux session in the server folder (as root)
    tmux_create(name)
    
    return jsonify({"success": True, "server": name})

@app.route("/servers", methods=["GET"])
def list_servers():
    return jsonify(os.listdir(SERVERS_DIR))

@app.route("/console/<server>", methods=["POST"])
def send_command(server):
    cmd = request.json.get("command")
    if not tmux_exists(server):
        return jsonify({"success": False, "error": "Server not running"})
    if not tmux_send(server, cmd):
        return jsonify({"success": False, "error": "nano is disabled or invalid command"})
    return jsonify({"success": True})

@app.route("/console/<server>/output", methods=["GET"])
def console_output(server):
    output = tmux_capture(server)
    return jsonify({"output": output})

@app.route("/start/<server>", methods=["POST"])
def start_server(server):
    tmux_create(server)
    return jsonify({"success": True})

@app.route("/restart/<server>", methods=["POST"])
def restart_server(server):
    tmux_kill(server)
    tmux_create(server)
    return jsonify({"success": True})

@app.route("/stop/<server>", methods=["POST"])
def stop_server(server):
    tmux_kill(server)
    return jsonify({"success": True})

@app.route("/files/<server>", methods=["GET"])
def list_files(server):
    path = os.path.join(SERVERS_DIR, server)
    if not os.path.exists(path):
        return jsonify([])
    return jsonify(os.listdir(path))

@app.route("/files/<server>/<filename>", methods=["GET"])
def get_file(server, filename):
    path = os.path.join(SERVERS_DIR, server)
    file_path = os.path.join(path, filename)
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    return "", 404

@app.route("/files/<server>/<filename>", methods=["PUT"])
def edit_file(server, filename):
    data = request.json
    content = data.get("content", "")
    path = os.path.join(SERVERS_DIR, server)
    file_path = os.path.join(path, filename)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return jsonify({"success": True})

@app.route("/files/<server>/<filename>", methods=["DELETE"])
def delete_file(server, filename):
    path = os.path.join(SERVERS_DIR, server)
    file_path = os.path.join(path, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "File not found"})

@app.route("/files/<server>/upload", methods=["POST"])
def upload_file(server):
    file = request.files['file']
    path = os.path.join(SERVERS_DIR, server)
    os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, file.filename)
    file.save(file_path)
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001) # change port to any
