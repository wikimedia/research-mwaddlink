import requests


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
        :param api_url The URL to use for connecting to MediaWiki REST API, it should contain the full path to rest.php,
          e.g. http://localhost:8080/w/rest.php
        :param proxy_api_url: The proxy URL to use for connecting to MediaWiki API. In production it is a value
          like http://localhost:6500/w/rest.php
        :param project The project to use for the request, e.g. "wikipedia" or "wiktionary"
        """
        self.api_url = api_url
        self.proxy_api_url = proxy_api_url
        self.project = project
        self.wiki_domain = wiki_domain
        # In production, API queries should go to the proxy URL
        if self.proxy_api_url:
            self.api_url = self.proxy_api_url

    def get_article(self, title: str, revision: int = None) -> dict:
        """
        Get the wikitext, rev ID and page ID for a title.
        :param title The page title, not urlencoded.
        :param revision Page revision (defaults to latest)
        """

        # Use the API url if specified via an environment variable or
        # the production API endpoint; both of these are developer
        # setup configurations.
        if not self.proxy_api_url:
            self.api_url = self.api_url or "https://%s.%s.org/w/" % (
                self.wiki_domain,
                self.project,
            )

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

        headers = {
            "User-Agent": "linkrecommendation",
        }
        # If we have a proxy URL then we should use the Host header
        if self.proxy_api_url:
            headers["Host"] = "%s.%s.org" % (self.wiki_domain, self.project)

        response = requests.get(
            self.api_url + "api.php", headers=headers, params=request_params
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
