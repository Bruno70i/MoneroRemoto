# Build Instructions - MoneroRemoto Service

Para facilitar o deploy e remover a necessidade de instalar Python na máquina alvo, você deve compilar o `SystemOutCache.py` em um executável único (`.exe`).

## Pré-requisitos de Build
Na sua máquina de desenvolvimento:

1. Instale o PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Instale as dependências do projeto (caso não tenha):
   ```bash
   pip install pywin32 psutil
   ```

## Compilação

Execute o seguinte comando na pasta principal do projeto:

```bash
pyinstaller --noconsole --onefile --hidden-import=win32timezone --name=SystemOutCache SystemOutCache.py
```

### Explicação das Flags:
- `--noconsole`: O executável não abrirá uma janela preta (comportamento de serviço/background).
- `--onefile`: Gera um único arquivo `.exe` (mais fácil de copiar).
- `--hidden-import=win32timezone`: Necessário para evitar erros comuns com `pywin32` e datas.

## Pós-Build

1. O executável será gerado na pasta `dist/`.
2. O arquivo `SystemOutCache.exe` já é Auto-Instalável.
3. Copie APENAS este arquivo para a máquina alvo e dê duplo clique para instalar.
