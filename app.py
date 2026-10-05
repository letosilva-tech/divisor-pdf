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
    page_title="Separador de Documentos Comprobatórios e Comprovantes",
    page_icon="📄",
    layout="wide"
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .rodape {
        text-align: center;
        margin-top: 60px;
        padding: 18px 0;
        color: #888888;
        font-size: 14px;
        border-top: 1px solid #444444;
    }

    .rodape strong {
        color: #aaaaaa;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# FUNÇÃO - NORMALIZAR TEXTO
# ============================================================

def normalizar_texto(texto):

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
# FUNÇÃO - NOME SEGURO
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

    nome = nome.strip("._")

    if not nome:
        nome = "arquivo"

    return nome


# ============================================================
# FUNÇÃO - FORMATAR TAMANHO
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
# IDENTIFICAR COMPROVANTE
# ============================================================

def identificar_comprovante(texto):

    texto = normalizar_texto(
        texto
    )

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
    # PAGAMENTO
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
# CRIAR PDF EM MEMÓRIA
# ============================================================

def criar_pdf_em_memoria(
    reader,
    indices_paginas
):

    if not indices_paginas:
        return None

    writer = PdfWriter()

    for indice in indices_paginas:

        writer.add_page(
            reader.pages[indice]
        )

    buffer = io.BytesIO()

    writer.write(
        buffer
    )

    writer.close()

    buffer.seek(0)

    return buffer.getvalue()


# ============================================================
# PROCESSAR UM PDF
# ============================================================

def processar_um_pdf(
    arquivo_enviado,
    pasta_trabalho,
    numero_arquivo,
    total_arquivos,
    progress_bar,
    status
):

    inicio = time.time()

    nome_original = arquivo_enviado.name

    # ========================================================
    # SALVAR PDF TEMPORÁRIO
    # ========================================================

    nome_temporario = nome_seguro(
        nome_original
    )

    caminho_pdf = os.path.join(
        pasta_trabalho,
        nome_temporario
    )

    with open(
        caminho_pdf,
        "wb"
    ) as arquivo:

        arquivo.write(
            arquivo_enviado.getbuffer()
        )


    # ========================================================
    # ABRIR PDF
    # ========================================================

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

    diagnostico = []


    # ========================================================
    # CONTADORES
    # ========================================================

    quantidade_pix = 0

    quantidade_transferencia = 0

    quantidade_pagamento = 0

    quantidade_transacao = 0


    # ========================================================
    # ANALISAR CADA PÁGINA
    # ========================================================

    for indice in range(
        total_paginas
    ):

        numero_pagina = indice + 1

        progresso_pdf = (
            numero_pagina
            /
            total_paginas
        )

        progresso_geral = (
            (
                numero_arquivo - 1
            )
            +
            progresso_pdf
        ) / total_arquivos

        progress_bar.progress(
            min(
                progresso_geral * 0.85,
                0.85
            )
        )

        status.info(
            f"📄 PDF {numero_arquivo} de "
            f"{total_arquivos} | "
            f"{nome_original} | "
            f"Página {numero_pagina} de "
            f"{total_paginas}"
        )

        pagina = reader.pages[indice]


        # ====================================================
        # EXTRAIR TEXTO
        # ====================================================

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


        # ====================================================
        # IDENTIFICAR
        # ====================================================

        tipo = identificar_comprovante(
            texto
        )


        # ====================================================
        # É COMPROVANTE
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
        # NÃO É COMPROVANTE
        # ====================================================

        else:

            paginas_sem_comprovantes.append(
                indice
            )


    # ========================================================
    # CONFERÊNCIA
    # ========================================================

    total_classificado = (
        len(paginas_comprovantes)
        +
        len(paginas_sem_comprovantes)
    )

    if total_classificado != total_paginas:

        raise ValueError(
            f"Nem todas as páginas foram classificadas.\n"
            f"PDF: {nome_original}\n"
            f"Total: {total_paginas}\n"
            f"Classificadas: {total_classificado}"
        )


    # ========================================================
    # CONFERIR DUPLICIDADE
    # ========================================================

    conjunto_comprovantes = set(
        paginas_comprovantes
    )

    conjunto_sem_comprovantes = set(
        paginas_sem_comprovantes
    )

    duplicadas = (
        conjunto_comprovantes
        &
        conjunto_sem_comprovantes
    )

    if duplicadas:

        raise ValueError(
            "Existem páginas classificadas "
            "nos dois grupos."
        )


    # ========================================================
    # CRIAR PDF COMPROVANTES
    # ========================================================

    status.info(
        f"💾 Separando comprovantes: "
        f"{nome_original}"
    )

    dados_comprovantes = criar_pdf_em_memoria(
        reader,
        paginas_comprovantes
    )


    # ========================================================
    # CRIAR PDF SEM COMPROVANTES
    # ========================================================

    status.info(
        f"💾 Separando documentos sem "
        f"comprovantes: {nome_original}"
    )

    dados_sem_comprovantes = criar_pdf_em_memoria(
        reader,
        paginas_sem_comprovantes
    )


    # ========================================================
    # RESULTADO
    # ========================================================

    resultado = {

        "nome_original":
            nome_original,

        "dados_comprovantes":
            dados_comprovantes,

        "dados_sem_comprovantes":
            dados_sem_comprovantes,

        "total_paginas":
            total_paginas,

        "total_comprovantes":
            len(
                paginas_comprovantes
            ),

        "total_sem_comprovantes":
            len(
                paginas_sem_comprovantes
            ),

        "paginas_comprovantes":
            [
                pagina + 1
                for pagina in paginas_comprovantes
            ],

        "paginas_sem_comprovantes":
            [
                pagina + 1
                for pagina in paginas_sem_comprovantes
            ],

        "quantidade_pix":
            quantidade_pix,

        "quantidade_transferencia":
            quantidade_transferencia,

        "quantidade_pagamento":
            quantidade_pagamento,

        "quantidade_transacao":
            quantidade_transacao,

        "diagnostico":
            diagnostico,

        "tempo_total":
            time.time() - inicio
    }


    # ========================================================
    # LIMPEZA
    # ========================================================

    try:

        os.remove(
            caminho_pdf
        )

    except Exception:

        pass

    gc.collect()

    return resultado


# ============================================================
# CRIAR ZIP FINAL
# ============================================================

def criar_zip_final(
    resultados
):

    buffer_zip = io.BytesIO()

    nomes_usados_sem = set()

    nomes_usados_com = set()


    with zipfile.ZipFile(
        buffer_zip,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=1
    ) as zip_file:


        # ====================================================
        # SEM COMPROVANTES
        # ====================================================

        for resultado in resultados:

            dados_pdf = resultado[
                "dados_sem_comprovantes"
            ]

            if not dados_pdf:
                continue

            nome_pdf = nome_seguro(
                resultado[
                    "nome_original"
                ]
            )

            nome_final = nome_pdf

            contador = 2

            while (
                nome_final.lower()
                in nomes_usados_sem
            ):

                base, extensao = os.path.splitext(
                    nome_pdf
                )

                nome_final = (
                    f"{base}_{contador}"
                    f"{extensao}"
                )

                contador += 1

            nomes_usados_sem.add(
                nome_final.lower()
            )

            caminho_zip = (
                "SEM_COMPROVANTES/"
                +
                nome_final
            )

            zip_file.writestr(
                caminho_zip,
                dados_pdf
            )


        # ====================================================
        # COMPROVANTES
        # ====================================================

        for resultado in resultados:

            dados_pdf = resultado[
                "dados_comprovantes"
            ]

            if not dados_pdf:
                continue

            nome_pdf = nome_seguro(
                resultado[
                    "nome_original"
                ]
            )

            nome_final = nome_pdf

            contador = 2

            while (
                nome_final.lower()
                in nomes_usados_com
            ):

                base, extensao = os.path.splitext(
                    nome_pdf
                )

                nome_final = (
                    f"{base}_{contador}"
                    f"{extensao}"
                )

                contador += 1

            nomes_usados_com.add(
                nome_final.lower()
            )

            caminho_zip = (
                "COMPROVANTES/"
                +
                nome_final
            )

            zip_file.writestr(
                caminho_zip,
                dados_pdf
            )


    buffer_zip.seek(0)

    return buffer_zip.getvalue()


# ============================================================
# TÍTULO
# ============================================================

st.title(
    "📄 Separador de Comprovantes"
)


# ============================================================
# DESCRIÇÃO
# ============================================================

st.markdown(
    """
Selecione **vários PDFs de uma vez**.

Cada PDF será analisado individualmente e suas páginas
serão separadas automaticamente entre:

🟢 **SEM_COMPROVANTES**

🔵 **COMPROVANTES**

O **nome original de cada PDF será preservado**.
"""
)


# ============================================================
# UPLOAD MÚLTIPLO
# ============================================================

arquivos_enviados = st.file_uploader(
    "Selecione os PDFs que deseja processar",
    type=["pdf"],
    accept_multiple_files=True,
    key="upload_pdfs"
)


# ============================================================
# SE EXISTEM ARQUIVOS
# ============================================================

if arquivos_enviados:

    st.success(
        f"📄 {len(arquivos_enviados)} "
        f"PDF(s) selecionado(s)."
    )


    # ========================================================
    # LISTA DE ARQUIVOS
    # ========================================================

    with st.expander(
        f"📋 Ver {len(arquivos_enviados)} "
        f"arquivo(s) selecionado(s)",
        expanded=True
    ):

        for numero, arquivo in enumerate(
            arquivos_enviados,
            start=1
        ):

            col1, col2 = st.columns(
                [5, 1]
            )

            with col1:

                st.write(
                    f"**{numero}.** "
                    f"{arquivo.name}"
                )

            with col2:

                st.write(
                    formatar_tamanho(
                        arquivo.size
                    )
                )


    st.divider()


    # ========================================================
    # BOTÃO PROCESSAR
    # ========================================================

    if st.button(
        "🚀 PROCESSAR TODOS OS PDFs",
        type="primary",
        use_container_width=True
    ):

        pasta_trabalho = tempfile.mkdtemp(
            prefix="separador_comprovantes_"
        )

        try:

            # =================================================
            # BARRA DE PROGRESSO
            # =================================================

            progress_bar = st.progress(
                0
            )

            status = st.empty()


            # =================================================
            # VARIÁVEIS
            # =================================================

            resultados = []

            erros = []

            total_arquivos = len(
                arquivos_enviados
            )

            inicio_total = time.time()


            # =================================================
            # PROCESSAR CADA PDF
            # =================================================

            for numero_arquivo, arquivo_enviado in enumerate(
                arquivos_enviados,
                start=1
            ):

                try:

                    resultado = processar_um_pdf(

                        arquivo_enviado=arquivo_enviado,

                        pasta_trabalho=pasta_trabalho,

                        numero_arquivo=numero_arquivo,

                        total_arquivos=total_arquivos,

                        progress_bar=progress_bar,

                        status=status
                    )

                    resultados.append(
                        resultado
                    )

                except Exception as erro:

                    erros.append(
                        {
                            "arquivo":
                                arquivo_enviado.name,

                            "erro":
                                str(erro)
                        }
                    )


            # =================================================
            # VERIFICAR PROCESSAMENTO
            # =================================================

            if not resultados:

                raise ValueError(
                    "Nenhum PDF foi processado "
                    "com sucesso."
                )


            # =================================================
            # CRIAR ZIP
            # =================================================

            status.info(
                "📦 Criando ZIP final..."
            )

            progress_bar.progress(
                0.90
            )

            dados_zip = criar_zip_final(
                resultados
            )


            # =================================================
            # FINAL
            # =================================================

            progress_bar.progress(
                1.0
            )

            status.success(
                "✅ Processamento concluído!"
            )


            tempo_total = (
                time.time()
                -
                inicio_total
            )


            # =================================================
            # ESTATÍSTICAS
            # =================================================

            total_paginas = sum(
                resultado[
                    "total_paginas"
                ]
                for resultado in resultados
            )

            total_comprovantes = sum(
                resultado[
                    "total_comprovantes"
                ]
                for resultado in resultados
            )

            total_sem_comprovantes = sum(
                resultado[
                    "total_sem_comprovantes"
                ]
                for resultado in resultados
            )

            total_pix = sum(
                resultado[
                    "quantidade_pix"
                ]
                for resultado in resultados
            )

            total_transferencias = sum(
                resultado[
                    "quantidade_transferencia"
                ]
                for resultado in resultados
            )

            total_pagamentos = sum(
                resultado[
                    "quantidade_pagamento"
                ]
                for resultado in resultados
            )

            total_transacoes = sum(
                resultado[
                    "quantidade_transacao"
                ]
                for resultado in resultados
            )


            # =================================================
            # RESULTADO GERAL
            # =================================================

            st.divider()

            st.subheader(
                "📊 Resultado geral"
            )


            col1, col2, col3, col4 = st.columns(
                4
            )


            col1.metric(
                "PDFs processados",
                len(resultados)
            )


            col2.metric(
                "Total de páginas",
                total_paginas
            )


            col3.metric(
                "Comprovantes",
                total_comprovantes
            )


            col4.metric(
                "Sem comprovantes",
                total_sem_comprovantes
            )


            # =================================================
            # TIPOS DE COMPROVANTES
            # =================================================

            st.subheader(
                "🔎 Tipos de comprovantes"
            )


            c1, c2, c3, c4 = st.columns(
                4
            )


            c1.metric(
                "🔵 PIX",
                total_pix
            )


            c2.metric(
                "🟢 Transferência",
                total_transferencias
            )


            c3.metric(
                "🟠 Pagamento",
                total_pagamentos
            )


            c4.metric(
                "🟣 Transação bancária",
                total_transacoes
            )


            # =================================================
            # RESULTADO POR PDF
            # =================================================

            st.subheader(
                "📄 Resultado por PDF"
            )


            for resultado in resultados:

                nome = resultado[
                    "nome_original"
                ]

                total_pdf = resultado[
                    "total_paginas"
                ]

                comprovantes_pdf = resultado[
                    "total_comprovantes"
                ]

                sem_comprovantes_pdf = resultado[
                    "total_sem_comprovantes"
                ]


                if comprovantes_pdf > 0:

                    icone = "🔵"

                else:

                    icone = "🟢"


                st.write(
                    f"{icone} **{nome}**"
                )


                c1, c2, c3 = st.columns(
                    3
                )


                with c1:

                    st.write(
                        f"Total: "
                        f"**{total_pdf} página(s)**"
                    )


                with c2:

                    st.write(
                        f"Comprovantes: "
                        f"**{comprovantes_pdf}**"
                    )


                with c3:

                    st.write(
                        f"Sem comprovantes: "
                        f"**{sem_comprovantes_pdf}**"
                    )


            # =================================================
            # ERROS
            # =================================================

            if erros:

                st.warning(
                    f"⚠️ {len(erros)} "
                    f"PDF(s) apresentaram erro."
                )


                with st.expander(
                    "⚠️ Ver arquivos com erro"
                ):

                    for item in erros:

                        st.error(
                            f"**{item['arquivo']}**\n\n"
                            f"{item['erro']}"
                        )


            # =================================================
            # DOWNLOAD
            # =================================================

            st.divider()

            st.subheader(
                "📦 Resultado final"
            )


            st.success(
                """
O ZIP foi criado com duas pastas:

🟢 **SEM_COMPROVANTES**

🔵 **COMPROVANTES**

Cada arquivo mantém o nome original.
"""
            )


            st.write(
                f"**Tamanho do ZIP:** "
                f"{formatar_tamanho(len(dados_zip))}"
            )


            st.write(
                f"**Tempo total:** "
                f"{tempo_total:.1f} segundos"
            )


            st.download_button(
                label=(
                    "⬇️ BAIXAR ZIP — "
                    "COMPROVANTES + SEM COMPROVANTES"
                ),

                data=dados_zip,

                file_name=(
                    "RESULTADO_COMPROVANTES.zip"
                ),

                mime="application/zip",

                key="download_zip_final",

                type="primary",

                use_container_width=True
            )


            # =================================================
            # CONFERÊNCIA DAS PÁGINAS
            # =================================================

            with st.expander(
                "🔎 Conferir páginas separadas"
            ):

                for resultado in resultados:

                    st.write(
                        f"### 📄 "
                        f"{resultado['nome_original']}"
                    )


                    st.write(
                        "🟢 **SEM_COMPROVANTES**"
                    )


                    if resultado[
                        "paginas_sem_comprovantes"
                    ]:

                        st.write(
                            "Páginas: "
                            +
                            str(
                                resultado[
                                    "paginas_sem_comprovantes"
                                ]
                            )
                        )

                    else:

                        st.info(
                            "Nenhuma página."
                        )


                    st.write(
                        "🔵 **COMPROVANTES**"
                    )


                    if resultado[
                        "paginas_comprovantes"
                    ]:

                        st.write(
                            "Páginas: "
                            +
                            str(
                                resultado[
                                    "paginas_comprovantes"
                                ]
                            )
                        )

                    else:

                        st.info(
                            "Nenhum comprovante."
                        )


                    st.divider()


            # =================================================
            # DIAGNÓSTICO
            # =================================================

            diagnosticos = []


            for resultado in resultados:

                for mensagem in resultado[
                    "diagnostico"
                ]:

                    diagnosticos.append(
                        f"{resultado['nome_original']}: "
                        f"{mensagem}"
                    )


            if diagnosticos:

                with st.expander(
                    "⚠️ Diagnóstico"
                ):

                    for mensagem in diagnosticos:

                        st.write(
                            mensagem
                        )


        # =====================================================
        # ERRO GERAL
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


# ============================================================
# RODAPÉ
# ============================================================

st.markdown(
    """
    <div class="rodape">
        Desenvolvido por <strong>Leto Milton</strong>
    </div>
    """,
    unsafe_allow_html=True
)
