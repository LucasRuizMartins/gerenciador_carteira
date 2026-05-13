"""Funções utilitárias de suporte ao processamento de carteiras.

Este módulo contém helpers de uso geral para:
    - Processamento de DataFrames de planilhas no formato COBUCCIO/FIDC.
    - Criação de subconjuntos de DataFrames por código/categoria.
    - Persistência de dados em Excel (via xlwings) e CSV.
    - Validação e categorização de cotas de investimento.

Note:
    Funções de conversão monetária e parsing de seções foram migradas
    para ``src.core.converters`` (única fonte de verdade).
    As duplicatas aqui presentes serão removidas progressivamente.

Deprecated:
    ``resetar_cabecalho()``, ``encontrar_linha_categoria()`` (versão legada)
    → Use ``src.core.converters`` em código novo.
"""

# --- Imports ---
import time
import re
from datetime import datetime

import pandas as pd
# xlwings é importado tardiamente nas funções que o utilizam para evitar
# dependência obrigatória em ambientes de teste onde o Excel não está disponível.



def processar_dataframes(path_excel: str, aba: str = "CD_ATUAL") -> dict:
    """Processa o relatório COBUCCIO FIDC CD e retorna DataFrames por categoria.

    Lê a planilha Excel, localiza cada seção pelo marcador na coluna 'Código'
    e retorna um dicionário com DataFrames individuais por categoria.

    Args:
        path_excel: Caminho absoluto do arquivo Excel a processar.
        aba: Nome da aba Excel. Padrão: "CD_ATUAL".

    Returns:
        dict: Dicionário com chaves ``renda_fixa``, ``fundos_invest``,
            ``conta_corrente``, ``outros_ativos``, ``contas_pagar``,
            ``tesouraria``, ``patrimonio``, ``rentabilidade_acumulada``
            e ``data_arquivo``.

    Raises:
        RuntimeError: Se ocorrer falha durante o processamento das categorias.
    """
    # Lê e prepara o DataFrame base (pula as primeiras 9 linhas de cabeçalho)
    df = pd.read_excel(path_excel, sheet_name=aba).iloc[9:].reset_index(drop=True)
    data_do_arquivo = pd.read_excel(path_excel, sheet_name=aba).iloc[3, 1]
    
    # Definir cabeçalhos
    try:
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)
    except Exception as e:
        print(f"Erro ao definir cabeçalhos: {str(e)}")
        df.columns = [f"Coluna_{i}" for i in range(len(df.columns))]
    
    # Função auxiliar para encontrar linhas de categorias
    def encontrar_linha_categoria(nome_categoria):
        linhas = df.index[df['Código'] == nome_categoria].tolist()
        return linhas[0] if linhas else None
    
    # Categorias a serem localizadas
    categorias = {
        'renda_fixa': 'Fundos de Investimento - Outros Fundos',
        'fundo_investimento': 'Fundos de Investimento - Outros Fundos',
        'conta_corrente': 'Conta Corrente',
        'outros_ativos': 'Outros Ativos',
        'contas_pagar_receber': 'Contas a Pagar/Receber',
        'tesouraria': 'Tesouraria',
        'patrimonio': 'Patrimônio',
        'rentabilidade_acumulada': 'Rentabilidade Acumulada'
    }
    
    # Encontrar linhas para cada categoria
    linhas_categorias = {}
    for key, value in categorias.items():
        linha = encontrar_linha_categoria(value)
        if linha is not None:
            linhas_categorias[key] = linha
        else:
            print(f"Aviso: Categoria '{value}' não encontrada. Usando valor padrão.")
            linhas_categorias[key] = len(df)  # Usa o final do DataFrame como fallback
    
    # Função auxiliar para resetar cabeçalho com verificação de segurança
    def resetar_cabecalho(df_temp):
        if df_temp.empty or len(df_temp) < 1:
            return pd.DataFrame()
        try:
            df_temp.columns = df_temp.iloc[0]
            return df_temp.iloc[1:].reset_index(drop=True)
        except Exception as e:
            print(f"Erro ao resetar cabeçalho: {str(e)}")
            return df_temp
    
    # Processar cada categoria com verificações de segurança
    secoes_carteira = {}
    try:
        secoes_carteira['renda_fixa'] = df.iloc[:linhas_categorias['renda_fixa']].reset_index(drop=True)
        
        # Fundos de investimento
        start = linhas_categorias['fundo_investimento']+1
        end = linhas_categorias['outros_ativos']
        if start < end:
            secoes_carteira['fundos_invest'] = resetar_cabecalho(df.iloc[start:end].reset_index(drop=True))
        else:
            secoes_carteira['fundos_invest'] = pd.DataFrame()
        
        # Conta corrente
        start = linhas_categorias['conta_corrente']+1
        end = linhas_categorias['outros_ativos']
        if start < end:
            secoes_carteira['conta_corrente'] = resetar_cabecalho(df.iloc[start:end].reset_index(drop=True))
        else:
            secoes_carteira['conta_corrente'] = pd.DataFrame()
        
        # Outros ativos
        start = linhas_categorias['outros_ativos']+1
        end = linhas_categorias['contas_pagar_receber']
        if start < end:
            secoes_carteira['outros_ativos'] = resetar_cabecalho(df.iloc[start:end].reset_index(drop=True))
        else:
            secoes_carteira['outros_ativos'] = pd.DataFrame()
        
        # Contas a pagar
        start = linhas_categorias['contas_pagar_receber']+1
        end = linhas_categorias['tesouraria']
        if start < end:
            secoes_carteira['contas_pagar'] = resetar_cabecalho(df.iloc[start:end].reset_index(drop=True))
        else:
            secoes_carteira['contas_pagar'] = pd.DataFrame()
        
        # Tesouraria
        start = linhas_categorias['tesouraria']+1
        end = linhas_categorias['patrimonio']
        if start < end:
            secoes_carteira['tesouraria'] = resetar_cabecalho(df.iloc[start:end].reset_index(drop=True))
        else:
            secoes_carteira['tesouraria'] = pd.DataFrame()
        
        # Patrimônio
        start = linhas_categorias['patrimonio']
        end = linhas_categorias['rentabilidade_acumulada']
        if start < end:
            secoes_carteira['patrimonio'] = resetar_cabecalho(df.iloc[start:end].reset_index(drop=True))
        else:
            secoes_carteira['patrimonio'] = pd.DataFrame()
        
        # Rentabilidade acumulada
        start = linhas_categorias['rentabilidade_acumulada']+1
        if start < len(df):
            secoes_carteira['rentabilidade_acumulada'] = resetar_cabecalho(df.iloc[start:].reset_index(drop=True))
        else:
            secoes_carteira['rentabilidade_acumulada'] = pd.DataFrame()
        
        secoes_carteira['data_arquivo'] = data_do_arquivo
        
        # Ajustes específicos
        if not secoes_carteira['fundos_invest'].empty:
            secoes_carteira['fundos_invest']['Código'] = secoes_carteira['fundos_invest']['Código'].replace("TOTAL", "SUBTOTAL")
        if not secoes_carteira['tesouraria'].empty:
            secoes_carteira['tesouraria'] = secoes_carteira['tesouraria'].rename(columns={"Descrição": "Código"})
        if not secoes_carteira['rentabilidade_acumulada'].empty:
            secoes_carteira['rentabilidade_acumulada'] = secoes_carteira['rentabilidade_acumulada'].rename(columns={"Indexador": "Código"})
            
    except Exception as e:
        print(f"Erro durante o processamento das categorias: {str(e)}")
        raise RuntimeError(f"Erro ao processar dataframes: {str(e)}")
    
    return secoes_carteira


def categorizar_cota(dataframe, categoria):
    """Retorna o PU Mercado de uma cota filtrada por categoria.

    Args:
        dataframe: DataFrame com colunas 'CATEGORIA' e 'PU Mercado'.
        categoria: Valor da categoria a filtrar.

    Returns:
        Valor de PU Mercado encontrado, ou 0 se não encontrado.
    """
    try:
        return dataframe.loc[dataframe["CATEGORIA"] == categoria, "PU Mercado"].values[0, 0]
    except Exception as e:
        print(f"Erro ao categorizar cota '{categoria}': {e}")
        return 0




def gerar_df_dic_entre_linhas(carteira,dataframe, lista):
    dicionario = {}
    for codigo in lista:
        dicionario[f"{codigo.lower()}"] = criar_df_entre_linhas_unico(dataframe, codigo)
    return dicionario



def criar_df_entre_linhas_unico(df: pd.DataFrame, codigo: str, *args: str) -> pd.DataFrame:
    """Cria um subconjunto do DataFrame entre o código inicial e a linha 'SUBTOTAL'.

    Tenta localizar *codigo* no DataFrame; se não encontrar, tenta os códigos
    alternativos passados em *args*. A seção extraída vai do código encontrado
    até a próxima linha 'SUBTOTAL'.

    Args:
        df: DataFrame com coluna 'Código'.
        codigo: Código principal a localizar.
        *args: Códigos alternativos (fallback).

    Returns:
        pd.DataFrame: Subconjunto do DataFrame, ou DataFrame vazio se não encontrado.
    """
    codigos = [codigo] + list(args)
    linha_codigo = None

    for cod in codigos:
        linha_codigo = encontrar_linha_codigo(df, cod)
        if linha_codigo is not None:
            break

    if linha_codigo is None:
        return pd.DataFrame()

    # Localiza a primeira linha 'SUBTOTAL' após o código encontrado
    linha_subtotal = encontrar_linha_codigo(df.iloc[linha_codigo + 1:], "SUBTOTAL")
    if linha_subtotal is not None:
        linha_subtotal += 1  # Ajusta índice relativo ao slice

    return df.iloc[linha_codigo:linha_subtotal]



def gerar_df_dic_agrupado(carteira,dataframe, lista):
    dicionario = {}
    for codigo in lista:
        dicionario[f"{codigo.lower()}"] = agrupar_dataframe(dataframe, codigo,"Descrição")
    return dicionario

def somar_valores_de_dicionario(
    df_dict: dict,
    lista_codigos: list[str],
    coluna_valor: int = 1,
    forcar_negativo: bool = False,
) -> float:
    """Soma valores de um dicionário de DataFrames filtrado por códigos.

    Substitui as funções legadas ``gerar_outros_valores_moovpay``,
    ``gerar_outros_valores_pagar`` e ``gerar_outros_valores_receber``
    que dependiam de uma variável global ``df_dict_despesas`` inexistente.

    Args:
        df_dict: Dicionário ``{codigo_lower: pd.DataFrame}`` com os dados.
        lista_codigos: Códigos a somar.
        coluna_valor: Índice da coluna de valor em cada DataFrame. Padrão: 1.
        forcar_negativo: Se True, garante que valores positivos sejam negados.

    Returns:
        float: Soma dos valores encontrados.
    """
    resultado = 0.0
    for cod in lista_codigos:
        cod_lower = cod.lower()
        try:
            valor = float(df_dict[cod_lower].iloc[0, coluna_valor])
            if forcar_negativo and valor > 0:
                valor *= -1
            resultado += valor
        except (KeyError, IndexError, TypeError):
            print(f"Código '{cod_lower}' não encontrado no dicionário.")
    return resultado


def extrair_valor_fundo_investimento(dataframe):
    try:
        df = dataframe.copy()
        if not df.empty:
            return df.iloc[0, 9]
    except IndexError:
        print(f'Índice [0, 9] inválido para o DataFrame do código {dataframe}.')
        return 0
    return 0 

def calcular_renda_fixa(dataframe: pd.DataFrame) -> float:
    """Retorna o valor de subtotal da renda fixa no DataFrame.

    Args:
        dataframe: DataFrame com colunas 'Código' e 'Valor Bruto'.

    Returns:
        float: Valor do SUBTOTAL, ou 0.0 se não encontrado.
    """
    try:
        return float(
            dataframe.loc[dataframe["Código"] == "SUBTOTAL", "Valor Bruto"].values[0]
        )
    except (IndexError, KeyError, TypeError) as exc:
        print(f"Erro ao recuperar subtotal da renda fixa: {exc}")
        return 0.0


# Carrega os dados da aba DICIONARIO_CATEGORIA 

def salvar_novos_codigos(path, novos_codigos, nome_planilha="DICIONARIO_CATEGORIA"):
    import xlwings as xw
    
    if not novos_codigos.empty:
        app = xw.App(visible=False)
        try:
            wb = xw.Book(path)
            ws = wb.sheets[nome_planilha]
            
            # Encontra a última linha com dados
            ultima_linha = ws.range("A" + str(ws.cells.last_cell.row)).end("up").row + 1
            
            # Prepara os dados para inserção
            dados_para_inserir = novos_codigos[["Código"]].copy()
            dados_para_inserir["CATEGORIA"] = "VALIDAR"  # Adiciona coluna CATEGORIA
            
            # Escreve os dados na planilha
            ws.range(f"A{ultima_linha}").options(index=False, header=False).value = dados_para_inserir.values
            
            wb.save()
            print(f"{len(novos_codigos)} novos códigos adicionados com categoria 'VALIDAR'")
        finally:
            app.quit()




def gerar_categoria_cotas(codigo, path_relatorio, dict_renda):
    """Gera o DataFrame final com categorias"""
    try:
        # Obtém dados já validados e com categorias
        df_validado = validar_categorias(codigo, path_relatorio, dict_renda)
        
        # Seleciona colunas necessárias
        colunas = ["Código", "PU Mercado", "Valor Bruto", "Valor Líquido", "Quantidade","PU Mercado"]
        if "CATEGORIA" in df_validado.columns:
            colunas.append("CATEGORIA")
            
        return df_validado[colunas].copy()
        
    except Exception as e:
        print(f"ERRO em gerar_categoria_cotas: {str(e)}")
        return pd.DataFrame()

def validar_categorias(codigo, path_relatorio, dict_renda):
    """Valida categorias e salva novos códigos encontrados"""
    try:
        # 1. Carrega o dicionário de categorias existentes
        df_categorias_existentes = pd.read_excel(
            path_relatorio,
            sheet_name="DICIONARIO_CATEGORIA",
            engine='pyxlsb'
        )
        
        # Verificação crítica das colunas
        if 'Código' not in df_categorias_existentes.columns:
            raise KeyError('Coluna "Código" não encontrada no arquivo Excel')
        
        # 2. Filtra os dados atuais
        df_filtrado = dict_renda[codigo][
            (~dict_renda[codigo]["Código"].isin(["SUBTOTAL", "TOTAL", codigo.upper()])) &
            (dict_renda[codigo]["Código"].notna())
        ].copy()
        
        # 3. Identifica novos códigos (que não estão no Excel)
        novos_codigos = df_filtrado[~df_filtrado["Código"].isin(df_categorias_existentes["Código"])]
        
        # 4. Se houver novos códigos, salva no arquivo
        if not novos_codigos.empty:
            print(f"Encontrados {len(novos_codigos)} novos códigos")
            salvar_novos_codigos(path_relatorio, novos_codigos)
            
            # Atualiza o DataFrame de categorias existentes
            df_categorias_existentes = pd.concat(
                [df_categorias_existentes, novos_codigos[["Código"]]],
                ignore_index=True
            )
        
        # 5. Retorna o DataFrame completo com categorias
        df_completo = df_filtrado.merge(
            df_categorias_existentes,
            on="Código",
            how="left"
        )
        
        return df_completo
        
    except Exception as e:
        print(f"ERRO em validar_categorias: {str(e)}")
        return pd.DataFrame()






# ---------------------------------------------------------------------------
# Funções deprecadas — mantidas por compatibilidade retroativa
# ---------------------------------------------------------------------------
# DEPRECADO: Use src.core.converters.encontrar_linha_categoria() em código novo.
# Esta versão depende de uma variável global 'valores_procurados' que não existe
# no escopo atual — mantida apenas para não quebrar código legado que possa
# estar importando-a por nome.
def encontrar_linha_categoria_legado(categoria: str, valores_procurados: list) -> list:
    """(Deprecado) Localiza a linha de uma categoria em uma lista de valores.

    Deprecated:
        Use ``src.core.converters.encontrar_linha_categoria()`` em código novo.
        Esta função requer o parâmetro ``valores_procurados`` explicitamente.

    Args:
        categoria: Nome da categoria a localizar.
        valores_procurados: Lista de dicts ``{"nome": str, "linha": int}``.

    Returns:
        list: Lista com os índices de linha encontrados, ou [1] se não encontrado.
    """
    lin = [v["linha"] for v in valores_procurados if v["nome"] == categoria]
    if not lin:
        print(f"Linha não encontrada para categoria: {categoria}")
        return [1]
    return lin


# DEPRECADO: Use src.core.converters.resetar_cabecalho() em código novo.
def resetar_cabecalho(df: pd.DataFrame) -> pd.DataFrame:
    """(Deprecado) Promove a primeira linha como cabeçalho.

    Deprecated:
        Use ``src.core.converters.resetar_cabecalho()`` em código novo.
    """
    df = df.copy()
    df.columns = df.iloc[0]
    return df.iloc[1:].reset_index(drop=True)

def agrupar_dataframe(df,texto, coluna):
    #novo_df = df.copy()
    novo_df = df[df[coluna].str.contains(texto, case=False, na=False)].copy()
    #novo_df = novo_df[df_contas_pagar[coluna].str.contains(texto, case=False, na=False)]
    novo_df.loc[:,coluna] = texto
    resultado = novo_df.groupby(coluna, as_index=False).sum()

    return resultado 

def agrupar_dataframe_varias_condicoes(df, texto, coluna, novo_texto, *args):
    textos = [texto] + list(args)
    
    # Cria uma cópia do DataFrame para evitar modificar o original
    novo_df = df.copy()
    
    # Itera sobre cada texto para substituir
    for txt in textos:
        # Filtra as linhas que contêm o texto atual
        mask = novo_df[coluna].str.contains(txt, case=False, na=False)
        
        # Substitui o valor da coluna pelo novo_texto nas linhas filtradas
        novo_df.loc[mask, coluna] = novo_texto
    
    # Agrupa pelo novo_texto e soma os valores numéricos
    resultado = novo_df.groupby(coluna, as_index=False).sum()
    
    return resultado

def agrupar_dataframe_codigo(df, lista_palavras_chave):
    """
    Substitui TODAS as descrições pelo código referente,
    classificando o restante como "Contas a pagar/receber" e agrupando.
    """
    novo_df = df[df["Descrição"] != "TOTAL"].copy()  
    descricoes = novo_df['Descrição'].str.lower()
    palavras_chave = [p.lower() for p in lista_palavras_chave]
    
    # Substitui TODAS as descrições que contêm qualquer palavra-chave
    for palavra in palavras_chave:
        mask = descricoes.str.contains(palavra, na=False)
        novo_df.loc[mask, 'Descrição'] = palavra.capitalize()
    
    # Classifica o restante (o que não foi substituído)
    mask_nao_substituido = ~novo_df['Descrição'].str.lower().isin(palavras_chave)
    novo_df.loc[mask_nao_substituido, 'Descrição'] = novo_df.loc[mask_nao_substituido, 'Valor'].apply(
        lambda x: "Contas a receber" if x > 0 else "Contas a pagar"
    )
    
    # Agrupa por descrição modificada
    resultado = novo_df.groupby('Descrição', as_index=False)['Valor'].sum()
    
    return resultado.sort_values('Valor')


def encontrar_linha_codigo(df, codigo):

    linha = df.index[df['Código'] == codigo].tolist()
    return linha[0] if linha else None

def criar_df_entre_linhas(df: pd.DataFrame, codigo: str, *args: str) -> pd.DataFrame:
    """Cria um subconjunto do DataFrame entre o código e a próxima linha SUBTOTAL.

    Alias de ``criar_df_entre_linhas_unico`` para compatibilidade retroativa.

    Args:
        df: DataFrame com coluna 'Código'.
        codigo: Código principal a localizar.
        *args: Códigos alternativos (fallback).

    Returns:
        pd.DataFrame: Subconjunto ou DataFrame vazio se não encontrado.
    """
    return criar_df_entre_linhas_unico(df, codigo, *args)





def salvar_para_csv(df, nome_arquivo="resultado.csv"):
    try:
        df.to_csv(nome_arquivo, index=False, encoding='utf-8', sep=';', decimal=',')
        print(f"Arquivo salvo com sucesso: {nome_arquivo}")
    except Exception as e:
        print(f"Erro ao salvar o arquivo CSV: {e}")

def salvar_excel(df,nome_arquivo="resultado.xlsx"):
    try:
        df.to_excel(nome_arquivo, index=False)
        print(f"Arquivo salvo com sucesso: {nome_arquivo}")
    except Exception as e:
        print(f"Erro ao salvar o arquivo EXCEL: {e}")

def ajustar_formula(formula, linha_atual):
    # Regex para encontrar referências de células (ex: A1, B2, C3)
    padrao = re.compile(r'([A-Za-z]+)(\d+)')
    
    # Função para ajustar a referência da célula
    def ajustar_referencia(match):
        coluna = match.group(1)  # Captura a parte da coluna (ex: A, B, C)
        linha = int(match.group(2))  # Captura a parte da linha (ex: 1, 2, 3)
        # Ajusta a linha para a nova linha
        nova_linha = linha_atual
        return f"{coluna}{nova_linha}"  # Retorna a referência ajustada
    
    # Aplica o ajuste na fórmula
    formula_ajustada = padrao.sub(ajustar_referencia, formula)
    return formula_ajustada



def verificar_aba(wb, nome_aba):
    """Verifica se a aba existe na pasta de trabalho."""
    if nome_aba not in [sheet.name for sheet in wb.sheets]:
        raise ValueError(f"Planilha '{nome_aba}' não encontrada!")

def processar_aba(wb, nome_aba, mapeamento):
    """Processa uma aba específica com o mapeamento fornecido."""
    ws = wb.sheets[nome_aba]
    
    # Encontra a última linha de forma robusta
    last_cell = ws.range('C1048576').end('up')
    ultima_linha = last_cell.row + 1 if last_cell.row != 1 else 1
    
    # Processa cada coluna
    for col in range(1, ws.range("B2").end("right").column + 1):
        nome_coluna = ws.range(2, col).value
        if not nome_coluna:
            continue
            
        for item in mapeamento:
            if item["Categoria"] == nome_coluna:
                ws.range(ultima_linha, col).value = item["Valor"]
                break

def salvar_carteira_diaria(path, mapeamento_excel_cd, mapeamento_excel_mec):
    """Função principal para salvar dados nas abas CD e MEC."""
    app = xw.App(visible=False)
    try:
        # Fecha instâncias prévias e abre nova
        app.quit()
        app = xw.App(visible=False)
        
        wb = xw.Book(path)
        time.sleep(1)  # Garante carregamento completo
        
        # Verifica abas
        verificar_aba(wb, "CD")
        verificar_aba(wb, "MEC")
        
        # Processa cada aba
        processar_aba(wb, "CD", mapeamento_excel_cd)
        processar_aba(wb, "MEC", mapeamento_excel_mec)
        
        wb.save()
        print("Dados salvos com sucesso nas abas CD e MEC!")
        
    except Exception as e:
        print(f"Erro durante o processamento: {str(e)}")
        if 'wb' in locals():
            wb.close()
    finally:
        app.quit()


def calcular_valor_cota(df_categoria, categoria):
    cota_filtrada = df_categoria[df_categoria["CATEGORIA"] == categoria].copy()
    if cota_filtrada.empty:
        print(f"Aviso: Categoria '{categoria}' não encontrada.")
        return None
    valor_liquido = cota_filtrada["Valor Líquido"].sum()
    return valor_liquido


def calcular_qtd_cota(df_categoria, categoria):
    cota_filtrada = df_categoria[df_categoria["CATEGORIA"] == categoria].copy()
    if cota_filtrada.empty:
        print(f"Aviso: Categoria '{categoria}' não encontrada.")
        return 0
    valor_liquido = cota_filtrada["Quantidade"].sum()
    return valor_liquido
