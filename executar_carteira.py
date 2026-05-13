import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
from carteira_apex import obter_path_absoluto, CONFIG
from src.registry import REGISTRO, processar_fundo_registrado

def listar_fundos():
    print("\n--- FUNDOS DISPONÍVEIS ---")
    for i, fundo in enumerate(REGISTRO.keys(), 1):
        print(f"{i}. {fundo}")
    print("--------------------------\n")

def executar(nome_fundo, aba="CD_ATUAL"):
    try:
        nome_fundo = nome_fundo.upper().strip()
        
        if nome_fundo not in REGISTRO:
            print(f"Erro: Fundo '{nome_fundo}' não encontrado no REGISTRO.")
            return False

        print(f"\n>>> Iniciando processamento: {nome_fundo} na aba {aba}")
        
        # Executa a função de geração via registro
        processar_fundo_registrado(nome_fundo, aba=aba)
        
        # Tenta localizar o caminho do relatório para confirmar
        try:
            rel_filename = CONFIG['arquivo_gerencial'].get(nome_fundo)
            if rel_filename:
                rel_path = obter_path_absoluto(os.path.join(CONFIG['paths']['relatorio_diario'], rel_filename))
                print(f"✔ Relatório concluído: {rel_path}")
        except:
            pass
        return True

    except Exception as e:
        print(f"❌ Falha ao processar {nome_fundo}: {e}")
        raise e

def _executar_gui(nome_fundo, aba, status_label):
    def task():
        try:
            status_label.config(text=f"Processando {nome_fundo} ({aba})...", fg="blue")
            executar(nome_fundo, aba)
            status_label.config(text=f"✔ {nome_fundo} ({aba}) gerado com sucesso!", fg="green")
            messagebox.showinfo("Sucesso", f"O relatório de {nome_fundo} ({aba}) foi gerado e aberto.")
        except Exception as e:
            status_label.config(text=f"❌ Erro em {nome_fundo} ({aba}).", fg="red")
            messagebox.showerror("Erro", f"Falha ao processar {nome_fundo} ({aba}):\n{e}")
            
    threading.Thread(target=task, daemon=True).start()

def abrir_janela_abas(nome_fundo, root, status_label):
    # Carrega as abas em background
    def carregar():
        try:
            status_label.config(text=f"Lendo abas de {nome_fundo}...", fg="blue")
            path_relativo = CONFIG['carteiras'].get(nome_fundo)
            if not path_relativo:
                raise ValueError(f"Caminho não encontrado no config para {nome_fundo}")
                
            path_carteira = obter_path_absoluto(path_relativo)
            
            engine = "pyxlsb" if path_carteira.endswith(".xlsb") else None
            xls = pd.ExcelFile(path_carteira, engine=engine)
            abas = xls.sheet_names
            
            # Abre a nova janela na thread principal
            root.after(0, lambda: exibir_janela_abas(nome_fundo, abas, status_label))
            root.after(0, lambda: status_label.config(text="Pronto.", fg="black"))
        except Exception as e:
            erro_msg = str(e)
            root.after(0, lambda: status_label.config(text=f"❌ Erro ao ler {nome_fundo}.", fg="red"))
            root.after(0, lambda msg=erro_msg: messagebox.showerror("Erro", f"Falha ao ler abas de {nome_fundo}:\n{msg}"))

    threading.Thread(target=carregar, daemon=True).start()

def exibir_janela_abas(nome_fundo, abas, status_label):
    janela = tk.Toplevel()
    janela.title(f"Selecionar Aba - {nome_fundo}")
    janela.geometry("300x400")
    
    # Transição e foco
    janela.transient()
    janela.focus_force()
    
    lbl = tk.Label(janela, text=f"Selecione a aba para processar:", font=("Segoe UI", 10, "bold"))
    lbl.pack(pady=10)
    
    frame_lista = tk.Frame(janela)
    frame_lista.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    
    scrollbar = tk.Scrollbar(frame_lista)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    listbox = tk.Listbox(frame_lista, yscrollcommand=scrollbar.set, font=("Segoe UI", 10), selectbackground="#0078D7")
    for aba in abas:
        listbox.insert(tk.END, aba)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=listbox.yview)
    
    # Seleciona o CD_ATUAL por padrão se existir
    if "CD_ATUAL" in abas:
        idx = abas.index("CD_ATUAL")
        listbox.selection_set(idx)
        listbox.see(idx)
    elif abas:
        listbox.selection_set(0)
        
    def confirmar():
        selecao = listbox.curselection()
        if not selecao:
            messagebox.showwarning("Aviso", "Selecione uma aba.", parent=janela)
            return
        aba_selecionada = listbox.get(selecao[0])
        janela.destroy()
        _executar_gui(nome_fundo, aba_selecionada, status_label)
        
    btn_proc = ttk.Button(janela, text="Processar Aba", command=confirmar)
    btn_proc.pack(pady=10)

def iniciar_interface():
    root = tk.Tk()
    root.title("Gerador de Carteiras Diárias")
    root.geometry("450x550")
    
    # Estilo moderno básico
    style = ttk.Style(root)
    # Usa um tema mais bonito se disponível
    if 'clam' in style.theme_names():
        style.theme_use('clam')
        
    style.configure("TButton", font=("Segoe UI", 10), padding=5)
    
    lbl_titulo = tk.Label(root, text="Selecione o Fundo para gerar a carteira:", font=("Segoe UI", 12, "bold"))
    lbl_titulo.pack(pady=15)
    
    frame_botoes = tk.Frame(root)
    frame_botoes.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    
    # Status bar
    status_frame = tk.Frame(root, relief=tk.SUNKEN, bd=1)
    status_frame.pack(side=tk.BOTTOM, fill=tk.X)
    status_label = tk.Label(status_frame, text="Pronto.", font=("Segoe UI", 10))
    status_label.pack(pady=5)

    # Configurando o Grid de botões
    col_count = 2
    for i in range(col_count):
        frame_botoes.columnconfigure(i, weight=1)

    row = 0
    col = 0
    for nome_fundo in REGISTRO.keys():
        btn = ttk.Button(
            frame_botoes, 
            text=nome_fundo, 
            command=lambda f=nome_fundo: abrir_janela_abas(f, root, status_label)
        )
        btn.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
        
        col += 1
        if col >= col_count:
            col = 0
            row += 1

    # Botão Sair
    btn_sair = ttk.Button(root, text="Sair", command=root.destroy)
    btn_sair.pack(pady=15)

    root.mainloop()

def main():
    # Verifica se o nome do fundo foi passado via linha de comando (ex: python executar_carteira.py FIDARA CD_ATUAL)
    if len(sys.argv) > 1:
        fundo_escolhido = sys.argv[1]
        aba = sys.argv[2] if len(sys.argv) > 2 else "CD_ATUAL"
        if fundo_escolhido.lower() != 'sair':
            try:
                executar(fundo_escolhido, aba)
            except:
                pass
            input("\nProcessamento finalizado. Pressione Enter para fechar...")
    else:
        # Se nenhum argumento for passado, inicia a GUI
        iniciar_interface()

if __name__ == "__main__":
    main()
