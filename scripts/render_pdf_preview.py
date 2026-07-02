from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium


ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "output" / "pdf" / "manuale-utente-raspberry-wifi-portal.pdf"
OUTPUT_DIR = ROOT / "tmp" / "pdfs"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(PDF_PATH))
    for index in range(len(pdf)):
        page = pdf[index]
        bitmap = page.render(scale=2.0)
        image = bitmap.to_pil()
        output_path = OUTPUT_DIR / f"manuale-utente-page-{index + 1}.png"
        image.save(output_path)
        page.close()
    pdf.close()
    print(OUTPUT_DIR)


if __name__ == "__main__":
    main()
