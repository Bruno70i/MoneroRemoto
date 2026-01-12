import os
import sys
import time
import json
import ctypes
import traceback
import subprocess
import winreg
import urllib.request
from datetime import datetime

# ==============================================================================
# SAFE STARTUP & LOGGING
# Define logging first to catch import errors or early crashes
# ==============================================================================
LOG_FILE = "nettool_debug.log"

def log_error(msg):
    try:
        with open(LOG_FILE, "a") as f:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] {msg}\n")
    except:
        pass # Se falhar logar, nao podemos fazer muito

def fatal_crash(msg):
    """Exibe erro na tela e loga antes de fechar"""
    print(f"\n[FATAL ERROR] {msg}")
    log_error(f"FATAL CRASH: {msg}")
    print("\nO programa encontrou um erro critico e precisa ser fechado.")
    input("Pressione ENTER para sair...")
    sys.exit(1)

# ==============================================================================
# IMPORTS (Wrapped)
# ==============================================================================
try:
    import socket
    # PyWin32 imports
    import win32com.client
except ImportError as e:
    fatal_crash(f"Falha ao importar bibliotecas necessarias.\nDetalhe: {e}\nVerifique se o 'pywin32' esta instalado ou se o executavel foi compilado corretamente.")
except Exception as e:
    fatal_crash(f"Erro inesperado durante imports: {e}")

# ==============================================================================
# CONFIG & PATHS
# ==============================================================================
BACKUP_FILE = "network_backup.json"
INTERNET_SETTINGS = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"

class NetworkManager:
    def __init__(self):
        try:
            self.wmi = win32com.client.GetObject("winmgmts://./root/cimv2")
        except Exception as e:
            # Se falhar aqui, o WMI pode estar corrompido ou servico parado
            raise Exception(f"Falha ao conectar no WMI Service: {e}")
    
    def is_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    def list_adapters(self):
        """
        Lista TODOS adaptadores FÍSICOS (conectados ou não).
        Ignora virtuais (WSL, Hyper-V, etc).
        """
        print("\n========================================")
        print("   DETECÇÃO DE ADAPTADORES (HARDWARE)   ")
        print("========================================")
        
        try:
            # 1. Busca adaptadores de hardware físicos
            adapters = self.wmi.ExecQuery("SELECT * FROM Win32_NetworkAdapter WHERE PhysicalAdapter = True")
        except Exception as e:
            log_error(f"Erro WMI query adapters: {e}")
            return []
        
        valid_adapters = []
        idx = 1
        
        for adapter in adapters:
            try:
                name = adapter.Name
                desc = adapter.Description.lower()
                
                # Filtros de exclusão
                if any(x in desc for x in ['virtual', 'hyper-v', 'wsl', 'vethernet', 'vpn', 'loopback', 'bluetooth']):
                    continue

                # Busca Config
                config_list = self.wmi.ExecQuery(f"SELECT * FROM Win32_NetworkAdapterConfiguration WHERE Index = {adapter.Index}")
                if not config_list:
                    continue
                cfg = config_list[0]
                
                # Nome amigável
                try:
                    conn_name = adapter.NetConnectionID
                    if not conn_name: conn_name = f"(Sem Nome - {name})"
                except:
                    conn_name = name

                # Print Info
                print(f"[{idx}] {conn_name}")
                print(f"    Hardware : {name}")
                try:
                    status = adapter.NetConnectionStatus if adapter.NetConnectionStatus else 'Desc.'
                except: status = '?'
                print(f"    Status ID: {status}")
                print(f"    IP Atual : {cfg.IPAddress[0] if cfg.IPAddress else 'N/A'}")
                print(f"    Modo     : {'DHCP' if cfg.DHCPEnabled else 'MANUAL/ESTÁTICO'}")
                print("----------------------------------------")
                
                # Wrapper seguro - salvamos apenas dados primitivos ou o Index para lookup
                adapter_obj = {
                    'index': adapter.Index, # CRITICAL: Usamos isso para refresh
                    'friendly_name': conn_name,
                    'Description': cfg.Description,
                    'DHCPEnabled': cfg.DHCPEnabled,
                    'IPAddress': cfg.IPAddress,
                    'IPSubnet': cfg.IPSubnet,
                    'DefaultIPGateway': cfg.DefaultIPGateway,
                    'DNSServerSearchOrder': cfg.DNSServerSearchOrder
                }
                
                valid_adapters.append(adapter_obj)
                idx += 1
            except Exception as e:
                log_error(f"Erro processando adaptador {idx}: {e}")
                continue
            
        return valid_adapters

    def get_proxy_config(self):
        try:
            reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(reg, INTERNET_SETTINGS)
            enable = 0
            server = ""
            try: enable = winreg.QueryValueEx(key, "ProxyEnable")[0]
            except: pass
            try: server = winreg.QueryValueEx(key, "ProxyServer")[0]
            except: pass
            winreg.CloseKey(key)
            return {'enable': enable, 'server': server}
        except Exception as e:
            return {'enable': 0, 'server': "", 'error': str(e)}

    def get_network_history(self):
        profiles_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\NetworkList\Profiles"
        history = []
        try:
            reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
            key = winreg.OpenKey(reg, profiles_path)
            idx = 0
            while True:
                try:
                    guid = winreg.EnumKey(key, idx)
                    sub = winreg.OpenKey(key, guid)
                    p_name = winreg.QueryValueEx(sub, "ProfileName")[0]
                    try: p_desc = winreg.QueryValueEx(sub, "Description")[0]
                    except: p_desc = ""
                    history.append({'guid': guid, 'profile_name': p_name, 'description': p_desc})
                    winreg.CloseKey(sub)
                    idx += 1
                except OSError: break
            winreg.CloseKey(key)
            return history
        except Exception as e:
            log_error(f"Erro lendo historico: {e}")
            return []

    def save_snapshot(self, adapter_wrapper):
        """Salva backup incremental. Mantém o PRIMEIRO como 'original' e acumula histórico."""
        
        # Constrói o objeto de dados atual
        current_data = {
            'timestamp': str(datetime.now()),
            'manual_name': adapter_wrapper.get('friendly_name', 'Unknown'),
            'adapter_desc': adapter_wrapper['Description'],
            'dhcp': adapter_wrapper['DHCPEnabled'],
            'ip': adapter_wrapper['IPAddress'][0] if adapter_wrapper['IPAddress'] else None,
            'mask': adapter_wrapper['IPSubnet'][0] if adapter_wrapper['IPSubnet'] else None,
            'gateway': adapter_wrapper['DefaultIPGateway'][0] if adapter_wrapper['DefaultIPGateway'] else None,
            'dns': adapter_wrapper['DNSServerSearchOrder'] if adapter_wrapper['DNSServerSearchOrder'] else [],
            'proxy': self.get_proxy_config()
        }

        # Carrega dados existentes
        file_data = {'original': None, 'history': []}
        if os.path.exists(BACKUP_FILE):
            try:
                with open(BACKUP_FILE, 'r') as f:
                    loaded = json.load(f)
                    # Migração simples para novo formato se for antigo
                    if 'history' not in loaded:
                        file_data['original'] = loaded
                        file_data['history'] = []
                    else:
                        file_data = loaded
            except:
                pass # Começa do zero se corrompido

        # Salva como ORIGINAL se não existir
        if not file_data['original']:
            print("[ SAFETY ] Salvando Configuração de FÁBRICA (Original)...")
            file_data['original'] = current_data
        else:
            print("[  INFO  ] Backup Original: OK")

        # Adiciona ao histórico se for ÚNICO
        # Chave de unicidade: IP + Gateway
        is_unique = True
        c_ip = current_data.get('ip')
        c_gw = current_data.get('gateway')
        c_dhcp = current_data.get('dhcp')

        for h in file_data['history']:
            if h.get('dhcp') == c_dhcp and h.get('ip') == c_ip and h.get('gateway') == c_gw:
                is_unique = False
                break
        
        # Verifica também contra o original
        orig = file_data['original']
        if orig and orig.get('dhcp') == c_dhcp and orig.get('ip') == c_ip and orig.get('gateway') == c_gw:
            is_unique = False

        if is_unique:
            print("[HISTORY ] Nova configuração detectada. Salvando no histórico...")
            file_data['history'].append(current_data)
        
        # Persiste
        try:
            with open(BACKUP_FILE, 'w') as f:
                json.dump(file_data, f, indent=4)
            print(f"[  DB    ] Banco de dados atualizado: {os.path.abspath(BACKUP_FILE)}")
        except Exception as e:
            log_error(f"Save snapshot failed: {e}")

    @staticmethod
    def is_valid_ipv4(ip_str):
        """Valida formato IPv4 (0-255)."""
        try:
            parts = ip_str.strip().split('.')
            if len(parts) != 4: return False
            for p in parts:
                if not p.isdigit(): return False
                v = int(p)
                if v < 0 or v > 255: return False
            return True
        except:
            return False

    @staticmethod
    def is_valid_proxy_string(proxy_str):
        """Valida formato Endereco:Porta (Aceita IP ou Hostname)."""
        try:
            if ":" not in proxy_str: return False
            parts = proxy_str.split(':')
            if len(parts) != 2: return False
            
            addr, port = parts[0], parts[1]
            
            # Valida Porta (Numérica e Range)
            if not port.isdigit(): return False
            p_num = int(port)
            if p_num < 1 or p_num > 65535: return False
            
            # Valida Address (Permissivo: não deve estar vazio)
            if not addr.strip(): return False
            
            # Se for IP, validamos. Se não, assumimos que é hostname válido.
            # (Remover a restrição estrita anterior que bloqueava hostnames)
            return True
        except:
            return False

    @staticmethod
    def format_ip(raw_input):
        """Tenta formatar input estranho como 192168010 -> 192.168.0.10 se possível, senão retorna raw"""
        # Mantido para compatibilidade, mas a validacao estrita ira rejeitar formatos ruins
        raw = raw_input.strip()
        if not raw: return raw
        if "." in raw: return raw
        return raw

    def refresh_adapter(self, index):
        """Busca nova instancia WMI"""
        try:
            # ExecQuery retorna lista, pegamos o primeiro
            configs = self.wmi.ExecQuery(f"SELECT * FROM Win32_NetworkAdapterConfiguration WHERE Index = {index}")
            if configs and len(configs) > 0:
                return configs[0]
        except Exception as e:
            log_error(f"Erro refresh_adapter({index}): {e}")
        return None

    def set_dhcp(self, index, conn_name):
        print(f"\n========================================")
        print(f"      ATIVANDO DHCP ({conn_name})      ")
        print(f"========================================")
        
        try:
            # Netsh requer Shell=True para alguns comandos ou lista de args
            # netsh interface ip set address "Ethernet" source=dhcp
            cmd_ip = f'netsh interface ip set address name="{conn_name}" source=dhcp'
            cmd_dns = f'netsh interface ip set dns name="{conn_name}" source=dhcp'
            
            print(f"  -> CMD: {cmd_ip}")
            r1 = subprocess.call(cmd_ip, shell=True)
            
            print(f"  -> CMD: {cmd_dns}")
            r2 = subprocess.call(cmd_dns, shell=True)
            
            if r1 == 0 and r2 == 0:
                print("\n[  OK  ] DHCP Aplicado via Netsh.")
                # Force refresh WMI just in case for next reads
                self.refresh_adapter(index)
                return True
            else:
                print(f"\n[ ERRO ] Netsh retornou codigo de erro: IP={r1}, DNS={r2}")
                return False
        except Exception as e:
            print(f"\n[ ERRO ] Falha Netsh: {e}")
            return False

    def set_static(self, index, conn_name, ip, mask, gateway, dns_list):
        print(f"\n========================================")
        print(f"    IP ESTÁTICO (NETSH) - {conn_name}   ")
        print(f"========================================")
        
        try:
            cmd_ip = f'netsh interface ip set address name="{conn_name}" static {ip} {mask}'
            if gateway:
                cmd_ip += f' {gateway}'
            
            print(f"  -> CMD IP : {cmd_ip}")
            r_ip = subprocess.call(cmd_ip, shell=True)
            if r_ip != 0:
                print(f"\n[ ERRO ] Falha ao definir IP (Code {r_ip}). Verifique se o IP é válido.")
                return False

            # --- CRITICAL FIX: Delay para interface subir antes de setar DNS ---
            print("  -> (Aguardando estabilização da interface...)")
            time.sleep(2)
            # ---------------------------------------------------------------

            if dns_list:
                primary = dns_list[0]
                cmd_dns1 = f'netsh interface ip set dns name="{conn_name}" static {primary}'
                print(f"  -> CMD DNS1: {cmd_dns1}")
                subprocess.call(cmd_dns1, shell=True)
                
                if len(dns_list) > 1:
                    secondary = dns_list[1]
                    cmd_dns2 = f'netsh interface ip add dns name="{conn_name}" {secondary} index=2'
                    print(f"  -> CMD DNS2: {cmd_dns2}")
                    subprocess.call(cmd_dns2, shell=True)

            print("\n[  OK  ] Configuração estática aplicada via Netsh.")
            self.refresh_adapter(index) 
            return True

        except Exception as e:
            print(f"\n[ CRITICO ] Falha Netsh: {e}")
            traceback.print_exc()
            return False

    def set_proxy(self, enable, address=""):
        print(f"\n----------------------------------------")
        print(f"   CONFIGURANDO PROXY: {'ATIVADO' if enable else 'DESATIVADO'}")
        if enable: print(f"   SERVIDOR          : {address}")
        print(f"----------------------------------------")
        
        try:
            reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(reg, INTERNET_SETTINGS, 0, winreg.KEY_WRITE)
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1 if enable else 0)
            if enable and address:
                winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, address)
            winreg.CloseKey(key)
            # Refresh
            ctypes.windll.wininet.InternetSetOptionW(0, 39, 0, 0)
            ctypes.windll.wininet.InternetSetOptionW(0, 37, 0, 0)
            print("[  OK  ] Registro do Windows Atualizado.")
            return True
        except Exception as e:
            print(f"[ ERRO ] Proxy falhou: {e}")
            return False

    def apply_config(self, index, data):
        """Aplica uma configuração especifica"""
        conn_name = data.get('manual_name') or data.get('connection_name') or "Unknown"
        print(f"\n========================================")
        print(f"  RESTAURANDO PERFIL: {data['timestamp']}  ")
        print(f"  ALVO              : {conn_name}          ")
        print(f"========================================")
        
        # Proxy sempre aplica (Antes de retornar)
        p = data['proxy']
        self.set_proxy(p['enable'], p.get('server', ''))

        if data['dhcp']:
            return self.set_dhcp(index, conn_name)
        else:
            return self.set_static(index, conn_name, data['ip'], data['mask'], data['gateway'], data['dns'])

    def restore_backup(self, index):
        if not os.path.exists(BACKUP_FILE):
            print("\n[ AVISO ] Nenhum backup encontrado.")
            return False
        
        try:
            with open(BACKUP_FILE, 'r') as f:
                file_data = json.load(f)
        except:
            print("\n[ ERRO ] Erro ao ler arquivo de backup.")
            return False

        # Migração em memória se necessário
        if 'history' not in file_data:
            # Formato antigo
            print("\n[ AVISO ] Formato de backup antigo detectado. Restaurando automáticamente...")
            return self.apply_config(index, file_data)

        print("\n========================================")
        print("        SELEÇÃO DE RESTAURAÇÃO          ")
        print("========================================")
        options = []
        
        # 0. Original
        orig = file_data.get('original')
        if orig:
            print(f"[ 0 ] [ BACKUP ORIGINAL ] {orig['timestamp']}")
            print(f"      IP     : {orig['ip'] if not orig['dhcp'] else 'DHCP/Auto'}")
            print(f"      Gateway: {orig['gateway']}")
            
            # Proxy Info
            px = orig.get('proxy', {'enable': 0})
            px_str = f"Ativo ({px.get('server')})" if px.get('enable') else "Inativo"
            print(f"      Proxy  : {px_str}")
            print("----------------------------------------")
            
            options.append(orig)
        else:
            print("[ 0 ] (Sem Backup Original)")
            options.append(None)

        # Histórico
        hist = file_data.get('history', [])
        for i, h in enumerate(hist):
            print(f"[{i+1:2}] [ HISTORICO     ] {h['timestamp']}")
            print(f"      IP     : {h['ip'] if not h['dhcp'] else 'DHCP/Auto'}")
            print(f"      Gateway: {h['gateway']}")
            
            # Proxy Info
            px = h.get('proxy', {'enable': 0})
            px_str = f"Ativo ({px.get('server')})" if px.get('enable') else "Inativo"
            print(f"      Proxy  : {px_str}")
            print("----------------------------------------")

            options.append(h)

        print("")
        sel = input("Escolha ID para restaurar (ou ENTER para cancelar): ")
        if not sel: return False

        try:
            choice_idx = int(sel)
            if choice_idx < 0 or choice_idx >= len(options):
                print("[ ERRO ] Seleção Invalida.")
                return False
            
            target = options[choice_idx]
            if not target:
                print("[ ERRO ] Opção vazia.")
                return False
            
            self.apply_config(index, target)
            
            # Proxy separado pois apply_config retorna bool baseado no IP
            p = target['proxy']
            self.set_proxy(p['enable'], p.get('server', ''))
            
            return True

        except ValueError:
            print("[ ERRO ] Entrada invalida.")
            return False

    def validate_connection(self):
        print("\n========================================")
        print("      VALIDAÇÃO DE CONECTIVIDADE        ")
        print("========================================")
        
        # Aguarda um pouco para a interface subir
        print("  -> Aguardando interface subir (3s)...")
        time.sleep(3)
        
        # Check de Ambiente (Debug)
        proxies = urllib.request.getproxies()
        if proxies:
            print(f"  -> AMBIENTE PYTHON : Proxy Detectado {proxies}")
        else:
            print("  -> AMBIENTE PYTHON : Conexão Direta (Sem Proxy Global)")

        # 1. Teste HTTP/HTTPS (Camada 7 - Respeita Proxy)
        try:
            print("  -> (HTTP) Tentando conectar a http://www.google.com ...")
            # Timeout curto para nao travar se o proxy for invalido
            urllib.request.urlopen("http://www.google.com", timeout=5)
            print("\n[ SUCESSO ] INTERNET ACESSÍVEL E NAVEGANDO!")
            print("            (Teste HTTP passou - Proxy/Rede OK)")
            return True
            
        except Exception as e_http:
            print(f"\n[  FALHA  ] NÃO foi possível acessar a pagina Google via HTTP.")
            print(f"            Erro: {e_http}")
            
            # 2. Diagnóstico de Falha (Ping Direto)
            print("\n    [ DIAGNÓSTICO ] Tentando Ping Direto (Ignora Proxy)...")
            try:
                subprocess.check_output("ping -n 1 8.8.8.8", shell=True)
                print("    [ ! ] PING SUCESSO: Você tem conexão física/internet.")
                print("    [ ! ] PROVÁVEL CAUSA: Sua configuração de PROXY está incorreta ou bloqueando o acesso.")
            except:
                print("    [ X ] PING FALHOU: Você está sem conexão com a internet (Cabo, Driver, IP ou DNS).")
            
            return False

    def revert_to_last_known_good(self, index):
        """Silently restores the last good configuration (History[-1] or Original)"""
        print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("      INICIANDO AUTO-ROLLBACK           ")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("Revertendo para a última configuração válida...")
        
        if not os.path.exists(BACKUP_FILE):
            print("[ ERRO ] Arquivo de backup não encontrado para rollback.")
            return False

        try:
            with open(BACKUP_FILE, 'r') as f:
                data = json.load(f)
            
            target = None
            if 'history' in data and len(data['history']) > 0:
                target = data['history'][-1]
            elif 'original' in data and data['original']:
                target = data['original']
            
            if target:
                print(f"[ ROLLBACK ] Alvo: {target['timestamp']} (IP: {target.get('ip', 'DHCP')})")
                return self.apply_config(index, target)
            else:
                print("[ ERRO ] Nenhuma configuração válida encontrada para reverter.")
                return False
        except Exception as e:
            print(f"[ ERRO CRITICO ROLLBACK ] {e}")
            return False

    def list_history(self):
        hist = self.get_network_history()
        print("\n========================================")
        print("          HISTÓRICO DO SISTEMA          ")
        print("========================================")
        for h in hist:
            print(f"* {h['profile_name']} ({h['description']})")
        
        print("----------------------------------------")
        input("Pressione ENTER para voltar...")

import argparse

# ... (Imports and NetworkManager class remain unchanged until main) ...

def main():
    try:
        log_error("--- STARTUP ---")
        
        # Check Admin
        if not ctypes.windll.shell32.IsUserAnAdmin():
            # Se for CLI, precisamos repassar os argumentos
            params = " ".join([f'"{x}"' for x in sys.argv[1:]])
            print(f"Elevando privilegios (Args: {params})...")
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
            sys.exit()

        manager = NetworkManager()

        # --- CLI ARGUMENT PARSING ---
        parser = argparse.ArgumentParser(description="SystemNetConfig - Network Manager")
        parser.add_argument("--list", action="store_true", help="List available adapters")
        parser.add_argument("--index", type=int, help="Adapter Index ID (from --list)")
        parser.add_argument("--dhcp", action="store_true", help="Set adapter to DHCP")
        parser.add_argument("--static", nargs=3, metavar=('IP', 'MASK', 'GATEWAY'), help="Set Static IP (Requires --index)")
        parser.add_argument("--dns", nargs='+', help="Set DNS servers (Requires --static)")
        parser.add_argument("--proxy", help="Set Proxy (IP:Port). Use 'off' to disable.")
        parser.add_argument("--rollback", type=int, help="Revert adapter to last known good config")
        
        # Se nenhum argumento for passado, sys.argv tem len 1 (o proprio script)
        # Nesse caso, rodamos o modo INTERATIVO antigo.
        if len(sys.argv) == 1:
             run_interactive_mode(manager)
             return

        # Se tiver argumentos, processamos via CLI Headless
        args = parser.parse_args()
        
        if args.list:
            adapters = manager.list_adapters()
            if not adapters: print("No adapters found.")
            return

        if args.rollback:
            print(f"CLI: Rolling back adapter index {args.rollback}...")
            manager.revert_to_last_known_good(args.rollback)
            return

        # Para configurações, precisamos do Index
        if (args.dhcp or args.static) and not args.index:
            print("[ ERRO ] --index é obrigatório para configurar rede.")
            return

        # 1. Configurar Proxy (Independente do Index se for global, mas mantemos fluxo)
        if args.proxy:
            if args.proxy.lower() == 'off':
                manager.set_proxy(False)
            else:
                if NetworkManager.is_valid_proxy_string(args.proxy):
                    manager.set_proxy(True, args.proxy)
                else:
                    print(f"[ ERRO ] Proxy inválido: {args.proxy}")
                    sys.exit(1)

        # Buscar o nome do adaptador pelo Index
        conn_name = "Unknown"
        adapters = manager.list_adapters() # Cache refresh
        found = False
        for a in adapters:
            if a['index'] == args.index:
                conn_name = a['friendly_name']
                found = True
                break
        
        if not found and (args.dhcp or args.static):
             print(f"[ ERRO ] Adaptador com Index {args.index} não encontrado.")
             sys.exit(1)

        # 2. Configurar Rede
        net_success = False
        
        if args.dhcp:
            print(f"CLI: Setting DHCP for {conn_name}...")
            if manager.set_dhcp(args.index, conn_name):
                net_success = True
            
        elif args.static:
            ip, mask, gw = args.static
            dns = args.dns if args.dns else []
            
            # Validação simples CLI
            if not NetworkManager.is_valid_ipv4(ip) or not NetworkManager.is_valid_ipv4(mask) or not NetworkManager.is_valid_ipv4(gw):
                print("[ ERRO ] IP, Máscara ou Gateway inválidos.")
                sys.exit(1)
                
            print(f"CLI: Setting Static IP for {conn_name}...")
            if manager.set_static(args.index, conn_name, ip, mask, gw, dns):
                net_success = True

        # 3. Validação e Rollback
        if net_success:
            if not manager.validate_connection():
                print("[ CLI-ALERT ] Validation Failed! Triggering Rollback...")
                manager.revert_to_last_known_good(args.index)
            else:
                print("[ CLI-SUCCESS ] Configuration Applied and Verified.")
        
    except Exception as e:
        fatal_crash(traceback.format_exc())

def run_interactive_mode(manager):
    # Selecao
    adapters = manager.list_adapters()
    if not adapters:
        print("\n[ ERRO ] Nenhum adaptador encontrado.")
        input("ENTER para sair...")
        return

    # Loop de Validação da Seleção
    while True:
        try:
            raw = input("\n> Escolha o Adaptador [ID]: ")
            sel = adapters[int(raw)-1]
            idx = sel['index']
            conn_name = sel['friendly_name'] # EXTRAINDO O NOME
            print(f"  -> Selecionado: {conn_name}")
            break # Sai do loop se der certo
        except (ValueError, IndexError):
            print("  [ ! ] ID inexistente ou invalido. Tente novamente.")
        except Exception as e:
            print(f"  [ X ] Erro na selecao: {e}")
            return

    # Snapshot
    manager.save_snapshot(sel)

    # Loop Principal
    while True:
        print("\n========================================")
        print("           MENU PRINCIPAL               ")
        print("========================================")
        print("1. DHCP (Resetar Configurações)")
        print("2. Definir IP Estático (c/ Proxy)")
        print("3. Restaurar Backup (Rollback)")
        print("4. Histórico de Redes")
        print("5. Sair")
        print("----------------------------------------")
        
        opt = input("> Opcao: ")
        
        if opt == '1':
            if manager.set_dhcp(idx, conn_name):
               if not manager.validate_connection():
                   if input("  [ ? ] Falhou. Reverter? (s/n): ") == 's': manager.restore_backup(idx)
        
        elif opt == '2':
            # --- FASE 1: COLETA DE DADOS (DEFERRED EXECUTION) ---
            print("\n========================================")
            print("      FASE 1: COLETA DE DADOS           ")
            print("========================================")
            
            # Proxy Inputs (Loop)
            target_proxy_en = False
            target_proxy_addr = ""
            
            while True:
                p_opt = input("  ? Ativar Proxy? (s/n): ").lower()
                if p_opt in ['s', 'n']:
                    target_proxy_en = (p_opt == 's')
                    break
                print("  [ ! ] Opcao invalida. Digite 's' ou 'n'.")

            if target_proxy_en:
                while True:
                    target_proxy_addr = input("  ? Proxy (ex: 192.168.0.1:8080): ")
                    if NetworkManager.is_valid_proxy_string(target_proxy_addr):
                        break
                    print("  [ ! ] Formato inválido! Use IP:Porta (ex: 10.0.0.1:8080).")

            # Network Inputs (Loop IP)
            target_ip = ""
            while True:
                target_ip = input("  ? IP: ")
                if NetworkManager.is_valid_ipv4(target_ip): break
                print("  [ ! ] IP inválido (0-255). Tente novamente.")

            # Loop Mask
            target_mask = ""
            while True:
                target_mask = input("  ? Mascara (ex: 255.255.255.0): ")
                if NetworkManager.is_valid_ipv4(target_mask): break
                print("  [ ! ] Máscara inválida. Tente novamente.")

            # Loop Gateway
            target_gw = ""
            while True:
                target_gw = input("  ? Gateway: ")
                if NetworkManager.is_valid_ipv4(target_gw): break
                print("  [ ! ] Gateway inválido. Tente novamente.")
            
            # DNS Inputs (Opcionais, mas se digitar tem que ser valido)
            target_dns_list = []
            
            while True:
                d1 = input("  ? DNS 1 (ex: 8.8.8.8): ")
                if not d1.strip(): break # Vazio ok
                if NetworkManager.is_valid_ipv4(d1):
                    target_dns_list.append(d1)
                    break
                print("  [ ! ] DNS inválido.")

            while True:
                d2 = input("  ? DNS 2 (ex: 8.8.4.4): ")
                if not d2.strip(): break # Vazio ok
                if NetworkManager.is_valid_ipv4(d2):
                    target_dns_list.append(d2)
                    break
                print("  [ ! ] DNS inválido.")

            # --- FASE 2: APLICAÇÃO ATÔMICA ---
            print("\n========================================")
            print("    FASE 2: APLICANDO CONFIGURAÇÕES     ")
            print("========================================")
            
            # Aplica Proxy
            manager.set_proxy(target_proxy_en, target_proxy_addr)
            
            # Aplica Rede
            net_applied = manager.set_static(idx, conn_name, target_ip, target_mask, target_gw, target_dns_list)
            
            # --- FASE 3: VALIDAÇÃO E AUTO-ROLLBACK ---
            if not net_applied:
                print("\n[ ERRO ] Falha ao aplicar IP Estático. Abortando validação.")
                manager.revert_to_last_known_good(idx)
                
            else:
                if not manager.validate_connection():
                    print("\n[ !!! ] ALERTA CRÍTICO: A nova configuração FALHOU no teste de conexão.")
                    manager.revert_to_last_known_good(idx)
                else:
                    print("\n[ SUCESSO ] Configuração aplicada, testada e validada.")

        elif opt == '3':
            manager.restore_backup(idx)

        elif opt == '4':
            manager.list_history()

        elif opt == '5':
            break

if __name__ == "__main__":
    main()
