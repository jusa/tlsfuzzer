# Author: Hubert Kario, (c) 2015
# Released under Gnu GPL v2.0, see LICENSE file for details

from __future__ import print_function
import traceback
import sys
import getopt
import re
from itertools import chain
from random import sample

from tlsfuzzer.runner import Runner
from tlsfuzzer.messages import Connect, ClientHelloGenerator, \
        ClientKeyExchangeGenerator, ChangeCipherSpecGenerator, \
        FinishedGenerator, ApplicationDataGenerator, AlertGenerator, Close, \
        ResetHandshakeHashes, ResetRenegotiationInfo
from tlsfuzzer.expect import ExpectServerHello, ExpectCertificate, \
        ExpectServerHelloDone, ExpectChangeCipherSpec, ExpectFinished, \
        ExpectAlert, ExpectClose, ExpectApplicationData, \
        ExpectServerKeyExchange
from tlsfuzzer.helpers import AutoEmptyExtension

from tlslite.extensions import TLSExtension
from tlslite.extensions import SupportedGroupsExtension
from tlslite.extensions import SignatureAlgorithmsExtension, \
        SignatureAlgorithmsCertExtension
from tlslite.constants import CipherSuite, AlertLevel, AlertDescription, \
        ExtensionType, GroupName
from tlsfuzzer.helpers import RSA_SIG_ALL


def natural_sort_keys(s, _nsre=re.compile('([0-9]+)')):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(_nsre, s)]


def help_msg():
    print("Usage: <script-name> [-h hostname] [-p port] [[probe-name] ...]")
    print(" -h hostname    name of the host to run the test against")
    print("                localhost by default")
    print(" -p port        port number to use for connection, 4433 by default")
    print(" probe-name     if present, will run only the probes with given")
    print("                names and not all of them, e.g \"sanity\"")
    print(" -e probe-name  exclude the probe from the list of the ones run")
    print("                may be specified multiple times")
    print(" --no-http      don't send HTTP query")
    print(" -d             negotiate (EC)DHE instead of RSA key exchange")
    print(" --help         this message")


def main():
    host = "localhost"
    port = 4433
    run_exclude = set()
    http = True
    dhe = False

    argv = sys.argv[1:]
    opts, args = getopt.getopt(argv, "h:p:e:d", ["help", "no-http"])
    for opt, arg in opts:
        if opt == '-h':
            host = arg
        elif opt == '-p':
            port = int(arg)
        elif opt == '-e':
            run_exclude.add(arg)
        elif opt == '-d':
            dhe = True
        elif opt == '--help':
            help_msg()
            sys.exit(0)
        elif opt == '--no-http':
            http = False
        else:
            raise ValueError("Unknown option: {0}".format(opt))

    if args:
        run_only = set(args)
    else:
        run_only = None

    conversations = {}

    # check if server works at all
    conversation = Connect(host, port)
    node = conversation
    ext = {ExtensionType.renegotiation_info: None}
    if dhe:
        groups = [GroupName.secp256r1, GroupName.ffdhe2048]
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension() \
            .create(groups)
        ext[ExtensionType.signature_algorithms] = \
            SignatureAlgorithmsExtension().create(RSA_SIG_ALL)
        ext[ExtensionType.signature_algorithms_cert] = \
            SignatureAlgorithmsCertExtension().create(RSA_SIG_ALL)
        ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
                   CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
    else:
        ciphers = [CipherSuite.TLS_RSA_WITH_AES_128_CBC_SHA]
    node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
    node = node.add_child(ExpectServerHello(
        extensions={ExtensionType.renegotiation_info:None}))
    node = node.add_child(ExpectCertificate())
    if dhe:
        node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    if http:
        node = node.add_child(ApplicationDataGenerator(
            bytearray(b"GET / HTTP/1.0\n\n")))
        node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node.add_child(Close())

    conversations["sanity"] = conversation

    # check if server works with SHA384 PRF ciphersuite
    conversation = Connect(host, port)
    node = conversation
    ext = {ExtensionType.renegotiation_info: None}
    if dhe:
        groups = [GroupName.secp256r1, GroupName.ffdhe2048]
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension() \
            .create(groups)
        ext[ExtensionType.signature_algorithms] = \
            SignatureAlgorithmsExtension().create(RSA_SIG_ALL)
        ext[ExtensionType.signature_algorithms_cert] = \
            SignatureAlgorithmsCertExtension().create(RSA_SIG_ALL)
        ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
                   CipherSuite.TLS_DHE_RSA_WITH_AES_256_GCM_SHA384]
    else:
        ciphers = [CipherSuite.TLS_RSA_WITH_AES_256_GCM_SHA384]
    node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
    node = node.add_child(ExpectServerHello(
        extensions={ExtensionType.renegotiation_info:None}))
    node = node.add_child(ExpectCertificate())
    if dhe:
        node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    if http:
        node = node.add_child(ApplicationDataGenerator(
            bytearray(b"GET / HTTP/1.0\n\n")))
        node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node.add_child(Close())

    conversations["sanity sha384 prf"] = conversation

    # check if server works at all (TLSv1.1)
    conversation = Connect(host, port)
    node = conversation
    ext = {ExtensionType.renegotiation_info: None}
    if dhe:
        groups = [GroupName.secp256r1, GroupName.ffdhe2048]
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension() \
            .create(groups)
        ext[ExtensionType.signature_algorithms] = \
            SignatureAlgorithmsExtension().create(RSA_SIG_ALL)
        ext[ExtensionType.signature_algorithms_cert] = \
            SignatureAlgorithmsCertExtension().create(RSA_SIG_ALL)
        ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
                   CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
    else:
        ciphers = [CipherSuite.TLS_RSA_WITH_AES_128_CBC_SHA]

    node = node.add_child(ClientHelloGenerator(ciphers, version=(3, 2),
                                               extensions=ext))
    node = node.add_child(ExpectServerHello(
        version=(3, 2),
        extensions={ExtensionType.renegotiation_info:None}))
    node = node.add_child(ExpectCertificate())
    if dhe:
        node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    if http:
        node = node.add_child(ApplicationDataGenerator(
            bytearray(b"GET / HTTP/1.0\n\n")))
        node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node.add_child(Close())

    conversations["sanity TLSv1.1"] = conversation

    # check if server supports extended master secret
    conversation = Connect(host, port)
    node = conversation
    ext = {ExtensionType.renegotiation_info: None,
           ExtensionType.extended_master_secret: AutoEmptyExtension()}
    if dhe:
        groups = [GroupName.secp256r1, GroupName.ffdhe2048]
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension() \
            .create(groups)
        ext[ExtensionType.signature_algorithms] = \
            SignatureAlgorithmsExtension().create(RSA_SIG_ALL)
        ext[ExtensionType.signature_algorithms_cert] = \
            SignatureAlgorithmsCertExtension().create(RSA_SIG_ALL)
        ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
                   CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
    else:
        ciphers = [CipherSuite.TLS_RSA_WITH_AES_128_CBC_SHA]
    node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
    node = node.add_child(ExpectServerHello(
        extensions={ExtensionType.renegotiation_info:None,
                    ExtensionType.extended_master_secret:None}))
    node = node.add_child(ExpectCertificate())
    if dhe:
        node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    if http:
        node = node.add_child(ApplicationDataGenerator(
            bytearray(b"GET / HTTP/1.0\n\n")))
        node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node.add_child(Close())

    conversations["extended master secret"] = conversation

    # check if server supports extended master secret with ECDHE
    conversation = Connect(host, port)
    node = conversation
    ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA]
    node = node.add_child(ClientHelloGenerator(
        ciphers,
        extensions={ExtensionType.renegotiation_info:None,
                    ExtensionType.extended_master_secret: AutoEmptyExtension(),
                    ExtensionType.supported_groups:SupportedGroupsExtension().
                    create([GroupName.secp256r1])}))
    node = node.add_child(ExpectServerHello(
        extensions={ExtensionType.renegotiation_info:None,
                    ExtensionType.extended_master_secret:None}))
    node = node.add_child(ExpectCertificate())
    node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    if http:
        node = node.add_child(ApplicationDataGenerator(
            bytearray(b"GET / HTTP/1.0\n\n")))
        node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node.add_child(Close())

    conversations["extended master secret w/ECDHE"] = conversation

    # check if server supports extended master secret with DHE
    conversation = Connect(host, port)
    node = conversation
    ciphers = [CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
    node = node.add_child(ClientHelloGenerator(
        ciphers,
        extensions={ExtensionType.renegotiation_info:None,
                    ExtensionType.extended_master_secret: AutoEmptyExtension()
                    }))
    node = node.add_child(ExpectServerHello(
        extensions={ExtensionType.renegotiation_info:None,
                    ExtensionType.extended_master_secret:None}))
    node = node.add_child(ExpectCertificate())
    node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    if http:
        node = node.add_child(ApplicationDataGenerator(
            bytearray(b"GET / HTTP/1.0\n\n")))
        node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node.add_child(Close())

    conversations["extended master secret w/DHE"] = conversation

    # check if server rejects malformed EMS extension
    # (extension must be empty)
    conversation = Connect(host, port)
    node = conversation
    ext = {ExtensionType.renegotiation_info: None,
           ExtensionType.extended_master_secret: \
                TLSExtension(extType=ExtensionType.extended_master_secret) \
                .create(bytearray(b'\x00'))}
    if dhe:
        groups = [GroupName.secp256r1, GroupName.ffdhe2048]
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension()\
            .create(groups)
        ext[ExtensionType.signature_algorithms] = \
            SignatureAlgorithmsExtension().create(RSA_SIG_ALL)
        ext[ExtensionType.signature_algorithms_cert] = \
            SignatureAlgorithmsCertExtension().create(RSA_SIG_ALL)
        ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
                   CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
    else:
        ciphers = [CipherSuite.TLS_RSA_WITH_AES_128_CBC_SHA]
    node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
    node = node.add_child(ExpectAlert(AlertLevel.fatal,
                                      AlertDescription.decode_error))
    node.next_sibling = ExpectClose()
    conversations["malformed extended master secret ext"] = conversation

    # check if server supports extended master secret with SHA384 PRF
    conversation = Connect(host, port)
    node = conversation
    ext = {ExtensionType.renegotiation_info: None,
           ExtensionType.extended_master_secret: AutoEmptyExtension()}
    if dhe:
        groups = [GroupName.secp256r1,
                  GroupName.ffdhe2048]
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension() \
            .create(groups)
        ext[ExtensionType.signature_algorithms] = \
            SignatureAlgorithmsExtension().create(RSA_SIG_ALL)
        ext[ExtensionType.signature_algorithms_cert] = \
            SignatureAlgorithmsCertExtension().create(RSA_SIG_ALL)
        ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
                   CipherSuite.TLS_DHE_RSA_WITH_AES_256_GCM_SHA384]
    else:
        ciphers = [CipherSuite.TLS_RSA_WITH_AES_256_GCM_SHA384]
    node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
    node = node.add_child(ExpectServerHello(
        extensions={ExtensionType.renegotiation_info:None,
                    ExtensionType.extended_master_secret:None}))
    node = node.add_child(ExpectCertificate())
    if dhe:
        node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    if http:
        node = node.add_child(ApplicationDataGenerator(
            bytearray(b"GET / HTTP/1.0\n\n")))
        node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node.add_child(Close())

    conversations["extended master secret w/SHA384 PRF"] = conversation

    # check if server supports extended master secret
    conversation = Connect(host, port)
    node = conversation
    ext = {ExtensionType.renegotiation_info: None,
           ExtensionType.extended_master_secret: AutoEmptyExtension()}
    if dhe:
        groups = [GroupName.secp256r1, GroupName.ffdhe2048]
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension() \
            .create(groups)
        ext[ExtensionType.signature_algorithms] = \
            SignatureAlgorithmsExtension().create(RSA_SIG_ALL)
        ext[ExtensionType.signature_algorithms_cert] = \
            SignatureAlgorithmsCertExtension().create(RSA_SIG_ALL)
        ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
                   CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
    else:
        ciphers = [CipherSuite.TLS_RSA_WITH_AES_128_CBC_SHA]
    node = node.add_child(ClientHelloGenerator(ciphers, version=(3, 2),
                                               extensions=ext))
    node = node.add_child(ExpectServerHello(
        version=(3, 2),
        extensions={ExtensionType.renegotiation_info:None,
                    ExtensionType.extended_master_secret:None}))
    node = node.add_child(ExpectCertificate())
    if dhe:
        node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    if http:
        node = node.add_child(ApplicationDataGenerator(
            bytearray(b"GET / HTTP/1.0\n\n")))
        node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node.add_child(Close())

    conversations["extended master secret in TLSv1.1"] = conversation

    # check if server doesn't default to extended master secret
    conversation = Connect(host, port)
    node = conversation
    ext = {ExtensionType.renegotiation_info: None}
    if dhe:
        groups = [GroupName.secp256r1, GroupName.ffdhe2048]
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension() \
            .create(groups)
        ext[ExtensionType.signature_algorithms] = \
            SignatureAlgorithmsExtension().create(RSA_SIG_ALL)
        ext[ExtensionType.signature_algorithms_cert] = \
            SignatureAlgorithmsCertExtension().create(RSA_SIG_ALL)
        ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
                   CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
    else:
        ciphers = [CipherSuite.TLS_RSA_WITH_AES_128_CBC_SHA]
    node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
    node = node.add_child(ExpectServerHello(
        extensions={ExtensionType.renegotiation_info:None}))
    node = node.add_child(ExpectCertificate())
    if dhe:
        node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator(
        extended_master_secret=True))
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectAlert(AlertLevel.fatal,
                                      AlertDescription.bad_record_mac))
    node = node.add_child(ExpectClose())
    node = node.add_child(Close())

    conversations["no EMS by default"] = conversation

    # check if server uses EMS for resumed connections
    conversation = Connect(host, port)
    node = conversation
    ext = {ExtensionType.renegotiation_info: None,
           ExtensionType.extended_master_secret: AutoEmptyExtension()}
    if dhe:
        groups = [GroupName.secp256r1, GroupName.ffdhe2048]
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension() \
            .create(groups)
        ext[ExtensionType.signature_algorithms] = \
            SignatureAlgorithmsExtension().create(RSA_SIG_ALL)
        ext[ExtensionType.signature_algorithms_cert] = \
            SignatureAlgorithmsCertExtension().create(RSA_SIG_ALL)
        ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
                   CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
    else:
        ciphers = [CipherSuite.TLS_RSA_WITH_AES_128_CBC_SHA]
    node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
    node = node.add_child(ExpectServerHello(
        extensions={ExtensionType.renegotiation_info:None,
                    ExtensionType.extended_master_secret:None}))
    node = node.add_child(ExpectCertificate())
    if dhe:
        node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    close = ExpectClose()
    node.next_sibling = close
    node = node.add_child(ExpectClose())
    node = node.add_child(Close())

    node = node.add_child(Connect(host, port))
    close.add_child(node)
    node = node.add_child(ResetHandshakeHashes())
    node = node.add_child(ResetRenegotiationInfo())
    node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
    node = node.add_child(ExpectServerHello(
        extensions={ExtensionType.renegotiation_info:None,
                    ExtensionType.extended_master_secret:None},
        resume=True))
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    if http:
        node = node.add_child(ApplicationDataGenerator(
            bytearray(b"GET / HTTP/1.0\n\n")))
        node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node.add_child(Close())

    conversations["EMS with session resume"] = conversation

    # check if server uses EMS for resumed connections and SHA384 PRF
    conversation = Connect(host, port)
    node = conversation
    ext = {ExtensionType.renegotiation_info: None,
           ExtensionType.extended_master_secret: AutoEmptyExtension()}
    if dhe:
        groups = [GroupName.secp256r1,
                  GroupName.ffdhe2048]
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension() \
            .create(groups)
        ext[ExtensionType.signature_algorithms] = \
            SignatureAlgorithmsExtension().create(RSA_SIG_ALL)
        ext[ExtensionType.signature_algorithms_cert] = \
            SignatureAlgorithmsCertExtension().create(RSA_SIG_ALL)
        ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
                   CipherSuite.TLS_DHE_RSA_WITH_AES_256_GCM_SHA384]
    else:
        ciphers = [CipherSuite.TLS_RSA_WITH_AES_256_GCM_SHA384]
    node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
    node = node.add_child(ExpectServerHello(
        extensions={ExtensionType.renegotiation_info:None,
                    ExtensionType.extended_master_secret:None}))
    node = node.add_child(ExpectCertificate())
    if dhe:
        node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    close = ExpectClose()
    node.next_sibling = close
    node = node.add_child(ExpectClose())
    node = node.add_child(Close())

    node = node.add_child(Connect(host, port))
    close.add_child(node)
    node = node.add_child(ResetHandshakeHashes())
    node = node.add_child(ResetRenegotiationInfo())
    node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
    node = node.add_child(ExpectServerHello(
        extensions={ExtensionType.renegotiation_info:None,
                    ExtensionType.extended_master_secret:None},
        resume=True))
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    if http:
        node = node.add_child(ApplicationDataGenerator(
            bytearray(b"GET / HTTP/1.0\n\n")))
        node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node.add_child(Close())

    conversations["EMS with session resume and SHA384 PRF"] = conversation

    # check if server aborts session resume without EMS extension
    conversation = Connect(host, port)
    node = conversation
    ext = {ExtensionType.renegotiation_info: None,
           ExtensionType.extended_master_secret: AutoEmptyExtension()}
    if dhe:
        groups = [GroupName.secp256r1, GroupName.ffdhe2048]
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension() \
            .create(groups)
        ext[ExtensionType.signature_algorithms] = \
            SignatureAlgorithmsExtension().create(RSA_SIG_ALL)
        ext[ExtensionType.signature_algorithms_cert] = \
            SignatureAlgorithmsCertExtension().create(RSA_SIG_ALL)
        ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
                   CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
    else:
        ciphers = [CipherSuite.TLS_RSA_WITH_AES_128_CBC_SHA]
    node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
    node = node.add_child(ExpectServerHello(
        extensions={ExtensionType.renegotiation_info:None,
                    ExtensionType.extended_master_secret:None}))
    node = node.add_child(ExpectCertificate())
    if dhe:
        node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    close = ExpectClose()
    node.next_sibling = close
    node = node.add_child(ExpectClose())
    node = node.add_child(Close())

    node = node.add_child(Connect(host, port))
    close.add_child(node)
    node = node.add_child(ResetHandshakeHashes())
    node = node.add_child(ResetRenegotiationInfo())
    ext = {ExtensionType.renegotiation_info: None}
    if dhe:
        groups = [GroupName.secp256r1, GroupName.ffdhe2048]
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension() \
            .create(groups)
        ext[ExtensionType.signature_algorithms] = \
            SignatureAlgorithmsExtension().create(RSA_SIG_ALL)
        ext[ExtensionType.signature_algorithms_cert] = \
            SignatureAlgorithmsCertExtension().create(RSA_SIG_ALL)
    node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
    node = node.add_child(ExpectAlert(AlertLevel.fatal,
                                      AlertDescription.handshake_failure))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node = node.add_child(Close())

    conversations["EMS with session resume without extension"] = conversation

    # check if server does full handshake on resumed session without EMS
    conversation = Connect(host, port)
    node = conversation
    ext = {ExtensionType.renegotiation_info: None}
    if dhe:
        groups = [GroupName.secp256r1, GroupName.ffdhe2048]
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension() \
            .create(groups)
        ext[ExtensionType.signature_algorithms] = \
            SignatureAlgorithmsExtension().create(RSA_SIG_ALL)
        ext[ExtensionType.signature_algorithms_cert] = \
            SignatureAlgorithmsCertExtension().create(RSA_SIG_ALL)
        ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
                   CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
    else:
        ciphers = [CipherSuite.TLS_RSA_WITH_AES_128_CBC_SHA]
    node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
    node = node.add_child(ExpectServerHello(
        extensions={ExtensionType.renegotiation_info:None}))
    node = node.add_child(ExpectCertificate())
    if dhe:
        node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    close = ExpectClose()
    node.next_sibling = close
    node = node.add_child(ExpectClose())
    node = node.add_child(Close())

    node = node.add_child(Connect(host, port))
    close.add_child(node)
    node = node.add_child(ResetHandshakeHashes())
    node = node.add_child(ResetRenegotiationInfo())
    ext = {ExtensionType.renegotiation_info: None,
           ExtensionType.extended_master_secret: AutoEmptyExtension()}
    if dhe:
        groups = [GroupName.secp256r1, GroupName.ffdhe2048]
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension() \
            .create(groups)
        ext[ExtensionType.signature_algorithms] = \
            SignatureAlgorithmsExtension().create(RSA_SIG_ALL)
        ext[ExtensionType.signature_algorithms_cert] = \
            SignatureAlgorithmsCertExtension().create(RSA_SIG_ALL)
    node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
    node = node.add_child(ExpectServerHello(
        extensions={ExtensionType.renegotiation_info:None,
                    ExtensionType.extended_master_secret:None},
        resume=False))
    node = node.add_child(ExpectCertificate())
    if dhe:
        node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    if http:
        node = node.add_child(ApplicationDataGenerator(
            bytearray(b"GET / HTTP/1.0\n\n")))
        node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node.next_sibling.add_child(Close())
    node.add_child(Close())

    conversations["resume non-EMS session with EMS extension"] = \
            conversation

    # EMS with renegotiation
    conversation = Connect(host, port)
    node = conversation
    ext = {ExtensionType.renegotiation_info: None,
           ExtensionType.extended_master_secret: AutoEmptyExtension()}
    if dhe:
        groups = [GroupName.secp256r1, GroupName.ffdhe2048]
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension() \
            .create(groups)
        ext[ExtensionType.signature_algorithms] = \
            SignatureAlgorithmsExtension().create(RSA_SIG_ALL)
        ext[ExtensionType.signature_algorithms_cert] = \
            SignatureAlgorithmsCertExtension().create(RSA_SIG_ALL)
        ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
                   CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
    else:
        ciphers = [CipherSuite.TLS_RSA_WITH_AES_128_CBC_SHA]
    node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
    node = node.add_child(ExpectServerHello(
        extensions={ExtensionType.renegotiation_info:None,
                    ExtensionType.extended_master_secret:None}))
    node = node.add_child(ExpectCertificate())
    if dhe:
        node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    # 2nd handshake
    node = node.add_child(ResetHandshakeHashes())
    node = node.add_child(ClientHelloGenerator(
        ciphers,
        session_id=bytearray(0), # do not resume
        extensions=ext))
    node = node.add_child(ExpectServerHello(
        extensions={ExtensionType.renegotiation_info:None,
                    ExtensionType.extended_master_secret:None}))
    node = node.add_child(ExpectCertificate())
    if dhe:
        node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    if http:
        node = node.add_child(ApplicationDataGenerator(
               bytearray(b"GET / HTTP/1.0\n\n")))
        node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node = node.add_child(Close())
    conversations["extended master secret with renegotiation"] = conversation

    # renegotiation in non-EMS session
    conversation = Connect(host, port)
    node = conversation
    ext = {ExtensionType.renegotiation_info: None}
    if dhe:
        groups = [GroupName.secp256r1, GroupName.ffdhe2048]
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension() \
            .create(groups)
        ext[ExtensionType.signature_algorithms] = \
            SignatureAlgorithmsExtension().create(RSA_SIG_ALL)
        ext[ExtensionType.signature_algorithms_cert] = \
            SignatureAlgorithmsCertExtension().create(RSA_SIG_ALL)
        ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
                   CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
    else:
        ciphers = [CipherSuite.TLS_RSA_WITH_AES_128_CBC_SHA]
    node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
    node = node.add_child(ExpectServerHello(
        extensions={ExtensionType.renegotiation_info:None}))
    node = node.add_child(ExpectCertificate())
    if dhe:
        node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    # 2nd handshake
    node = node.add_child(ResetHandshakeHashes())
    ext = {ExtensionType.renegotiation_info: None,
           ExtensionType.extended_master_secret: AutoEmptyExtension()}
    if dhe:
        groups = [GroupName.secp256r1, GroupName.ffdhe2048]
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension() \
            .create(groups)
        ext[ExtensionType.signature_algorithms] = \
            SignatureAlgorithmsExtension().create(RSA_SIG_ALL)
        ext[ExtensionType.signature_algorithms_cert] = \
            SignatureAlgorithmsCertExtension().create(RSA_SIG_ALL)
    node = node.add_child(ClientHelloGenerator(
        ciphers,
        session_id=bytearray(0), # do not resume
        extensions=ext))
    node = node.add_child(ExpectServerHello(
        extensions={ExtensionType.renegotiation_info:None,
                    ExtensionType.extended_master_secret:None}))
    node = node.add_child(ExpectCertificate())
    if dhe:
        node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    if http:
        node = node.add_child(ApplicationDataGenerator(
            bytearray(b"GET / HTTP/1.0\n\n")))
        node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node = node.add_child(Close())
    conversations["renegotiate with EMS in session without EMS"] = conversation

    # renegotiation of non-EMS session in EMS session
    conversation = Connect(host, port)
    node = conversation
    ext = {ExtensionType.renegotiation_info: None,
           ExtensionType.extended_master_secret: AutoEmptyExtension()}
    if dhe:
        groups = [GroupName.secp256r1, GroupName.ffdhe2048]
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension() \
            .create(groups)
        ext[ExtensionType.signature_algorithms] = \
            SignatureAlgorithmsExtension().create(RSA_SIG_ALL)
        ext[ExtensionType.signature_algorithms_cert] = \
            SignatureAlgorithmsCertExtension().create(RSA_SIG_ALL)
        ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
                   CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
    else:
        ciphers = [CipherSuite.TLS_RSA_WITH_AES_128_CBC_SHA]
    node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
    node = node.add_child(ExpectServerHello(
        extensions={ExtensionType.renegotiation_info:None,
                    ExtensionType.extended_master_secret:None}))
    node = node.add_child(ExpectCertificate())
    if dhe:
        node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    # 2nd handshake
    node = node.add_child(ResetHandshakeHashes())
    ext = {ExtensionType.renegotiation_info: None}
    if dhe:
        groups = [GroupName.secp256r1, GroupName.ffdhe2048]
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension() \
            .create(groups)
        ext[ExtensionType.signature_algorithms] = \
            SignatureAlgorithmsExtension().create(RSA_SIG_ALL)
        ext[ExtensionType.signature_algorithms_cert] = \
            SignatureAlgorithmsCertExtension().create(RSA_SIG_ALL)
    node = node.add_child(ClientHelloGenerator(
        ciphers,
        session_id=bytearray(0), # do not resume
        extensions=ext))
    node = node.add_child(ExpectServerHello(
        extensions={ExtensionType.renegotiation_info:None}))
    node = node.add_child(ExpectCertificate())
    if dhe:
        node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    if http:
        node = node.add_child(ApplicationDataGenerator(
            bytearray(b"GET / HTTP/1.0\n\n")))
        node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    node = node.add_child(Close())

    conversations["renegotiate without EMS in session with EMS"] = conversation

    # run the conversation
    good = 0
    bad = 0
    failed = []

    # make sure that sanity test is run first and last
    # to verify that server was running and kept running throughout
    sanity_tests = [('sanity', conversations['sanity'])]
    regular_tests = [(k, v) for k, v in conversations.items() if k != 'sanity']
    shuffled_tests = sample(regular_tests, len(regular_tests))
    ordered_tests = chain(sanity_tests, shuffled_tests, sanity_tests)

    for c_name, c_test in ordered_tests:
        if run_only and c_name not in run_only or c_name in run_exclude:
            continue
        print("{0} ...".format(c_name))

        runner = Runner(c_test)

        res = True
        try:
            runner.run()
        except:
            print("Error while processing")
            print(traceback.format_exc())
            res = False

        if res:
            good += 1
            print("OK\n")
        else:
            bad += 1
            failed.append(c_name)

    print("Test end")
    print("successful: {0}".format(good))
    print("failed: {0}".format(bad))
    failed_sorted = sorted(failed, key=natural_sort_keys)
    print("  {0}".format('\n  '.join(repr(i) for i in failed_sorted)))

    if bad > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
