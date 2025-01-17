# Author: Ivan Nikolchev, (c) 2019
# Released under Gnu GPL v2.0, see LICENSE file for details

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
        fuzz_encrypted_message
from tlsfuzzer.expect import ExpectServerHello, ExpectCertificate, \
        ExpectServerHelloDone, ExpectChangeCipherSpec, ExpectFinished, \
        ExpectAlert, ExpectApplicationData, ExpectClose, \
        ExpectEncryptedExtensions, ExpectCertificateVerify, \
        ExpectNewSessionTicket

from tlslite.constants import CipherSuite, AlertLevel, AlertDescription, \
        TLS_1_3_DRAFT, GroupName, ExtensionType, SignatureScheme
from tlslite.keyexchange import ECDHKeyExchange
from tlsfuzzer.utils.lists import natural_sort_keys
from tlslite.extensions import KeyShareEntry, ClientKeyShareExtension, \
        SupportedVersionsExtension, SupportedGroupsExtension, \
        SignatureAlgorithmsExtension, SignatureAlgorithmsCertExtension
from tlsfuzzer.helpers import key_share_gen, RSA_SIG_ALL, \
        key_share_ext_gen


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
    print("                (\"sanity\" tests are always executed)")
    print(" --help         this message")


def main():
    host = "localhost"
    port = 4433
    num_limit = None
    run_exclude = set()

    argv = sys.argv[1:]
    opts, args = getopt.getopt(argv, "h:p:e:n:", ["help"])
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
        else:
            raise ValueError("Unknown option: {0}".format(opt))

    if args:
        run_only = set(args)
    else:
        run_only = None

    conversations = {}

    conversation = Connect(host, port)
    node = conversation
    ciphers = [CipherSuite.TLS_AES_128_GCM_SHA256, CipherSuite.TLS_AES_256_GCM_SHA384,
            CipherSuite.TLS_CHACHA20_POLY1305_SHA256]

    ext = {}
    groups = [GroupName.secp256r1]
    key_shares = []
    for group in groups:
        key_shares.append(key_share_gen(group))
    ext[ExtensionType.key_share] = ClientKeyShareExtension().create(key_shares)
    ext[ExtensionType.supported_versions] = SupportedVersionsExtension()\
        .create([TLS_1_3_DRAFT, (3, 3)])
    ext[ExtensionType.supported_groups] = SupportedGroupsExtension()\
        .create(groups)
    sig_algs = [SignatureScheme.rsa_pss_rsae_sha256,
                SignatureScheme.rsa_pss_pss_sha256]
    ext[ExtensionType.signature_algorithms] = SignatureAlgorithmsExtension()\
        .create(sig_algs)
    ext[ExtensionType.signature_algorithms_cert] = SignatureAlgorithmsCertExtension()\
        .create(RSA_SIG_ALL)
    node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
    node = node.add_child(ExpectServerHello())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectEncryptedExtensions())
    node = node.add_child(ExpectCertificate())
    node = node.add_child(ExpectCertificateVerify())
    node = node.add_child(ExpectFinished())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ApplicationDataGenerator(
        bytearray(b"GET / HTTP/1.0\r\n\r\n")))

    # This message is optional and may show up 0 to many times
    cycle = ExpectNewSessionTicket()
    node = node.add_child(cycle)
    node.add_child(cycle)

    node.next_sibling = ExpectApplicationData()
    node = node.next_sibling.add_child(AlertGenerator(AlertLevel.warning,
                                       AlertDescription.close_notify))

    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    conversations["sanity"] = conversation

    for cipher in [CipherSuite.TLS_AES_128_GCM_SHA256, CipherSuite.TLS_AES_256_GCM_SHA384,
            CipherSuite.TLS_CHACHA20_POLY1305_SHA256]:

        conversation = Connect(host, port)
        node = conversation
        ciphers = [cipher]

        ext = {}
        groups = [GroupName.secp256r1]
        key_shares = []
        for group in groups:
            key_shares.append(key_share_gen(group))
        ext[ExtensionType.key_share] = ClientKeyShareExtension().create(key_shares)
        ext[ExtensionType.supported_versions] = SupportedVersionsExtension()\
            .create([TLS_1_3_DRAFT, (3, 3)])
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension()\
            .create(groups)
        sig_algs = [SignatureScheme.rsa_pss_rsae_sha256,
                    SignatureScheme.rsa_pss_pss_sha256]
        ext[ExtensionType.signature_algorithms] = SignatureAlgorithmsExtension()\
            .create(sig_algs)
        ext[ExtensionType.signature_algorithms_cert] = SignatureAlgorithmsCertExtension()\
            .create(RSA_SIG_ALL)
        node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
        node = node.add_child(ExpectServerHello())
        node = node.add_child(ExpectChangeCipherSpec())
        node = node.add_child(ExpectEncryptedExtensions())
        node = node.add_child(ExpectCertificate())
        node = node.add_child(ExpectCertificateVerify())
        node = node.add_child(ExpectFinished())
        node = node.add_child(FinishedGenerator())
        node = node.add_child(ApplicationDataGenerator(
            bytearray(b"GET / HTTP/1.0\r\n\r\n")))

        # This message is optional and may show up 0 to many times
        cycle = ExpectNewSessionTicket()
        node = node.add_child(cycle)
        node.add_child(cycle)

        node.next_sibling = ExpectApplicationData()
        node = node.next_sibling.add_child(AlertGenerator(AlertLevel.warning,
                                           AlertDescription.close_notify))

        node = node.add_child(ExpectAlert())
        node.next_sibling = ExpectClose()
        conversations["check connection with {0}".format(CipherSuite.ietfNames[cipher])] = conversation


        # fuzz the tag (16 last bytes)
        for val in [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80]:
            for pos in range(-1, -17, -1):

                # Fuzz application data
                conversation = Connect(host, port)
                node = conversation
                ciphers = [cipher]

                ext = {}
                groups = [GroupName.secp256r1]
                ext[ExtensionType.key_share] = key_share_ext_gen(groups)
                ext[ExtensionType.supported_versions] = SupportedVersionsExtension()\
                    .create([TLS_1_3_DRAFT, (3, 3)])
                ext[ExtensionType.supported_groups] = SupportedGroupsExtension()\
                    .create(groups)
                sig_algs = [SignatureScheme.rsa_pss_rsae_sha256,
                            SignatureScheme.rsa_pss_pss_sha256]
                ext[ExtensionType.signature_algorithms] = SignatureAlgorithmsExtension()\
                    .create(sig_algs)
                ext[ExtensionType.signature_algorithms_cert] = SignatureAlgorithmsCertExtension()\
                    .create(RSA_SIG_ALL)
                node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
                node = node.add_child(ExpectServerHello())
                node = node.add_child(ExpectChangeCipherSpec())
                node = node.add_child(ExpectEncryptedExtensions())
                node = node.add_child(ExpectCertificate())
                node = node.add_child(ExpectCertificateVerify())
                node = node.add_child(ExpectFinished())
                node = node.add_child(FinishedGenerator())
                msg = ApplicationDataGenerator(bytearray(b"GET / HTTP/1.0\r\n\r\n"))

                node = node.add_child(fuzz_encrypted_message(msg, xors={pos:val}))

                # This message is optional and may show up 0 to many times
                cycle = ExpectNewSessionTicket()
                node = node.add_child(cycle)
                node.add_child(cycle)

                node.next_sibling = ExpectAlert(AlertLevel.fatal, AlertDescription.bad_record_mac)
                node = node.next_sibling.add_child(ExpectClose())

                conversations["check connection with {0} - fuzz tag on application data with {1} on pos {2}".format(CipherSuite.ietfNames[cipher], val, pos)] = conversation

                # Fuzz Finished message
                conversation = Connect(host, port)
                node = conversation
                ciphers = [cipher]

                ext = {}
                groups = [GroupName.secp256r1]
                ext[ExtensionType.key_share] = key_share_ext_gen(groups)
                ext[ExtensionType.supported_versions] = SupportedVersionsExtension()\
                    .create([TLS_1_3_DRAFT, (3, 3)])
                ext[ExtensionType.supported_groups] = SupportedGroupsExtension()\
                    .create(groups)
                sig_algs = [SignatureScheme.rsa_pss_rsae_sha256,
                            SignatureScheme.rsa_pss_pss_sha256]
                ext[ExtensionType.signature_algorithms] = SignatureAlgorithmsExtension()\
                    .create(sig_algs)
                ext[ExtensionType.signature_algorithms_cert] = SignatureAlgorithmsCertExtension()\
                    .create(RSA_SIG_ALL)
                node = node.add_child(ClientHelloGenerator(ciphers, extensions=ext))
                node = node.add_child(ExpectServerHello())
                node = node.add_child(ExpectChangeCipherSpec())
                node = node.add_child(ExpectEncryptedExtensions())
                node = node.add_child(ExpectCertificate())
                node = node.add_child(ExpectCertificateVerify())
                node = node.add_child(ExpectFinished())
                msg = FinishedGenerator()

                node = node.add_child(fuzz_encrypted_message(msg, xors={pos:val}))

                # This message is optional and may show up 0 to many times
                cycle = ExpectNewSessionTicket()
                node = node.add_child(cycle)
                node.add_child(cycle)

                node.next_sibling = ExpectAlert(AlertLevel.fatal, AlertDescription.bad_record_mac)
                node = node.next_sibling.add_child(ExpectClose())

                conversations["check connection with {0} - fuzz tag on finished message with {1} on pos {2}".format(CipherSuite.ietfNames[cipher], val, pos)] = conversation

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
        print("{0} ...".format(c_name))

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

    print("The test verifies that TLS 1.3 symmetric ciphers can be negotiated")
    print("and that fuzzing the authentication tag for the same ciphers")
    print("is detected by the server and causes connection failure.")
    print("version: {0}\n".format(version))

    print("Test end")
    print("successful: {0}".format(good))
    print("failed: {0}".format(bad))
    failed_sorted = sorted(failed, key=natural_sort_keys)
    print("  {0}".format('\n  '.join(repr(i) for i in failed_sorted)))

    if bad > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
