from scraper.auto_extractor import detect_next_url, extract_auto_data


def test_auto_detects_html_table():
    html = '''
    <table>
      <tr><th>Name</th><th>Price</th></tr>
      <tr><td>Alpha</td><td>₹10</td></tr>
      <tr><td>Beta</td><td>₹20</td></tr>
    </table>
    '''
    result = extract_auto_data(html, 'https://example.com/products')
    assert result.dataset_type == 'html-table'
    assert len(result.records) == 2
    assert result.records[0]['Name'] == 'Alpha'


def test_auto_detects_repeated_cards_and_resolves_urls():
    html = '''
    <main>
      <article class="product-card"><h2>One</h2><p>Good item ₹10</p><a href="/one">Open</a><img src="/1.jpg"></article>
      <article class="product-card"><h2>Two</h2><p>Good item ₹20</p><a href="/two">Open</a><img src="/2.jpg"></article>
      <article class="product-card"><h2>Three</h2><p>Good item ₹30</p><a href="/three">Open</a><img src="/3.jpg"></article>
    </main>
    '''
    result = extract_auto_data(html, 'https://example.com/catalog')
    assert result.dataset_type == 'repeated-items'
    assert len(result.records) == 3
    assert result.records[0]['URL'].startswith('https://example.com/')
    assert result.records[0]['Price'] == '₹10'


def test_auto_detects_json_ld():
    html = '''<script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Product","name":"Phone","url":"/phone","offers":{"price":"999"}}
    </script>'''
    result = extract_auto_data(html, 'https://example.com')
    assert result.dataset_type == 'json-ld'
    assert any(row.get('name') == 'Phone' for row in result.records)


def test_detects_next_page_url():
    html = '<a rel="next" href="/page/2">Next</a>'
    assert detect_next_url(html, 'https://example.com/page/1') == 'https://example.com/page/2'
