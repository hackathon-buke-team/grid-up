"""Sunumu tek, bağımsız bir HTML dosyasına derler; istenirse PDF'ini de basar.

    python sunum/build.py          ->  sunum/index.html
    python sunum/build.py --pdf    ->  sunum/index.html + sunum/PANO-GOZ-Final-Sunumu.pdf

Kaynaklar sunum/src/ altında, görseller sunum/assets/ altındadır. Görseller data URI
olarak gömülür; çıktı internetsiz, tek dosya olarak açılır ve olduğu gibi barındırılabilir.

PDF, aynı HTML'in ?print görünümünden (engine.js "PDF BASKISI") Chrome ya da Edge'in
başsız yazdırmasıyla üretilir: her slayt 1280×720 bir sayfa, metin seçilebilir ve vektörel.
Tarayıcı yolu bulunamazsa CHROME ortam değişkeniyle verilir. PyMuPDF kuruluysa slayt
başlıkları PDF'e yer imi olarak yazılır.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src"
ASSETS = ROOT / "assets"
PDF = ROOT / "PANO-GOZ-Final-Sunumu.pdf"

CSS = ["deck.css", "slides.css"]
JS = ["helpers.js", "slides-a.js", "slides-b.js", "slides-c.js", "engine.js"]
ASSET_MAP = {
    "adm": "logo-adm-dark.png",
    "gdz": "logo-gdz-dark.png",
    "gridup": "logo-gridup-dark.png",
    "ekran_filo": "ekran-filo.webp",
    "ekran_ikiz": "ekran-ikiz.webp",
    "ekran_kanit": "ekran-kanit.webp",
    "ekran_bastir": "ekran-bastir.webp",
    "ekran_prpd": "ekran-prpd.webp",
    "ekran_scada": "ekran-scada.webp",
}
MIME = {".png": "image/png", ".webp": "image/webp", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml"}
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def data_uri(path: pathlib.Path) -> str:
    return f"data:{MIME[path.suffix.lower()]};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def build_html() -> pathlib.Path:
    tpl = (SRC / "index.template.html").read_text(encoding="utf-8")
    css = "\n".join((SRC / f).read_text(encoding="utf-8") for f in CSS)
    js = "\n;\n".join((SRC / f).read_text(encoding="utf-8") for f in JS)
    assets = {k: data_uri(ASSETS / v) for k, v in ASSET_MAP.items()}
    # Takım fotoğrafları: sunum/assets/foto_<ad>.jpg → A.foto_<ad> (TEAM.photo alanında kullanılır).
    for p in sorted(ASSETS.glob("foto*.*")):
        if p.suffix.lower() in MIME:
            assets[p.stem] = data_uri(p)
    out = (tpl.replace("/*CSS*/", css)
              .replace("/*ASSETS*/", json.dumps(assets))
              .replace("/*JS*/", js))
    target = ROOT / "index.html"
    target.write_text(out, encoding="utf-8")
    print(f"{target}  ·  {len(out) / 1024:.0f} KB  ·  {len(assets)} görsel")
    return target


def find_browser() -> str:
    cands = [os.environ.get("CHROME", "")] + BROWSERS
    cands += [shutil.which(n) or "" for n in ("chrome", "google-chrome", "chromium", "chromium-browser", "msedge")]
    for c in cands:
        if c and pathlib.Path(c).is_file():
            return c
    sys.exit("PDF için Chrome ya da Edge bulunamadı; yolunu CHROME ortam değişkeniyle verin.")


def build_pdf(html: pathlib.Path) -> None:
    browser = find_browser()
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run([
            browser, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
            f"--user-data-dir={profile}", "--no-pdf-header-footer", "--virtual-time-budget=15000",
            f"--print-to-pdf={PDF}", html.as_uri() + "?print",
        ], check=True, capture_output=True, timeout=180)
    finish_pdf()
    print(f"{PDF}  ·  {PDF.stat().st_size / 1024:.0f} KB")


def finish_pdf() -> None:
    """Slayt başlıklarını yer imi, künyeyi meta veri olarak yazar (PyMuPDF varsa)."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("PyMuPDF yok: PDF yer imsiz kaldı (pip install pymupdf)")
        return
    js = "\n".join((SRC / f).read_text(encoding="utf-8") for f in JS)
    titles = re.findall(r"^  title: '([^']+)'", js, re.M)
    team = re.search(r"const TEAM = \{\s*name: '([^']+)'", js)
    doc = fitz.open(PDF)
    if len(titles) == doc.page_count:
        doc.set_toc([[1, f"{i + 1}. {t}", i + 1] for i, t in enumerate(titles)])
    else:
        print(f"uyarı: {len(titles)} başlık, {doc.page_count} sayfa; yer imleri atlandı")
    doc.set_metadata({
        "title": "PANO GÖZ · Final Sunumu",
        "author": f"Takım {team.group(1)}" if team else "",
        "subject": "ADM & GDZ Elektrik · Grid Up Hackathon · Pano/hücre içi anomali erken uyarı sistemi",
        "keywords": "PANO GÖZ, θ, anomali, erken uyarı, AG pano, SCADA, Modbus",
        "creator": "sunum/build.py",
    })
    tmp = PDF.with_suffix(".tmp.pdf")
    doc.save(tmp, garbage=4, deflate=True)
    doc.close()
    tmp.replace(PDF)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdf", action="store_true", help="HTML'den sonra PDF'i de bas")
    args = ap.parse_args()
    html = build_html()
    if args.pdf:
        build_pdf(html)


if __name__ == "__main__":
    main()
