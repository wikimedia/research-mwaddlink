import requests
from urllib.parse import urlparse


class MediaWikiApi:
    def __init__(
        self,
        wiki_domain: str,
        api_url: str = None,
        proxy_api_url: str = None,
        project: str = "wikipedia",
    ):
        """
        :param wiki_domain The wiki domain to use with queries, e.g. "en" for English Wikipedia.
          Current assumption is that it is a Wikipedia wiki ID,
          non-Wikipedia wiki IDs are not yet supported.
        :param api_url The base URL to use for connecting to MediaWiki, it should contain the path,
          to the wiki's root directory, e.g. http://localhost:8080/w/
        :param proxy_api_url: The proxy URL to use for network requests (only scheme and network location
          is used). In production it is a value like http://localhost:6500.
        :param project The project to use for the request, e.g. "wikipedia" or "wiktionary"
        """
        self.proxy_api_url = proxy_api_url
        self.project = project
        # Ensure that wiki IDs like bat_smg are converted to bat-smg for domain resolution.
        self.wiki_domain = wiki_domain.replace("_", "-")

        self.api_url = api_url or "https://%s.%s.org/w/" % (
            self.wiki_domain,
            self.project,
        )

    def _make_request(
        self, method: str, url: str, *args, **kwargs
    ) -> requests.Response:
        kwargs["allow_redirects"] = False

        if "headers" not in kwargs:
            kwargs["headers"] = {}
        kwargs["headers"]["User-Agent"] = "linkrecommendation"

        redirects_followed = 0
        while True:
            # In production, API queries should go to the proxy URL
            if self.proxy_api_url:
                parsed_url = urlparse(url)
                parsed_proxy = urlparse(self.proxy_api_url)

                kwargs["headers"]["Host"] = parsed_url.netloc

                url = parsed_url._replace(
                    scheme=parsed_proxy.scheme, netloc=parsed_proxy.netloc
                ).geturl()

            r = requests.request(method, url, *args, **kwargs)
            if not r.is_redirect:
                break

            url = r.headers["location"]
            redirects_followed += 1

            if redirects_followed > 10:
                raise Exception("Too many redirects")

        return r

    def get_article(self, title: str, revision: int = None) -> dict:
        """
        Get the wikitext, rev ID and page ID for a title.
        :param title The page title, not urlencoded.
        :param revision Page revision (defaults to latest)
        """

        request_params = {
            "action": "query",
            "prop": "revisions",
            "rvprop": "content|ids",
            "rvslots": "main",
            "format": "json",
            "formatversion": "2",
        }
        if revision:
            request_params["revids"] = revision
        else:
            request_params["titles"] = title
            request_params["rvlimit"] = 1

        response = self._make_request(
            "GET", self.api_url + "api.php", params=request_params
        )
        return self.make_response(response.json())

    @staticmethod
    def make_response(response: dict) -> dict:
        return {
            "wikitext": response["query"]["pages"][0]["revisions"][0]["slots"]["main"][
                "content"
            ],
            "pageid": response["query"]["pages"][0]["pageid"],
            "revid": response["query"]["pages"][0]["revisions"][0]["revid"],
        }
