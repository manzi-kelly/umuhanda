"""Validate extraction evidence and activate complete bank revisions atomically."""

import hashlib
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import UTC, datetime
from math import isfinite

from sqlalchemy import select, text

from app.models.exam_bank import BankQuestion, BankRevision
from app.models.pdf_import import (
    PdfDocument,
    QuestionDraft,
    QuestionDraftAnswer,
    QuestionDraftAsset,
    QuestionDraftOption,
)
from app.services.pdf.parsing import (
    BARE_MARKED,
    BARE_OPTION,
    MARKED_OPTION,
    TABLE_OPTION,
    covers_option,
)
from app.services.pdf.storage import PdfError

QUOTAS = {"HARD": 7, "MEDIUM": 4, "EASY": 9}
DIFFICULTY_POLICIES = {"DIFFICULTY_QUOTAS", "DIFFICULTY_BALANCED"}


def category_targets(sign_count):
    if type(sign_count) is not int or not 1 <= sign_count <= 19:
        return {}
    return {"ROAD_SIGN": sign_count, "GENERAL": 20 - sign_count}


SIGN = re.compile(r"\b(?:road signs?|traffic signs?|sign shown|icyapa|cyapa|ibyapa|byapa)\b", re.I)
FIGURE = re.compile(r"\b(?:image|illustration|figure|ishusho|amashusho)\b", re.I)
INLINE = re.compile(r"\s*(?:answer|igisubizo)\s*:\s*([A-D])\s*", re.I)
KEY = re.compile(r"\s*(\d{1,4})[.):\-]?\s+([A-D])\s*[.)]?\s*", re.I)
DIFFICULTY = re.compile(r"\s*(?:difficulty|urwego)\s*:\s*(HARD|MEDIUM|EASY)\s*", re.I)
ANSWER_MARKER = re.compile(r"\b(?:(?:correct|right)\s+answer|answer|igisubizo)\s*:\s*[A-D]\b", re.I)


def fingerprint(value):
    normalized = " ".join(unicodedata.normalize("NFKC", value).casefold().split())
    return hashlib.sha256(normalized.encode()).hexdigest()


def box(value):
    return (
        isinstance(value, list)
        and len(value) == 4
        and all(type(n) in (int, float) and isfinite(n) for n in value)
        and 0 <= value[0] < value[2]
        and 0 <= value[1] < value[3]
    )


def page_valid(page, pages):
    return type(page) is int and 1 <= page <= pages


def segments(location, pages):
    items = location.get("segments", []) if isinstance(location, dict) else []
    if not isinstance(items, list):
        return []
    if not all(
        isinstance(s, dict)
        and s.get("method") == "TEXT"
        and page_valid(s.get("page"), pages)
        and box(s.get("bbox"))
        and isinstance(s.get("text"), str)
        and s["text"].strip()
        for s in items
    ):
        return []
    return items


def matches_source(location, page, value, pages):
    items = segments(location, pages)
    return bool(items and items[0]["page"] == page and "\n".join(s["text"] for s in items) == value)


def answer_index(draft, options, answer, pages):
    if not answer or not answer.raw_answer_text:
        return None, "INELIGIBLE_MISSING_ANSWER"
    if (
        answer.verification_status != "EXTRACTED_UNVERIFIED"
        or draft.answer_status != "EXTRACTED_UNVERIFIED"
        or not matches_source(
            answer.evidence_location, answer.evidence_page_number, answer.raw_answer_text, pages
        )
    ):
        return None, "INELIGIBLE_AMBIGUOUS_ANSWER"
    labels = set()
    for source in segments(answer.evidence_location, pages):
        inline = INLINE.fullmatch(source["text"])
        key = KEY.fullmatch(source["text"])
        if inline:
            labels.add(inline[1].upper())
        elif key and key[1] == draft.source_question_number:
            labels.add(key[2].upper())
        elif bare := BARE_MARKED.fullmatch(source["text"]):
            if not any(
                not option.option_text
                and option.option_label == bare[1].upper()
                and segments(option.source_location, pages) == [source]
                for option in options
            ):
                return None, "INELIGIBLE_AMBIGUOUS_ANSWER"
            labels.add(bare[1].upper())
        elif marked := (
            MARKED_OPTION.fullmatch(source["text"])
            or (
                box(source.get("green_highlight"))
                and covers_option(source["green_highlight"], source["bbox"])
                and TABLE_OPTION.fullmatch(source["text"])
            )
        ):
            if not any(
                option.option_label == marked[1].upper()
                and (parts := segments(option.source_location, pages))
                and parts[0]["page"] == source["page"]
                and parts[0]["bbox"] == source["bbox"]
                and parts[0]["text"].strip() == marked[2]
                for option in options
            ):
                return None, "INELIGIBLE_AMBIGUOUS_ANSWER"
            labels.add(marked[1].upper())
        else:
            return None, "INELIGIBLE_AMBIGUOUS_ANSWER"
    for index, option in enumerate(options):
        if option.id == answer.selected_option_id and labels == {option.option_label}:
            return index, "ELIGIBLE"
    return None, "INELIGIBLE_AMBIGUOUS_ANSWER"


def valid_assets(draft, assets, storage, pages):
    verified = []
    for asset in assets:
        region = asset.source_location.get("bbox")
        if (
            asset.document_id != draft.document_id
            or not box(region)
            or not page_valid(asset.source_page_number, pages)
        ):
            continue
        if not any(
            r["page"] == asset.source_page_number
            and box(r["bbox"])
            and r["bbox"][0] <= region[0] < region[2] <= r["bbox"][2]
            and r["bbox"][1] <= region[1] < region[3] <= r["bbox"][3]
            for r in draft.source_location.get("regions", [])
        ):
            continue
        try:
            with storage.path(asset.storage_key).open("rb") as stream:
                if stream.read(8) != b"\x89PNG\r\n\x1a\n":
                    continue
                stream.seek(0)
                if hashlib.file_digest(stream, "sha256").hexdigest() != asset.sha256_hash:
                    continue
        except (OSError, PdfError):
            continue
        verified.append(
            {
                "storage_key": asset.storage_key,
                "sha256": asset.sha256_hash,
                "page": asset.source_page_number,
                "bbox": region,
                **(
                    {"option_label": label}
                    if (label := asset.source_location.get("option_label"))
                    else {}
                ),
            }
        )
    return verified


def image_option_source(option, assets, pages):
    parts = segments(option.source_location, pages)
    if len(parts) != 1:
        return False
    source = parts[0]
    label = BARE_MARKED.fullmatch(source["text"]) or BARE_OPTION.fullmatch(source["text"])
    return (
        label is not None
        and label[1].upper() == option.option_label
        and source["page"] == option.source_page_number
        and any(
            asset["option_label"] == option.option_label
            and asset["page"] == source["page"]
            and source["bbox"][2] - 4 <= asset["bbox"][0] <= source["bbox"][2] + 48
            and abs(asset["bbox"][3] - source["bbox"][3]) <= 13
            for asset in assets
        )
    )


def classify(draft, options, answer, assets, document, storage, duplicates):
    sign = bool(SIGN.search(draft.question_text))
    category = "ROAD_SIGN" if sign else "GENERAL"
    image_required = sign or FIGURE.search(draft.question_text)
    verified = valid_assets(draft, assets, storage, document.page_count)
    pages = document.page_count
    option_images = [asset for asset in verified if "option_label" in asset]
    image_labels = [asset["option_label"] for asset in option_images]
    empty_labels = [option.option_label for option in options if not option.option_text]
    text_options = [option for option in options if option.option_text]
    images_valid = not (empty_labels or image_labels) or (
        len(empty_labels) == len(options)
        and sorted(empty_labels) == sorted(image_labels)
        and len({asset["sha256"] for asset in option_images}) == len(option_images)
        and all(image_option_source(option, option_images, pages) for option in options)
    )
    labels = [o.option_label for o in options]
    difficulty = None
    metadata = segments(draft.source_location.get("difficulty"), pages)
    if len(metadata) == 1 and (match := DIFFICULTY.fullmatch(metadata[0]["text"])):
        difficulty = match[1].upper()
    index, state = answer_index(draft, options, answer, pages)
    if (
        draft.document_id != document.id
        or not draft.question_text.strip()
        or any(
            ANSWER_MARKER.search(value)
            for value in [draft.question_text, *(o.option_text for o in options)]
        )
        or not matches_source(
            draft.source_location, draft.source_page_number, draft.question_text, pages
        )
        or duplicates[fingerprint(draft.question_text)] > 1
    ):
        state = "INELIGIBLE_EXTRACTION_ERROR"
    elif (
        not 2 <= len(options) <= 4
        or labels != list("ABCD"[: len(labels)])
        or len({fingerprint(o.option_text) for o in text_options}) != len(text_options)
        or any(
            o.display_order != i
            or (
                o.option_text
                and not matches_source(
                    o.source_location, o.source_page_number, o.option_text, pages
                )
            )
            for i, o in enumerate(options)
        )
    ):
        state = "INELIGIBLE_INCOMPLETE_OPTIONS"
    elif not images_valid or (image_required and not verified) or len(verified) != len(assets):
        state = "INELIGIBLE_IMAGE_ERROR"
    elif draft.extraction_status != "EXTRACTED_UNVERIFIED" and state == "ELIGIBLE":
        state = "INELIGIBLE_EXTRACTION_ERROR"
    return BankQuestion(
        fingerprint=fingerprint(draft.question_text),
        source_order=draft.source_order,
        source_page=draft.source_page_number,
        source_location=draft.source_location,
        question_text=draft.question_text,
        options=[
            {
                "label": o.option_label,
                "text": o.option_text,
                "source_page": o.source_page_number,
                "source_location": o.source_location,
            }
            for o in options
        ],
        answer_evidence=answer.evidence_location if answer else None,
        correct_index=index if state == "ELIGIBLE" else None,
        assets=verified,
        category=category,
        difficulty=difficulty,
        eligibility=state,
    )


def grouped(session, model, job_id):
    rows = session.scalars(
        select(model)
        .join(QuestionDraft, model.question_draft_id == QuestionDraft.id)
        .where(QuestionDraft.import_job_id == job_id)
    )
    result = defaultdict(list)
    for row in rows:
        result[row.question_draft_id].append(row)
    return result


def finalize_bank(session, job, document, storage, policy, *, road_sign_count=1):
    # All writers serialize only the final transaction, after PDF work has completed.
    session.execute(text("SELECT pg_advisory_xact_lock(138112, 9)"))
    drafts = session.scalars(
        select(QuestionDraft).where(QuestionDraft.import_job_id == job.id)
    ).all()
    duplicates = Counter(fingerprint(d.question_text) for d in drafts)
    options = grouped(session, QuestionDraftOption, job.id)
    answers = grouped(session, QuestionDraftAnswer, job.id)
    assets = grouped(session, QuestionDraftAsset, job.id)
    questions = [
        classify(
            d,
            sorted(options[d.id], key=lambda o: o.display_order),
            next(iter(answers[d.id]), None),
            assets[d.id],
            document,
            storage,
            duplicates,
        )
        for d in drafts
    ]
    eligible = [q for q in questions if q.eligibility == "ELIGIBLE"]
    usable = [q for q in eligible if policy not in DIFFICULTY_POLICIES or q.difficulty in QUOTAS]
    difficulty = Counter(q.difficulty for q in usable)
    counts = Counter(q.eligibility for q in questions)
    counts.update(extracted=len(drafts), road_sign=sum(q.category == "ROAD_SIGN" for q in eligible))
    supported_answers = [q.answer_evidence for q in eligible]
    green_answers = sum(
        any(segment.get("green_highlight") for segment in answer["segments"])
        for answer in supported_answers
    )
    parenthesized_answers = sum(
        any(
            MARKED_OPTION.fullmatch(segment["text"]) or BARE_MARKED.fullmatch(segment["text"])
            for segment in answer["segments"]
        )
        for answer in supported_answers
    )
    image_only_options = sum(
        not option["text"] for question in questions for option in question.options
    )
    if image_only_options:
        counts["image_only_options"] = image_only_options
    if green_answers or parenthesized_answers:
        counts.update(
            supported_answers=len(supported_answers),
            green_answers=green_answers,
            parenthesized_answers=parenthesized_answers,
        )
    counts["difficulty"] = {key: difficulty[key] for key in QUOTAS}
    targets = category_targets(road_sign_count) if policy == "CATEGORY_BALANCED" else {}
    categories = Counter(q.category for q in usable)
    blockers = [
        item
        for item in job.diagnostics
        if policy != "CATEGORY_BALANCED"
        or item.get("code") != "UNSUPPORTED_QUESTION_STRUCTURE"
        or item.get("scope") != "QUESTION_LOCAL"
    ]
    unrecorded_warnings = max(0, job.failed_item_count - len(job.diagnostics))
    if targets:
        counts["category_targets"] = targets
        counts["category_available"] = {key: categories[key] for key in targets}
        counts["structural_warnings"] = len(job.diagnostics)
        counts["blocking_warnings"] = len(blockers) + unrecorded_warnings
    if blockers or unrecorded_warnings:
        status = "EXTRACTION_IMPROVEMENTS_REQUIRED"
    elif policy == "CATEGORY_BALANCED" and (
        not targets or any(categories[key] < count for key, count in targets.items())
    ):
        status = "INSUFFICIENT_CATEGORIES"
    elif policy == "DIFFICULTY_BALANCED" and any(difficulty[k] < n for k, n in QUOTAS.items()):
        status = "INSUFFICIENT_DIFFICULTY"
    elif len(usable) < 20 or set(categories) != {"ROAD_SIGN", "GENERAL"}:
        status = "INSUFFICIENT_QUESTIONS"
    elif policy in DIFFICULTY_POLICIES and any(difficulty[k] < n for k, n in QUOTAS.items()):
        status = "INSUFFICIENT_DIFFICULTY"
    else:
        status = "READY"
    revision = BankRevision(
        document_id=document.id,
        job_id=job.id,
        source_sha256=document.sha256_hash,
        policy=policy,
        status=status,
        counts=dict(counts),
        active=False,
    )
    session.add(revision)
    session.flush()
    for question in questions:
        question.revision_id = revision.id
    session.add_all(questions)
    if status == "READY":
        active = session.scalar(select(BankRevision).where(BankRevision.active))
        if active:
            old = session.get(PdfDocument, active.document_id)
            if (old.created_at, old.id) > (document.created_at, document.id):
                return revision
            active.active = False
            session.flush()
        revision.active = True
        revision.activated_at = datetime.now(UTC)
    return revision
