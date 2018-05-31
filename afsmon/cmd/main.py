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
import sys

import afsmon

def main(args=None):

    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description='An AFS monitoring tool')

    parser.add_argument("config", help="Path to config file")
    parser.add_argument("-d", '--debug', action="store_true")

    args = parser.parse_args(args)

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
        logging.debug("Debugging enabled")

    config = configparser.RawConfigParser()
    config.read(args.config)

    cell = config.get('main', 'cell').strip()

    fileservers = afsmon.get_fs_addresses(cell)
    logging.debug("Found fileservers: %s" % ", ".join(fileservers))

    for fileserver in fileservers:
        logging.debug("Finding stats for: %s" % fileserver)

        fs = afsmon.FileServerStats(fileserver)
        fs.get_stats()
        print(fs)

    sys.exit(0)
