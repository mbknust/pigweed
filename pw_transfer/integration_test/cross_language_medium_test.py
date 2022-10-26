#!/usr/bin/env python3
# Copyright 2022 The Pigweed Authors
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.
"""Cross-language pw_transfer tests that take several seconds each.

Usage:

   bazel run pw_transfer/integration_test:cross_language_medium_test

Command-line arguments must be provided after a double-dash:

   bazel run pw_transfer/integration_test:cross_language_medium_test -- \
       --server-port 3304

Which tests to run can be specified as command-line arguments:

  bazel run pw_transfer/integration_test:cross_language_medium_test -- \
      MediumTransferIntegrationTest.test_medium_client_write_1_java

"""

import itertools
from parameterized import parameterized
import random

from pigweed.pw_transfer.integration_test import config_pb2
import test_fixture
from test_fixture import TransferIntegrationTestHarness


class MediumTransferIntegrationTest(test_fixture.TransferIntegrationTest):
    # Each set of transfer tests uses a different client/server port pair to
    # allow tests to be run in parallel.
    HARNESS_CONFIG = TransferIntegrationTestHarness.Config(server_port=3304,
                                                           client_port=3305)

    @parameterized.expand(
        itertools.product(("cpp", "java", "python"),
                          (config_pb2.TransferAction.ProtocolVersion.V1,
                           config_pb2.TransferAction.ProtocolVersion.V2)))
    def test_medium_client_write(self, client_type, protocol_version):
        payload = random.Random(67336391945).randbytes(512)
        config = self.default_config()
        resource_id = 5
        self.do_single_write(client_type, config, resource_id, payload,
                             protocol_version)

    @parameterized.expand(
        itertools.product(("cpp", "java", "python"),
                          (config_pb2.TransferAction.ProtocolVersion.V1,
                           config_pb2.TransferAction.ProtocolVersion.V2)))
    def test_large_hdlc_escape_client_write(self, client_type,
                                            protocol_version):
        payload = b"~" * 98731
        config = self.default_config()
        resource_id = 5
        self.do_single_write(client_type, config, resource_id, payload,
                             protocol_version)

    @parameterized.expand(
        itertools.product(("cpp", "java", "python"),
                          (config_pb2.TransferAction.ProtocolVersion.V1,
                           config_pb2.TransferAction.ProtocolVersion.V2)))
    def test_medium_client_read(self, client_type, protocol_version):
        payload = random.Random(67336391945).randbytes(512)
        config = self.default_config()
        resource_id = 5
        self.do_single_read(client_type, config, resource_id, payload,
                            protocol_version)

    @parameterized.expand(
        itertools.product(("cpp", "java", "python"),
                          (config_pb2.TransferAction.ProtocolVersion.V1,
                           config_pb2.TransferAction.ProtocolVersion.V2)))
    def test_large_hdlc_escape_client_read(self, client_type,
                                           protocol_version):
        payload = b"~" * 98731
        config = self.default_config()
        resource_id = 5
        self.do_single_read(client_type, config, resource_id, payload,
                            protocol_version)


if __name__ == '__main__':
    test_fixture.run_tests_for(MediumTransferIntegrationTest)
