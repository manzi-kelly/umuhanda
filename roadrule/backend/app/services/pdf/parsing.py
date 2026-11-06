"""Conservative numbered A-D strategy. No inference or rewriting of source answers."""

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol

import pymupdf

from app.services.pdf.storage import PdfError

MARKED_OPTION = re.compile(r"^\s*\(([A-Da-d])\)\s*(\S.*?)\s*$")
BARE_MARKED = re.compile(r"^\s*\(([A-Da-d])\)\s*$")
BARE_OPTION = re.compile(r"^\s*([A-Da-d])[.)]\s*$")
TABLE_OPTION = re.compile(r"^\s*([A-Da-d])[.)]\s*(\S.*?)\s*$")
TABLE_QUESTION = re.compile(r"^\s*(\d{1,4})\s*[.)]\s*([^\d\s].*)$")
RULED_NUMBER = re.compile(r"^\s*(\d{1,4})(?:\s*[.)]\s*|(?=[^\W\d_]))(.*?)\s*$")


def mark_table_rows(page, lines):
    rules = [
        drawing["rect"]
        for drawing in page.get_drawings()
        if drawing["rect"].width >= 150 and drawing["rect"].height <= 1
    ]
    columns = {}
    for rule in rules:
        columns.setdefault((round(rule.x0, 1), round(rule.x1, 1)), set()).add(rule.y0)
    for line in lines:
        x, y, right, bottom = line.bbox
        line.ruled_start = any(rule.x0 <= x <= rule.x1 and abs(y - rule.y0) <= 3 for rule in rules)
        cells = []
        for (left, edge), boundaries in columns.items():
            if not left <= x < right <= edge + 2:
                continue
            ordered = sorted(boundaries)
            cells.extend(
                ((line.page, left, top, edge, end), top == ordered[0], end == ordered[-1])
                for top, end in zip(ordered, ordered[1:], strict=False)
                if top - 0.25 <= y < bottom <= end + 0.25
            )
        if len(cells) == 1:
            line.table_cell, line.first_cell, line.last_cell = cells[0]


def table_question(line):
    if line.ruled_start is True:
        return RULED_NUMBER.fullmatch(line.text)
    return TABLE_QUESTION.fullmatch(line.text)


def covers_option(highlight, line):
    cover, text = pymupdf.Rect(highlight), pymupdf.Rect(line)
    overlap = cover & text
    return (
        not text.is_empty
        and overlap.width >= text.width * 0.9
        and overlap.height >= text.height * 0.65
        and cover.height <= text.height * 1.35
    )


def apply_green_highlights(page, lines):
    green = [
        drawing["rect"]
        for drawing in page.get_drawings()
        if drawing["fill"] == (0.0, 1.0, 0.0)
        and len(drawing["items"]) == 1
        and drawing["items"][0][0] == "re"
    ]
    for line in lines:
        if line.ocr or not TABLE_OPTION.fullmatch(line.text):
            continue
        covers = [rect for rect in green if covers_option(rect, line.bbox)]
        if len(covers) == 1:
            line.highlight = list(covers[0])


def has_marked_table_layout(lines):
    values = {line.text.strip() for line in lines if not line.ocr}
    return {"RESTRICTED", "IKINYARWANDA"} <= values and sum(
        bool(MARKED_OPTION.fullmatch(value)) for value in values
    ) >= 2


@dataclass
class SourceLine:
    text: str
    page: int
    bbox: list[float]
    ocr: bool = False
    highlight: list[float] | None = None
    ruled_start: bool | None = None
    table_cell: tuple | None = None
    first_cell: bool = False
    last_cell: bool = False

    def evidence(self):
        return {
            "page": self.page,
            "bbox": self.bbox,
            "text": self.text,
            "method": "OCR" if self.ocr else "TEXT",
            **({"green_highlight": self.highlight} if self.highlight else {}),
        }


@dataclass
class ParsedOption:
    label: str
    lines: list[SourceLine]
    image_only: bool = False

    @property
    def text(self):
        return "" if self.image_only else "\n".join(line.text for line in self.lines)


@dataclass
class ParsedQuestion:
    number: str
    lines: list[SourceLine]
    options: list[ParsedOption] = field(default_factory=list)
    regions: list[dict] = field(default_factory=list)
    answers: list[SourceLine] = field(default_factory=list)
    difficulty: SourceLine | None = None
    selected_label: str | None = None
    status: str = "ANSWER_NOT_FOUND"
    uncertain: bool = False
    raw_lines: list[SourceLine] = field(default_factory=list)

    @property
    def text(self):
        return "\n".join(line.text for line in self.lines)


class ParsingStrategy(Protocol):
    def feed(self, lines: list[SourceLine], width: float, height: float) -> None: ...
    def finish(self) -> list[ParsedQuestion]: ...


class NumberedChoiceStrategy:
    def __init__(
        self,
        question_pattern: str,
        option_pattern: str,
        max_questions: int,
        *,
        marked_table: bool = False,
    ):
        self.question = re.compile(question_pattern)
        self.option = re.compile(option_pattern)
        self.maximum = max_questions
        self.marked_table = marked_table
        self.questions: list[ParsedQuestion] = []
        self.number_occurrences: Counter[str] = Counter()
        self.current: ParsedQuestion | None = None
        self.keys: dict[str, list[SourceLine]] = {}
        self.key_mode = False
        self.page = 1
        self.diagnostics: list[dict] = []
        self.cell_starts: Counter = Counter()
        self.local_candidates: list[tuple[dict, tuple, tuple | None]] = []

    def close(self, boundary=None):
        if self.current:
            labels = [item.label for item in self.current.options]
            if len(labels) >= 2 and len(set(labels)) == len(labels) and self.current.text.strip():
                self.questions.append(self.current)
                if len(self.questions) > self.maximum:
                    raise PdfError("QUESTION_LIMIT")
            else:
                question = self.current
                diagnostic = {
                    "code": "UNSUPPORTED_QUESTION_STRUCTURE",
                    "page": question.regions[0]["page"],
                    "question": question.number,
                    "labels": labels,
                }
                self.diagnostics.append(diagnostic)
                if self.marked_table and len(labels) == 4 and len(set(labels)) == 3:
                    self.check_local_collision(question, diagnostic, boundary)
            self.current = None

    def check_local_collision(self, question, diagnostic, boundary):
        if not question.raw_lines or any(line.ocr for line in question.raw_lines):
            return
        first = question.raw_lines[0]
        cell = first.table_cell
        if not cell or not first.ruled_start:
            return
        other = [line for line in question.raw_lines if line.table_cell != cell]
        end = question.regions[-1]["bbox"][3]
        if not other and len(question.regions) == 1 and end >= cell[4] - 3:
            self.local_candidates.append((diagnostic, cell, None))
        if (
            not other
            and len(question.regions) == 2
            and first.last_cell
            and boundary
            and boundary.table_cell
            and boundary.first_cell
            and boundary.ruled_start
            and boundary.page == cell[0] + 1
            and (boundary.table_cell[1], boundary.table_cell[3]) == (cell[1], cell[3])
        ):
            self.local_candidates.append((diagnostic, cell, None))
        if not other or len(question.regions) != 2 or not first.last_cell:
            return
        continuation = other[0].table_cell
        if (
            continuation
            and other[0].first_cell
            and continuation[0] == cell[0] + 1
            and (continuation[1], continuation[3]) == (cell[1], cell[3])
            and end >= continuation[4] - 3
            and all(line.table_cell == continuation for line in other)
        ):
            self.local_candidates.append((diagnostic, cell, continuation))

    def feed(self, lines, width, height):
        lines = [line for line in lines if line.bbox[1] >= 24 and line.bbox[3] <= height - 24]
        if not lines:
            self.diagnostics.append({"code": "OCR_REQUIRED_UNAVAILABLE", "page": self.page})
            if self.current:
                self.current.uncertain = True
            return
        question_start = (
            table_question if self.marked_table else lambda line: self.question.match(line.text)
        )
        starts = [line for line in lines if question_start(line)]
        if (
            starts
            and max(line.bbox[0] for line in starts) - min(line.bbox[0] for line in starts)
            > width * 0.25
        ):
            self.close()
            self.diagnostics.append({"code": "MULTICOLUMN_REVIEW_REQUIRED", "page": lines[0].page})
            return
        if self.current and not self.key_mode:
            self.current.regions.append(
                {"page": lines[0].page, "bbox": [24, 24, width - 24, height - 24]}
            )
        for line in lines:
            value = line.text
            if self.marked_table and value.strip() in {"RESTRICTED", "IKINYARWANDA"}:
                continue
            if re.fullmatch(r"\s*(?:answer\s*key|answers|ibisubizo)\s*:?\s*", value, re.I):
                if self.current and self.current.regions:
                    self.current.regions[-1]["bbox"][3] = line.bbox[1]
                self.close()
                self.key_mode = True
                continue
            if self.key_mode:
                match = re.fullmatch(r"\s*(\d{1,4})[.):\-]?\s+([A-Da-d])\s*[.)]?\s*", value)
                if match:
                    self.keys.setdefault(match[1], []).append(line)
                elif value.strip():
                    self.diagnostics.append(
                        {"code": "UNRECOGNIZED_ANSWER_KEY_ROW", "page": line.page}
                    )
                continue
            match = question_start(line)
            if (
                match
                and self.marked_table
                and line.ruled_start is False
                and self.current
                and self.current.lines
                and not self.current.options
                and self.current.lines[-1].page == line.page
                and self.current.lines[-1].text.rstrip().casefold().endswith(" cm")
                and len(match[1]) == 1
                and int(match[1]) < int(self.current.number)
            ):
                match = None
            if match:
                self.number_occurrences[match[1]] += 1
                if line.table_cell:
                    self.cell_starts[line.table_cell] += 1
                if self.current and self.current.regions:
                    self.current.regions[-1]["bbox"][3] = line.bbox[1]
                self.close(line)
                self.current = ParsedQuestion(
                    match[1],
                    [SourceLine(match[2], line.page, line.bbox, line.ocr)] if match[2] else [],
                    uncertain=line.ocr,
                    raw_lines=[line],
                )
                self.current.regions.append(
                    {"page": line.page, "bbox": [24, line.bbox[1], width - 24, height - 24]}
                )
                continue
            if not self.current:
                continue
            if self.marked_table and re.fullmatch(r"\s*\d+\s*", value):
                continue
            self.current.raw_lines.append(line)
            if re.fullmatch(r"\s*(?:difficulty|urwego)\s*:\s*(HARD|MEDIUM|EASY)\s*", value, re.I):
                if self.current.difficulty is not None or line.ocr:
                    self.current.uncertain = True
                self.current.difficulty = line
                continue
            inline = re.fullmatch(r"\s*(?:answer|igisubizo)\s*:\s*([A-Da-d])\s*", value, re.I)
            if inline:
                self.current.answers.append(line)
                continue
            marked = MARKED_OPTION.fullmatch(value) if self.marked_table and not line.ocr else None
            option = marked or self.option.match(value)
            if option is None and self.marked_table:
                option = TABLE_OPTION.fullmatch(value)
            if marked or (option and self.marked_table and line.highlight):
                self.current.answers.append(line)
            bare_marked = (
                BARE_MARKED.fullmatch(value) if self.marked_table and not line.ocr else None
            )
            bare = bare_marked or (BARE_OPTION.fullmatch(value) if self.marked_table else None)
            if bare:
                self.current.options.append(ParsedOption(bare[1].upper(), [line], image_only=True))
                if bare_marked:
                    self.current.answers.append(line)
                continue
            if option:
                self.current.options.append(
                    ParsedOption(
                        option[1].upper(), [SourceLine(option[2], line.page, line.bbox, line.ocr)]
                    )
                )
            elif not re.fullmatch(r"\s*(?:page|urupapuro)?\s*\d+\s*", value, re.I):
                target = (
                    self.current.options[-1].lines if self.current.options else self.current.lines
                )
                if self.current.options and self.current.options[-1].image_only:
                    self.current.uncertain = True
                else:
                    target.append(line)

    def finish(self):
        self.close()
        for diagnostic, cell, continuation in self.local_candidates:
            if self.cell_starts[cell] == 1 and (
                not continuation or not self.cell_starts[continuation]
            ):
                regions = [{"page": cell[0], "bbox": list(cell[1:])}]
                if continuation:
                    regions.append({"page": continuation[0], "bbox": list(continuation[1:])})
                diagnostic.update(scope="QUESTION_LOCAL", regions=regions)
        counts = self.number_occurrences
        for item in self.questions:
            if self.marked_table:
                cells = {line.table_cell for line in item.raw_lines if line.table_cell}
                if len(cells) != len({cell[0] for cell in cells}):
                    item.uncertain = True
            item.answers += self.keys.get(item.number, [])
            all_lines = (
                item.lines
                + item.answers
                + [line for option in item.options for line in option.lines]
            )
            if any(line.ocr for line in all_lines):
                item.uncertain = True
            if item.answers:
                labels = []
                for line in item.answers:
                    match = (
                        (MARKED_OPTION.fullmatch(line.text) or BARE_MARKED.fullmatch(line.text))
                        if self.marked_table
                        else None
                    )
                    if not match and self.marked_table and line.highlight:
                        match = TABLE_OPTION.fullmatch(line.text)
                    if not match:
                        match = re.search(r"([A-Da-d])\s*[.)]?\s*$", line.text)
                    if match:
                        labels.append(match[1].upper())
                matching = [
                    option for option in item.options if labels and option.label == labels[0]
                ]
                if (
                    counts[item.number] == 1
                    and len(set(labels)) == 1
                    and len(matching) == 1
                    and not item.uncertain
                ):
                    item.selected_label = labels[0]
                    item.status = "EXTRACTED_UNVERIFIED"
                else:
                    item.status = "NEEDS_REVIEW"
            if counts[item.number] > 1:
                item.uncertain = True
        return self.questions


def page_lines(page, maximum: int, *, textpage=None):
    # Text flags exclude image binary payloads, keeping extraction page bounded.
    blocks = page.get_text(
        "dict", flags=pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES, textpage=textpage
    )["blocks"]
    result = []
    total = 0
    for block in blocks:
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"])
            total += len(text)
            if total > maximum or len(text) > 4000:
                raise PdfError("PAGE_TEXT_LIMIT")
            if text.strip():
                result.append(
                    SourceLine(text, page.number + 1, list(line["bbox"]), textpage is not None)
                )
    return sorted(result, key=lambda line: (round(line.bbox[1], 1), line.bbox[0]))


def evidence(lines):
    return {"segments": [line.evidence() for line in lines]}
