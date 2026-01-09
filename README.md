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
- **Automação**: PowerShell 5.1+ (para instalação e regras de Firewall).
- **Build**: PyInstaller (Compilação para `.exe` standalone compatível com Windows 10/11).

## 📦 Instalação e Deploy

### 1. Preparação (Build)
Como o Python não é nativo no Windows, a prática recomendada é compilar o agente.
*(Veja `BUILD_INSTRUCTIONS.md` para detalhes completos)*.

```bash
# Na máquina de desenvolvimento
pyinstaller --noconsole --onefile --hidden-import=win32timezone --name=SystemOutCache SystemOutCache.py
```

### 2. Instalação na Máquina Alvo
Copie o arquivo `SystemOutCache.exe` (gerado na pasta `dist`) para a máquina alvo.

**Instalação Automática (One-Click):**
Basta dar **duplo clique** no arquivo `SystemOutCache.exe`.

*O executável irá:*
1.  Solicitar privilégios de Administrador (se não tiver).
2.  Configurar automaticamente o Firewall (Portas 7722 TCP/UDP).
3.  Instalar-se como Serviço do Windows.
4.  Configurar recuperação automática.
5.  Iniciar imediatamente em background.

> **Nota:** Se quiser rodar manualmente ou depurar, pode usar comandos via terminal como `SystemOutCache.exe debug` ou `SystemOutCache.exe remove`.

## 🕹 Manual de Uso (Comandos)

No `client.py`, conecte-se ao IP da máquina alvo. Os seguintes comandos estão disponíveis:

| Comando | Sintaxe | Descrição |
| :--- | :--- | :--- |
| **START** | `START:<cmd> [--dir <path>]` | Inicia um processo em background. Ex: `START:xmrig.exe --dir C:\Miner` |
| **STOP** | `STOP:<pid>` | Encerra forçadamente um processo pelo ID. |
| **STOPNAME** | `STOPNAME:<nome>` | Encerra **todos** os processos com determinado nome. Ex: `STOPNAME:chrome` |
| **LIST** | `LIST` | Lista processos iniciados e gerenciados pelo agente. |
| **FIND** | `FIND:<nome>` | Busca qualquer processo rodando no sistema pelo nome. |
| **PROCESSES** | `PROCESSES` | Lista os Top 50 processos consumindo CPU na máquina. |
| **EXEC** | `EXEC:<cmd>` | Executa um comando de terminal (cmd/powershell) e retorna o output texto. |

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
