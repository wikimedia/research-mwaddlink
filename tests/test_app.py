import json
import pytest
import os

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
            0,  # Fixture number
            "wikipedia",  # Project
            "simple",  # Domain
            "Cat",  # Page title
            8097163,  # Revision ID
            0.5,  # Threshold
            2,  # Max link recommendations
            None,  # Sections to exclude
            200,  # Status code
        ],
        [
            1,  # Fixture number
            "wikipedia",  # Project
            "simple",  # Domain
            "Somepagethatwontbefound",  # Page title
            None,  # Revision ID
            None,  # Threshold
            None,  # Max link recommendations
            None,  # Sections to exclude
            404,  # Status code
        ],
        [
            2,  # Fixture number
            "wikipedia",  # Project
            "foo",  # Domain
            "Bar",  # Page title
            None,  # Revision ID
            None,  # Threshold
            None,  # Max link recommendations
            None,  # Sections to exclude
            400,  # HTTP status code
        ],
        [
            3,  # Fixture number
            "wikipedia",  # Project
            "bat_smg",  # Domain
            "Somepagethatwontbefound",  # Page title
            None,  # Revision ID
            None,  # Threshold
            None,  # Max link recommendations
            None,  # Sections to exclude
            404,  # HTTP status code
        ],
    ]


@pytest.mark.integration
@parametrize(
    "fixture_number,project,wiki_domain,page_title,revision,threshold,max_recommendations,"
    "sections_to_exclude,expected_status_code",
    provide_query_get(),
)
def test_query_get(
    client,
    pytestconfig,
    fixture_number,
    project,
    wiki_domain,
    page_title,
    revision,
    threshold,
    max_recommendations,
    sections_to_exclude,
    expected_status_code,
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
    with open(
        os.path.join(
            pytestconfig.rootdir,
            "tests",
            "fixtures",
            "provide_query_get",
            str(fixture_number),
            "expected_data.json",
        ),
        mode="r",
    ) as file:
        expected_data = json.loads(file.read())
    response_json = json.loads(res.data)

    if "meta" in expected_data:
        del expected_data["meta"]
        assert list(response_json.keys()) == [
            "links",
            "links_count",
            "meta",
            "page_title",
            "pageid",
            "revid",
        ]
        # Remove the meta key, as the dataset hashes can change, as can the
        # application version
        del response_json["meta"]
    assert json.dumps(response_json) == json.dumps(expected_data)


def provide_query_post():
    return [
        [
            0,  # fixture number
            "wikipedia",  # project
            "simple",  # domain
            "Cat",  # page title
            8097163,  # Revision
            0.5,  # Threshold
            2,  # Max recommendations
            None,  # Sections to exclude
            2815,  # Page ID
            200,  # Expected response code
            True,  # Assert the response
        ],
        [
            1,  # fixture number
            "wikipedia",  # project
            "foo",  # domain
            "Bar",  # Page title
            0,  # Revision
            None,  # Threshold
            None,  # Max recommendations
            None,  # Sections to exclude
            0,  # Page ID
            400,  # Expected response code
            False,  # Assert the response
        ],
    ]


@pytest.mark.integration
@parametrize(
    "fixture_number,project,wiki_domain,page_title,revision,threshold,max_recommendations,"
    "sections_to_exclude,pageid,expected_status_code,assert_expected_data",
    provide_query_post(),
)
def test_query_post(
    client,
    pytestconfig,
    fixture_number,
    project,
    wiki_domain,
    page_title,
    revision,
    threshold,
    max_recommendations,
    sections_to_exclude,
    pageid,
    expected_status_code,
    assert_expected_data,
):
    query_params = {}

    if max_recommendations:
        query_params["max_recommendations"] = max_recommendations
    if threshold:
        query_params["threshold"] = threshold

    with open(
        os.path.join(
            os.getcwd(),
            pytestconfig.rootdir,
            "tests",
            "fixtures",
            "provide_query_post",
            str(fixture_number),
            "source.wikitext",
        ),
        mode="r",
    ) as file:
        json_params = {"revid": revision, "pageid": pageid, "wikitext": file.read()}
    if sections_to_exclude:
        json_params["sections_to_exclude"] = sections_to_exclude
    url = "v1/linkrecommendations/%s/%s/%s" % (project, wiki_domain, page_title)
    res = client.post(url, json=json_params, query_string=query_params)
    assert res.status_code == expected_status_code

    # assert that the shape of the response is correct
    with open(
        os.path.join(
            pytestconfig.rootdir,
            "tests",
            "fixtures",
            "provide_query_post",
            str(fixture_number),
            "expected_data.json",
        ),
        mode="r",
    ) as file:
        expected_data = json.loads(file.read())
    response_json = json.loads(res.data)
    if "meta" in response_json:
        assert list(response_json.keys()) == [
            "links",
            "links_count",
            "meta",
            "page_title",
            "pageid",
            "revid",
        ]
        # Remove the meta key, as the dataset hashes can change, as can the
        # application version
        del response_json["meta"]
        if "meta" in expected_data:
            del expected_data["meta"]

    assert json.dumps(response_json) == json.dumps(expected_data)
