from fanstatic import Library, Resource, NeededResources
from fanstatic import compat
from fanstatic import set_resource_file_existence_checking as check_files
from fanstatic.compiler import Compiler, Minifier
import fanstatic
import fanstatic.compiler
import os
import pytest
import time


class MockCompiler(fanstatic.compiler.Compiler):

    name = 'mock'
    source_extension = '.source'
    available = True

    def __init__(self):
        self.calls = []

    def __call__(self, resource, force=False):
        self.calls.append(resource)


class MockMinifier(fanstatic.compiler.Minifier):

    name = 'mock'
    target_extension = '.min.js'
    available = True

    def __init__(self):
        self.calls = []

    def __call__(self, resource, force=False):
        self.calls.append(resource)


class TestingRegistry(object):

    def __init__(self, request):
        self.request = request

    def add_compiler(self, compiler):
        return self._register_compiler(
            fanstatic.CompilerRegistry, compiler)

    def add_minifier(self, compiler):
        return self._register_compiler(
            fanstatic.MinifierRegistry, compiler)

    def _register_compiler(self, registry, compiler):
        self.request.addfinalizer(
            lambda: registry.instance().pop(compiler.name))
        registry.instance().add(compiler)
        return compiler

    def compiler(self, name):
        return fanstatic.CompilerRegistry.instance()[name]

    def minifier(self, name):
        return fanstatic.MinifierRegistry.instance()[name]


@pytest.fixture
def compilers(request):
    return TestingRegistry(request)


def test_setting_compile_False_should_not_call_compiler_and_minifier(
    compilers):
    compilers.add_compiler(MockCompiler())
    compilers.add_minifier(MockMinifier())

    lib = Library('lib', '')
    a = Resource(lib, 'a.js', compiler='mock', minifier='mock')

    needed = NeededResources()
    needed.need(a)
    needed.render()
    assert not compilers.compiler('mock').calls
    assert not compilers.minifier('mock').calls


def test_setting_compile_True_should_call_compiler_and_minifier(
    compilers):
    compilers.add_compiler(MockCompiler())
    compilers.add_minifier(MockMinifier())
    lib = Library('lib', '')
    a = Resource(lib, 'a.js', compiler='mock', minifier='mock')

    needed = NeededResources(compile=True)
    needed.need(a)
    needed.render()

    mock_compiler = compilers.compiler('mock')
    mock_minifier = compilers.minifier('mock')
    assert len(mock_compiler.calls) == 1
    assert mock_compiler.calls[0] == a
    assert len(mock_minifier.calls) == 1
    assert mock_minifier.calls[0] == a


def test_minified_mode_should_call_compiler_and_minifier_of_parent_resource(
    compilers):
    compilers.add_compiler(MockCompiler())
    compilers.add_minifier(MockMinifier())
    lib = Library('lib', '')
    a = Resource(lib, 'a.js', compiler='mock', minifier='mock')

    needed = NeededResources(compile=True, minified=True)
    needed.need(a)

    resources = needed.resources()
    assert len(resources) == 1
    assert resources[0].relpath == 'a.min.js'
    assert resources[0] != a

    needed.render()
    mock_compiler = compilers.compiler('mock')
    mock_minifier = compilers.minifier('mock')
    assert len(mock_compiler.calls) == 1
    assert mock_compiler.calls[0] == a
    assert len(mock_minifier.calls) == 1
    assert mock_minifier.calls[0] == a


def test_nothing_given_on_resource_uses_settings_from_library(compilers):
    mock_compiler = MockCompiler()
    compilers.add_compiler(mock_compiler)
    mock_minifier = MockMinifier()
    compilers.add_minifier(mock_minifier)
    lib = Library(
        'lib', '', compilers={'.js': 'mock'}, minifiers={'.js': 'mock'})
    a = Resource(lib, 'a.js')
    assert a.compiler is mock_compiler
    assert a.minifier is mock_minifier


def test_settings_on_resource_override_settings_from_library(compilers):
    compilers.add_compiler(MockCompiler())
    other_compiler = MockCompiler()
    other_compiler.name = 'other'
    compilers.add_compiler(other_compiler)
    compilers.add_minifier(MockMinifier())
    lib = Library(
        'lib', '', compilers={'.js': 'mock'}, minifiers={'.js': 'mock'})
    a = Resource(lib, 'a.js', compiler='other', minifier=None)
    assert a.compiler is other_compiler
    assert isinstance(a.minifier, fanstatic.compiler.NullCompiler)


def test_compiler_target_is_full_resource_path():
    lib = Library('lib', '/foo')
    a = Resource(lib, 'a.js')
    compiler = Compiler()
    assert compiler.target_path(a) == '/foo/a.js'


def test_compiler_uses_source_if_given_on_resource():
    lib = Library('lib', '/foo')
    a = Resource(lib, 'a.js', source='a.source')
    compiler = Compiler()
    assert compiler.source_path(a) == '/foo/a.source'


def test_compiler_source_transforms_extension_if_no_source_given():
    lib = Library('lib', '/foo')
    a = Resource(lib, 'a.js')
    compiler = Compiler()
    compiler.source_extension = '.source'
    assert compiler.source_path(a) == '/foo/a.source'


def test_minifier_source_is_full_resource_path():
    lib = Library('lib', '/foo')
    a = Resource(lib, 'a.js')
    minifier = Minifier()
    assert minifier.source_path(a) == '/foo/a.js'


def test_minifier_uses_minified_if_given_on_resource():
    lib = Library('lib', '/foo')
    a = Resource(lib, 'a.js', minified='a.min.js')
    minifier = Minifier()
    assert minifier.target_path(a) == '/foo/a.min.js'


def test_minifier_target_transforms_extension_if_no_name_given():
    lib = Library('lib', '/foo')
    a = Resource(lib, 'a.js')
    minifier = Minifier()
    minifier.target_extension = '.min.js'
    assert minifier.target_path(a) == '/foo/a.min.js'


def test_should_process_if_target_does_not_exist(tmpdir):
    assert Compiler().should_process(None, str(tmpdir / 'target'))


def test_should_process_if_target_is_older_than_source(tmpdir):
    source = str(tmpdir / 'source')
    open(source, 'w').close()
    target = str(tmpdir / 'target')
    open(target, 'w').close()
    old = time.time() - 1
    os.utime(target, (old, old))
    assert Compiler().should_process(source, target)


def test_should_not_process_if_target_is_newer_than_source(tmpdir):
    source = str(tmpdir / 'source')
    open(source, 'w').close()
    target = str(tmpdir / 'target')
    open(target, 'w').close()
    old = time.time() - 1
    os.utime(source, (old, old))
    assert not Compiler().should_process(source, target)


def test_compiler_available_and_source_not_present_should_raise(
    tmpdir, compilers):
    compilers.add_compiler(MockCompiler())
    check_files(True)
    lib = Library('lib', str(tmpdir))
    with pytest.raises(fanstatic.UnknownResourceError) as exc:
        a = Resource(lib, 'a.js', compiler='mock')
    assert 'a.source' in str(exc.value)


def test_compiler_not_available_and_source_not_present_should_raise(
    tmpdir, compilers):
    open(str(tmpdir / 'a.js'), 'w').close()
    compiler = MockCompiler()
    compiler.available = False
    compilers.add_compiler(compiler)
    check_files(True)
    lib = Library('lib', str(tmpdir))
    # assert_nothing_raised
    a = Resource(lib, 'a.js', compiler='mock')


def test_compiler_available_and_resource_file_not_present_should_not_raise(
    tmpdir, compilers):
    open(str(tmpdir / 'a.source'), 'w').close()
    # since the compiler can be used to generate the resource file
    compilers.add_compiler(MockCompiler())
    check_files(True)
    lib = Library('lib', str(tmpdir))
    # assert_nothing_raised
    a = Resource(lib, 'a.js', compiler='mock')


def test_compiler_not_available_and_resource_file_not_present_should_raise(
    tmpdir, compilers):
    compiler = MockCompiler()
    compiler.available = False
    compilers.add_compiler(compiler)
    check_files(True)
    lib = Library('lib', str(tmpdir))
    with pytest.raises(fanstatic.UnknownResourceError) as exc:
        a = Resource(lib, 'a.js', compiler='mock')
    assert 'a.js' in str(exc.value)


def test_minifier_available_and_minified_file_not_present_should_not_raise(
    tmpdir, compilers):
    open(str(tmpdir / 'a.js'), 'w').close()
    compilers.add_minifier(MockMinifier())
    check_files(True)
    lib = Library('lib', str(tmpdir))
    # assert_nothing_raised
    a = Resource(lib, 'a.js', minifier='mock')


def test_minifier_available_and_minified_not_a_string_should_raise(compilers):
    compilers.add_minifier(MockMinifier())
    lib = Library('lib', '')
    minified = Resource(lib, 'a.min.js')
    with pytest.raises(fanstatic.ConfigurationError) as exc:
        a = Resource(lib, 'a.js', minifier='mock', minified=minified)


def test_cli_compiler_is_not_available_if_command_not_found_on_path():
    class Nonexistent(fanstatic.compiler.CommandlineBase):
        command = 'does-not-exist'
    assert not Nonexistent().available


def test_cli_compiler_is_available_if_command_found_on_path():
    class Cat(fanstatic.compiler.CommandlineBase):
        command = 'cat'
    assert Cat().available


def test_cli_compiler_is_available_if_command_is_absolute_path():
    class Cat(fanstatic.compiler.CommandlineBase):
        command = '/bin/cat'
    assert Cat().available


def test_converts_placeholders_to_arguments(tmpdir):
    from fanstatic.compiler import SOURCE, TARGET

    source = str(tmpdir / 'source')
    with open(source, 'w') as f:
        f.write('source')
    target = str(tmpdir / 'target')
    with open(target, 'w') as f:
        f.write('target')

    class Echo(fanstatic.compiler.CommandlineBase):
        command = 'echo'
        arguments = ['-n', SOURCE, TARGET]

        def process(self, source, target):
            p = super(Echo, self).process(source, target)
            return p.stdout.read()

    assert Echo().process(source, target) == compat.as_bytestring(
        '%s %s' % (source, target))


def test_coffeescript_compiler(tmpdir):
    compiler = fanstatic.CompilerRegistry.instance()['coffee']
    if not compiler.available:
        pytest.skip('`%s` not found on PATH' % compiler.command)

    source = str(tmpdir / 'a.coffee')
    target = str(tmpdir / 'a.js')
    with open(source, 'w') as f:
        f.write('square = (x) -> x * x')
    compiler.process(source, target)

    assert 'square = function(x) {' in open(target).read()


def test_less_compiler(tmpdir):
    compiler = fanstatic.CompilerRegistry.instance()['less']
    if not compiler.available:
        pytest.skip('`%s` not found on PATH' % compiler.command)

    source = str(tmpdir / 'a.less')
    target = str(tmpdir / 'a.css')
    with open(source, 'w') as f:
        f.write('body { padding: (1 + 1)px; }')
    compiler.process(source, target)

    assert 'padding: 2 px;' in open(target).read()


def test_sass_compiler(tmpdir):
    compiler = fanstatic.CompilerRegistry.instance()['sass']
    if not compiler.available:
        pytest.skip('`%s` not found on PATH' % compiler.command)
    compiler.arguments = ['--no-cache'] + compiler.arguments

    source = str(tmpdir / 'a.scss')
    target = str(tmpdir / 'a.css')
    with open(source, 'w') as f:
        f.write('body { padding: (1 + 1)px; }')
    compiler.process(source, target)

    assert 'padding: 2 px;' in open(target).read()


def test_package_compiler_is_not_available_if_package_not_importable():
    class Nonexistent(fanstatic.compiler.PythonPackageBase):
        package = 'does-not-exist'
    assert not Nonexistent().available


def test_package_compiler_is_available_if_package_is_importable():
    class Example(fanstatic.compiler.PythonPackageBase):
        package = 'fanstatic'
    assert Example().available


def test_cssmin_minifier(tmpdir):
    compiler = fanstatic.MinifierRegistry.instance()['cssmin']
    if not compiler.available:
        pytest.skip('`%s` not found' % compiler.package)

    source = str(tmpdir / 'a.scss')
    target = str(tmpdir / 'a.css')
    with open(source, 'w') as f:
        f.write('body { padding: 2px; }')
    compiler.process(source, target)

    assert 'body{padding:2px}' == open(target).read()


def test_jsmin_minifier(tmpdir):
    compiler = fanstatic.MinifierRegistry.instance()['jsmin']
    if not compiler.available:
        pytest.skip('`%s` not found' % compiler.package)

    source = str(tmpdir / 'a.js')
    target = str(tmpdir / 'a.min.js')
    with open(source, 'w') as f:
        f.write('function foo() { var bar = "baz"; };')
    compiler.process(source, target)

    assert 'function foo(){var bar="baz";};' == open(target).read()


@pytest.fixture
def libraries(request):
    def cleanup():
        fanstatic.LibraryRegistry._instance = None
    request.addfinalizer(cleanup)


def test_console_script_collects_resources_from_package(
    monkeypatch, libraries):
    mypackage = pytest.importorskip('mypackage')

    lib = Library('other', '')
    a = Resource(lib, 'a.js')
    fanstatic.LibraryRegistry.instance().add(lib)

    def log_compile(self, force=False):
        calls.append((self, force))
    calls = []
    monkeypatch.setattr(Resource, 'compile', log_compile)
    fanstatic.compiler._compile_resources('mypackage')
    assert len(calls) == 1
    assert calls[0] == (mypackage.style, True)
