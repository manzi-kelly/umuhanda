"""Conservative geometric association of PDF visuals with questions and options."""

from itertools import combinations

import pymupdf


def clean_option_crop(rect, words):
    clip = pymupdf.Rect(rect)
    for word in words:
        box = pymupdf.Rect(word[:4])
        overlap = box & rect
        if overlap.get_area() <= 0:
            continue
        # PDF font boxes and image edges can differ by a fraction of a point.
        if box.x0 >= rect.x0 or box.x1 - rect.x0 > 0.2:
            return None
        clip.x0 = max(clip.x0, box.x1)
    return clip


def question_images(pdf, regions, storage, *, raster_only=False, option_anchors=()):
    emitted = set()
    for region in regions:
        page = pdf[region["page"] - 1]
        bounds = pymupdf.Rect(region["bbox"]) & page.rect
        candidates = []
        for image in page.get_image_info():
            rect = pymupdf.Rect(image["bbox"])
            if bounds.contains(rect) and min(rect.width, rect.height) >= 12:
                candidates.append((rect, "RASTER_REGION"))
        clusters = []
        for drawing in [] if raster_only and not option_anchors else page.get_drawings():
            rect = drawing["rect"]
            if (
                not bounds.contains(rect)
                or max(rect.width, rect.height) < 10
                or (raster_only and (rect.width > 140 or rect.height > 140))
            ):
                continue
            for index, cluster in enumerate(clusters):
                expanded = cluster + (-6, -6, 6, 6)
                if expanded.intersects(rect):
                    clusters[index] |= rect
                    break
            else:
                clusters.append(pymupdf.Rect(rect))
        for rect in clusters:
            if min(rect.width, rect.height) >= 12 and rect.width < page.rect.width * 0.8:
                candidates.append((rect, "VECTOR_REGION"))
        words = page.get_text("words") if raster_only and candidates else ()
        matches = {}
        if option_anchors:
            # These source rows place the printed label at the lower left of its image.
            for label, anchor in option_anchors:
                if anchor.page != region["page"]:
                    continue
                x, y = anchor.bbox[2], anchor.bbox[3]
                choices = [
                    (tuple(rect), kind)
                    for rect, kind in candidates
                    if x - 4 <= rect.x0 <= x + 48
                    and abs(rect.y1 - y) <= 13
                    and clean_option_crop(rect, words) is not None
                ]
                raster = [choice for choice in choices if choice[1] == "RASTER_REGION"]
                choices = raster or choices
                if len(choices) == 1:
                    matches[label] = choices[0]
            if any(
                pymupdf.Rect(left[0]).intersects(pymupdf.Rect(right[0]))
                for left, right in combinations(matches.values(), 2)
            ):
                matches = {}
            by_crop = {crop: label for label, crop in matches.items()}
        else:
            by_crop = {}
        for rect, kind in candidates[:20]:
            option_label = by_crop.get((tuple(rect), kind))
            if option_anchors and not option_label:
                continue
            marker = (region["page"], tuple(round(x, 1) for x in rect))
            if marker in emitted:
                continue
            emitted.add(marker)
            # Crop in PDF coordinates; render scale is bounded and aspect ratio retained.
            clip = (
                clean_option_crop(rect, words) if option_label else (rect + (-2, -2, 2, 2)) & bounds
            )
            if (
                raster_only
                and not option_label
                and any((pymupdf.Rect(word[:4]) & clip).get_area() > 0 for word in words)
            ):
                continue
            scale = min(2, 1200 / max(clip.width, clip.height))
            pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=clip, alpha=False)
            data = pix.tobytes("png")
            key, digest = storage.asset(data)
            yield {
                "storage_key": key,
                "sha256_hash": digest,
                "asset_type": kind,
                "source_page_number": region["page"],
                "source_location": {
                    "bbox": list(clip),
                    **({"option_label": option_label} if option_label else {}),
                },
            }
