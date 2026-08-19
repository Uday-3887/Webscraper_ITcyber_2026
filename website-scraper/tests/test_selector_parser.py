from scraper.selector_parser import deduplicate_records, extract_records

HTML = '''<div class="card"><h2>One</h2><span class="price">₹10</span><a href="/one">Open</a></div>
<div class="card"><h2>Two</h2><span class="price">₹20</span><a href="/two">Open</a></div>'''


def test_extracts_records_and_resolves_links():
    records, warnings, count = extract_records(HTML, 'https://example.com/list', '.card', [
        {'field_name': 'Title', 'selector': 'h2', 'extraction_type': 'text'},
        {'field_name': 'Price', 'selector': '.price', 'extraction_type': 'text'},
        {'field_name': 'URL', 'selector': 'a', 'extraction_type': 'link'},
    ])
    assert count == 2
    assert not warnings
    assert records[0]['Title'] == 'One'
    assert records[0]['URL'] == 'https://example.com/one'


def test_deduplicates_records():
    assert deduplicate_records([{'a': '1'}, {'a': '1'}]) == [{'a': '1'}]
