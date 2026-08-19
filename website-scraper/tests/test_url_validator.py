import pytest
from scraper.url_validator import UnsafeURLError, validate_url


def test_blocks_localhost():
    with pytest.raises(UnsafeURLError):
        validate_url('http://localhost:5000')


def test_blocks_private_ip():
    with pytest.raises(UnsafeURLError):
        validate_url('http://192.168.1.20')


def test_blocks_file_scheme():
    with pytest.raises(UnsafeURLError):
        validate_url('file:///etc/passwd')


def test_accepts_public_url(monkeypatch):
    monkeypatch.setattr('scraper.url_validator.resolve_public_addresses', lambda host: ('93.184.216.34',))
    result = validate_url('https://example.com/path')
    assert result.hostname == 'example.com'
