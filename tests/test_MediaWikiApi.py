from src.MediaWikiApi import MediaWikiApi
import requests_mock


def test_init():
    mw_api = MediaWikiApi("https://api", "https://proxy_api")
    assert mw_api.api_url == "https://proxy_api"
    mw_api = MediaWikiApi("https://api")
    assert mw_api.api_url == "https://api"


def test_get_article():
    mw_api = MediaWikiApi("https://api")
    with requests_mock.Mocker() as m:
        m.get(
            "https://api",
            json=get_default_response(),
        )
        assert mw_api.get_article("Lipsko", "cs", "wikipedia") == {
            "wikitext": "Foo",
            "pageid": 12345,
            "revid": 56789,
        }


def test_host_headers():
    mw_api = MediaWikiApi(proxy_api_url="https://proxy")
    with requests_mock.Mocker() as m:
        m.get(
            "https://proxy",
            json=get_default_response(),
            request_headers={"Host": "cs.wikipedia.org"},
        )
        mw_api.get_article(title="Lipsko", project="wikipedia", wiki_domain="cs")


def get_default_response() -> dict:
    return {
        "query": {
            "pages": [
                {
                    "revisions": [
                        {
                            "slots": {
                                "main": {"content": "Foo"},
                            },
                            "revid": 56789,
                        }
                    ],
                    "pageid": 12345,
                }
            ]
        }
    }
