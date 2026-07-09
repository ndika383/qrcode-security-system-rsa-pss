#!/usr/bin/env python3
"""Build the print-ready QR Code Security user manual DOCX."""

import math
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "dokumen"
SOURCE = DOCS / "manual_pengguna_qr_code_security.md"
ASSETS = DOCS / "manual-assets"
OUTPUT = DOCS / "Word" / "Buku_Panduan_Pengguna_QR_Code_Security_System.docx"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
CP = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC = "http://purl.org/dc/elements/1.1/"

for prefix, uri in (("w", W), ("r", R), ("cp", CP), ("dc", DC)):
    ET.register_namespace(prefix, uri)

SCREENSHOTS = [f"{i:02d}_" for i in range(28)]


def prepare_assets():
    """Split tall screenshots into readable A4 panels."""
    ASSETS.mkdir(exist_ok=True)
    for old in ASSETS.glob("*.jpg"):
        old.unlink()
    files = sorted((ROOT / "Screenshoot").glob("*.jpg"))
    files = [p for p in files if any(p.name.startswith(x) for x in SCREENSHOTS)]
    for source in files:
        with Image.open(source) as image:
            image = image.convert("RGB")
            if image.height <= 1250:
                image.save(ASSETS / source.name, quality=90, optimize=True)
                continue
            panel_count = math.ceil((image.height - 70) / (1250 - 70))
            panel_height = math.ceil((image.height + 70 * (panel_count - 1)) / panel_count)
            top = 0
            panel = 1
            while top < image.height:
                bottom = min(top + panel_height, image.height)
                image.crop((0, top, image.width, bottom)).save(
                    ASSETS / f"{source.stem}_{panel:02d}.jpg",
                    quality=90, optimize=True,
                )
                if bottom == image.height:
                    break
                top, panel = bottom - 70, panel + 1


def ensure(parent, tag):
    node = parent.find(f"{{{W}}}{tag}")
    return node if node is not None else ET.SubElement(parent, f"{{{W}}}{tag}")


def wattr(parent, tag, **values):
    node = ensure(parent, tag)
    for key, value in values.items():
        node.set(f"{{{W}}}{key}", value)
    return node


def style_document(xml):
    root = ET.fromstring(xml)
    styles = {s.get(f"{{{W}}}styleId"): s for s in root.findall(f"{{{W}}}style")}
    for style in styles.values():
        fonts = wattr(ensure(style, "rPr"), "rFonts", ascii="Arial", hAnsi="Arial", cs="Arial")
        fonts.set(f"{{{W}}}eastAsia", "Arial")
    normal = styles.get("Normal")
    if normal is not None:
        wattr(ensure(normal, "pPr"), "spacing", after="120", line="276", lineRule="auto")
        wattr(ensure(normal, "pPr"), "jc", val="both")
        wattr(ensure(normal, "rPr"), "sz", val="21")
    specs = {
        "Title": (44, "274060", False), "Subtitle": (26, "4F6D7A", False),
        "Heading1": (30, "274060", True), "Heading2": (26, "365F91", False),
        "Heading3": (23, "4F6D7A", False), "Heading4": (21, "4F6D7A", False),
        "TOCHeading": (32, "274060", True),
    }
    for name, (size, color, page_break) in specs.items():
        style = styles.get(name)
        if style is None:
            continue
        ppr, rpr = ensure(style, "pPr"), ensure(style, "rPr")
        wattr(ppr, "keepNext", val="1")
        wattr(ppr, "spacing", before="240", after="120")
        if page_break:
            wattr(ppr, "pageBreakBefore", val="1")
        wattr(rpr, "color", val=color)
        wattr(rpr, "sz", val=str(size))
        wattr(rpr, "b", val="1")
    caption = styles.get("Caption")
    if caption is not None:
        ppr, rpr = ensure(caption, "pPr"), ensure(caption, "rPr")
        wattr(ppr, "jc", val="center")
        wattr(ppr, "spacing", before="80", after="160")
        wattr(rpr, "color", val="5B6573")
        wattr(rpr, "sz", val="18")
        wattr(rpr, "i", val="1")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def header_xml():
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:hdr xmlns:w="{W}"><w:p><w:pPr><w:pStyle w:val="Header"/><w:jc w:val="right"/></w:pPr><w:r><w:rPr><w:color w:val="6B7280"/><w:sz w:val="17"/></w:rPr><w:t>BUKU PANDUAN PENGGUNA | QR CODE SECURITY SYSTEM</w:t></w:r></w:p></w:hdr>'''.encode()


def footer_xml():
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="{W}"><w:p><w:pPr><w:pStyle w:val="Footer"/><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:color w:val="6B7280"/><w:sz w:val="18"/></w:rPr><w:t>Halaman </w:t></w:r><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>1</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p></w:ftr>'''.encode()


def patch_docx(path):
    with ZipFile(path) as source:
        files = {name: source.read(name) for name in source.namelist()}
    files["word/styles.xml"] = style_document(files["word/styles.xml"])

    settings = ET.fromstring(files["word/settings.xml"])
    if settings.find(f"{{{W}}}mirrorMargins") is None:
        ET.SubElement(settings, f"{{{W}}}mirrorMargins")
    wattr(settings, "updateFields", val="true")
    files["word/settings.xml"] = ET.tostring(settings, encoding="utf-8", xml_declaration=True)

    core = ET.fromstring(files["docProps/core.xml"])
    for tag, value in {
        f"{{{DC}}}title": "Buku Panduan Pengguna QR Code Security System",
        f"{{{DC}}}creator": "Tim Pengelola QR Code Security System",
        f"{{{DC}}}subject": "Panduan operasional pengguna, operator, auditor, dan penguji",
        f"{{{CP}}}keywords": "QR Code, RSA-PSS, ECDSA, verifikasi, user manual",
    }.items():
        node = core.find(tag)
        if node is None:
            node = ET.SubElement(core, tag)
        node.text = value
    files["docProps/core.xml"] = ET.tostring(core, encoding="utf-8", xml_declaration=True)

    rels = ET.fromstring(files["word/_rels/document.xml.rels"])
    ids = [int(m.group(1)) for x in rels for m in [re.match(r"rId(\d+)$", x.get("Id", ""))] if m]
    hid, fid = f"rId{max(ids, default=0)+1}", f"rId{max(ids, default=0)+2}"
    for rid, kind, target in ((hid, "header", "header1.xml"), (fid, "footer", "footer1.xml")):
        ET.SubElement(rels, f"{{{PR}}}Relationship", Id=rid,
                      Type=f"http://schemas.openxmlformats.org/officeDocument/2006/relationships/{kind}",
                      Target=target)
    files["word/_rels/document.xml.rels"] = ET.tostring(rels, encoding="utf-8", xml_declaration=True)

    document = ET.fromstring(files["word/document.xml"])
    body = document.find(f"{{{W}}}body")
    sect = body.find(f"{{{W}}}sectPr")
    for child in list(sect):
        if child.tag in (f"{{{W}}}headerReference", f"{{{W}}}footerReference"):
            sect.remove(child)
    sect.insert(0, ET.Element(f"{{{W}}}footerReference", {f"{{{W}}}type": "default", f"{{{R}}}id": fid}))
    sect.insert(0, ET.Element(f"{{{W}}}headerReference", {f"{{{W}}}type": "default", f"{{{R}}}id": hid}))
    wattr(sect, "pgSz", w="11906", h="16838")
    wattr(sect, "pgMar", top="1134", right="1134", bottom="1134", left="1417", header="567", footer="567", gutter="0")
    wattr(sect, "pgNumType", start="1")
    files["word/document.xml"] = ET.tostring(document, encoding="utf-8", xml_declaration=True)

    types = ET.fromstring(files["[Content_Types].xml"])
    for part, kind in (("/word/header1.xml", "header"), ("/word/footer1.xml", "footer")):
        ET.SubElement(types, f"{{{CT}}}Override", PartName=part,
                      ContentType=f"application/vnd.openxmlformats-officedocument.wordprocessingml.{kind}+xml")
    files["[Content_Types].xml"] = ET.tostring(types, encoding="utf-8", xml_declaration=True)
    files["word/header1.xml"], files["word/footer1.xml"] = header_xml(), footer_xml()

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as handle:
        temp = Path(handle.name)
    try:
        with ZipFile(temp, "w", ZIP_DEFLATED, compresslevel=6) as target:
            for name, data in files.items():
                target.writestr(name, data)
        shutil.move(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def main():
    prepare_assets()
    OUTPUT.parent.mkdir(exist_ok=True)
    subprocess.run([
        "pandoc", str(SOURCE), "--from=markdown+raw_attribute", "--to=docx",
        "--standalone", "--toc", "--toc-depth=3", "--number-sections",
        "--metadata=lang:id-ID", "--metadata=toc-title:DAFTAR ISI",
        "--resource-path", str(DOCS), "--output", str(OUTPUT),
    ], cwd=DOCS, check=True)
    patch_docx(OUTPUT)
    OUTPUT.chmod(0o644)
    print(OUTPUT)


if __name__ == "__main__":
    main()
