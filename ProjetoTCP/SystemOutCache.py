#!/usr/bin/env python3
# Arquivo: SystemOutCache.py

import socket
import threading
import subprocess
import os
import ctypes
import sys
import argparse
import psutil
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import platform


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




# Verificar se está rodando no Windows
if platform.system() != 'Windows':
    print("[ERRO] Este script deve ser executado em um sistema Windows.")
    sys.exit(1)

# Verificação e elevação de privilégios
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    if not is_admin():
        print("[!] Elevando privilégios...")
        try:
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            sys.exit(0)
        except Exception as e:
            print(f"[ERRO] Falha ao elevar privilégios: {e}")
            sys.exit(1)

# Executar como admin obrigatoriamente
run_as_admin()
print("[+] Executando com privilégios administrativos")

class ProcessController:
    def __init__(self):
        self.processes = {}
        self.next_id = 1
        self.lock = threading.Lock()
    
    def start_process(self, command, work_dir=None):
        """Inicia um processo com terminal visível"""
        try:
            if work_dir and not os.path.isdir(work_dir):
                raise ValueError(f"Diretório de trabalho inválido: {work_dir}")
            
            # Configurar ambiente
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 1  # SW_SHOWNORMAL (mostra a janela)
            
            # Iniciar processo
            proc = subprocess.Popen(
                command,
                shell=True,
                cwd=work_dir,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            
            # Registrar processo
            with self.lock:
                proc_id = self.next_id
                self.next_id += 1
                
                self.processes[proc_id] = {
                    'id': proc_id,
                    'process': proc,
                    'pid': proc.pid,
                    'command': command,
                    'work_dir': work_dir or os.getcwd(),
                    'started': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'status': 'running'
                }
            
            print(f"[+] Processo iniciado - ID: {proc_id}, PID: {proc.pid}")
            return proc_id, proc.pid
            
        except Exception as e:
            print(f"[ERRO] Falha ao iniciar '{command}': {e}")
            raise
    
    def stop_process(self, proc_id, kill_children=True):
        """Para um processo"""
        with self.lock:
            if proc_id not in self.processes:
                raise ValueError(f"Processo {proc_id} não encontrado")
            
            proc_info = self.processes[proc_id]
            if proc_info['status'] != 'running':
                raise ValueError(f"Processo {proc_id} não está rodando")
        
        killed_pids = []
        
        try:
            # Matar filhos primeiro se solicitado
            if kill_children:
                try:
                    parent = psutil.Process(proc_info['pid'])
                    children = parent.children(recursive=True)
                    
                    for child in children:
                        try:
                            child.kill()
                            killed_pids.append(child.pid)
                        except:
                            pass
                except:
                    pass
            
            # Matar processo principal
            try:
                proc_info['process'].kill()
                killed_pids.append(proc_info['pid'])
            except:
                pass
            
            # Atualizar status
            with self.lock:
                self.processes[proc_id]['status'] = 'killed'
            
            print(f"[+] Processo {proc_id} terminado - PIDs: {killed_pids}")
            return killed_pids
            
        except Exception as e:
            print(f"[ERRO] Falha ao parar processo {proc_id}: {e}")
            raise
    
    def stop_by_name(self, name):
        """Para processos por nome"""
        killed_pids = []
        
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if name.lower() in proc.info['name'].lower():
                    pid = proc.info['pid']
                    proc.kill()
                    killed_pids.append(pid)
                    print(f"[+] Processo {name} (PID {pid}) terminado")
            except:
                continue
        
        return killed_pids
    
    def list_processes(self):
        """Lista processos controlados"""
        with self.lock:
            result = []
            for proc_id, info in self.processes.items():
                # Atualizar status
                if info['status'] == 'running':
                    if info['process'].poll() is not None:
                        info['status'] = 'terminated'
                
                result.append({
                    'id': proc_id,
                    'pid': info['pid'],
                    'command': info['command'],
                    'status': info['status'],
                    'started': info['started']
                })
            
            return result
    
    def find_processes(self, name):
        """Encontra processos por nome"""
        found = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if name.lower() in proc.info['name'].lower():
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    found.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cmdline': cmdline
                    })
            except:
                continue
        
        return found

# Instância global do controlador
controller = ProcessController()

def handle_client(conn, addr):
    """Manipula conexão do cliente"""
    try:
        data = conn.recv(4096).decode('utf-8').strip()
        if not data:
            return
        
        print(f"[{addr[0]}] {data}")
        
        try:
            response = process_command(data)
            conn.sendall(response.encode('utf-8'))
        except Exception as e:
            error_msg = f"[ERRO] {str(e)}\n"
            conn.sendall(error_msg.encode('utf-8'))
    
    except Exception as e:
        print(f"[ERRO] Erro na conexão {addr}: {e}")
    finally:
        try:
            conn.close()
        except:
            pass

def process_command(command):
    """Processa comandos"""
    parts = command.split(':', 1)
    if len(parts) < 2:
        return get_help()
    
    cmd = parts[0].upper().strip()
    args = parts[1].strip()
    
    if cmd == "START":
        return cmd_start(args)
    elif cmd == "STOP":
        return cmd_stop(args)
    elif cmd == "STOPNAME":
        return cmd_stop_name(args)
    elif cmd == "LIST":
        return cmd_list()
    elif cmd == "FIND":
        return cmd_find(args)
    elif cmd == "EXEC":
        return cmd_exec(args)
    elif cmd == "PROCESSES":
        return cmd_processes()
    else:
        return get_help()

def cmd_start(args):
    """Comando START"""
    if not args:
        return "[ERRO] Comando não especificado\n"
    
    # Separar comando e diretório se especificado
    work_dir = None
    if " --dir " in args:
        parts = args.split(" --dir ", 1)
        command = parts[0].strip()
        work_dir = parts[1].strip().strip('"')
    else:
        command = args
    
    try:
        proc_id, pid = controller.start_process(command, work_dir)
        return f"[OK] Processo iniciado - ID: {proc_id}, PID: {pid}\n"
    except Exception as e:
        return f"[ERRO] {str(e)}\n"

def cmd_stop(args):
    """Comando STOP"""
    try:
        proc_id = int(args.strip())
        killed_pids = controller.stop_process(proc_id)
        return f"[OK] Processo {proc_id} terminado - PIDs: {killed_pids}\n"
    except ValueError:
        return "[ERRO] ID inválido\n"
    except Exception as e:
        return f"[ERRO] {str(e)}\n"

def cmd_stop_name(args):
    """Comando STOPNAME"""
    name = args.strip()
    if not name:
        return "[ERRO] Nome não especificado\n"
    
    try:
        killed_pids = controller.stop_by_name(name)
        if killed_pids:
            return f"[OK] {len(killed_pids)} processos '{name}' terminados - PIDs: {killed_pids}\n"
        else:
            return f"[INFO] Nenhum processo '{name}' encontrado\n"
    except Exception as e:
        return f"[ERRO] {str(e)}\n"

def cmd_list():
    """Comando LIST"""
    processes = controller.list_processes()
    if not processes:
        return "[INFO] Nenhum processo controlado\n"
    
    result = "[PROCESSOS CONTROLADOS]\n"
    for proc in processes:
        result += f"ID {proc['id']}: PID {proc['pid']} - {proc['status']} - {proc['started']}\n"
        result += f"  Comando: {proc['command']}\n"
    
    return result

def cmd_find(args):
    """Comando FIND"""
    name = args.strip()
    if not name:
        return "[ERRO] Nome não especificado\n"
    
    found = controller.find_processes(name)
    if not found:
        return f"[INFO] Nenhum processo '{name}' encontrado\n"
    
    result = f"[PROCESSOS ENCONTRADOS - '{name}']\n"
    for proc in found[:20]:  # Limitar a 20 resultados
        result += f"PID {proc['pid']}: {proc['name']}\n"
        if proc['cmdline']:
            result += f"  Comando: {proc['cmdline'][:100]}...\n"
    
    if len(found) > 20:
        result += f"... e mais {len(found) - 20} processos\n"
    
    return result

def cmd_exec(args):
    """Comando EXEC"""
    if not args:
        return "[ERRO] Comando não especificado\n"
    
    try:
        result = subprocess.run(
            args,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += result.stderr
        
        if not output:
            output = "[OK] Comando executado sem saída"
        
        return f"[EXEC] Código: {result.returncode}\n{output}\n"
    
    except subprocess.TimeoutExpired:
        return "[ERRO] Timeout na execução\n"
    except Exception as e:
        return f"[ERRO] {str(e)}\n"

def cmd_processes():
    """Comando PROCESSES"""
    result = "[PROCESSOS DO SISTEMA (Top 50)]\n"
    
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            processes.append((proc.info['pid'], proc.info['name'], proc.info['cpu_percent']))
        except:
            continue
    
    # Ordenar por CPU
    processes.sort(key=lambda x: x[2], reverse=True)
    
    for pid, name, cpu in processes[:50]:
        result += f"PID {pid:>6}: {name:<25} CPU: {cpu:>5.1f}%\n"
    
    return result

def get_help():
    """Ajuda dos comandos"""
    return """
=== CONTROLADOR DE PROCESSOS ===

COMANDOS:
START:<comando> [--dir <diretorio>]  - Inicia processo
STOP:<id>                           - Para processo por ID
STOPNAME:<nome>                     - Para processos por nome
LIST                                - Lista processos controlados
FIND:<nome>                         - Encontra processos por nome
EXEC:<comando>                      - Executa comando e retorna resultado
PROCESSES                           - Lista processos do sistema

EXEMPLOS:
START:notepad.exe
START:"C:\\Windows\\System32\\notepad.exe" --dir C:\\Temp
STOP:1
STOPNAME:xmrig.exe
FIND:python
EXEC:tasklist | findstr python

"""

def main():
    """Função principal"""
    HOST = '0.0.0.0'
    PORT = 7722
    
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen(10)
        
        print(f"[+] Servidor iniciado em {HOST}:{PORT}")
        print("[+] Aguardando conexões...")
        
        while True:
            try:
                conn, addr = server.accept()
                threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
            except KeyboardInterrupt:
                print("\n[INFO] Encerrando servidor...")
                break
            except Exception as e:
                print(f"[ERRO] {e}")
    
    except Exception as e:
        print(f"[ERRO] Falha ao iniciar servidor: {e}")
    finally:
        try:
            server.close()
        except:
            pass

if __name__ == "__main__":
    main()