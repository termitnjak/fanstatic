import webob

from datetime import datetime, timedelta

from fanstatic import (Library, ResourceInclusion, Publisher, Delegator)
from fanstatic.publisher import FOREVER

def test_resource(tmpdir):
    foo_library_dir = tmpdir.mkdir('foo')
    resource = tmpdir.join('foo').join('test.js')
    resource.write('/* a test */')

    foo_library = Library('foo', foo_library_dir.strpath)

    app = Publisher([foo_library])
    
    request = webob.Request.blank('/foo/test.js')
    response = request.get_response(app)
    assert response.body == '/* a test */'

def test_just_publisher():
    app = Publisher([])
    request = webob.Request.blank('/')
    response = request.get_response(app)
    assert response.status == '403 Forbidden'

def test_just_library(tmpdir):
    foo_library_dir = tmpdir.mkdir('foo')
    resource = tmpdir.join('foo').join('test.js')
    resource.write('/* a test */')

    foo_library = Library('foo', foo_library_dir.strpath)

    app = Publisher([foo_library])
    
    request = webob.Request.blank('/foo')
    response = request.get_response(app)
    assert response.status == '403 Forbidden'

def test_unknown_library(tmpdir):
    foo_library_dir = tmpdir.mkdir('foo')
    resource = tmpdir.join('foo').join('test.js')
    resource.write('/* a test */')

    foo_library = Library('foo', foo_library_dir.strpath)

    app = Publisher([foo_library])
    
    request = webob.Request.blank('/bar')
    response = request.get_response(app)
    assert response.status == '404 Not Found'
    
def test_resource_hash_skipped(tmpdir):
    foo_library_dir = tmpdir.mkdir('foo')
    resource = tmpdir.join('foo').join('test.js')
    resource.write('/* a test */')

    foo_library = Library('foo', foo_library_dir.strpath)

    app = Publisher([foo_library])
    
    request = webob.Request.blank('/foo/:hash:something/test.js')
    response = request.get_response(app)
    assert response.body == '/* a test */'

def test_resource_no_hash_no_cache(tmpdir):
    foo_library_dir = tmpdir.mkdir('foo')
    resource = tmpdir.join('foo').join('test.js')
    resource.write('/* a test */')

    foo_library = Library('foo', foo_library_dir.strpath)

    app = Publisher([foo_library])
    
    request = webob.Request.blank('/foo/test.js')
    response = request.get_response(app)
    assert response.body == '/* a test */'
    assert response.cache_control.max_age is None
    assert response.expires is None

def test_resource_hash_cache(tmpdir):
    foo_library_dir = tmpdir.mkdir('foo')
    resource = tmpdir.join('foo').join('test.js')
    resource.write('/* a test */')

    foo_library = Library('foo', foo_library_dir.strpath)

    app = Publisher([foo_library])
    
    request = webob.Request.blank('/foo/:hash:something/test.js')
    response = request.get_response(app)
    assert response.body == '/* a test */'
    assert response.cache_control.max_age == FOREVER
    # the test has just run and will take less than a full day to
    # run. we therefore expect the expires to be greater than
    # one_day_ago + FOREVER
    utc = response.expires.tzinfo # get UTC as a hack
    one_day_ago = datetime.now(utc) - timedelta(days=1)
    future = one_day_ago + timedelta(seconds=FOREVER)
    assert response.expires > future

def test_resource_cache_only_for_success(tmpdir):
    foo_library_dir = tmpdir.mkdir('foo')
    foo_library = Library('foo', foo_library_dir.strpath)

    app = Publisher([foo_library])
    
    request = webob.Request.blank('/foo/:hash:something/nonexistent.js')
    response = request.get_response(app)
    assert response.status == '404 Not Found'
    assert response.cache_control.max_age is None
    assert response.expires is None

def test_delegator(tmpdir):
    foo_library_dir = tmpdir.mkdir('foo')
    resource = tmpdir.join('foo').join('test.js')
    resource.write('/* a test */')

    foo_library = Library('foo', foo_library_dir.strpath)

    publisher = Publisher([foo_library])

    def real_app(environ, start_response):
        start_response('200 OK', [])
        return ['Hello world!']
    
    delegator = Delegator(real_app, publisher)
    
    request = webob.Request.blank('/fanstatic/foo/test.js')
    response = request.get_response(delegator) 
    assert response.body == '/* a test */'

    request = webob.Request.blank('/somethingelse')
    response = request.get_response(delegator)
    assert response.body == 'Hello world!'
