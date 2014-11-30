########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import re
import time

from elasticsearch import Elasticsearch
from neutronclient.common.exceptions import NeutronClientException

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.git_helper import clone
from cosmo_tester.framework.util import YamlPatcher
from cosmo_tester.framework.handlers.openstack import OpenstackHandler

DEFAULT_EXECUTE_TIMEOUT = 1800

NODECELLAR_URL = "https://github.com/cloudify-cosmo/" \
                 "cloudify-nodecellar-example.git"


class ElasticsearchTimestampFormatTest(TestCase):

    """
    CFY-54
    this test checks Elasticsearch Timestamp Format.
    it creates events by uploading a blueprint and creating deployment.
    after creating events the test connects to Elasticsearch and compares
    Timestamp Format of the events to a regular expression.

    This test requires access to the management on port 9200 (elastic search",
    The rule is added by create_elasticsearch_rule
    """
    def _create_elasticsearch_rule(self):
        os_handler = OpenstackHandler(self.env)
        neutron_client = os_handler.openstack_clients()[1]
        sgr = {
            'direction': 'ingress',
            'ethertype': 'IPv4',
            'port_range_max': '9200',
            'port_range_min': '9200',
            'protocol': 'tcp',
            'remote_group_id': None,
            'remote_ip_prefix': '0.0.0.0/0',
            }

        mng_sec_grp_name = self.env.management_security_group

        mng_sec_grp = neutron_client. \
            list_security_groups(name=mng_sec_grp_name)['security_groups'][0]

        sg_id = mng_sec_grp['id']
        sgr['security_group_id'] = sg_id
        try:
            self.elasticsearch_rule = neutron_client.create_security_group_rule
            ({'security_group_rule': sgr})['security_group_rule']['id']
            time.sleep(20)  # allow rule to be created
        except NeutronClientException as e:
            self.elasticsearch_rule = None
            print "Got NeutronClientException({0}). Resuming".format(str(e))
            pass

    def setUp(self):
        super(ElasticsearchTimestampFormatTest, self).setUp()
        self._create_elasticsearch_rule()

    def _delete_elasticsearch_rule(self):
        if self.elasticsearch_rule is not None:
            os_handler = OpenstackHandler(self.env)
            neutron_client = os_handler.openstack_clients()[1]
            neutron_client.delete_security_group_rule(self.elasticsearch_rule)

    def tearDown(self):
        self._delete_elasticsearch_rule()
        super(ElasticsearchTimestampFormatTest, self).tearDown()

    def test_events_timestamp_format(self):

        self.repo_dir = clone(NODECELLAR_URL, self.workdir)
        self.blueprint_yaml = self.repo_dir / 'openstack-blueprint.yaml'
        self.modify_blueprint()
        try:
            self.cfy.upload_blueprint(self.test_id, self.blueprint_yaml, False)
        except Exception:
            self.fail('failed to upload the blueprint')
        time.sleep(5)
        try:
            self.cfy.create_deployment(blueprint_id=self.test_id,
                                       deployment_id=self.test_id)
        except Exception:
            self.fail('failed to create a deployment')
        time.sleep(5)

        #  connect to Elastic search
        try:
            es = Elasticsearch(self.env.management_ip + ':9200')
        except Exception:
            self.fail('failed to connect Elasticsearch')
        #  get events from events index
        res = es.search(index="cloudify_events",
                        body={"query": {"match_all": {}}})
        print("res Got %d Hits:" % res['hits']['total'])
        #  check if events were created
        if(0 == (res['hits']['total'])):
            self.fail('there are no events with '
                      'timestamp in index cloudify_events')
        #  loop over all the events and compare timestamp to regular expression
        for hit in res['hits']['hits']:
            if not (re.match('\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.\d{3}',
                             (str("%(timestamp)s" % hit["_source"])))):
                self.fail('Got {0}. Does not match format '
                          'YYYY-MM-DD HH:MM:SS.***'
                          .format((str("%(timestamp)s" % hit["_source"]))))
        return

    def modify_blueprint(self):
        with YamlPatcher(self.blueprint_yaml) as patch:
            vm_type_path = 'node_types.vm_host.properties'
            patch.merge_obj('{0}.server.default'.format(vm_type_path), {
                'image_name': self.env.ubuntu_image_name,
                'flavor_name': self.env.flavor_name
            })
        return
