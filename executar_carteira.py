from src.core.logger import get_logger
logger = get_logger(__name__)
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
from carteira_apex import obter_path_absoluto, CONFIG
from src.registry import REGISTRO, processar_fundo_registrado

def listar_fundos():
    logger.info("\n--- FUNDOS DISPONÍVEIS ---")
    for i, fundo in enumerate(REGISTRO.keys(), 1):
        logger.info(f"{i}. {fundo}")
    logger.info("--------------------------\n")

def executar(nome_fundo, aba="CD_ATUAL"):
    try:
        nome_fundo = nome_fundo.upper().strip()
        
        if nome_fundo not in REGISTRO:
            logger.error(f"Erro: Fundo '{nome_fundo}' não encontrado no REGISTRO.")
            return False

        logger.info(f"\n>>> Iniciando processamento: {nome_fundo} na aba {aba}")
        
        # Executa a função de geração via registro
        processar_fundo_registrado(nome_fundo, aba=aba)
        
        # Tenta localizar o caminho do relatório para confirmar
        try:
            rel_filename = CONFIG['arquivo_gerencial'].get(nome_fundo)
            if rel_filename:
                rel_path = obter_path_absoluto(os.path.join(CONFIG['paths']['relatorio_diario'], rel_filename))
                logger.info(f"✔ Relatório concluído: {rel_path}")
        except:
            pass
        return True

    except Exception as e:
        logger.error(f"❌ Falha ao processar {nome_fundo}: {e}")
        raise e

def _executar_batch(abas_dict, status_label):
    def task():
        sucessos = []
        erros = []
        for fundo, aba in abas_dict.items():
            try:
                status_label.config(text=f"Processando {fundo} ({aba})...", fg="blue")
                if executar(fundo, aba):
                    sucessos.append(fundo)
            except Exception as e:
                erros.append(f"{fundo} ({aba}): {str(e)}")
        
        # Relatório consolidado
        msg = f"Processamento Batch Finalizado!\n\nSucesso: {len(sucessos)}\nFalhas: {len(erros)}"
        if erros:
            logger.error("--- RELATÓRIO CONSOLIDADO DE ERROS ---")
            for erro in erros:
                logger.error(erro)
            logger.error("--------------------------------------")
            msg += "\n\nErros (veja o log para detalhes):\n" + "\n".join(erros[:5])
            if len(erros) > 5:
                msg += f"\n... e mais {len(erros)-5} erros."
            status_label.config(text=f"Batch finalizado com erros.", fg="red")
            messagebox.showwarning("Relatório Batch", msg)
        else:
            status_label.config(text=f"Batch finalizado com 100% de sucesso.", fg="green")
            messagebox.showinfo("Relatório Batch", msg)

    threading.Thread(target=task, daemon=True).start()

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

    # Botão Sair e Batch
    frame_rodape = tk.Frame(root)
    frame_rodape.pack(pady=15, fill=tk.X, padx=20)
    
    def on_batch():
        # Por padrão usa CD_ATUAL para todos os fundos
        abas_dict = {f: "CD_ATUAL" for f in REGISTRO.keys()}
        if messagebox.askyesno("Processar Todos", f"Isso irá processar todos os {len(REGISTRO)} fundos usando a aba CD_ATUAL.\nConfirma?"):
            _executar_batch(abas_dict, status_label)
            
    btn_batch = ttk.Button(frame_rodape, text="Processar Todos", command=on_batch)
    btn_batch.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

    btn_sair = ttk.Button(frame_rodape, text="Sair", command=root.destroy)
    btn_sair.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=5)

    root.mainloop()


def main():
    # Modo headless: fundo passado por linha de comando
    if len(sys.argv) > 1:
        fundo_escolhido = sys.argv[1]
        aba = sys.argv[2] if len(sys.argv) > 2 else "CD_ATUAL"
        if fundo_escolhido.lower() != 'sair':
            try:
                executar(fundo_escolhido, aba)
            except Exception:
                pass
            input("\nProcessamento finalizado. Pressione Enter para fechar...")
        return

    # Modo GUI: PySide6 primeiro, fallback Tkinter
    try:
        from src.gui import main as gui_main
        gui_main()
    except ImportError:
        logger.warning("PySide6 não disponível — usando interface Tkinter legada.")
        iniciar_interface()


if __name__ == "__main__":
    main()
