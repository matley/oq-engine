# Copyright (c) 2010-2012, GEM Foundation.
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake.  If not, see <http://www.gnu.org/licenses/>.

"""
Iterators that help in task distribution.
"""

import kombu


class SiteBlockTaskIterator(object):
    """
    Iterate over a block of site, returning an object that can be
    used to spawn a worker for computation over a block of sites.
    """

    def __init__(self, sites, block_size):
        self.sites = sites
        self.block_size = block_size
        self.pointer = 0
        self.computed = 0
        self.total = 0

    def __iter__(self):
        return self

    def next(self):
        new_pointer = self.pointer + self.block_size
        site_block = self.sites[self.pointer:new_pointer]

        if len(site_block) < self.block_size:
            return StopIteration

        self.pointer = new_pointer

        return SiteBlockTask(site_block)

    def wait_for_all(self):
        with kombu.BrokerConnection(**conn_args) as conn:
            while (self.computed < self.total):
                conn.drain_events()


class SiteBlockTask(object):
    """
    A task that can be spawned to compute something over a block of
    sites
    """

    def 
