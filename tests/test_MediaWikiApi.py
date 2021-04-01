from src.MediaWikiApi import MediaWikiApi
import requests_mock


def test_init():
    mw_api = MediaWikiApi(
        wiki_domain="cs", api_url="https://api", proxy_api_url="https://proxy_api"
    )
    assert mw_api.api_url == "https://proxy_api"
    mw_api = MediaWikiApi(wiki_domain="cs", api_url="https://api")
    assert mw_api.api_url == "https://api"


def test_get_article():
    mw_api = MediaWikiApi(wiki_domain="cs", api_url="https://api")
    with requests_mock.Mocker() as m:
        m.get(
            "https://api/v1/page/Lipsko",
            json=get_default_response(),
        )
        assert mw_api.get_article("Lipsko") == {
            "wikitext": "Foo",
            "pageid": 12345,
            "revid": 56789,
        }


def test_host_headers():
    mw_api = MediaWikiApi(
        wiki_domain="cs", project="wikipedia", proxy_api_url="https://proxy"
    )
    with requests_mock.Mocker() as m:
        m.get(
            "https://proxy/v1/page/Lipsko",
            json=get_default_response(),
            request_headers={"Host": "cs.wikipedia.org"},
        )
        mw_api.get_article(title="Lipsko")


def get_default_response() -> dict:
    return {"source": "Foo", "latest": {"id": 56789}, "id": 12345}