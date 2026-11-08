from pathlib import Path

import pytest

from regolith.builders.activitylogbuilder import published_or_non_article
from regolith.builders.basebuilder import LatexBuilderBase
from regolith.main import main

ARTICLE_WITH_DOI = {"_id": "article-with-doi", "entrytype": "article", "doi": "10.1/a"}
ARTICLE_WITHOUT_DOI = {"_id": "article-without-doi", "entrytype": "article"}
PROCEEDINGS_WITH_DOI = {"_id": "proceedings-with-doi", "entrytype": "inproceedings", "doi": "10.1/p"}
BOOK_WITHOUT_DOI = {"_id": "book-without-doi", "entrytype": "book"}


# Test selection of the citations that go into the annual activity report
@pytest.mark.parametrize(
    "publications, expected_ids",
    [
        # C1: articles with and without a DOI and a book without one, expect
        # the article with a DOI then the book, and the unpublished article left out
        pytest.param(
            [ARTICLE_WITH_DOI, ARTICLE_WITHOUT_DOI, BOOK_WITHOUT_DOI],
            ["article-with-doi", "book-without-doi"],
            id="unpublished-article-left-out",
        ),
        # C2: a conference paper with a DOI, which is both published and not
        # an article, expect it once
        pytest.param(
            [PROCEEDINGS_WITH_DOI, ARTICLE_WITH_DOI],
            ["proceedings-with-doi", "article-with-doi"],
            id="non-article-with-doi-once",
        ),
        # C3: no citations, expect none
        pytest.param([], [], id="empty"),
    ],
)
def test_published_or_non_article(publications, expected_ids):
    actual_ids = [pub["_id"] for pub in published_or_non_article(publications)]
    assert actual_ids == expected_ids


# Test that the LaTeX run for the annual activity report names the .tex file
# the builder wrote, so the PDF can be made
def test_annual_activity_pdf_names_the_written_tex_file(make_db, monkeypatch):
    latex_commands = []

    def record(self, cmd):
        latex_commands.append((Path(self.bldir), cmd))

    monkeypatch.setattr(LatexBuilderBase, "run", record)
    monkeypatch.chdir(make_db)
    main(["build", "annual-activity", "--people", "sbillinge", "--from", "2017-04-01"])
    tex_files = [bldir / arg for bldir, cmd in latex_commands for arg in cmd if arg.endswith(".tex")]
    assert tex_files
    for tex_file in tex_files:
        assert tex_file.is_file()
