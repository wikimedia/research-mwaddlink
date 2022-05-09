import json
from json.decoder import JSONDecodeError
import os

import pytest
from pytest_cases import parametrize, fixture

import app

# Needed so that the tests will make use of SQLite files downloaded by
# .pipeline/integration.sh
os.environ.setdefault("DB_BACKEND", "sqlite")


@fixture()
def client():
    with app.create_app().test_client() as client:
        yield client


@pytest.mark.integration
def test_healthz(client):
    # Make sure the endpoint exists
    res = client.get("/healthz")
    assert res.status_code == 200


@pytest.mark.integration
def test_apispec_json(client):
    # Let's not verify the whole thing; just check if the get/post
    # definitions are there
    res = client.get("/apispec_1.json")
    data = json.loads(res.data)
    assert list(
        data["paths"]["/v1/linkrecommendations/{project}/{domain}/{page_title}"].keys()
    ) == ["get", "post"]


@pytest.mark.integration
def test_apidocs(client):
    # GET to / redirects to API docs
    res = client.get("/", follow_redirects=True)
    assert res.data.decode().find("Flasgger") > 0


def provide_query_get():
    return [
        [
            "wikipedia",
            "simple",
            "Cat",
            # Use a revision ID so that the results are deterministic.
            # The only reason the results would change are if significantly
            # different datasets are generated or the algorithm changes.
            8097163,
            0.5,
            2,
            None,
            {
                "links": [
                    {
                        "context_after": " rodents a",
                        "context_before": "s for ",
                        "link_index": 0,
                        "link_target": "Hunting",
                        "link_text": "hunting",
                        "match_index": 0,
                        "score": 0.5160561203956604,
                        "wikitext_offset": 3334,
                    },
                    {
                        "context_after": " cat that ",
                        "context_before": " A ",
                        "link_index": 1,
                        "link_target": "Female",
                        "link_text": "female",
                        "match_index": 0,
                        "score": 0.5170595645904541,
                        "wikitext_offset": 4443,
                    },
                ],
                "links_count": 2,
                "meta": {
                    "application_version": "2b19309",
                    "dataset_checksums": {
                        "anchors": "0ee38697e1bb61df56c52b0a2617ceb33660e941238e65499acf96266639e9d6",
                        "model": "3de13ab5975aabe92fbb06453f17ca2b5605907fba5eaf5bc2f0b0c65677af93",
                        "pageids": "a1c8fd9e73b998c8a77310104278e2d94c4a60e49dab644fefcafea5d19b20d6",
                        "redirects": "842fe2a920a34c48d86427ec4cbae7f5ca736642303af3969e1479f7f8e8a258",
                        "w2vfiltered": "5ca140e629dbd882c8b02d5e9cc69571bef1146408eff31cd9ecff3c3af10608",
                    },
                    "format_version": 1,
                },
                "page_title": "Cat",
                "pageid": 2815,
                "revid": 8097163,
            },
            200,
            True,
        ],
        [
            "wikipedia",
            "simple",
            "Somepagethatwontbefound",
            None,
            None,
            None,
            None,
            "Page not found: Somepagethatwontbefound",
            404,
            False,
        ],
        [
            "wikipedia",
            "foo",
            "Bar",
            None,
            None,
            None,
            None,
            "Unable to process request for wikipedia/foo. Project/domain pairs that can be processed by the service: \n"
            "- \n",  # The app doesn't provide a list of valid project/domain pairs for SQLite.
            400,
            True,
        ],
    ]


@pytest.mark.integration
@parametrize(
    "project,wiki_domain,page_title,revision,threshold,max_recommendations,"
    "sections_to_exclude,expected_data,expected_status_code,assert_expected_data",
    provide_query_get(),
)
def test_query_get(
    client,
    project,
    wiki_domain,
    page_title,
    expected_data,
    revision,
    threshold,
    max_recommendations,
    sections_to_exclude,
    expected_status_code,
    assert_expected_data,
):
    params = {}
    if revision:
        params["revision"] = revision
    if max_recommendations:
        params["max_recommendations"] = max_recommendations
    if sections_to_exclude:
        params["sections_to_exclude"] = sections_to_exclude
    if threshold:
        params["threshold"] = threshold
    url = "v1/linkrecommendations/%s/%s/%s" % (project, wiki_domain, page_title)
    res = client.get(url, query_string=params)
    assert res.status_code == expected_status_code
    # assert that the shape of the response is correct
    try:
        response_json = json.loads(res.data)
        assert list(response_json.keys()) == [
            "links",
            "links_count",
            "meta",
            "page_title",
            "pageid",
            "revid",
        ]
        if assert_expected_data:
            # Remove the meta key, as the dataset hashes can change, as can the
            # application version
            del response_json["meta"]
            if "meta" in expected_data:
                del expected_data["meta"]
            assert json.dumps(response_json) == json.dumps(expected_data)
    except JSONDecodeError:
        # The API doesn't return a JSON response when the application errors
        # due to not finding the dataset. We should fix that in a follow-up, but
        # for now this code exists to handle the case where the response isn't
        # JSON and we still want to compare the response with what we expected.
        assert res.data.decode() == expected_data
