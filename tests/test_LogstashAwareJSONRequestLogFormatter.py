from src.LogstashAwareJSONRequestLogFormatter import (
    LogstashAwareJSONRequestLogFormatter,
)


def test_log_modification():
    record = {"foo": "bar", "request": "somestring"}
    result = LogstashAwareJSONRequestLogFormatter._rename_request_field(record)
    assert "request" not in result
    assert result["url"] == "somestring"


def test_log_no_modification():
    record = {"foo": "bar"}
    result = LogstashAwareJSONRequestLogFormatter._rename_request_field(record)
    assert "request" not in result
    assert "url" not in result
