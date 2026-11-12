from app.knowledge import load_tenants


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_loads_each_subdirectory_as_tenant(tmp_path):
    _write(tmp_path / "salon" / "cennik.md", "Strzyżenie 80 zł")
    _write(tmp_path / "sklep" / "zwroty.md", "Zwrot w 14 dni")

    tenants = load_tenants(tmp_path)

    assert set(tenants) == {"salon", "sklep"}
    assert "Strzyżenie 80 zł" in tenants["salon"]


def test_files_are_joined_alphabetically_with_filename_header(tmp_path):
    _write(tmp_path / "salon" / "b_godziny.md", "Pn-Pt 9-17")
    _write(tmp_path / "salon" / "a_cennik.md", "Strzyżenie 80 zł")

    text = load_tenants(tmp_path)["salon"]

    assert text.index("a_cennik") < text.index("b_godziny")
    assert "## a_cennik" in text


def test_ignores_non_markdown_files_and_loose_files(tmp_path):
    _write(tmp_path / "salon" / "faq.md", "Pytania")
    _write(tmp_path / "salon" / "notatki.txt", "ignoruj")
    _write(tmp_path / "README.md", "luźny plik")

    tenants = load_tenants(tmp_path)

    assert set(tenants) == {"salon"}
    assert "ignoruj" not in tenants["salon"]


def test_skips_invalid_tenant_names_and_empty_tenants(tmp_path):
    _write(tmp_path / "Zły Tenant" / "faq.md", "x")
    _write(tmp_path / "ok-1" / "faq.md", "dobry")
    (tmp_path / "pusty").mkdir()

    assert set(load_tenants(tmp_path)) == {"ok-1"}


def test_missing_directory_returns_empty(tmp_path):
    assert load_tenants(tmp_path / "nie-ma") == {}
