# Liceul Teoretic „Traian” București, orar profesori 2024–2025

Sursă publică: https://www.liceultraianbucuresti.ro/documente/2024/ORAR_PROFESORI_2024_2025.pdf

PDF-ul și textul OCR conțin nume, deci nu sunt în arhivă. Numele sunt înlocuite cu T01–T56.

    pdftoppm -r 300 -gray ORAR_PROFESORI_2024_2025.pdf DIR/g   # apoi rotire -90° -> DIR/r-XX.png
    python3 deskew.py DIR
    python3 extract.py DIR traian_raw.json
    python3 build.py traian_raw.json
    python3 make_instance.py            # -> ../traian_anon.json
    cd .. && python3 exp_real.py && python3 exp_real_present.py
