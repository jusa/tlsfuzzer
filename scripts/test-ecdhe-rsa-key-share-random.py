# Author: Hubert Kario, (c) 2018
# Released under Gnu GPL v2.0, see LICENSE file for details

"""Minimal test for verifying uniqueness of server ECDHE key shares."""

from __future__ import print_function
import traceback
import sys
import getopt
from itertools import chain
from random import sample

from tlsfuzzer.runner import Runner
from tlsfuzzer.messages import Connect, ClientHelloGenerator, \
        ClientKeyExchangeGenerator, ChangeCipherSpecGenerator, \
        FinishedGenerator, ApplicationDataGenerator, AlertGenerator, \
        CopyVariables
from tlsfuzzer.expect import ExpectServerHello, ExpectCertificate, \
        ExpectServerHelloDone, ExpectChangeCipherSpec, ExpectFinished, \
        ExpectAlert, ExpectClose, ExpectServerKeyExchange, \
        ExpectApplicationData

from tlslite.constants import CipherSuite, AlertLevel, AlertDescription, \
        ExtensionType, GroupName, ECPointFormat
from tlslite.extensions import ECPointFormatsExtension, \
        SupportedGroupsExtension
from tlsfuzzer.utils.lists import natural_sort_keys
from tlsfuzzer.helpers import uniqueness_check


version = 1


def help_msg():
    print("Usage: <script-name> [-h hostname] [-p port] [[probe-name] ...]")
    print(" -h hostname    name of the host to run the test against")
    print("                localhost by default")
    print(" -p port        port number to use for connection, 4433 by default")
    print(" probe-name     if present, will run only the probes with given")
    print("                names and not all of them, e.g \"sanity\"")
    print(" -e probe-name  exclude the probe from the list of the ones run")
    print("                may be specified multiple times")
    print(" -n num         only run `num` random tests instead of a full set")
    print("                (excluding \"sanity\" tests)")
    print(" --repeat num   repeat every test num times to collect the values")
    print("                32 by default")
    print(" -z             don't expect 1/n-1 record split in TLS1.0")
    print(" --help         this message")


def main():
    """Test if server provides unique ECDHE_RSA key shares."""
    host = "localhost"
    port = 4433
    num_limit = None
    run_exclude = set()
    repeats = 32
    record_split = True

    argv = sys.argv[1:]
    opts, args = getopt.getopt(argv, "h:p:e:n:z", ["help", "repeat="])
    for opt, arg in opts:
        if opt == '-h':
            host = arg
        elif opt == '-p':
            port = int(arg)
        elif opt == '-e':
            run_exclude.add(arg)
        elif opt == '-n':
            num_limit = int(arg)
        elif opt == '--help':
            help_msg()
            sys.exit(0)
        elif opt == '-z':
            record_split = False
        elif opt == '--repeat':
            repeats = int(arg)
        else:
            raise ValueError("Unknown option: {0}".format(opt))

    if args:
        run_only = set(args)
    else:
        run_only = None

    collected_randoms = []
    collected_key_shares = []
    collected_session_ids = []
    variables_check = \
        {'ServerHello.random':
         collected_randoms,
         'ServerKeyExchange.key_share':
         collected_key_shares,
         'ServerHello.session_id':
         collected_session_ids}

    groups = [GroupName.x25519, GroupName.x448, GroupName.secp256r1,
              GroupName.secp384r1, GroupName.secp521r1]

    conversations = {}

    conversation = Connect(host, port)
    node = conversation
    ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA]
    groups_ext = SupportedGroupsExtension().create(groups)
    points_ext = ECPointFormatsExtension().create([ECPointFormat.uncompressed])
    exts = {ExtensionType.renegotiation_info: None,
            ExtensionType.supported_groups: groups_ext,
            ExtensionType.ec_point_formats: points_ext}
    node = node.add_child(ClientHelloGenerator(ciphers, extensions=exts))
    exts = {ExtensionType.renegotiation_info:None,
            ExtensionType.ec_point_formats: None}
    node = node.add_child(ExpectServerHello(extensions=exts))
    node = node.add_child(ExpectCertificate())
    node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(CopyVariables(variables_check))
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    node = node.add_child(ApplicationDataGenerator(
        bytearray(b"GET / HTTP/1.0\n\n")))
    node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()

    conversations["sanity"] = conversation

    for prot in [(3, 0), (3, 1), (3, 2), (3, 3)]:
        for ssl2 in [True, False]:
            for group in groups:
                # with SSLv2 compatible or with SSLv3 we can't advertise
                # curves so do just one check
                if (ssl2 or prot == (3, 0)) and group != groups[0]:
                    continue
                conversation = Connect(host, port,
                                       version=(0, 2) if ssl2 else (3, 0))
                node = conversation
                ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA,
                           CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV]
                if ssl2 or prot == (3, 0):
                    exts = None
                else:
                    groups_ext = SupportedGroupsExtension().create([group])
                    exts = {ExtensionType.supported_groups: groups_ext,
                            ExtensionType.ec_point_formats: points_ext}
                node = node.add_child(ClientHelloGenerator(ciphers,
                                                           version=prot,
                                                           extensions=exts,
                                                           ssl2=ssl2))
                if prot > (3, 0):
                    if ssl2:
                        ext = {ExtensionType.renegotiation_info: None}
                    else:
                        ext = {ExtensionType.renegotiation_info: None,
                               ExtensionType.ec_point_formats: None}
                else:
                    ext = None
                node = node.add_child(ExpectServerHello(extensions=ext,
                                                        version=prot))
                node = node.add_child(ExpectCertificate())
                node = node.add_child(ExpectServerKeyExchange())
                node = node.add_child(CopyVariables(variables_check))
                node = node.add_child(ExpectServerHelloDone())
                node = node.add_child(ClientKeyExchangeGenerator())
                node = node.add_child(ChangeCipherSpecGenerator())
                node = node.add_child(FinishedGenerator())
                node = node.add_child(ExpectChangeCipherSpec())
                node = node.add_child(ExpectFinished())
                node = node.add_child(ApplicationDataGenerator(
                    bytearray(b"GET / HTTP/1.0\n\n")))
                node = node.add_child(ExpectApplicationData())
                if prot < (3, 2) and record_split:
                    # 1/n-1 record splitting
                    node = node.add_child(ExpectApplicationData())
                node = node.add_child(AlertGenerator(AlertLevel.warning,
                                                     AlertDescription.close_notify))
                node = node.add_child(ExpectAlert())
                node.next_sibling = ExpectClose()

                conversations["Protocol {0}{1}{2}".format(
                    prot,
                    "" if ssl2 or prot < (3, 1)
                        else " with {0} group".format(GroupName.toStr(group)),
                    " in SSLv2 compatible ClientHello" if ssl2 else "")] = \
                        conversation

    # run the conversation
    good = 0
    bad = 0
    failed = []
    if not num_limit:
        num_limit = len(conversations)

    # make sure that sanity test is run first and last
    # to verify that server was running and kept running throughout
    sanity_tests = [('sanity', conversations['sanity'])]
    regular_tests = [(k, v) for k, v in conversations.items() if k != 'sanity']
    sampled_tests = sample(regular_tests, min(num_limit, len(regular_tests)))
    ordered_tests = chain(sanity_tests, sampled_tests, sanity_tests)

    for c_name, c_test in ordered_tests:
        if run_only and c_name not in run_only or c_name in run_exclude:
            continue
        for i in range(repeats):
            print("\"{1}\" repeat {0}...".format(i, c_name))

            runner = Runner(c_test)

            res = True
            try:
                runner.run()
            except Exception:
                print("Error while processing")
                print(traceback.format_exc())
                res = False

            if res:
                good += 1
                print("OK\n")
            else:
                bad += 1
                failed.append(c_name)

    failed_tests = uniqueness_check(variables_check, good + bad)
    if failed_tests:
        print("\n".join(failed_tests))
    else:
        print("\n".join("{0} values: OK".format(i) for i in variables_check))

    print('')

    print("Check if the server provided random values are unique")
    print("Checks random and session_id from Server Hello and ECDHE key share")
    print("Note: not supporting ECDHE in SSLv3 or with SSLv2 Client Hello is")
    print("valid behaviour, as the client can't advertise groups it supports")
    print("there.")
    print("version: {0}\n".format(version))

    print("Test end")
    print("successful: {0}".format(good))
    print("failed: {0}".format(bad + len(failed_tests)))
    failed_sorted = sorted(failed, key=natural_sort_keys)
    print("  {0}".format('\n  '.join(repr(i) for i in failed_sorted)))

    if bad > 0 or failed_tests:
        sys.exit(1)

if __name__ == "__main__":
    main()
