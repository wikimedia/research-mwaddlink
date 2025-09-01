from collections.abc import Generator

from mwtokenizer import Tokenizer  # type: ignore[import-untyped]


def tokenize_sentence(text: str, tokenizer: Tokenizer) -> Generator[str, None, None]:
    """split text into sentences.
    - split by newlines because mwtokenizer does not split by newline
    - extract sentences using mwtokenizer
    """
    for line in text.split("\n"):
        if line and len(line) > 0:
            yield from tokenizer.sentence_tokenize(line, use_abbreviation=True)


def get_tokens(sent: str, tokenizer: Tokenizer) -> list[str]:
    """tokenize a sentence.
    e.g: "Berlin, Germany" tokenizes to ["Berlin", ",", " ", "Germany"]
    """
    return list(tokenizer.word_tokenize(sent, use_abbreviation=True))


def get_ngrams(tokens: list[str], n: int) -> Generator[str, None, None]:
    """concatenate n non-whitespace tokens"""
    for i_start, w_start in enumerate(tokens):
        if w_start == " ":
            continue
        gram = ""
        gram_count = 0
        for j in range(i_start, len(tokens)):
            w = tokens[j]
            gram += w
            if w != " ":
                gram_count += 1
            if gram_count == n:
                yield gram
                break
