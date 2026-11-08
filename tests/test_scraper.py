from app.scraper import parse_sections


def test_parses_real_results_page(comp211_html):
    sections = parse_sections(comp211_html)

    assert [s.section for s in sections] == ["001", "002"]
    first, second = sections
    # Second row has no subject/catalog cells (rowspan); they must carry over.
    assert second.subject == "COMP" and second.catalog_number == "211"
    assert first.title == "System Programming Fundamental"
    assert first.term == "2027 Spring"
    assert first.schedule == "MWF 11:15 AM-12:05 PM"
    assert first.available_seats == 0
    assert second.available_seats == 40


def test_page_without_results_table():
    assert parse_sections("<html><body>No classes found</body></html>") == []


def test_parses_term_list(comp211_html):
    from app.scraper import parse_terms
    assert parse_terms(comp211_html) == ["2026 Fall", "2027 Spring"]
    assert parse_terms("<html></html>") == []


def test_parses_subject_list_sorted_and_unique(comp211_html):
    from app.scraper import parse_subjects
    subjects = parse_subjects(comp211_html)
    assert subjects == sorted(set(subjects))
    assert "COMP" in subjects and "MATH" in subjects
    assert len(subjects) > 100
