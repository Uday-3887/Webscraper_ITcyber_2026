def test_health(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.get_json()['status'] == 'ok'


def test_dashboard(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'ScrapeFlow' in response.data


def test_rejects_unsafe_preview(client):
    response = client.post('/api/preview', json={'website_url': 'http://127.0.0.1'})
    assert response.status_code == 400
