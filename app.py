import streamlit as st

st.set_page_config(
    page_title="Divisor de PDF",
    page_icon="📄"
)

st.title("📄 Divisor de PDF")

st.write(
    "Envie um PDF e o sistema irá dividir "
    "o arquivo em partes de até 10 MB."
)

arquivo = st.file_uploader(
    "Selecione o PDF",
    type=["pdf"]
)

if arquivo:
    st.success(f"Arquivo recebido: {arquivo.name}")
