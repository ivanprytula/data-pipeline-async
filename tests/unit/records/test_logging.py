import logging

import pytest

from app.config import settings
from app.core.logging import setup_logging


def _messages(records):
    return [(r.getMessage(), r.levelno) for r in records]


@pytest.mark.unit
def test_logging_respects_log_level_and_callable_interface(caplog):
    # DEBUG level: debug messages should be emitted
    settings.log_level = "DEBUG"
    logger = setup_logging()
    assert logging.getLogger().level == logging.DEBUG

    caplog.clear()
    logger("callable_debug", level="debug", extra_key="x")
    logger.info("info_msg")

    msgs = _messages(caplog.records)
    assert ("callable_debug", logging.DEBUG) in msgs
    assert ("info_msg", logging.INFO) in msgs

    # INFO level: debug messages should be suppressed
    settings.log_level = "INFO"
    logger = setup_logging()
    assert logging.getLogger().level == logging.INFO

    caplog.clear()
    logger("callable_debug_suppressed", level="debug")
    logger.info("info_msg_again")

    msgs = _messages(caplog.records)
    assert ("callable_debug_suppressed", logging.DEBUG) not in msgs
    assert ("info_msg_again", logging.INFO) in msgs
