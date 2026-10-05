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
# NOME SEGURO
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

    return (
        nome.strip("._")
        or "arquivo"
    )


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

    Não guarda PageObjects em listas.
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
# CRIAR ZIP COM OS DOIS PDFs
# ============================================================

def criar_zip_final(
    dados_comprovantes,
    dados_sem_comprovantes
):
    """
    Cria um único ZIP contendo:

        COMPROVANTES.pdf
        SEM_COMPROVANTES.pdf
    """

    buffer_zip = io.BytesIO()

    with zipfile.ZipFile(
        buffer_zip,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=1
    ) as zip_file:

        # ----------------------------------------------------
        # PDF DE COMPROVANTES
        # ----------------------------------------------------

        if dados_comprovantes:

            zip_file.writestr(
                "COMPROVANTES.pdf",
                dados_comprovantes
            )

        # ----------------------------------------------------
        # PDF SEM COMPROVANTES
        # ----------------------------------------------------

        if dados_sem_comprovantes:

            zip_file.writestr(
                "SEM_COMPROVANTES.pdf",
                dados_sem_comprovantes
            )

    buffer_zip.seek(0)

    return buffer_zip.getvalue()


# ============================================================
# PROCESSAMENTO
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
    # LISTAS
    # ========================================================

    paginas_comprovantes = []

    paginas_sem_comprovantes = []

    tipos_paginas = {}

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
        # IDENTIFICAR
        # ----------------------------------------------------

        tipo = identificar_comprovante(
            texto
        )

        tipos_paginas[
            numero_pagina
        ] = tipo

        # ====================================================
        # COMPROVANTE
        # ====================================================

        if tipo is not None:

            paginas_comprovantes.append(
                indice
            )

            if tipo == "PIX":

                quantidade_pix += 1

            elif tipo == "TRANSFERENCIA":

                quantidade_transferencia += 1

            elif tipo == "PAGAMENTO":

                quantidade_pagamento += 1

            elif tipo == "TRANSACAO_BANCARIA":

                quantidade_transacao += 1

        # ====================================================
        # SEM COMPROVANTE
        # ====================================================

        else:

            paginas_sem_comprovantes.append(
                indice
            )

    # ========================================================
    # VALIDAÇÃO
    # ========================================================

    total_classificado = (
        len(paginas_comprovantes)
        +
        len(paginas_sem_comprovantes)
    )

    if total_classificado != total_paginas:

        raise ValueError(
            "Erro na classificação das páginas.\n\n"
            f"Total do PDF: {total_paginas}\n"
            f"Total classificado: {total_classificado}"
        )

    # ========================================================
    # VERIFICAR DUPLICIDADE
    # ========================================================

    conjunto_comprovantes = set(
        paginas_comprovantes
    )

    conjunto_sem_comprovantes = set(
        paginas_sem_comprovantes
    )

    paginas_duplicadas = (
        conjunto_comprovantes
        &
        conjunto_sem_comprovantes
    )

    if paginas_duplicadas:

        raise ValueError(
            "Erro: existem páginas classificadas "
            "nos dois grupos."
        )

    # ========================================================
    # CRIAR PDF COMPROVANTES
    # ========================================================

    status.info(
        "💾 Criando COMPROVANTES.pdf..."
    )

    progress_bar.progress(
        0.75
    )

    dados_comprovantes = criar_pdf_em_memoria(
        reader=reader,
        indices_paginas=paginas_comprovantes
    )

    # ========================================================
    # CRIAR PDF SEM COMPROVANTES
    # ========================================================

    status.info(
        "💾 Criando SEM_COMPROVANTES.pdf..."
    )

    progress_bar.progress(
        0.85
    )

    dados_sem_comprovantes = criar_pdf_em_memoria(
        reader=reader,
        indices_paginas=paginas_sem_comprovantes
    )

    # ========================================================
    # CRIAR ZIP FINAL
    # ========================================================

    status.info(
        "📦 Criando ZIP com os dois PDFs..."
    )

    progress_bar.progress(
        0.95
    )

    dados_zip = criar_zip_final(
        dados_comprovantes=dados_comprovantes,
        dados_sem_comprovantes=dados_sem_comprovantes
    )

    # ========================================================
    # TAMANHOS
    # ========================================================

    tamanho_comprovantes = (
        len(dados_comprovantes)
        if dados_comprovantes
        else 0
    )

    tamanho_sem_comprovantes = (
        len(dados_sem_comprovantes)
        if dados_sem_comprovantes
        else 0
    )

    tamanho_zip = len(
        dados_zip
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

        "total_comprovantes":
            len(paginas_comprovantes),

        "total_sem_comprovantes":
            len(paginas_sem_comprovantes),

        "quantidade_pix":
            quantidade_pix,

        "quantidade_transferencia":
            quantidade_transferencia,

        "quantidade_pagamento":
            quantidade_pagamento,

        "quantidade_transacao":
            quantidade_transacao,

        "paginas_comprovantes": [
            indice + 1
            for indice in paginas_comprovantes
        ],

        "paginas_sem_comprovantes": [
            indice + 1
            for indice in paginas_sem_comprovantes
        ],

        "tipos_paginas":
            tipos_paginas,

        "dados_comprovantes":
            dados_comprovantes,

        "dados_sem_comprovantes":
            dados_sem_comprovantes,

        "dados_zip":
            dados_zip,

        "tamanho_comprovantes":
            tamanho_comprovantes,

        "tamanho_sem_comprovantes":
            tamanho_sem_comprovantes,

        "tamanho_zip":
            tamanho_zip,

        "diagnostico":
            diagnostico,

        "tempo_total":
            tempo_total
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
O sistema analisa o PDF página por página e separa:

🔵 **COMPROVANTES**

🟢 **PÁGINAS SEM COMPROVANTES**

São reconhecidos:

• PIX

• Transferência

• TED

• DOC

• Comprovante de Pagamento

• Transação bancária
"""
)

st.info(
    """
💡 O PDF original não é alterado.

Ao final será disponibilizado **um único ZIP**
contendo:

📄 COMPROVANTES.pdf

📄 SEM_COMPROVANTES.pdf
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
                "Comprovantes",
                resultado[
                    "total_comprovantes"
                ]
            )

            col3.metric(
                "Sem comprovante",
                resultado[
                    "total_sem_comprovantes"
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

                st.error(
                    "❌ Existe diferença na "
                    "quantidade de páginas."
                )

            # =================================================
            # TIPOS IDENTIFICADOS
            # =================================================

            st.subheader(
                "🔎 Tipos de comprovantes identificados"
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
            # RESUMO DOS PDFs
            # =================================================

            st.divider()

            st.subheader(
                "📄 Arquivos gerados"
            )

            col1, col2 = st.columns(2)

            with col1:

                st.write(
                    "### 🔵 COMPROVANTES.pdf"
                )

                st.write(
                    f"**{resultado['total_comprovantes']} "
                    f"página(s)**"
                )

                st.write(
                    formatar_tamanho(
                        resultado[
                            "tamanho_comprovantes"
                        ]
                    )
                )

                if resultado[
                    "dados_comprovantes"
                ]:

                    st.download_button(
                        label="⬇️ Baixar COMPROVANTES.pdf",
                        data=resultado[
                            "dados_comprovantes"
                        ],
                        file_name="COMPROVANTES.pdf",
                        mime="application/pdf",
                        key="download_comprovantes",
                        use_container_width=True
                    )

                else:

                    st.info(
                        "Nenhum comprovante identificado."
                    )

            with col2:

                st.write(
                    "### 🟢 SEM_COMPROVANTES.pdf"
                )

                st.write(
                    f"**{resultado['total_sem_comprovantes']} "
                    f"página(s)**"
                )

                st.write(
                    formatar_tamanho(
                        resultado[
                            "tamanho_sem_comprovantes"
                        ]
                    )
                )

                if resultado[
                    "dados_sem_comprovantes"
                ]:

                    st.download_button(
                        label="⬇️ Baixar SEM_COMPROVANTES.pdf",
                        data=resultado[
                            "dados_sem_comprovantes"
                        ],
                        file_name="SEM_COMPROVANTES.pdf",
                        mime="application/pdf",
                        key="download_sem_comprovantes",
                        use_container_width=True
                    )

                else:

                    st.info(
                        "Não existem páginas sem comprovantes."
                    )

            # =================================================
            # ZIP ÚNICO
            # =================================================

            st.divider()

            st.subheader(
                "📦 Download dos dois arquivos"
            )

            st.success(
                "O ZIP abaixo contém os dois PDFs:"
            )

            st.write(
                """
                📄 **COMPROVANTES.pdf**

                📄 **SEM_COMPROVANTES.pdf**
                """
            )

            st.write(
                f"**Tamanho do ZIP:** "
                f"{formatar_tamanho(resultado['tamanho_zip'])}"
            )

            st.download_button(
                label=(
                    "⬇️ BAIXAR ZIP — "
                    "COMPROVANTES + SEM COMPROVANTES"
                ),
                data=resultado[
                    "dados_zip"
                ],
                file_name="COMPROVANTES_E_SEM_COMPROVANTES.zip",
                mime="application/zip",
                key="download_zip_final",
                type="primary",
                use_container_width=True
            )

            # =================================================
            # CONFERIR PÁGINAS
            # =================================================

            with st.expander(
                "🔎 Conferir páginas separadas"
            ):

                st.write(
                    "### 🔵 COMPROVANTES.pdf"
                )

                if resultado[
                    "paginas_comprovantes"
                ]:

                    st.write(
                        resultado[
                            "paginas_comprovantes"
                        ]
                    )

                else:

                    st.warning(
                        "Nenhum comprovante foi identificado."
                    )

                st.write(
                    "### 🟢 SEM_COMPROVANTES.pdf"
                )

                if resultado[
                    "paginas_sem_comprovantes"
                ]:

                    st.write(
                        resultado[
                            "paginas_sem_comprovantes"
                        ]
                    )

                else:

                    st.info(
                        "Nenhuma página ficou "
                        "neste grupo."
                    )

            # =================================================
            # DIAGNÓSTICO
            # =================================================

            if resultado[
                "diagnostico"
            ]:

                with st.expander(
                    "⚠️ Diagnóstico"
                ):

                    for mensagem in (
                        resultado[
                            "diagnostico"
                        ]
                    ):

                        st.write(
                            mensagem
                        )

            # =================================================
            # NENHUM COMPROVANTE
            # =================================================

            if (
                resultado[
                    "total_comprovantes"
                ]
                == 0
            ):

                st.warning(
                    "⚠️ Nenhum comprovante foi "
                    "identificado."
                )

                st.info(
                    """
Se o PDF possui comprovantes, mas nenhum foi
identificado, provavelmente o PDF é escaneado/imagem
ou utiliza textos diferentes dos padrões configurados.
"""
                )

            # =================================================
            # TODAS AS PÁGINAS SÃO COMPROVANTES
            # =================================================

            if (
                resultado[
                    "total_sem_comprovantes"
                ]
                == 0
            ):

                st.info(
                    "ℹ️ Todas as páginas foram "
                    "identificadas como comprovantes."
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
