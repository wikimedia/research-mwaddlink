import pytest

from types import SimpleNamespace
from src.scripts.utils import process_page


anchors = {
    "anchor1": {"Page1": 1},
}
pageids = {
    "Page1": 1,
}
redirects = {}
word2vec = {}
# pretend XGBClassifier
model = SimpleNamespace(
    predict_proba=(
        # probability for anchor1->Page1 link
        # this only works because we have just one anchor so we can ignore the input
        lambda features: {(0, 1): 0.9}
    ),
)


def provide_process_page():
    return [
        [
            # basic
            "Lorem ipsum anchor1 dolor sit amet",
            "Lorem ipsum [[Page1|anchor1]] dolor sit amet",
            [{"link_target": "Page1", "link_text": "anchor1", "match_index": 0}],
        ],
        [
            # should only match whole words
            "Lorem ipsum xanchor1 dolor sit amet",
            "Lorem ipsum xanchor1 dolor sit amet",
            [],
        ],
        [
            # should only match whole words
            "Lorem ipsum anchor1x dolor sit amet",
            "Lorem ipsum anchor1x dolor sit amet",
            [],
        ],
        [
            # should match first instance
            "Lorem ipsum anchor1 dolor sit anchor1 amet",
            "Lorem ipsum [[Page1|anchor1]] dolor sit anchor1 amet",
            [{"link_target": "Page1", "link_text": "anchor1", "match_index": 0}],
        ],
        [
            # should skip non-full matches when locating match
            "Lorem ipsum xanchor1 dolor sit anchor1 amet",
            "Lorem ipsum xanchor1 dolor sit [[Page1|anchor1]] amet",
            [{"link_target": "Page1", "link_text": "anchor1", "match_index": 1}],
        ],
    ]


@pytest.mark.parametrize(
    "original_wikitext,expected_wikitext,expected_data", provide_process_page()
)
def test_process_page(original_wikitext, expected_wikitext, expected_data):
    actual_wikitext = process_page(
        original_wikitext,
        "Page",
        anchors,
        pageids,
        redirects,
        word2vec,
        model,
        pr=False,
        return_wikitext=True,
    )
    assert actual_wikitext == expected_wikitext

    actual_data = process_page(
        original_wikitext,
        "Page",
        anchors,
        pageids,
        redirects,
        word2vec,
        model,
        pr=False,
        return_wikitext=False,
    )["links"]
    assert len(actual_data) == len(expected_data)
    actual_data.sort()
    expected_data.sort()
    for actual_item, expected_item in zip(actual_data, expected_data):
        assert expected_item.items() <= actual_item.items()
