import streamlit as st
from pypdf import PdfReader, PdfWriter
from io import BytesIO
import zipfile


# ============================================================
# CONFIGURAÇÕES
# ============================================================

LIMITE_MB = 10
LIMITE_BYTES = LIMITE_MB * 1024 * 1024


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="Divisor de PDF",
    page_icon="📄",
    layout="centered"
)


# ============================================================
# TÍTULO
# ============================================================

st.title("📄 Divisor de PDF")

st.write(
    "Envie um PDF e ele será dividido automaticamente "
    "em arquivos de até 10 MB."
)

st.info(
    "Cada arquivo gerado terá no máximo 10 MB."
)


# ============================================================
# UPLOAD
# ============================================================

arquivo = st.file_uploader(
    "📂 Selecione o PDF",
    type=["pdf"]
)


# ============================================================
# FUNÇÃO PARA CRIAR PDF EM MEMÓRIA
# ============================================================

def criar_pdf(paginas):
    writer = PdfWriter()

    for pagina in paginas:
        writer.add_page(pagina)

    buffer = BytesIO()
    writer.write(buffer)

    return buffer.getvalue()


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

def dividir_pdf(arquivo_pdf):

    reader = PdfReader(arquivo_pdf)

    partes = []
    paginas_atual = []

    for pagina in reader.pages:

        paginas_teste = paginas_atual + [pagina]

        pdf_teste = criar_pdf(paginas_teste)

        if len(pdf_teste) <= LIMITE_BYTES:

            paginas_atual.append(pagina)

        else:

            if not paginas_atual:
                raise ValueError(
                    "Uma página individual ultrapassa 10 MB."
                )

            pdf_parte = criar_pdf(paginas_atual)

            partes.append(pdf_parte)

            paginas_atual = [pagina]

            pdf_pagina = criar_pdf(paginas_atual)

            if len(pdf_pagina) > LIMITE_BYTES:
                raise ValueError(
                    "Uma página individual ultrapassa 10 MB."
                )

    # Adiciona a última parte
    if paginas_atual:
        pdf_parte = criar_pdf(paginas_atual)
        partes.append(pdf_parte)

    return partes


# ============================================================
# PROCESSAMENTO
# ============================================================

if arquivo:

    tamanho_original = len(arquivo.getvalue())

    tamanho_mb = tamanho_original / (1024 * 1024)

    st.write(
        f"**Arquivo:** {arquivo.name}"
    )

    st.write(
        f"**Tamanho:** {tamanho_mb:.2f} MB"
    )

    if st.button("✂️ DIVIDIR PDF", type="primary"):

        with st.spinner("Processando PDF..."):

            try:

                partes = dividir_pdf(arquivo)

                st.success(
                    f"PDF dividido com sucesso em "
                    f"{len(partes)} arquivo(s)!"
                )

                # ====================================================
                # CRIA ZIP
                # ====================================================

                zip_buffer = BytesIO()

                nome_base = arquivo.name.rsplit(".", 1)[0]

                with zipfile.ZipFile(
                    zip_buffer,
                    "w",
                    zipfile.ZIP_DEFLATED
                ) as zip_file:

                    for i, parte in enumerate(partes, start=1):

                        nome_parte = (
                            f"{nome_base}_parte_{i:02d}.pdf"
                        )

                        zip_file.writestr(
                            nome_parte,
                            parte
                        )

                zip_buffer.seek(0)

                # ====================================================
                # INFORMAÇÕES
                # ====================================================

                st.subheader("📊 Arquivos gerados")

                for i, parte in enumerate(partes, start=1):

                    tamanho_parte = (
                        len(parte) / (1024 * 1024)
                    )

                    nome_parte = (
                        f"{nome_base}_parte_{i:02d}.pdf"
                    )

                    col1, col2 = st.columns(
                        [3, 1]
                    )

                    with col1:

                        st.write(
                            f"📄 {nome_parte}"
                        )

                        st.caption(
                            f"{tamanho_parte:.2f} MB"
                        )

                    with col2:

                        st.download_button(
                            "⬇️ Baixar",
                            data=parte,
                            file_name=nome_parte,
                            mime="application/pdf",
                            key=f"download_{i}"
                        )

                # ====================================================
                # DOWNLOAD ZIP
                # ====================================================

                st.divider()

                st.subheader(
                    "📦 Baixar todos os arquivos"
                )

                st.download_button(
                    label="⬇️ BAIXAR TODOS EM ZIP",
                    data=zip_buffer,
                    file_name=f"{nome_base}_dividido.zip",
                    mime="application/zip",
                    type="primary"
                )

            except Exception as erro:

                st.error(
                    f"Erro ao processar o PDF: {erro}"
                )
