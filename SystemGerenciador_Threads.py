import json
import os
import sys
import subprocess
import math
import re  # <--- Adicionado para arrumar a formatacao

# --- ENGENHARIA DO SISTEMA: DETECÇÃO DE HARDWARE ---
def get_hardware_info():
    print("[HARDWARE] Sondando sistema...")
    try:
        # Pega Cache L3 via WMIC (Windows)
        cmd_l3 = "wmic cpu get L3CacheSize /value"
        output_l3 = subprocess.check_output(cmd_l3, shell=True).decode().strip()
        l3_kb = 0
        for line in output_l3.splitlines():
            if "L3CacheSize" in line:
                l3_kb = int(line.split("=")[1])
        
        # Pega Núcleos Lógicos
        cores = os.cpu_count()
        
        return l3_kb, cores
    except Exception as e:
        print(f"[ERRO] Falha ao detectar hardware: {e}")
        return 0, os.cpu_count()

# --- LÓGICA RANDOMX ---
def calculate_profiles(l3_kb, cores):
    if l3_kb > 0:
        max_threads_cache = math.floor(l3_kb / 2048)
    else:
        max_threads_cache = math.floor(cores / 2)
    
    limit = min(max_threads_cache, cores)
    if limit < 1: limit = 1

    p_high = limit
    p_mid = math.floor(limit * 0.6)
    if p_mid < 1: p_mid = 1
    p_low = math.floor(limit * 0.3)
    if p_low < 1: p_low = 1
    
    return p_low, p_mid, p_high, limit, l3_kb

# --- MANIPULAÇÃO DO JSON (AGORA COM FORMATAÇÃO BONITA) ---
def update_json(threads_count, priority, mode_name):
    # --- LOGICA DE CAMINHO ---
    # 1. Procura na pasta atual
    if os.path.exists('config.json'):
        json_path = 'config.json'
    # 2. Procura na pasta padrao do projeto
    elif os.path.exists(r'C:\Windows\SystemOut\XMR\config.json'):
        json_path = r'C:\Windows\SystemOut\XMR\config.json'
    else:
        print(f"[ERRO] config.json não encontrado na pasta atual nem em C:\\Windows\\SystemOut\\XMR\\")
        input("Pressione Enter para sair...")
        sys.exit()

    print(f"[INFO] Usando configuração em: {json_path}")

    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # 1. Configurações Técnicas
        data['autosave'] = False
        
        if priority == 'low':
            data['cpu']['priority'] = 1
        elif priority == 'high':
            data['cpu']['priority'] = 4
        else:
            data['cpu']['priority'] = None
            
        thread_list = list(range(threads_count))
        data['cpu']['rx'] = thread_list
        
        # 2. GERAÇÃO DO TEXTO (Aqui entra a mágica visual)
        # Primeiro, gera o JSON "feio" (vertical)
        json_str = json.dumps(data, indent=4)
        
        # --- REGEX DE LIMPEZA ---
        # Padrão 1: Colapsa arrays pequenos de pares, ex: [ 8, 0 ] vira [8, 0]
        # (Ideal para cn-lite, ghostrider, etc)
        json_str = re.sub(r'\[\s+(\d+),\s+(\d+)\s+\]', r'[\1, \2]', json_str)

        # Padrão 2: Colapsa arrays longos de números, ex: "rx": [ 0, 1, 2... ]
        # Encontra colchetes que contenham APENAS números, vírgulas e espaços
        json_str = re.sub(r'\[\s*([\d,\s]+)\s*\]', lambda m: '[' + ' '.join(m.group(1).split()) + ']', json_str)

        # 3. Salva o arquivo formatado
        with open(json_path, 'w') as f:
            f.write(json_str)
            
        print(f"\n[SUCESSO] config.json atualizado para MODO {mode_name}!")
        print(f" -> Threads definidos: {thread_list}")
        print("-" * 50)
        
    except Exception as e:
        print(f"[ERRO CRÍTICO] Ao salvar JSON: {e}")

# --- MENU PRINCIPAL ---
def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("==========================================")
    print("    GERADOR DE CONFIGURAÇÃO XMRIG (V2)")
    print("==========================================")
    
    l3, cores = get_hardware_info()
    low, mid, high, limit, l3_val = calculate_profiles(l3, cores)
    
    print(f" CPU Detectada: {cores} Cores | L3 Cache: {l3_val/1024:.1f} MB")
    print(f" Limite RandomX: {limit} Threads")
    print("==========================================")
    print(f" [1] MODO FURTIVO     ({low} Threads)")
    print(f" [2] MODO EQUILIBRADO ({mid} Threads)")
    print(f" [3] MODO TURBO       ({high} Threads)")
    print("==========================================")
    
    choice = input(" Escolha uma opção (1-3): ")
    
    if choice == '1':
        update_json(low, 'low', 'FURTIVO')
    elif choice == '2':
        update_json(mid, 'normal', 'EQUILIBRADO')
    elif choice == '3':
        update_json(high, 'high', 'TURBO')
    else:
        print("Opção inválida.")

    input("\nPressione Enter para fechar...")

if __name__ == "__main__":
    main()