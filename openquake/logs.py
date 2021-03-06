# -*- coding: utf-8 -*-

# Copyright (c) 2010-2012, GEM Foundation.
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake.  If not, see <http://www.gnu.org/licenses/>.


"""
Set up some system-wide loggers
TODO(jmc): init_logs should take filename, or sysout
TODO(jmc): support debug level per logger.

"""
import logging
import socket
import threading

import kombu

from openquake.signalling import AMQPMessageConsumer, amqp_connect
from openquake.utils import stats


# Place the new level between info and warning
logging.PROGRESS = 25
logging.addLevelName(logging.PROGRESS, "PROGRESS")

LEVELS = {'debug': logging.DEBUG,
          'info': logging.INFO,
          'warn': logging.WARNING,
          'progress': logging.PROGRESS,
          'error': logging.ERROR,
          'critical': logging.CRITICAL}

LOG = logging.getLogger()
HAZARD_LOG = logging.getLogger('hazard')


# Progress report message prefixes
PR_PREFIXES = ["**", "**  >"]


def _log_progress(msg, *args, **kwargs):
    """Log the message using the progress reporting logging level."""
    LOG._log(logging.PROGRESS, msg, args, **kwargs)


def log_progress(msg, ilvl=1):
    """Log the progress message observing the indentation level.

    :param str msg: the progress report message to log
    :param int ilvl: indentation level
    """
    if ilvl < 1 or ilvl > len(PR_PREFIXES):
        ilvl = 0
    else:
        ilvl -= 1
    _log_progress("%s %s" % (PR_PREFIXES[ilvl], msg))


def log_percent_complete(job_id, ctype):
    """Log a message when the percentage completed changed for a calculation.

    :param int job_id: identifier of the job in question
    :param str ctype: calculation type, one of: hazard, risk
    """
    if ctype not in ("hazard", "risk"):
        LOG.warn("Unknown calculation type: '%s'" % ctype)
        return -1

    key = "nhzrd_total" if ctype == "hazard" else "nrisk_total"
    total = stats.pk_get(job_id, key)
    key = "nhzrd_done" if ctype == "hazard" else "nrisk_done"
    done = stats.pk_get(job_id, key)

    if done <= 0 or total <= 0:
        return 0

    percent = total / 100.0
    # Store percentage complete as well as the last value reported as integers
    # in order to avoid reporting the same percentage more than once.
    percent_complete = int(done / percent)
    # Get the last value reported
    lvr = stats.pk_get(job_id, "lvr")

    # Only report the percentage completed if it is above the last value shown
    if percent_complete > lvr:
        log_progress("%s %3d%% complete" % (ctype, percent_complete), 2)
        stats.pk_set(job_id, "lvr", percent_complete)

    return percent_complete


def init_logs_amqp_send(level, job_id):
    """
    Initialize logs to send records with level `level` or above from loggers
    'oq.job.*' through AMQP.

    Adds handler :class:`AMQPHandler` to logger 'oq.job'.
    """
    set_logger_level(logging.root, level)

    amqp_handlers = [h for h in logging.root.handlers
                     if isinstance(h, AMQPHandler)]
    if amqp_handlers:
        [handler] = amqp_handlers
        handler.set_job_id(job_id)
        return

    # Since we're using amqp to handle messages in the root logger,
    # we want to make sure log messages generated by the library
    # `amqplib` do not propagate to the root logger. If we don't disable
    # propagation, we could potentialy have a infinite logging loop.
    logging.getLogger("amqplib").propagate = False
    # Add a null to amqplib logger to silence "No handlers could be found for
    # logger 'amqplib'" warnings:
    logging.getLogger("amqplib").addHandler(logging.NullHandler())
    hdlr = AMQPHandler()
    hdlr.set_job_id(job_id)
    logging.root.addHandler(hdlr)


def set_logger_level(logger, level):
    """
    Apply symbolic name of level `level` to logger `logger`.

    Uses mapping :const:`LEVELS`.
    """
    logger.setLevel(LEVELS.get(level, logging.WARNING))


class AMQPHandler(logging.Handler):  # pylint: disable=R0902
    """
    Logging handler that sends log messages to AMQP.

    Transmitted log records are represented as json-encoded dictionaries
    with values of LogRecord object enclosed. Those values should be enough
    to reconstruct LogRecord upon receiving.

    :param level: minimum logging level to be sent.
    """

    #: Routing key for a record is generated by formatting the record
    #: with this format. All the same keys as for usual log records
    #: are available, but very few make sense being in routing key.
    ROUTING_KEY_FORMAT = "oq.job.%(job_id)s.%(name)s"

    _MDC = threading.local()

    # pylint: disable=R0913
    def __init__(self, level=logging.NOTSET):
        logging.Handler.__init__(self, level=level)
        self.producer = self._initialize()

    @staticmethod
    def _initialize():
        """Initialize amqp artefacts."""
        _, channel, exchange = amqp_connect()
        return kombu.messaging.Producer(channel, exchange, serializer='json')

    def set_job_id(self, job_id):
        """
        Set the job id for handler.

        Is called from :func:`init_logs_amqp_send`. Provided job id
        will be added to log records (see :meth:`emit`).
        """
        self._MDC.job_id = job_id

    def emit(self, record):  # pylint: disable=E0202
        data = vars(record).copy()
        msg = record.getMessage()
        if record.exc_info:
            # An exception was logged.
            # Set this to None because can't serialize `traceback` objects
            data['exc_info'] = None
            # The traceback text is in `msg`, so we still have everything we
            # need to log a useful error in the the case of logger.exception()

        # instead of 'msg' with placeholders putting formatted message
        # and removing args list to guarantee serializability no matter
        # what was in args
        data['msg'] = msg
        data['args'] = ()
        data['hostname'] = socket.getfqdn()
        data['job_id'] = getattr(self._MDC, 'job_id', None)

        routing_key = self.ROUTING_KEY_FORMAT % data
        self.producer.publish(data, routing_key)


class AMQPLogSource(AMQPMessageConsumer):
    """
    Receiving part of logging-over-AMQP solution.

    Works in pair with :class:`AMQPHandler`: receives its log messages
    with respect to provided routing key -- logger name. Relogs all received
    log records.
    """
    def message_callback(self, record_data, msg):
        """
        Create log record and handle it.

        Never stops :meth:`consumers's execution
        <openquake.signalling.AMQPMessageConsumer.run>`.
        """
        record = object.__new__(logging.LogRecord)
        record.__dict__.update(record_data)
        logger = logging.getLogger(record.name)
        if logger.isEnabledFor(record.levelno):
            logger.handle(record)
