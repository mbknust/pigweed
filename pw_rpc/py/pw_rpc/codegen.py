# Copyright 2021 The Pigweed Authors
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
"""Common RPC codegen utilities."""

import abc
from datetime import datetime
import os
from typing import cast, Any, Iterable, Sequence

from pw_protobuf.output_file import OutputFile
from pw_protobuf.proto_tree import ProtoNode, ProtoService, ProtoServiceMethod

import pw_rpc.ids

PLUGIN_NAME = 'pw_rpc_codegen'
PLUGIN_VERSION = '0.3.0'

RPC_NAMESPACE = '::pw::rpc'

STUB_REQUEST_TODO = (
    '// TODO: Read the request as appropriate for your application')
STUB_RESPONSE_TODO = (
    '// TODO: Fill in the response as appropriate for your application')
STUB_WRITER_TODO = (
    '// TODO: Send responses with the writer as appropriate for your '
    'application')
STUB_READER_TODO = (
    '// TODO: Set the client stream callback and send a response as '
    'appropriate for your application')
STUB_READER_WRITER_TODO = (
    '// TODO: Set the client stream callback and send responses as '
    'appropriate for your application')


class CodeGenerator(abc.ABC):
    """Generates RPC code for services and clients."""
    def __init__(self, output_filename: str) -> None:
        self.output = OutputFile(output_filename)

    def indent(self, amount: int = OutputFile.INDENT_WIDTH) -> Any:
        """Indents the output. Use in a with block."""
        return self.output.indent(amount)

    def line(self, value: str = '') -> None:
        """Writes a line to the output."""
        self.output.write_line(value)

    @abc.abstractmethod
    def name(self) -> str:
        """Name of the pw_rpc implementation."""

    @abc.abstractmethod
    def method_union_name(self) -> str:
        """Name of the MethodUnion class to use."""

    @abc.abstractmethod
    def includes(self, proto_file_name: str) -> Iterable[str]:
        """Yields #include lines."""

    @abc.abstractmethod
    def aliases(self) -> None:
        """Generates reader/writer aliases."""

    @abc.abstractmethod
    def method_descriptor(self, method: ProtoServiceMethod,
                          method_id: int) -> None:
        """Generates code for a service method."""

    @abc.abstractmethod
    def client_member_function(self, method: ProtoServiceMethod) -> None:
        """Generates the client code for the Client member functions."""

    @abc.abstractmethod
    def client_static_function(self, method: ProtoServiceMethod) -> None:
        """Generates method static functions that instantiate a Client."""

    @abc.abstractmethod
    def method_info_specialization(self, method: ProtoServiceMethod) -> None:
        """Generates impl-specific additions to the MethodInfo specialization.

        May be empty if the generator has nothing to add to the MethodInfo.
        """


def generate_package(file_descriptor_proto, proto_package: ProtoNode,
                     gen: CodeGenerator) -> None:
    """Generates service and client code for a package."""
    assert proto_package.type() == ProtoNode.Type.PACKAGE

    gen.line(f'// {os.path.basename(gen.output.name())} automatically '
             f'generated by {PLUGIN_NAME} {PLUGIN_VERSION}')
    gen.line(f'// on {datetime.now().isoformat()}')
    gen.line('// clang-format off')
    gen.line('#pragma once\n')

    gen.line('#include <array>')
    gen.line('#include <cstdint>')
    gen.line('#include <type_traits>\n')

    include_lines = [
        '#include "pw_rpc/internal/method_info.h"',
        '#include "pw_rpc/internal/method_lookup.h"',
        '#include "pw_rpc/internal/service_client.h"',
        '#include "pw_rpc/method_type.h"',
        '#include "pw_rpc/server_context.h"',
        '#include "pw_rpc/service.h"',
    ]
    include_lines += gen.includes(file_descriptor_proto.name)

    for include_line in sorted(include_lines):
        gen.line(include_line)

    gen.line()

    if proto_package.cpp_namespace():
        file_namespace = proto_package.cpp_namespace()
        if file_namespace.startswith('::'):
            file_namespace = file_namespace[2:]

        gen.line(f'namespace {file_namespace} {{')
    else:
        file_namespace = ''

    gen.line(f'namespace pw_rpc::{gen.name()} {{')
    gen.line()

    services = [
        cast(ProtoService, node) for node in proto_package
        if node.type() == ProtoNode.Type.SERVICE
    ]

    for service in services:
        _generate_service_and_client(gen, service)

    gen.line()
    gen.line(f'}}  // namespace pw_rpc::{gen.name()}\n')

    _generate_deprecated_aliases(gen, [
        cast(ProtoService, n)
        for n in proto_package if n.type() == ProtoNode.Type.SERVICE
    ])

    if file_namespace:
        gen.line('}  // namespace ' + file_namespace)

    gen.line()
    gen.line('// Specialize MethodInfo for each RPC to provide metadata at '
             'compile time.')
    for service in services:
        _generate_info(gen, file_namespace, service)


def _generate_service_and_client(gen: CodeGenerator,
                                 service: ProtoService) -> None:
    gen.line('// Wrapper class that namespaces server and client code for '
             'this RPC service.')
    gen.line(f'class {service.name()} final {{')
    gen.line(' public:')

    with gen.indent():
        gen.line(f'{service.name()}() = delete;')
        gen.line()

        _generate_service(gen, service)

        gen.line()

        _generate_client(gen, service)

    gen.line(' private:')

    with gen.indent():
        gen.line(f'// Hash of "{service.proto_path()}".')
        service_id = pw_rpc.ids.calculate(service.proto_path())
        gen.line(f'static constexpr uint32_t kServiceId = 0x{service_id:08x};')

    gen.line('};')


def _generate_client(gen: CodeGenerator, service: ProtoService) -> None:
    gen.line('// The Client is used to invoke RPCs for this service.')
    gen.line(f'class Client final : public {RPC_NAMESPACE}::internal::'
             'ServiceClient {')
    gen.line(' public:')

    with gen.indent():
        gen.line(f'constexpr Client({RPC_NAMESPACE}::Client& client,'
                 ' uint32_t channel_id)')
        gen.line('    : ServiceClient(client, channel_id) {}')

        for method in service.methods():
            gen.line()
            gen.client_member_function(method)

    gen.line('};')
    gen.line()

    gen.line('// Static functions for invoking RPCs on a pw_rpc server.')
    gen.line('// These functions are equivalent to instantiating a Client and '
             'calling the')
    gen.line('// corresponding RPC.')
    for method in service.methods():
        gen.client_static_function(method)
        gen.line()


def _generate_info(gen: CodeGenerator, namespace: str,
                   service: ProtoService) -> None:
    """Generates MethodInfo for each method."""
    service_id = f'0x{pw_rpc.ids.calculate(service.proto_path()):08x}'
    info = f'struct {RPC_NAMESPACE.lstrip(":")}::internal::MethodInfo'

    for method in service.methods():
        gen.line('template <>')
        gen.line(f'{info}<{namespace}::pw_rpc::{gen.name()}::'
                 f'{service.name()}::{method.name()}> {{')

        with gen.indent():
            gen.line(f'static constexpr uint32_t kServiceId = {service_id};')
            gen.line(f'static constexpr uint32_t kMethodId = '
                     f'0x{pw_rpc.ids.calculate(method.name()):08x};')
            gen.line(f'static constexpr {RPC_NAMESPACE}::MethodType kType = '
                     f'{method.type().cc_enum()};')
            gen.line()

            gen.line('template <typename ServiceImpl>')
            gen.line('static constexpr auto Function() {')

            with gen.indent():
                gen.line(f'return &ServiceImpl::{method.name()};')

            gen.line('}')

            gen.method_info_specialization(method)

        gen.line('};')
        gen.line()


def _generate_deprecated_aliases(gen: CodeGenerator,
                                 services: Sequence[ProtoService]) -> None:
    """Generates aliases for the original, deprecated naming scheme."""
    gen.line('// Aliases for the deprecated namespaces.')
    gen.line('namespace generated {')
    gen.line()

    for service in services:
        gen.line('template <typename Implementation>')
        gen.line(f'using {service.name()} = pw_rpc::{gen.name()}::'
                 f'{service.name()}::Service<Implementation>;')

    gen.line()
    gen.line('}  // namespace generated')
    gen.line()
    gen.line(f'namespace {gen.name()} {{')
    gen.line()

    for service in services:
        gen.line(f'using {service.name()}Client = '
                 f'pw_rpc::{gen.name()}::{service.name()}::Client;')

    gen.line()
    gen.line(f'}}  // namespace {gen.name()}')


def _generate_service(gen: CodeGenerator, service: ProtoService) -> None:
    """Generates a C++ class for an RPC service."""

    base_class = f'{RPC_NAMESPACE}::Service'
    gen.line('// The RPC service base class.')
    gen.line(
        '// Inherit from this to implement an RPC service for a pw_rpc server.'
    )
    gen.line('template <typename Implementation>')
    gen.line(f'class Service : public {base_class} {{')
    gen.line(' public:')

    with gen.indent():
        gen.line(f'using ServerContext = {RPC_NAMESPACE}::ServerContext;')
        gen.aliases()

        gen.line()
        gen.line(f'static constexpr const char* name() '
                 f'{{ return "{service.name()}"; }}')

        gen.line()
        gen.line(
            '// Used by MethodLookup to identify the generated service base.')
        gen.line('constexpr void _PwRpcInternalGeneratedBase() const {}')
        gen.line()

    gen.line(' protected:')

    with gen.indent():
        gen.line(
            f'constexpr Service() : {base_class}(kServiceId, kMethods) {{}}')

    gen.line()
    gen.line(' private:')

    with gen.indent():
        gen.line('friend class ::pw::rpc::internal::MethodLookup;')
        gen.line()

        # Generate the method table
        gen.line('static constexpr std::array<'
                 f'{RPC_NAMESPACE}::internal::{gen.method_union_name()},'
                 f' {len(service.methods())}> kMethods = {{')

        with gen.indent(4):
            for method in service.methods():
                gen.method_descriptor(method,
                                      pw_rpc.ids.calculate(method.name()))

        gen.line('};\n')

        # Generate the method lookup table
        _method_lookup_table(gen, service)

    gen.line('};')


def _method_lookup_table(gen: CodeGenerator, service: ProtoService) -> None:
    """Generates array of method IDs for looking up methods at compile time."""
    gen.line('static constexpr std::array<uint32_t, '
             f'{len(service.methods())}> kMethodIds = {{')

    with gen.indent(4):
        for method in service.methods():
            method_id = pw_rpc.ids.calculate(method.name())
            gen.line(f'0x{method_id:08x},  // Hash of "{method.name()}"')

    gen.line('};')


class StubGenerator(abc.ABC):
    """Generates stub method implementations that can be copied-and-pasted."""
    @abc.abstractmethod
    def unary_signature(self, method: ProtoServiceMethod, prefix: str) -> str:
        """Returns the signature of this unary method."""

    @abc.abstractmethod
    def unary_stub(self, method: ProtoServiceMethod,
                   output: OutputFile) -> None:
        """Returns the stub for this unary method."""

    @abc.abstractmethod
    def server_streaming_signature(self, method: ProtoServiceMethod,
                                   prefix: str) -> str:
        """Returns the signature of this server streaming method."""

    def server_streaming_stub(  # pylint: disable=no-self-use
            self, unused_method: ProtoServiceMethod,
            output: OutputFile) -> None:
        """Returns the stub for this server streaming method."""
        output.write_line(STUB_REQUEST_TODO)
        output.write_line('static_cast<void>(request);')
        output.write_line(STUB_WRITER_TODO)
        output.write_line('static_cast<void>(writer);')

    @abc.abstractmethod
    def client_streaming_signature(self, method: ProtoServiceMethod,
                                   prefix: str) -> str:
        """Returns the signature of this client streaming method."""

    def client_streaming_stub(  # pylint: disable=no-self-use
            self, unused_method: ProtoServiceMethod,
            output: OutputFile) -> None:
        """Returns the stub for this client streaming method."""
        output.write_line(STUB_READER_TODO)
        output.write_line('static_cast<void>(reader);')

    @abc.abstractmethod
    def bidirectional_streaming_signature(self, method: ProtoServiceMethod,
                                          prefix: str) -> str:
        """Returns the signature of this bidirectional streaming method."""

    def bidirectional_streaming_stub(  # pylint: disable=no-self-use
            self, unused_method: ProtoServiceMethod,
            output: OutputFile) -> None:
        """Returns the stub for this bidirectional streaming method."""
        output.write_line(STUB_READER_WRITER_TODO)
        output.write_line('static_cast<void>(reader_writer);')


def _select_stub_methods(gen: StubGenerator, method: ProtoServiceMethod):
    if method.type() is ProtoServiceMethod.Type.UNARY:
        return gen.unary_signature, gen.unary_stub

    if method.type() is ProtoServiceMethod.Type.SERVER_STREAMING:
        return gen.server_streaming_signature, gen.server_streaming_stub

    if method.type() is ProtoServiceMethod.Type.CLIENT_STREAMING:
        return gen.client_streaming_signature, gen.client_streaming_stub

    if method.type() is ProtoServiceMethod.Type.BIDIRECTIONAL_STREAMING:
        return (gen.bidirectional_streaming_signature,
                gen.bidirectional_streaming_stub)

    raise NotImplementedError(f'Unrecognized method type {method.type()}')


_STUBS_COMMENT = r'''
/*
    ____                __                          __        __  _
   /  _/___ ___  ____  / /__  ____ ___  ___  ____  / /_____ _/ /_(_)___  ____
   / // __ `__ \/ __ \/ / _ \/ __ `__ \/ _ \/ __ \/ __/ __ `/ __/ / __ \/ __ \
 _/ // / / / / / /_/ / /  __/ / / / / /  __/ / / / /_/ /_/ / /_/ / /_/ / / / /
/___/_/ /_/ /_/ .___/_/\___/_/ /_/ /_/\___/_/ /_/\__/\__,_/\__/_/\____/_/ /_/
             /_/
   _____ __        __         __
  / ___// /___  __/ /_  _____/ /
  \__ \/ __/ / / / __ \/ ___/ /
 ___/ / /_/ /_/ / /_/ (__  )_/
/____/\__/\__,_/_.___/____(_)

*/
// This section provides stub implementations of the RPC services in this file.
// The code below may be referenced or copied to serve as a starting point for
// your RPC service implementations.
'''


def package_stubs(proto_package: ProtoNode, output: OutputFile,
                  stub_generator: StubGenerator) -> None:
    """Generates the RPC stubs for a package."""
    if proto_package.cpp_namespace():
        file_ns = proto_package.cpp_namespace()
        if file_ns.startswith('::'):
            file_ns = file_ns[2:]

        start_ns = lambda: output.write_line(f'namespace {file_ns} {{\n')
        finish_ns = lambda: output.write_line(f'}}  // namespace {file_ns}\n')
    else:
        start_ns = finish_ns = lambda: None

    services = [
        cast(ProtoService, node) for node in proto_package
        if node.type() == ProtoNode.Type.SERVICE
    ]

    output.write_line('#ifdef _PW_RPC_COMPILE_GENERATED_SERVICE_STUBS')
    output.write_line(_STUBS_COMMENT)

    output.write_line(f'#include "{output.name()}"\n')

    start_ns()

    for node in services:
        _service_declaration_stub(node, output, stub_generator)

    output.write_line()

    finish_ns()

    start_ns()

    for node in services:
        _service_definition_stub(node, output, stub_generator)
        output.write_line()

    finish_ns()

    output.write_line('#endif  // _PW_RPC_COMPILE_GENERATED_SERVICE_STUBS')


def _service_declaration_stub(service: ProtoService, output: OutputFile,
                              stub_generator: StubGenerator) -> None:
    output.write_line(f'// Implementation class for {service.proto_path()}.')
    output.write_line(
        f'class {service.name()} '
        f': public generated::{service.name()}<{service.name()}> {{')

    output.write_line(' public:')

    with output.indent():
        blank_line = False

        for method in service.methods():
            if blank_line:
                output.write_line()
            else:
                blank_line = True

            signature, _ = _select_stub_methods(stub_generator, method)

            output.write_line(signature(method, '') + ';')

    output.write_line('};\n')


def _service_definition_stub(service: ProtoService, output: OutputFile,
                             stub_generator: StubGenerator) -> None:
    output.write_line(f'// Method definitions for {service.proto_path()}.')

    blank_line = False

    for method in service.methods():
        if blank_line:
            output.write_line()
        else:
            blank_line = True

        signature, stub = _select_stub_methods(stub_generator, method)

        output.write_line(signature(method, f'{service.name()}::') + ' {')
        with output.indent():
            stub(method, output)
        output.write_line('}')
