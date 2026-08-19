from __future__ import annotations

from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from scraper.url_validator import validate_url


def check_robots(url: str, timeout: int = 10) -> dict:
    validated = validate_url(url)
    parsed = urlparse(validated.url)
    robots_url = f'{parsed.scheme}://{parsed.netloc}/robots.txt'
    validate_url(robots_url)
    try:
        response = requests.get(
            robots_url,
            timeout=min(timeout, 15),
            headers={'User-Agent': 'ResponsibleWebsiteScraper/1.0'},
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        return {'found': False, 'allowed': None, 'crawl_delay': None, 'robots_url': robots_url, 'message': str(exc)}

    if response.status_code != 200:
        return {
            'found': False, 'allowed': None, 'crawl_delay': None,
            'robots_url': robots_url, 'message': f'robots.txt returned HTTP {response.status_code}'
        }

    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(response.text.splitlines())
    user_agent = 'ResponsibleWebsiteScraper'
    return {
        'found': True,
        'allowed': parser.can_fetch(user_agent, validated.url),
        'crawl_delay': parser.crawl_delay(user_agent) or parser.crawl_delay('*'),
        'robots_url': robots_url,
        'message': 'robots.txt checked successfully',
    }
