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

import argparse
import configparser
import logging
import os
import statsd
import sys

import afsmon

logger = logging.getLogger("afsmon.main")


class AFSMonCmd(object):

    def cmd_show(self):
        for fs in self.fileservers:
            print(fs)
        return 0

    def cmd_statsd(self):
        # note we're just being careful to let the default values fall
        # through to StatsClient()
        statsd_args = {}
        try:
            try:
                statsd_args['host'] = self.config.get('statsd', 'host')
            except configparser.NoOptionError:
                pass
            try:
                statsd_args['port'] = self.config.get('statsd', 'port')
            except configparser.NoOptionerror:
                pass
        except configparser.NoSectionError:
            pass
        if os.getenv('STATSD_HOST', None):
            statsd_args['host'] = os.environ['STATSD_HOST']
        if os.getenv('STATSD_PORT', None):
            statsd_args['port'] = os.environ['STATSD_PORT']
        logger.debug("Sending stats to %s:%s" % (
            statsd_args.get('host', 'localhost'),
            statsd_args.get('port', '8125'))
        )
        self.statsd = statsd.StatsClient(**statsd_args)

        # With a lot of volumes, we can flood out a lot of stats
        # quickly.  Use a pipeline to batch.
        pipe = self.statsd.pipeline()

        for f in self.fileservers:
            if f.status != afsmon.FileServerStatus.NORMAL:
                continue

            hn = f.hostname.replace('.', '_')
            pipe.gauge('afs.%s.idle_threads' % hn, f.idle_threads)
            pipe.gauge('afs.%s.calls_waiting' % hn, f.calls_waiting)
            for p in f.partitions:
                pipe.gauge(
                    'afs.%s.part.%s.used' % (hn, p.partition), p.used)
                pipe.gauge(
                    'afs.%s.part.%s.free' % (hn, p.partition), p.free)
                pipe.gauge(
                    'afs.%s.part.%s.total' % (hn, p.partition), p.total)
            for v in f.volumes:
                vn = v.volume.replace('.', '_')
                pipe.gauge(
                    'afs.%s.vol.%s.used' % (hn, vn), v.used)
                pipe.gauge(
                    'afs.%s.vol.%s.quota' % (hn, vn), v.quota)
                pipe.gauge(
                    'afs.%s.vol.%s.creation' % (hn, vn),
                    int(v.creation.strftime("%s")))

        pipe.send()

    def main(self, args=None):
        if args is None:
            args = sys.argv[1:]

        self.fileservers = []

        parser = argparse.ArgumentParser(
            description='An AFS monitoring tool')

        parser.add_argument("-c", "--config", action='store',
                            default="/etc/afsmon.cfg",
                            help="Path to config file")
        parser.add_argument("-d", '--debug', action="store_true")

        subparsers = parser.add_subparsers(title='commands',
                                           description='valid commands',
                                           dest='command')

        cmd_show = subparsers.add_parser('show', help='show table of results')
        cmd_show.set_defaults(func=self.cmd_show)

        cmd_statsd = subparsers.add_parser('statsd', help='report to statsd')
        cmd_statsd.set_defaults(func=self.cmd_statsd)

        self.args = parser.parse_args(args)

        if not os.path.exists(self.args.config):
            parser.error("Config file %s does not exist" % self.args.config)

        self.config = configparser.RawConfigParser()
        self.config.read(self.args.config)

        logfmt = '%(asctime)s %(name)-12s %(levelname)-8s %(message)s'
        if self.args.debug or \
           self.config.getboolean('main', 'debug', fallback=False):
            logging.basicConfig(level=logging.DEBUG, format=logfmt)
            logger.debug("Debugging enabled")

        if not self.args.command:
            parser.print_help()
            return 1

        fs_addrs = []

        # Look for fileservers from a given cell
        cell = self.config.get('main', 'cell', fallback=None)
        if cell:
            fs_addrs = afsmon.get_fs_addresses(cell.strip())
            logger.debug("cell %s fileservers: %s" % (
                cell, ", ".join(fs_addrs)))

        # Add in any specific fileservers from config
        cfg_fs = self.config.get('main', 'fileservers', fallback=None)
        if cfg_fs:
            cfg_fs = cfg_fs.strip().split('\n')
            logger.debug("cfg fileservers: %s" % ", ".join(cfg_fs))
            fs_addrs.extend(cfg_fs)

        if not fs_addrs:
            raise ValueError("No fileservers found!")

        # populate self.fileservers
        for addr in fs_addrs:
            logger.debug("Finding stats for: %s" % addr)
            fs = afsmon.FileServerStats(addr)
            fs.get_stats()
            self.fileservers.append(fs)

        # run the subcommand
        return self.args.func()


def main():
    cmd = AFSMonCmd()
    return cmd.main()
