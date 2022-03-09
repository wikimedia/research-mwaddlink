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
            # should skip items inside configured sections
            "Lorem ipsum xanchor1 dolor sit amet\n== References ==\n foo anchor1 blah\n",
            ["References"],
            "Lorem ipsum xanchor1 dolor sit amet\n== References ==\n foo anchor1 blah\n",
            [],
        ],
        [
            # exclusion does not flow down to sub-sections; links can be generated for sub-sections
            # even if the main section is excluded
            "Lorem ipsum xanchor1 dolor sit amet\n== References ==\n foo\n=== Bar ===\n baz anchor1 blah\n",
            ["References"],
            "Lorem ipsum xanchor1 dolor sit amet\n== References ==\n foo\n=== Bar ===\n baz [[Page1|anchor1]] blah\n",
            [{"link_target": "Page1", "link_text": "anchor1", "match_index": 1}],
        ],
        [
            # excluding 2nd level and 3rd level section
            "Lorem ipsum xanchor1 dolor sit amet\n== References ==\n foo\n=== Bar ===\n baz anchor1 blah\n",
            ["References", "Bar"],
            "Lorem ipsum xanchor1 dolor sit amet\n== References ==\n foo\n=== Bar ===\n baz anchor1 blah\n",
            [],
        ],
        [
            # should not do partial match
            "Lorem ipsum xanchor1 dolor sit amet\n==Referencesd== anchor1 blah\n",
            ["References"],
            "Lorem ipsum xanchor1 dolor sit amet\n==Referencesd== [[Page1|anchor1]] blah\n",
            [{"link_target": "Page1", "link_text": "anchor1", "match_index": 1}],
        ],
        [
            # should not do partial match
            "No partial match xanchor1 dolor sit amet\n==References== anchor1 blah\n",
            ["Reference"],
            "No partial match xanchor1 dolor sit amet\n==References== [[Page1|anchor1]] blah\n",
            [{"link_target": "Page1", "link_text": "anchor1", "match_index": 1}],
        ],
        [
            # skip items inside configured sections including sub-sections, but link in a new section
            "Skip sub-sections xanchor1 \n==References== foo\n "
            "=== Bar ===\n anchor1 \n== Something ==\n anchor1 test\n",
            ["References"],
            "Skip sub-sections xanchor1 \n==References== foo\n "
            "=== Bar ===\n anchor1 \n== Something ==\n [[Page1|anchor1]] test\n",
            [{"link_target": "Page1", "link_text": "anchor1", "match_index": 2}],
        ],
        [
            # Not finding the exclusion section doesn't break the algorithm
            "Lorem ipsum xanchor1 dolor sit amet\n==Foo== anchor1 blah\n",
            ["References"],
            "Lorem ipsum xanchor1 dolor sit amet\n==Foo== [[Page1|anchor1]] blah\n",
            [{"link_target": "Page1", "link_text": "anchor1", "match_index": 1}],
        ],
        [
            # basic
            "Lorem ipsum anchor1 dolor sit amet",
            [],
            "Lorem ipsum [[Page1|anchor1]] dolor sit amet",
            [{"link_target": "Page1", "link_text": "anchor1", "match_index": 0}],
        ],
        [
            # Should match in section
            "Lorem ipsum.\n== New section ==\n anchor1 blah",
            [],
            "Lorem ipsum.\n== New section ==\n [[Page1|anchor1]] blah",
            [{"link_target": "Page1", "link_text": "anchor1", "match_index": 0}],
        ],
        [
            # Can skip lead section
            "Skip lead anchor1 blah \n==Foo==\n Bar",
            ["%LEAD%"],
            "Skip lead anchor1 blah \n==Foo==\n Bar",
            [],
        ],
        [
            # Can skip lead section, but still make a link in a sub-section
            "Skip lead anchor1 blah\n==Foo==\n anchor1 blah",
            ["%LEAD%"],
            "Skip lead anchor1 blah\n==Foo==\n [[Page1|anchor1]] blah",
            [{"link_target": "Page1", "link_text": "anchor1", "match_index": 1}],
        ],
        [
            # should only match whole words
            "Lorem ipsum xanchor1 dolor sit amet",
            [],
            "Lorem ipsum xanchor1 dolor sit amet",
            [],
        ],
        [
            # should only match whole words
            "Lorem ipsum anchor1x dolor sit amet",
            [],
            "Lorem ipsum anchor1x dolor sit amet",
            [],
        ],
        [
            # should match first instance
            "Lorem ipsum anchor1 dolor sit anchor1 amet",
            [],
            "Lorem ipsum [[Page1|anchor1]] dolor sit anchor1 amet",
            [{"link_target": "Page1", "link_text": "anchor1", "match_index": 0}],
        ],
        [
            # should skip non-full matches when locating match
            "Lorem ipsum xanchor1 dolor sit anchor1 amet",
            [],
            "Lorem ipsum xanchor1 dolor sit [[Page1|anchor1]] amet",
            [{"link_target": "Page1", "link_text": "anchor1", "match_index": 1}],
        ],
    ]


@pytest.mark.parametrize(
    "original_wikitext,sections_to_exclude,expected_wikitext,expected_data",
    provide_process_page(),
)
def test_process_page(
    original_wikitext, sections_to_exclude, expected_wikitext, expected_data
):
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
        sections_to_exclude=sections_to_exclude,
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
        sections_to_exclude=sections_to_exclude,
    )["links"]
    assert len(actual_data) == len(expected_data)
    actual_data.sort()
    expected_data.sort()
    for actual_item, expected_item in zip(actual_data, expected_data):
        assert expected_item.items() <= actual_item.items()
