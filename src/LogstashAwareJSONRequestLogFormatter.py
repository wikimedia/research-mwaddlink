import json_logging

json_logging.ENABLE_JSON_LOGGING = True


class LogstashAwareJSONRequestLogFormatter(json_logging.JSONRequestLogFormatter):
    """
    Logstash-aware formatter for HTTP request instrumentation logging
    """

    def _format_log_object(self, record, request_util):
        json_log_object = super(
            LogstashAwareJSONRequestLogFormatter, self
        )._format_log_object(record, request_util)
        # Logstash wants "request" as an object instead of the URL path, so instead
        # rename the field to "url" and delete the "request" key.
        if "request" in json_log_object:
            json_log_object.update({"url": json_log_object["request"]})
            del json_log_object["request"]
        return json_log_object
