import pytest
from cosmo_tester.framework.util import is_community

skip_community = pytest.mark.skipif(is_community(),
                                    reason='Community does not support HA')
