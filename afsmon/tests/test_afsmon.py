# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
import afsmon
import configparser

from afsmon.cmd.main import AFSMonCmd
from afsmon.tests import base

"""
test_afsmon
----------------------------------

Tests for `afsmon` module.
"""


class TestPyAFSMon(base.TestCase):

    def setUp(self):
        super(TestPyAFSMon, self).setUp()

    def test_statsd(self):
        cmd = AFSMonCmd()
        cmd.config = configparser.ConfigParser()

        a = afsmon.FileServerStats('afs01.dfw.openstack.org')
        a.status = afsmon.FileServerStatus.NORMAL
        a.idle_threads = 250
        a.calls_waiting = 0
        a.partitions = [afsmon.Partition('vicepa', 512, 512, 1024, 50.00)]
        a.volumes = [
            afsmon.Volume('mirror.foo', 12345678, 'RW', 512, 1024, 50.00),
            afsmon.Volume('mirror.moo', 87654321, 'RW', 1024, 2048, 50.00),
        ]

        b = afsmon.FileServerStats('afs02.ord.openstack.org')
        b.status = afsmon.FileServerStatus.NORMAL
        b.idle_threads = 100
        b.calls_waiting = 2
        b.partitions = [afsmon.Partition('vicepa', 512, 512, 1024, 50.00)]
        b.volumes = []

        cmd.fileservers = [a, b]

        cmd.cmd_statsd()

        self.assertReportedStat(
            'afs.afs01_dfw_openstack_org.idle_threads', value='250', kind='g')
        self.assertReportedStat(
            'afs.afs02_ord_openstack_org.calls_waiting', value='2', kind='g')
        self.assertReportedStat(
            'afs.afs01_dfw_openstack_org.part.vicepa.used',
            value='512', kind='g')
        self.assertReportedStat(
            'afs.afs01_dfw_openstack_org.part.vicepa.total',
            value='1024', kind='g')
        self.assertReportedStat(
            'afs.afs01_dfw_openstack_org.vol.mirror_moo.used',
            value='1024', kind='g')
        self.assertReportedStat(
            'afs.afs01_dfw_openstack_org.vol.mirror_moo.quota',
            value='2048', kind='g')
