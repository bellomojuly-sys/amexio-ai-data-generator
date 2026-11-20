# Daniel's PDF Template Studio is a separate app with its own requirements
# (Streamlit, PyMuPDF). Its regression script has no pytest tests; it runs in
# its own CI job (`template-studio` in .github/workflows/tests.yml).
collect_ignore = ["pdf_template_studio"]
