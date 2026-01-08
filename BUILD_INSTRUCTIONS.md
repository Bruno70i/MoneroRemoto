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

Execute o seguinte comando na pasta `ProjetoTCP`:

```bash
pyinstaller --noconsole --onefile --hidden-import=win32timezone --name=SystemOutCache SystemOutCache.py
```

### Explicação das Flags:
- `--noconsole`: O executável não abrirá uma janela preta (comportamento de serviço/background).
- `--onefile`: Gera um único arquivo `.exe` (mais fácil de copiar).
- `--hidden-import=win32timezone`: Necessário para evitar erros comuns com `pywin32` e datas.

## Pós-Build

1. O executável será gerado na pasta `dist/`.
2. Mova o arquivo `SystemOutCache.exe` da pasta `dist/` para a pasta principal `ProjetoTCP/` (onde está o `install_service.ps1`).
3. Agora você pode copiar a pasta `ProjetoTCP` inteira para a máquina alvo e rodar o `install_service.ps1`.
