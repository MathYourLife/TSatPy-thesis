"""
Create a twisted daemon service to run on the host that ingests
postfix log lines over tcp to a parse port and provides an api
interface to query current state information.
"""

from __future__ import print_function

import time
import os

from twisted.application import service, internet
from twisted.web import server
from twisted.pair import rawudp

import TSatPy.Server
import TSatPy.Comm

def system_controller():
    """
    Define the parsing service that will be scrubbing incoming postfix log lines

    :param host: interface the service will run on (localhost)
    :type  host: str
    :param port: port the service will listen on
    :type  port: int
    :param flush_every: How many seconds between resetting parsed stats
    :type  flush_every: int
    """

    # Define the log parsing service
    tsat_controller = TSatPy.Server.TSatController()

    return tsat_controller


def api_service(tsat, host, port):
    """
    Define the api interface service that can report parsing stats

    :param parse_factory: A constructed parsing factory from parsing_service
                          used to pull parsed stats for reporting
    :type  parse_factory: PostfixMonitor.Server.ParseFactory
    :param host: interface the service will run on (localhost)
    :type  host: str
    :param port: port the service will listen on
    :type  port: int
    """

    api = TSatPy.Server.TSatPyAPI()
    api.tsat = tsat

    site = server.Site(api)

    return internet.TCPServer(port, site, interface=host)


def new(api_host, api_port, log_file):
    """
    Construct the postfix-monitor service with defined parsing, api, and logging
    configurations.


    :param parse_host: interface the parsing service will run on (localhost)
    :type  parse_host: str
    :param parse_port: port the parsing service will listen on
    :type  parse_port: int
    :param api_host: interface the api service will run on (localhost)
    :type  api_host: str
    :param api_port: port the api service will listen on
    :type  api_port: int
    :param flush_every: How many seconds between resetting parsed stats
    :type  flush_every: int
    :param log_file: full path to application log destination
    :type  log_file: str
    """

    # this will hold the services that combine to form the poetry server
    top_service = service.MultiService()

    # Setup parsing service and attach to parent service
    tsat_controller = system_controller()

    # Setup api service and attach to parent service
    api = api_service(tsat_controller, api_host, api_port)
    api.setServiceParent(top_service)

    bsize = 1
    dsize = 8
    vsize = 32767
    msg_handlers = {
        2:   [bsize, TSatPy.Comm.ReadAckMsg, 'Set run mode'],
        4:   [bsize, None, 'Set run mode'],
        18:  [4*dsize, None, 'Set fan speed'],
        19:  [bsize, None, 'Set log record mode'],
        20:  [bsize, None, 'Request sensor reading'],
        22:  [bsize, TSatPy.Comm.EndDataMsg, 'End of sensor log'],
        23:  [dsize, None, 'Request sensor log data'],
        33:  [dsize, None, 'Set log sample rate'],
        63:  [15*dsize, TSatPy.Comm.ReadRawData, 'Sensor readings'],
        64:  [16*dsize, TSatPy.Comm.ReadRawData, 'Sensor log entry'],
        65:  [dsize, TSatPy.Comm.ReadRawData, 'Sensor log size'],
        104: [bsize, TSatPy.Comm.ReadAckMsg, 'Ack run mode'],
        118: [bsize, TSatPy.Comm.ReadAckMsg, 'Ack fan volt'],
        119: [bsize, TSatPy.Comm.ReadAckMsg, 'Ack sensor log run mode'],
        133: [bsize, TSatPy.Comm.ReadAckMsg, 'ACK log sample rate'],
    }

    comm = TSatPy.Server.TSatComm(msg_handlers)
    udp_service = internet.UDPServer(9999, comm)

    # Defice service application name
    application = service.Application("tsatpy")

    # this hooks the collection we made to the application
    top_service.setServiceParent(application)
    udp_service.setServiceParent(application)

    return application