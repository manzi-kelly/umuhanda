from app.services.pdf.parsing import NumberedChoiceStrategy, SourceLine


def test_parentheses_and_green_are_explicit_and_conflicts_fail_closed():
    parser = NumberedChoiceStrategy(r"^(\d+)\. (.+)", r"^([A-Da-d])\) (.+)", 20, marked_table=True)
    lines = [
        SourceLine("1.Example", 1, [50, 50, 150, 65]),
        SourceLine("(a) First", 1, [50, 70, 150, 85]),
        SourceLine("b)Second", 1, [50, 90, 150, 105]),
        SourceLine("2. Example", 1, [50, 110, 150, 125]),
        SourceLine("a) First", 1, [50, 130, 150, 145]),
        SourceLine("b) Second", 1, [50, 150, 150, 165], highlight=[50, 150, 150, 165]),
        SourceLine("3. Example", 1, [50, 170, 150, 185]),
        SourceLine("(a) First", 1, [50, 190, 150, 205]),
        SourceLine("b) Second", 1, [50, 210, 150, 225], highlight=[50, 210, 150, 225]),
    ]
    parser.feed(lines, 600, 800)
    questions = parser.finish()
    assert [question.selected_label for question in questions] == ["A", "B", None]
    assert questions[2].status == "NEEDS_REVIEW"
    assert questions[1].answers[0].evidence()["green_highlight"] == [50, 150, 150, 165]


def test_real_pdf_answer_markers_and_sign_coordinates():
    import hashlib
    import os
    from pathlib import Path

    import pymupdf
    import pytest

    from app.core.config import Settings
    from app.services.pdf.images import question_images
    from app.services.pdf.parsing import (
        apply_green_highlights,
        has_marked_table_layout,
        mark_table_rows,
        page_lines,
    )

    source = os.getenv("PHASE04I_SOURCE_PDF")
    if not source or not Path(source).is_file():
        pytest.skip("Set PHASE04I_SOURCE_PDF to the local road-rules source.")
    settings = Settings()
    with pymupdf.open(source) as document:
        parser = NumberedChoiceStrategy(
            settings.pdf_question_pattern,
            settings.pdf_option_pattern,
            settings.pdf_max_questions,
            marked_table=has_marked_table_layout(page_lines(document[0], 50000)),
        )
        assert parser.marked_table
        for page in document:
            parser.page = page.number + 1
            lines = page_lines(page, 50000)
            mark_table_rows(page, lines)
            apply_green_highlights(page, lines)
            parser.feed(lines, page.rect.width, page.rect.height)
        questions = {question.number: question for question in parser.finish()}
        for number, page, answer in (
            ("1", 1, "A"),
            ("2", 1, "C"),
            ("246", 71, "B"),
            ("338", 110, "A"),
            ("427", 146, "B"),
        ):
            question = questions[number]
            assert question.lines[0].page == page
            assert [option.label for option in question.options] == list("ABCD")
            assert question.selected_label == answer
            assert question.answers[0].text in document[page - 1].get_text()
        assert questions["338"].answers[0].highlight is not None
        assert questions["20"].selected_label == "A"
        assert questions["225"].selected_label == "B"
        assert questions["406"].selected_label == "A"

        class MemoryAssets:
            def asset(self, data):
                assert data.startswith(b"\x89PNG")
                digest = hashlib.sha256(data).hexdigest()
                return digest, digest

        image_question = questions["235"]
        assert image_question.selected_label == "C"
        images = list(
            question_images(
                document,
                image_question.regions,
                MemoryAssets(),
                raster_only=True,
                option_anchors=[
                    (option.label, option.lines[0]) for option in image_question.options
                ],
            )
        )
        assert sorted(asset["source_location"]["option_label"] for asset in images) == list("ABCD")
        assert all(asset["source_page_number"] == 67 for asset in images)

        region = pymupdf.Rect(questions["246"].regions[0]["bbox"])
        assert (
            sum(
                region.contains(pymupdf.Rect(image["bbox"]))
                for image in document[70].get_image_info()
            )
            == 1
        )


def test_green_answer_with_source_trailing_spaces_is_eligible():
    from types import SimpleNamespace

    from app.services.exam_bank import answer_index
    from app.services.pdf.parsing import evidence

    rect = [50, 70, 150, 85]
    mark = SourceLine("a) First  ", 1, rect, highlight=rect)
    option = SimpleNamespace(
        id=1,
        option_label="A",
        source_location=evidence([SourceLine("First  ", 1, rect)]),
    )
    draft = SimpleNamespace(answer_status="EXTRACTED_UNVERIFIED", source_question_number="1")
    answer = SimpleNamespace(
        verification_status="EXTRACTED_UNVERIFIED",
        selected_option_id=1,
        evidence_location=evidence([mark]),
        evidence_page_number=1,
        raw_answer_text=mark.text,
    )
    assert answer_index(draft, [option], answer, 1) == (0, "ELIGIBLE")


def test_numbered_clause_does_not_split_a_ruled_stem():
    parser = NumberedChoiceStrategy(r"^(\d+)\. (.+)", r"^([A-Da-d])\) (.+)", 20, marked_table=True)
    lines = [
        SourceLine("24. Stem ending in cm", 1, [40, 40, 140, 50], ruled_start=True),
        SourceLine("4. Continue stem", 1, [40, 50, 140, 60], ruled_start=False),
        SourceLine("(a) First", 1, [40, 60, 140, 70]),
        SourceLine("b) Second", 1, [40, 70, 140, 80]),
        SourceLine("25.", 1, [40, 90, 50, 100], ruled_start=True),
        SourceLine("Separated stem", 1, [60, 90, 140, 100], ruled_start=True),
        SourceLine("a) First", 1, [40, 100, 140, 110]),
        SourceLine("(b) Second", 1, [40, 110, 140, 120]),
    ]
    parser.feed(lines, 600, 800)
    first, second = parser.finish()
    assert first.number == "24" and first.lines[-1].text == "4. Continue stem"
    assert second.number == "25" and second.text == "Separated stem"
    assert [first.selected_label, second.selected_label] == ["A", "B"]
