#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import collections
import io
import logging
import re
import subprocess


from datetime import datetime
from enum import Enum
from prettytable import PrettyTable


logger = logging.getLogger("afsmon")


class FileServerStatus(Enum):
    NORMAL = 0
    TEMPORARY_DISABLED = 1
    DISABLED = 2
    UNKNOWN = 3
    NO_CONNECTION = 4

Partition = collections.namedtuple(
    'Partition', 'partition, used, free, total, percent_used')

Volume = collections.namedtuple(
    'Voume', 'volume, id, perms, used, quota, percent_used, creation')


class FileServerStats(object):
    '''AFS fileserver status

    Call ``get_stats()`` to populate the statistics for the server.
    Note most attributes are only set if ``status`` is NORMAL

    Args:
       hostname (str): The hostname of server to query
         i.e. argument to ``-server`` for cmd line tools

    Attributes:
       status (FileServerStatus): enum of possible status
       timestamp(:obj:`datetime.datetime`): time statistics retrieved
       restart (:obj:`datetime.datetime`): time of last restart
       uptime (:obj:`datetime.timedelta`): current uptime
       partitions (:obj:`list`): list of :obj:`Partition` tuples for each
         partition on the server
       calls_waiting (:obj:`int`): number of calls waiting for a thread
       idle_threads (:obj:`int`): number of currently idle threads
       volumes (:obj:`list`): list of :obj:`Volume` tuples for each
         volume present on the server
       table (:obj:`PrettyTable`): a printable PrettyTable representation

    '''

    # Sample AFS timestamps:
    #   Tue Nov  2 03:35:15 2016
    #   Tue Nov 22 03:35:15 2016
    AFS_DATE_REGEX = '(?P<date>\w+ \w+\s+(\d{1,2}) \d+:\d+:\d+ \d+)'
    AFS_DATE_STRPTIME = '%a %b %d %H:%M:%S %Y'

    def _get_volumes(self):
        cmd = ["vos", "listvol", "-long", "-server", self.hostname]
        logger.debug("Running: %s" % cmd)
        output = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT).decode('ascii')

        # Matching:
        # mirror.yum-puppetlabs.readonly    536871036 RO   63026403 K  On-line
        vol_regex = re.compile(
          '^(?P<vol>[^\s]+)\s+(?P<id>\d+)\s(?P<perms>R[OW])\s+(?P<used>\d+) K'
        )

        # Read the output into chunks where each chunk is the info for
        # one volume.
        lines = io.StringIO(output)
        while True:
            line = lines.readline()
            if not line:
                break
            chunk = ''
            if "On-line" in line:  # chunks start with this
                chunk += line
                # read in the next 9 lines of status
                for i in range(8):
                    chunk += lines.readline()
                # convert it to a Volume()
                # todo: there's a bunch more we could extract...
                m = vol_regex.search(chunk)
                q = re.search('MaxQuota\s+(?P<quota>\d+) K', chunk)
                used = int(m.group('used'))
                quota = int(q.group('quota'))
                percent_used = round(float(used) / float(quota) * 100, 2)
                print(chunk)
                c = re.search(r'Creation\s+%s' % self.AFS_DATE_REGEX, chunk)
                creation = datetime.strptime(c.group('date'),
                                             self.AFS_DATE_STRPTIME)

                self.volumes.append(
                    Volume(m.group('vol'), m.group('id'), m.group('perms'),
                           used, quota, percent_used, creation))

    def _get_calls_waiting(self):
        cmd = ["rxdebug", self.hostname, "7000", "-rxstats", "-noconns"]
        logger.debug("Running: %s" % cmd)
        output = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT).decode('ascii')

        for line in output.split('\n'):
            m = re.search('(?P<waiting>\d+) calls waiting for a thread', line)
            if m:
                self.calls_waiting = int(m.group('waiting'))
            m = re.search('(?P<idle>\d+) threads are idle', line)
            if m:
                self.idle_threads = int(m.group('idle'))

    def _get_partition_stats(self):
        cmd = ["vos", "partinfo", self.hostname, "-noauth"]
        logger.debug("Running: %s" % cmd)
        output = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT).decode('ascii')

        for line in output.split('\n'):
            m = re.search(
                'Free space on partition '
                '/vicep(?P<partition>[a-z][a-z]?): '
                '(?P<free>\d+) K blocks out of total (?P<total>\d+)', line)
            if m:
                part = 'vicep%s' % m.group('partition')
                # (used, free, total, %age)
                used = int(m.group('total')) - int(m.group('free'))
                percent = round(float(used) / float(m.group('total')) * 100, 2)
                self.partitions.append(
                    Partition(part, used, int(m.group('free')),
                              int(m.group('total')), percent))

    def _get_fs_stats(self):
        cmd = ["bos", "status", self.hostname, "-long", "-noauth"]
        logger.debug("Running: %s" % cmd)
        try:
            output = subprocess.check_output(
                cmd, stderr=subprocess.STDOUT).decode('ascii')
        except subprocess.CalledProcessError:
            logger.debug(" ... failed!")
            self.status = FileServerStatus.NO_CONNECTION
            return

        if re.search('currently running normally', output):
            self.status = FileServerStatus.NORMAL
            m = re.search(r'last started at %s' % self.AFS_DATE_REGEX, output)
            self.restart = datetime.strptime(m.group('date'),
                                             self.AFS_DATE_STRPTIME)
            self.uptime = self.timestamp - self.restart

        elif re.search('temporarily disabled, currently shutdown', output):
            self.status = FileServerStatus.TEMPORARILY_DISABLED
        elif re.search('disabled, currently shutdown', output):
            self.status = FileServerStatus.DISABLED
        else:
            logger.debug(output)
            self.status = FileServerStatus.UNKNOWN

    def get_stats(self):
        '''Get the complete stats set for the fileserver'''
        self.timestamp = datetime.now()

        self._get_fs_stats()
        if self.status == FileServerStatus.NORMAL:
            self._get_partition_stats()
            self._get_calls_waiting()
            self._get_volumes()

        self.table = PrettyTable()
        self.table.field_names = ["Metric", "Value"]
        self.table.align["Metric"] = "l"
        self.table.align["Value"] = "l"
        self.table.add_row(["Hostname", self.hostname])
        self.table.add_row(["Timestamp", self.timestamp])
        self.table.add_row(["Status", self.status])
        self.table.add_row(["Uptime", self.uptime])
        self.table.add_row(["Last Restart", self.restart])
        self.table.add_row(["Calls Waiting", self.calls_waiting])
        self.table.add_row(["Idle Threads", self.idle_threads])
        for p in self.partitions:
            n = "/%s" % p.partition
            self.table.add_row(["%s used" % n, p.used])
            self.table.add_row(["%s free" % n, p.free])
            self.table.add_row(["%s total" % n, p.total])
            self.table.add_row(["%s %%used" % n,
                                "%s%%" % p.percent_used])
        for v in self.volumes:
            n = v.volume
            self.table.add_row(["%s used" % n, v.used])
            self.table.add_row(["%s quota" % n, v.quota])
            self.table.add_row(["%s %%used" % n,
                                "%s%%" % v.percent_used])
            self.table.add_row(["%s creation" % n, v.creation])

    def __str__(self):
        return str(self.table)

    def __init__(self, hostname):
        self.hostname = hostname

        self.timestamp = None
        self.restart = None
        self.uptime = None
        self.partitions = []
        self.volumes = []
        self.calls_waiting = None
        self.idle_threads = None


def get_fs_addresses(cell):
    '''Get the fileservers associated with a cell

    :arg str cell: The cell (e.g. ``openstack.org``)
    :returns: list of fileservers for the cell
    '''
    fs = []
    cmd = ["vos", "listaddrs", "-noauth", "-cell", cell]
    logger.debug("Running: %s" % cmd)
    try:
        output = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT).decode('ascii')
    except subprocess.CalledProcessError:
        logger.debug(" ... failed!")
        return []

    for line in output.split('\n'):
        if line.strip():
            fs.append(line)

    return fs
