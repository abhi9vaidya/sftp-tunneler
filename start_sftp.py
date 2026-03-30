import subprocess
import sys
import time
import re
import signal
import os

# -------- CONFIG --------
PINGGY_CMD = ["ssh", "-p", "443", "-R0:127.0.0.1:22", "-o", "StrictHostKeyChecking=no", "-T", "tcp@free.pinggy.io"]

# -------- HELPERS --------
def run(cmd, check=True):
    return subprocess.run(cmd, shell=True, check=check)

def install_ssh():
    print("[*] Checking OpenSSH server...")
    try:
        subprocess.run("which sshd", shell=True, check=True, stdout=subprocess.DEVNULL)
        print("[+] OpenSSH already installed")
    except:
        print("[*] Installing OpenSSH server...")
        run("apt update")
        run("apt install -y openssh-server")

def create_user(username, password):
    print(f"[*] Creating user: {username}")
    try:
        subprocess.run(f"id {username}", shell=True, check=True, stdout=subprocess.DEVNULL)
        print("[+] User already exists")
    except:
        run(f"useradd -m {username}")
    
    print("[*] Setting password...")
    run(f'echo "{username}:{password}" | chpasswd')

def start_ssh():
    print("[*] Starting SSH service...")
    run("systemctl start ssh", check=False)
    run("systemctl enable ssh", check=False)

def ensure_config():
    print("[*] Ensuring SSH config...")
    config_path = "/etc/ssh/sshd_config"
    
    with open(config_path, "r") as f:
        config = f.read()

    if "PasswordAuthentication yes" not in config:
        config += "\nPasswordAuthentication yes\n"
    
    if "Subsystem sftp internal-sftp" not in config:
        config = re.sub(r"Subsystem\s+sftp\s+.*", "Subsystem sftp internal-sftp", config)

    with open(config_path, "w") as f:
        f.write(config)

    run("systemctl restart ssh", check=False)

def start_pinggy():
    print("[*] Starting Pinggy tunnel...")
    proc = subprocess.Popen(PINGGY_CMD, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    host = None
    port = None

    for line in proc.stdout:
        print(line.strip())

        match = re.search(r"tcp://([a-zA-Z0-9\-.]+):(\d+)", line)
        if match:
            host = match.group(1)
            port = match.group(2)
            break

    if not host:
        print("[-] Failed to get Pinggy URL")
        proc.terminate()
        sys.exit(1)

    return proc, host, port

# -------- MAIN --------
def main():
    if os.geteuid() != 0:
        print("[-] Run as root (sudo)")
        sys.exit(1)

    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <username> <password>")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]

    install_ssh()
    create_user(username, password)
    start_ssh()
    ensure_config()

    proc, host, port = start_pinggy()

    print("\n====== SFTP DETAILS ======")
    print(f"Host     : {host}")
    print(f"Port     : {port}")
    print(f"Username : {username}")
    print(f"Password : {password}")
    print("\nSFTP CMD:")
    print(f"sftp -P {port} {username}@{host}")
    print("=========================\n")

    def cleanup(sig, frame):
        print("\n[*] Stopping server...")
        proc.terminate()
        run("systemctl stop ssh", check=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)

    print("[*] Press Ctrl+C to stop")
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()

