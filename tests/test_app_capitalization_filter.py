import os

import numpy as np
import pytest
import xgboost as xgb
from sqlitedict import SqliteDict

import app

os.environ.setdefault("DB_BACKEND", "sqlite")


def _build_wiki_fixture(root, wiki_id):
    """Create minimal SQLite datasets and a v2 model for ``wiki_id``.

    Datasets are written to ``root/data/<wiki_id>/`` in the layout the SQLite
    DatasetLoader expects. The single anchor maps the phrase "so much fun" to the
    Title-Cased target "So Much Fun", which is what the reverted-capitalization
    filter targets.
    """
    wiki_dir = os.path.join(root, "data", wiki_id)
    os.makedirs(wiki_dir, exist_ok=True)

    def _write(name, data):
        with SqliteDict(os.path.join(wiki_dir, f"{wiki_id}.{name}.sqlite")) as d:
            d.update(data)
            d.commit()

    _write("anchors", {"so much fun": {"So Much Fun": 100}})
    _write("pageids", {"So Much Fun": 123})
    _write("redirects", {})
    _write("w2vfiltered", {})
    _write("model", {})  # unused for the SQLite backend, but opened by the loader

    # Minimal v2 (7-feature) model. The predictions are irrelevant because the
    # requests use threshold=0; we only need a loadable model the loader detects
    # as v2 (i.e. not 6 features).
    rng = np.random.default_rng(0)
    features = rng.random((40, 7))
    labels = (features[:, 0] > 0.5).astype(int)
    clf = xgb.XGBClassifier(n_estimators=3, max_depth=2)
    clf.fit(features, labels)
    clf.save_model(os.path.join(wiki_dir, f"{wiki_id}.linkmodel.json"))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Flask test client backed by throwaway SQLite fixtures for enwiki and frwiki."""
    root = str(tmp_path)
    _build_wiki_fixture(root, "enwiki")
    _build_wiki_fixture(root, "frwiki")

    # app.query() constructs DatasetLoader with data_dir=app.root_path; redirect it
    # at our fixture directory instead of the (empty) repo data/ directory.
    orig_loader = app.DatasetLoader

    def make_loader(*args, **kwargs):
        kwargs["data_dir"] = root
        return orig_loader(*args, **kwargs)

    monkeypatch.setattr(app, "DatasetLoader", make_loader)

    with app.create_app().test_client() as client:
        yield client


def _post(client, wiki_domain, wikitext):
    res = client.post(
        f"/v1/linkrecommendations/wikipedia/{wiki_domain}/Test",
        query_string={"threshold": 0},
        json={"pageid": 1, "revid": 1, "wikitext": wikitext},
    )
    assert res.status_code == 200
    return res.get_json()["links"]


def test_api_filters_lowercase_mention_on_enwiki(client):
    """enwiki drops linking the running-text "so much fun" to "So Much Fun"."""
    links = _post(client, "en", "I had so much fun today.")
    assert links == []


def test_api_keeps_titlecased_mention_on_enwiki(client):
    """A properly Title-Cased mention of the same target is still linked."""
    links = _post(client, "en", "I listened to So Much Fun today.")
    assert len(links) == 1
    assert links[0]["link_text"] == "So Much Fun"
    assert links[0]["link_target"] == "So Much Fun"


def test_api_filter_is_scoped_to_enabled_wikis(client):
    """A wiki not opted in (frwiki) still links the lowercase mention."""
    links = _post(client, "fr", "I had so much fun today.")
    assert len(links) == 1
    assert links[0]["link_text"] == "so much fun"
    assert links[0]["link_target"] == "So Much Fun"
