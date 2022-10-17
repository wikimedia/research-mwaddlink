from src.MediaWikiApi import MediaWikiApi
import requests_mock


def test_init():
    mw_api = MediaWikiApi(
        wiki_domain="cs", api_url="https://api/", proxy_api_url="https://proxy_api/"
    )
    assert mw_api.api_url == "https://proxy_api/"

    mw_api = MediaWikiApi(wiki_domain="cs", api_url="https://api/")
    assert mw_api.api_url == "https://api/"

    mw_api = MediaWikiApi(wiki_domain="bat_smg", api_url="https://api/")
    assert mw_api.wiki_domain == "bat-smg"


def test_get_article():
    mw_api = MediaWikiApi(wiki_domain="cs", api_url="https://api/")
    with requests_mock.Mocker() as m:
        m.get(
            "https://api/api.php?action=query&prop=revisions&titles=Lipsko",
            json=get_default_response(),
        )
        assert mw_api.get_article("Lipsko") == {
            "wikitext": "Foo",
            "pageid": 12345,
            "revid": 56789,
        }


def test_get_article_revision():
    mw_api = MediaWikiApi(wiki_domain="cs", api_url="https://api/")
    with requests_mock.Mocker() as m:
        m.get(
            "https://api/api.php?action=query&prop=revisions&revids=100",
            json=get_default_response(),
        )
        assert mw_api.get_article("Lipsko", revision=100) == {
            "wikitext": "Foo",
            "pageid": 12345,
            "revid": 56789,
        }


def test_host_headers():
    mw_api = MediaWikiApi(
        wiki_domain="cs", project="wikipedia", proxy_api_url="https://proxy/"
    )
    with requests_mock.Mocker() as m:
        m.get(
            "https://proxy/api.php",
            json=get_default_response(),
            request_headers={"Host": "cs.wikipedia.org"},
        )
        mw_api.get_article(title="Lipsko")


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
