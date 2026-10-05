import gc
import io
import os
import re
import shutil
import tempfile
import time
import unicodedata
import zipfile

import streamlit as st
from pypdf import PdfReader, PdfWriter


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="Separador de Comprovantes",
    page_icon="📄",
    layout="wide",
)


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def normalizar_texto(texto):
    """
    Remove acentos, converte para maiúsculas
    e normaliza espaços.
    """

    if not texto:
        return ""

    texto = unicodedata.normalize(
        "NFKD",
        texto
    )

    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )

    texto = texto.upper()

    texto = re.sub(
        r"[^A-Z0-9]+",
        " ",
        texto
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


# ============================================================
# NOME SEGURO PARA ARQUIVO
# ============================================================

def nome_seguro(nome):

    nome = unicodedata.normalize(
        "NFKD",
        nome
    )

    nome = "".join(
        caractere
        for caractere in nome
        if not unicodedata.combining(caractere)
    )

    nome = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        nome
    )

    nome = re.sub(
        r"_+",
        "_",
        nome
    )

    return (
        nome.strip("._")
        or "arquivo"
    )


# ============================================================
# IDENTIFICAR NOME DO ARQUIVO
# ============================================================

def identificar_nome_arquivo(texto):
    """
    Tenta identificar o nome do arquivo/documento
    no texto da página.

    Exemplos esperados:

        1097-1026 LETO LTDA
        10958-1818 JFKAS
        1065656 MILTON LTDA

    Retorna:
        nome encontrado
        ou None
    """

    if not texto:
        return None

    linhas = texto.splitlines()

    for linha in linhas:

        linha_original = linha.strip()

        if not linha_original:
            continue

        linha = normalizar_texto(
            linha_original
        )

        # ----------------------------------------------------
        # PADRÃO 1
        #
        # Exemplo:
        # 1097-1026 LETO LTDA
        # 10958-1818 JFKAS
        # ----------------------------------------------------

        padrao_com_hifen = re.match(
            r"^(\d{3,})-(\d{3,})\s+(.+)$",
            linha
        )

        if padrao_com_hifen:

            numero1 = padrao_com_hifen.group(1)
            numero2 = padrao_com_hifen.group(2)
            empresa = padrao_com_hifen.group(3).strip()

            if empresa:

                return (
                    f"{numero1}-{numero2} {empresa}"
                )

        # ----------------------------------------------------
        # PADRÃO 2
        #
        # Exemplo:
        # 1065656 MILTON LTDA
        #
        # Atenção:
        # este padrão é mais genérico.
        # ----------------------------------------------------

        padrao_sem_hifen = re.match(
            r"^(\d{5,})\s+([A-Z][A-Z0-9 .&/-]{2,})$",
            linha
        )

        if padrao_sem_hifen:

            numero = padrao_sem_hifen.group(1)
            empresa = padrao_sem_hifen.group(2).strip()

            # Evita considerar linhas muito comuns
            palavras_proibidas = [
                "PAGAMENTO",
                "COMPROVANTE",
                "TRANSFERENCIA",
                "TRANSACAO",
                "DOCUMENTO",
                "NUMERO",
                "CODIGO",
                "VALOR",
                "DATA",
                "BANCO",
                "CONTA",
                "AGENCIA",
            ]

            if empresa not in palavras_proibidas:

                return (
                    f"{numero} {empresa}"
                )

    return None


# ============================================================
# IDENTIFICAÇÃO DO COMPROVANTE
# ============================================================

def identificar_comprovante(texto):
    """
    Identifica se a página possui características
    de um comprovante.

    Retorna:

        PIX
        TRANSFERENCIA
        PAGAMENTO
        TRANSACAO_BANCARIA
        None
    """

    texto = normalizar_texto(texto)

    if not texto:
        return None

    # ========================================================
    # PIX
    # ========================================================

    padroes_pix = [

        r"\bCOMPROVANTE\s+DE\s+PIX\b",
        r"\bCOMPROVANTE\s+PIX\b",
        r"\bCOMPROVANTE\s+DO\s+PIX\b",

        r"\bPIX\s+REALIZADO\b",
        r"\bPIX\s+EFETUADO\b",
        r"\bPAGAMENTO\s+PIX\b",

        r"\bPIX\s+ENVIADO\b",
        r"\bPIX\s+RECEBIDO\b",

        r"\bPAGAMENTO\s+REALIZADO\s+VIA\s+PIX\b",

        r"\bTRANSFERENCIA\s+VIA\s+PIX\b",

        r"\bTRANSACAO\s+PIX\b",
    ]

    for padrao in padroes_pix:

        if re.search(
            padrao,
            texto
        ):

            return "PIX"

    # ========================================================
    # TRANSFERÊNCIA
    # ========================================================

    padroes_transferencia = [

        r"\bCOMPROVANTE\s+DE\s+TRANSFERENCIA\b",
        r"\bCOMPROVANTE\s+TRANSFERENCIA\b",
        r"\bCOMPROVANTE\s+DA\s+TRANSFERENCIA\b",

        r"\bTRANSFERENCIA\s+REALIZADA\b",
        r"\bTRANSFERENCIA\s+EFETUADA\b",
        r"\bTRANSFERENCIA\s+BANCARIA\b",
        r"\bTRANSFERENCIA\s+ELETRONICA\b",
        r"\bTRANSFERENCIA\s+CONCLUIDA\b",

        r"\bCOMPROVANTE\s+TED\b",
        r"\bCOMPROVANTE\s+DOC\b",

        r"\bTED\s+REALIZADA\b",
        r"\bTED\s+EFETUADA\b",

        r"\bDOC\s+REALIZADO\b",
        r"\bDOC\s+EFETUADO\b",
    ]

    for padrao in padroes_transferencia:

        if re.search(
            padrao,
            texto
        ):

            return "TRANSFERENCIA"

    # ========================================================
    # COMPROVANTE DE PAGAMENTO
    # ========================================================

    padroes_pagamento = [

        r"\bCOMPROVANTE\s+DE\s+PAGAMENTO\b",
        r"\bCOMPROVANTE\s+PAGAMENTO\b",
        r"\bCOMPROVANTE\s+DO\s+PAGAMENTO\b",

        r"\bCOMPROVANTE\s+DE\s+PAGAMENTO\s+BANCARIO\b",
        r"\bCOMPROVANTE\s+DE\s+PAGAMENTO\s+ONLINE\b",

        r"\bPAGAMENTO\s+REALIZADO\b",
        r"\bPAGAMENTO\s+EFETUADO\b",
        r"\bPAGAMENTO\s+CONCLUIDO\b",
        r"\bPAGAMENTO\s+CONFIRMADO\b",
    ]

    for padrao in padroes_pagamento:

        if re.search(
            padrao,
            texto
        ):

            return "PAGAMENTO"

    # ========================================================
    # TRANSAÇÃO BANCÁRIA
    # ========================================================

    padroes_transacao = [

        r"\bCOMPROVANTE\s+DE\s+TRANSACAO\s+BANCARIA\b",
        r"\bCOMPROVANTE\s+TRANSACAO\s+BANCARIA\b",

        r"\bCOMPROVANTE\s+DE\s+TRANSACAO\b",

        r"\bTRANSACAO\s+BANCARIA\b",
        r"\bTRANSACAO\s+REALIZADA\b",
        r"\bTRANSACAO\s+EFETUADA\b",
        r"\bTRANSACAO\s+CONCLUIDA\b",
    ]

    for padrao in padroes_transacao:

        if re.search(
            padrao,
            texto
        ):

            return "TRANSACAO_BANCARIA"

    return None


# ============================================================
# FORMATAÇÃO DE TAMANHO
# ============================================================

def formatar_tamanho(tamanho):

    if tamanho is None:
        return "0 B"

    if tamanho < 1024:
        return f"{tamanho} B"

    if tamanho < 1024 * 1024:
        return f"{tamanho / 1024:.2f} KB"

    return f"{tamanho / (1024 * 1024):.2f} MB"


# ============================================================
# CRIAR PDF EM MEMÓRIA
# ============================================================

def criar_pdf_em_memoria(
    reader,
    indices_paginas
):
    """
    Cria um PDF em memória contendo somente
    as páginas informadas.
    """

    if not indices_paginas:
        return None

    writer = PdfWriter()

    for indice in indices_paginas:

        pagina = reader.pages[indice]

        writer.add_page(
            pagina
        )

    buffer = io.BytesIO()

    writer.write(
        buffer
    )

    writer.close()

    buffer.seek(0)

    return buffer.getvalue()


# ============================================================
# PROCESSAMENTO PRINCIPAL
# ============================================================

def processar_pdf(
    caminho_pdf,
    progress_bar,
    status
):

    inicio = time.time()

    # ========================================================
    # ABRIR PDF
    # ========================================================

    status.info(
        "📖 Abrindo PDF..."
    )

    reader = PdfReader(
        caminho_pdf,
        strict=False
    )

    total_paginas = len(
        reader.pages
    )

    if total_paginas == 0:

        raise ValueError(
            "O PDF não possui páginas."
        )

    # ========================================================
    # ESTRUTURA DOS ARQUIVOS
    # ========================================================

    arquivos = {}

    arquivo_atual = None

    diagnostico = []

    # ========================================================
    # CONTADORES
    # ========================================================

    quantidade_pix = 0
    quantidade_transferencia = 0
    quantidade_pagamento = 0
    quantidade_transacao = 0

    # ========================================================
    # ANALISAR PÁGINAS
    # ========================================================

    for indice in range(
        total_paginas
    ):

        numero_pagina = indice + 1

        status.info(
            f"🔍 Analisando página "
            f"{numero_pagina} de "
            f"{total_paginas}..."
        )

        progress_bar.progress(
            numero_pagina / total_paginas * 0.70
        )

        pagina = reader.pages[indice]

        # ----------------------------------------------------
        # EXTRAIR TEXTO
        # ----------------------------------------------------

        try:

            texto = (
                pagina.extract_text()
                or ""
            )

        except Exception as erro:

            texto = ""

            diagnostico.append(
                f"Página {numero_pagina}: "
                f"erro ao extrair texto: "
                f"{erro}"
            )

        # ----------------------------------------------------
        # TENTAR IDENTIFICAR NOVO ARQUIVO
        # ----------------------------------------------------

        nome_encontrado = identificar_nome_arquivo(
            texto
        )

        if nome_encontrado:

            arquivo_atual = nome_encontrado

            if arquivo_atual not in arquivos:

                arquivos[
                    arquivo_atual
                ] = {

                    "sem_comprovantes": [],

                    "comprovantes": [],

                    "tipos": [],
                }

        # ----------------------------------------------------
        # SE NÃO EXISTE NOME AINDA
        # ----------------------------------------------------

        if arquivo_atual is None:

            diagnostico.append(
                f"Página {numero_pagina}: "
                f"não foi possível identificar "
                f"o nome do arquivo."
            )

            continue

        # ----------------------------------------------------
        # IDENTIFICAR COMPROVANTE
        # ----------------------------------------------------

        tipo = identificar_comprovante(
            texto
        )

        # ----------------------------------------------------
        # COMPROVANTE
        # ----------------------------------------------------

        if tipo is not None:

            arquivos[
                arquivo_atual
            ][
                "comprovantes"
            ].append(
                indice
            )

            arquivos[
                arquivo_atual
            ][
                "tipos"
            ].append(
                tipo
            )

            # Contadores

            if tipo == "PIX":
                quantidade_pix += 1

            elif tipo == "TRANSFERENCIA":
                quantidade_transferencia += 1

            elif tipo == "PAGAMENTO":
                quantidade_pagamento += 1

            elif tipo == "TRANSACAO_BANCARIA":
                quantidade_transacao += 1

        # ----------------------------------------------------
        # SEM COMPROVANTE
        # ----------------------------------------------------

        else:

            arquivos[
                arquivo_atual
            ][
                "sem_comprovantes"
            ].append(
                indice
            )

    # ========================================================
    # VALIDAR
    # ========================================================

    if not arquivos:

        raise ValueError(
            "Nenhum arquivo foi identificado no PDF.\n\n"
            "Verifique se o nome dos arquivos aparece "
            "como texto no PDF."
        )

    # ========================================================
    # CRIAR PDFs INDIVIDUAIS
    # ========================================================

    status.info(
        "💾 Criando arquivos separados..."
    )

    progress_bar.progress(
        0.75
    )

    resultados_arquivos = {}

    for nome_arquivo, dados in arquivos.items():

        resultados_arquivos[
            nome_arquivo
        ] = {

            "sem_comprovantes": criar_pdf_em_memoria(
                reader,
                dados[
                    "sem_comprovantes"
                ]
            ),

            "comprovantes": criar_pdf_em_memoria(
                reader,
                dados[
                    "comprovantes"
                ]
            ),

            "paginas_sem_comprovantes": [
                pagina + 1
                for pagina in dados[
                    "sem_comprovantes"
                ]
            ],

            "paginas_comprovantes": [
                pagina + 1
                for pagina in dados[
                    "comprovantes"
                ]
            ],

            "tipos": dados[
                "tipos"
            ],
        }

    # ========================================================
    # CRIAR ZIP
    # ========================================================

    status.info(
        "📦 Criando ZIP..."
    )

    progress_bar.progress(
        0.90
    )

    buffer_zip = io.BytesIO()

    with zipfile.ZipFile(
        buffer_zip,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=1
    ) as zip_file:

        # ====================================================
        # PASTA SEM COMPROVANTES
        # ====================================================

        for nome_arquivo, dados in resultados_arquivos.items():

            dados_pdf = dados[
                "sem_comprovantes"
            ]

            if dados_pdf:

                nome_pdf = (
                    nome_seguro(
                        nome_arquivo
                    )
                    + ".pdf"
                )

                caminho_zip = (
                    "SEM_COMPROVANTES/"
                    + nome_pdf
                )

                zip_file.writestr(
                    caminho_zip,
                    dados_pdf
                )

        # ====================================================
        # PASTA COMPROVANTES
        # ====================================================

        for nome_arquivo, dados in resultados_arquivos.items():

            dados_pdf = dados[
                "comprovantes"
            ]

            if dados_pdf:

                nome_pdf = (
                    nome_seguro(
                        nome_arquivo
                    )
                    + ".pdf"
                )

                caminho_zip = (
                    "COMPROVANTES/"
                    + nome_pdf
                )

                zip_file.writestr(
                    caminho_zip,
                    dados_pdf
                )

    buffer_zip.seek(0)

    dados_zip = buffer_zip.getvalue()

    # ========================================================
    # TAMANHO
    # ========================================================

    tamanho_zip = len(
        dados_zip
    )

    # ========================================================
    # TOTAL DE PÁGINAS
    # ========================================================

    total_sem_comprovantes = 0
    total_comprovantes = 0

    for dados in resultados_arquivos.values():

        total_sem_comprovantes += len(
            dados[
                "paginas_sem_comprovantes"
            ]
        )

        total_comprovantes += len(
            dados[
                "paginas_comprovantes"
            ]
        )

    # ========================================================
    # TEMPO
    # ========================================================

    tempo_total = (
        time.time() - inicio
    )

    # ========================================================
    # RESULTADO
    # ========================================================

    resultado = {

        "total_paginas":
            total_paginas,

        "total_arquivos":
            len(
                resultados_arquivos
            ),

        "total_comprovantes":
            total_comprovantes,

        "total_sem_comprovantes":
            total_sem_comprovantes,

        "quantidade_pix":
            quantidade_pix,

        "quantidade_transferencia":
            quantidade_transferencia,

        "quantidade_pagamento":
            quantidade_pagamento,

        "quantidade_transacao":
            quantidade_transacao,

        "arquivos":
            resultados_arquivos,

        "dados_zip":
            dados_zip,

        "tamanho_zip":
            tamanho_zip,

        "diagnostico":
            diagnostico,

        "tempo_total":
            tempo_total,
    }

    progress_bar.progress(
        1.0
    )

    status.success(
        "✅ Processamento concluído!"
    )

    gc.collect()

    return resultado


# ============================================================
# INTERFACE
# ============================================================

st.title(
    "📄 Separador de Comprovantes"
)

st.write(
    """
O sistema analisa o PDF e identifica cada arquivo/documento
individualmente.

Para cada arquivo identificado serão criados:

📁 **SEM_COMPROVANTES**

📁 **COMPROVANTES**

Os arquivos são mantidos separados pelo nome identificado
no PDF.
"""
)

st.info(
    """
💡 Exemplo:

**SEM_COMPROVANTES**
- 1097-1026 LETO LTDA.pdf
- 10958-1818 JFKAS.pdf
- 1065656 MILTON LTDA.pdf

**COMPROVANTES**
- 1097-1026 LETO LTDA.pdf
- 10958-1818 JFKAS.pdf
- 1065656 MILTON LTDA.pdf
"""
)


# ============================================================
# UPLOAD
# ============================================================

arquivo_enviado = st.file_uploader(
    "Selecione o PDF que deseja processar",
    type=["pdf"]
)


if arquivo_enviado is not None:

    st.success(
        f"Arquivo selecionado: "
        f"**{arquivo_enviado.name}** "
        f"({formatar_tamanho(arquivo_enviado.size)})"
    )

    # ========================================================
    # BOTÃO PROCESSAR
    # ========================================================

    if st.button(
        "🚀 Processar PDF",
        type="primary",
        use_container_width=True
    ):

        pasta_trabalho = tempfile.mkdtemp(
            prefix="separador_comprovantes_"
        )

        caminho_pdf_original = os.path.join(
            pasta_trabalho,
            nome_seguro(
                arquivo_enviado.name
            )
        )

        try:

            # =================================================
            # SALVAR PDF ORIGINAL
            # =================================================

            with open(
                caminho_pdf_original,
                "wb"
            ) as arquivo:

                arquivo.write(
                    arquivo_enviado.getbuffer()
                )

            # =================================================
            # PROGRESSO
            # =================================================

            progress_bar = st.progress(
                0
            )

            status = st.empty()

            # =================================================
            # PROCESSAR
            # =================================================

            resultado = processar_pdf(
                caminho_pdf_original,
                progress_bar,
                status
            )

            # =================================================
            # RESULTADO
            # =================================================

            st.divider()

            st.subheader(
                "📊 Resultado"
            )

            col1, col2, col3, col4 = st.columns(
                4
            )

            col1.metric(
                "Total de páginas",
                resultado[
                    "total_paginas"
                ]
            )

            col2.metric(
                "Arquivos encontrados",
                resultado[
                    "total_arquivos"
                ]
            )

            col3.metric(
                "Comprovantes",
                resultado[
                    "total_comprovantes"
                ]
            )

            col4.metric(
                "Tempo",
                f"{resultado['tempo_total']:.1f}s"
            )

            # =================================================
            # CONFERÊNCIA
            # =================================================

            st.subheader(
                "🔐 Conferência"
            )

            total_classificado = (
                resultado[
                    "total_comprovantes"
                ]
                +
                resultado[
                    "total_sem_comprovantes"
                ]
            )

            if (
                total_classificado
                ==
                resultado[
                    "total_paginas"
                ]
            ):

                st.success(
                    "✅ Todas as páginas foram "
                    "classificadas corretamente."
                )

            else:

                st.warning(
                    "⚠️ Nem todas as páginas "
                    "foram classificadas."
                )

            # =================================================
            # ARQUIVOS IDENTIFICADOS
            # =================================================

            st.subheader(
                "📄 Arquivos identificados"
            )

            for nome_arquivo, dados in resultado[
                "arquivos"
            ].items():

                qtd_sem = len(
                    dados[
                        "paginas_sem_comprovantes"
                    ]
                )

                qtd_comprovantes = len(
                    dados[
                        "paginas_comprovantes"
                    ]
                )

                st.write(
                    f"**{nome_arquivo}**"
                )

                c1, c2 = st.columns(2)

                with c1:

                    st.write(
                        f"🟢 Sem comprovantes: "
                        f"**{qtd_sem} página(s)**"
                    )

                with c2:

                    st.write(
                        f"🔵 Comprovantes: "
                        f"**{qtd_comprovantes} página(s)**"
                    )

            # =================================================
            # TIPOS DE COMPROVANTES
            # =================================================

            st.subheader(
                "🔎 Tipos de comprovantes"
            )

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "🔵 PIX",
                resultado[
                    "quantidade_pix"
                ]
            )

            c2.metric(
                "🟢 Transferência",
                resultado[
                    "quantidade_transferencia"
                ]
            )

            c3.metric(
                "🟠 Pagamento",
                resultado[
                    "quantidade_pagamento"
                ]
            )

            c4.metric(
                "🟣 Transação bancária",
                resultado[
                    "quantidade_transacao"
                ]
            )

            # =================================================
            # DOWNLOAD ZIP
            # =================================================

            st.divider()

            st.subheader(
                "📦 Resultado final"
            )

            st.success(
                """
O ZIP contém duas pastas:

📁 **SEM_COMPROVANTES**

📁 **COMPROVANTES**
"""
            )

            st.write(
                f"**Tamanho do ZIP:** "
                f"{formatar_tamanho(resultado['tamanho_zip'])}"
            )

            st.download_button(
                label=(
                    "⬇️ BAIXAR ZIP — "
                    "ARQUIVOS SEPARADOS"
                ),

                data=resultado[
                    "dados_zip"
                ],

                file_name=(
                    "RESULTADO_COMPROVANTES.zip"
                ),

                mime="application/zip",

                key="download_zip_final",

                type="primary",

                use_container_width=True
            )

            # =================================================
            # CONFERÊNCIA DOS ARQUIVOS
            # =================================================

            st.divider()

            with st.expander(
                "🔎 Conferir páginas de cada arquivo"
            ):

                for nome_arquivo, dados in resultado[
                    "arquivos"
                ].items():

                    st.write(
                        f"### 📄 {nome_arquivo}"
                    )

                    st.write(
                        "**🟢 SEM_COMPROVANTES**"
                    )

                    if dados[
                        "paginas_sem_comprovantes"
                    ]:

                        st.write(
                            dados[
                                "paginas_sem_comprovantes"
                            ]
                        )

                    else:

                        st.info(
                            "Nenhuma página."
                        )

                    st.write(
                        "**🔵 COMPROVANTES**"
                    )

                    if dados[
                        "paginas_comprovantes"
                    ]:

                        st.write(
                            dados[
                                "paginas_comprovantes"
                            ]
                        )

                    else:

                        st.info(
                            "Nenhum comprovante."
                        )

                    st.divider()

            # =================================================
            # DIAGNÓSTICO
            # =================================================

            if resultado[
                "diagnostico"
            ]:

                with st.expander(
                    "⚠️ Diagnóstico"
                ):

                    for mensagem in resultado[
                        "diagnostico"
                    ]:

                        st.write(
                            mensagem
                        )

        # =====================================================
        # ERRO
        # =====================================================

        except Exception as erro:

            st.error(
                "❌ Ocorreu um erro durante "
                "o processamento."
            )

            st.exception(
                erro
            )

        # =====================================================
        # LIMPEZA
        # =====================================================

        finally:

            try:

                shutil.rmtree(
                    pasta_trabalho,
                    ignore_errors=True
                )

            except Exception:

                pass
