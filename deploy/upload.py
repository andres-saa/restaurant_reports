#!/usr/bin/env python3
"""Sube .env.production y server.env.example al servidor por SFTP. Lee la clave de deploy/server.secret."""
import os
import sys

def main():
    try:
        import paramiko
    except ImportError:
        print("Instala paramiko: pip install paramiko")
        sys.exit(1)

    server = "104.248.177.53"
    user = "root"
    remote_path = "/var/www/restaurant_reports"
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    secret_file = os.path.join(script_dir, "server.secret")
    if not os.path.exists(secret_file):
        print("Crea deploy/server.secret con una sola línea: la contraseña del servidor.")
        sys.exit(1)
    with open(secret_file) as f:
        password = f.read().strip()

    files_to_upload = [
        (os.path.join(project_root, "frontend", ".env.production"), ".env.production"),
        (os.path.join(project_root, "deploy", "server.env.example"), "server.env.example"),
    ]

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(server, username=user, password=password, timeout=15)
        sftp = ssh.open_sftp()
        try:
            try:
                sftp.stat(remote_path)
            except FileNotFoundError:
                ssh.exec_command(f"mkdir -p {remote_path}")
        except Exception:
            ssh.exec_command(f"mkdir -p {remote_path}")

        for local_path, remote_name in files_to_upload:
            if not os.path.exists(local_path):
                print(f"No existe: {local_path}")
                continue
            remote_full = f"{remote_path}/{remote_name}"
            print(f"Subiendo {remote_name}...")
            sftp.put(local_path, remote_full)
        print("Listo.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        ssh.close()

if __name__ == "__main__":
    main()
