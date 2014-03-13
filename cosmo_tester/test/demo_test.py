__author__ = 'nirb'

from attest import Tests
import framework.cloud_bootstrapper as bootstrapper

cosmo_test = Tests()

@cosmo_test.test
def test_hello_world_on_hp():

    # bootstrapper.bootstrap('hp-cloudify-config.yaml')

    assert 1 + 1 == 2
