from pathlib import Path
from scraper.exporters import export_all, safe_filename


def test_safe_filename():
    assert safe_filename('../../My Job') == 'My-Job'


def test_exports_all_formats(tmp_path):
    paths = export_all([{'Title': 'One', 'Price': 10}], str(tmp_path), 1, 'Demo')
    assert Path(paths['csv']).exists()
    assert Path(paths['json']).exists()
    assert Path(paths['excel']).exists()
