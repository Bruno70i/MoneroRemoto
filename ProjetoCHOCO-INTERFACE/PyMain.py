import time
import os
import win32com.client

import tkinter as tk
from tkinter import ttk
from tkinter import *

import PyPolitica
import PyVerifica





# ----------------------------- Primeira parte do codigo --------------------

PyPolitica.executar_powershell_alteracao_politicas

time.sleep(6)

# executa o PyVerifica.py que é o arquivo que verifica se o choco esta instalado de fato no sistema
PyVerifica.Verificar_Choco

# ----------------------------- Primeira parte do codigo --------------------




# Caminho do script PowerShell
comando_choco = r"C:\Users\vboxuser\Documents\github\ProjetoCHOCO\ChocoInstall.ps1"

# Cria o objeto Shell.Application para executar com privilégios
shell = win32com.client.Dispatch("Shell.Application")

# Função para executar um script PowerShell elevado
def executar_powershell():
    shell.ShellExecute(
        "powershell.exe",
        f"-ExecutionPolicy Bypass -File \"{comando_choco}\"",
        "",
        "runas",
        1
    )

# escreve os comando no arquivo ChocoInstall.ps1
with open("ChocoInstall.ps1", "a", encoding="utf-8") as arquivo:
    arquivo.write("choco install anydesk -y --force\n")


comandoAlterarSenha = r'cmd.exe /c echo SenhaComplexa@123|anydesk.exe --set-password''\n'
with open("ChocoInstall.ps1", "a", encoding="utf-8") as arquivo:
    arquivo.write(comandoAlterarSenha)


comandoInstall = r"""cmd.exe /c anydesk.exe --install "C:\Program Files (x86)\AnyDesk" --start-with-win --remove-first --silent"""
with open("ChocoInstall.ps1", "a", encoding="utf-8") as arquivo:
    arquivo.write(comandoInstall)

executar_powershell()
