import streamlit as st
from pypdf import PdfReader, PdfWriter
from io import BytesIO
import zipfile
import fitz


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
    "Páginas muito grandes serão comprimidas automaticamente."
)


# ============================================================
# UPLOAD
# ============================================================

arquivo = st.file_uploader(
    "📂 Selecione o PDF",
    type=["pdf"]
)


# ============================================================
# CRIA PDF COM PYPDF
# ============================================================

def criar_pdf(paginas):

    writer = PdfWriter()

    for pagina in paginas:
        writer.add_page(pagina)

    buffer = BytesIO()

    writer.write(buffer)

    return buffer.getvalue()


# ============================================================
# COMPRIME UMA PÁGINA GRANDE
# ============================================================

def comprimir_pagina(pdf_bytes):

    documento = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    )

    pagina = documento[0]

    # Tentativas de compressão
    tentativas = [
        (120, 70),
        (100, 60),
        (85, 50),
        (72, 45),
        (60, 40)
    ]

    for dpi, qualidade in tentativas:

        largura = pagina.rect.width
        altura = pagina.rect.height

        escala = dpi / 72

        matriz = fitz.Matrix(
            escala,
            escala
        )

        imagem = pagina.get_pixmap(
            matrix=matriz,
            alpha=False
        )

        jpg = imagem.tobytes(
            "jpg",
            jpg_quality=qualidade
        )

        novo_pdf = fitz.open()

        nova_pagina = novo_pdf.new_page(
            width=largura,
            height=altura
        )

        nova_pagina.insert_image(
            nova_pagina.rect,
            stream=jpg
        )

        resultado = novo_pdf.tobytes(
            garbage=4,
            deflate=True,
            clean=True
        )

        novo_pdf.close()

        if len(resultado) <= LIMITE_BYTES:
            documento.close()
            return resultado

    documento.close()

    raise ValueError(
        "Não foi possível reduzir uma página para menos de 10 MB."
    )


# ============================================================
# DIVISÃO DO PDF
# ============================================================

def dividir_pdf(arquivo_pdf):

    reader = PdfReader(arquivo_pdf)

    partes = []

    paginas_atual = []

    for numero, pagina in enumerate(
        reader.pages,
        start=1
    ):

        # Testa a página junto com as páginas atuais
        teste = criar_pdf(
            paginas_atual + [pagina]
        )

        # Se couber no limite
        if len(teste) <= LIMITE_BYTES:

            paginas_atual.append(pagina)

        else:

            # Se já temos páginas acumuladas,
            # salva a parte atual
            if paginas_atual:

                parte = criar_pdf(
                    paginas_atual
                )

                partes.append(
                    parte
                )

                paginas_atual = []

            # Agora testa a página sozinha
            pagina_individual = criar_pdf(
                [pagina]
            )

            if len(pagina_individual) <= LIMITE_BYTES:

                paginas_atual.append(
                    pagina
                )

            else:

                # Página individual maior que 10 MB
                st.write(
                    f"🗜️ Comprimindo página {numero}..."
                )

                pagina_comprimida = (
                    comprimir_pagina(
                        pagina_individual
                    )
                )

                partes.append(
                    pagina_comprimida
                )

    # Última parte
    if paginas_atual:

        parte = criar_pdf(
            paginas_atual
        )

        partes.append(
            parte
        )

    return partes


# ============================================================
# PROCESSAMENTO
# ============================================================

if arquivo:

    tamanho_original = len(
        arquivo.getvalue()
    )

    tamanho_mb = (
        tamanho_original /
        (1024 * 1024)
    )

    st.write(
        f"**Arquivo:** {arquivo.name}"
    )

    st.write(
        f"**Tamanho original:** "
        f"{tamanho_mb:.2f} MB"
    )

    if st.button(
        "✂️ DIVIDIR PDF",
        type="primary"
    ):

        try:

            with st.spinner(
                "Analisando e dividindo o PDF..."
            ):

                partes = dividir_pdf(
                    arquivo
                )

            st.success(
                f"PDF processado com sucesso! "
                f"{len(partes)} arquivo(s) gerado(s)."
            )

            # ====================================================
            # ZIP
            # ====================================================

            zip_buffer = BytesIO()

            nome_base = arquivo.name.rsplit(
                ".",
                1
            )[0]

            with zipfile.ZipFile(
                zip_buffer,
                "w",
                zipfile.ZIP_DEFLATED
            ) as zip_file:

                for i, parte in enumerate(
                    partes,
                    start=1
                ):

                    nome_parte = (
                        f"{nome_base}_parte_{i:02d}.pdf"
                    )

                    zip_file.writestr(
                        nome_parte,
                        parte
                    )

            zip_buffer.seek(0)

            # ====================================================
            # RESULTADOS
            # ====================================================

            st.subheader(
                "📊 Arquivos gerados"
            )

            for i, parte in enumerate(
                partes,
                start=1
            ):

                tamanho_parte = (
                    len(parte) /
                    (1024 * 1024)
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
            # ZIP
            # ====================================================

            st.divider()

            st.subheader(
                "📦 Baixar todos"
            )

            st.download_button(
                label="⬇️ BAIXAR TODOS EM ZIP",
                data=zip_buffer,
                file_name=(
                    f"{nome_base}_dividido.zip"
                ),
                mime="application/zip",
                type="primary"
            )

        except Exception as erro:

            st.error(
                f"Erro ao processar o PDF: {erro}"
            )
