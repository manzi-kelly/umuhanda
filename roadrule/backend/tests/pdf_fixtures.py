"""Clearly synthetic parser fixtures. Never real road-rules examination material."""

import pymupdf


def sample_pdf(*, answers=True, ambiguous=False, images=True):
    pdf = pymupdf.open()
    page = pdf.new_page()
    for y, line in [
        (35, "SYNTHETIC TEST FIXTURE - NOT EXAM CONTENT"),
        (60, "1. Iki ni ikibazo cy'igerageza?"),
        (78, "Uyu ni umurongo wa kabiri."),
        (100, "A. Ihitamo rya mbere"),
        (120, "B. Ihitamo rya kabiri"),
        (240, "2. Ikibazo gikomeza ku rundi rupapuro?"),
        (260, "A. Igisubizo kimwe"),
    ]:
        page.insert_text((40, y), line)
    if images:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 30, 30), False)
        pix.clear_with(200)
        page.insert_image(pymupdf.Rect(350, 90, 390, 130), stream=pix.tobytes("png"))
        page.insert_image(pymupdf.Rect(450, 5, 470, 25), stream=pix.tobytes("png"))
        page.draw_polyline(
            [(430, 140), (460, 90), (490, 140), (430, 140)], color=(1, 0, 0), width=2
        )
    page = pdf.new_page()
    page.insert_text((40, 60), "B. Igisubizo gikomeza")
    page.insert_text((40, 90), "kuri uyu murongo.")
    if answers:
        page = pdf.new_page()
        page.insert_text((40, 60), "Ibisubizo")
        page.insert_text((40, 90), "1. A")
        if ambiguous:
            page.insert_text((40, 110), "1. B")
        page.insert_text((40, 140), "2. B")
    data = pdf.tobytes()
    pdf.close()
    return data


def bulk_pdf(count=400):
    pdf = pymupdf.open()
    for start in range(1, count + 1, 8):
        page = pdf.new_page()
        page.insert_text((40, 30), "SYNTHETIC FIXTURE - NOT EXAM CONTENT")
        for offset, number in enumerate(range(start, min(start + 8, count + 1))):
            y = 60 + offset * 85
            page.insert_text((40, y), f"{number}. Ikibazo cy'igerageza {number}?")
            page.insert_text((40, y + 20), "A. Ihitamo rimwe")
            page.insert_text((40, y + 40), "B. Irindi hitamo")
    data = pdf.tobytes()
    pdf.close()
    return data
