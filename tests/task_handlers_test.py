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


import unittest
import random
from openquake.calculators import task_handlers


class DummyTask():
    def __init__(self, arg):
        self.arg = arg

    def run(self):
        return self.arg


class CeleryTaskHandlerTestCase(unittest.TestCase):
    def setUp(self):
        self.task_cls = DummyTask
        self.task_handler = task_handlers.CeleryTaskHandler()

    def test_apply_async(self):
        a_number = random.random()
        self.task_handler.enqueue(self.task_cls, a_number)
        self.task_handler.apply_async()
        ret = self.task_handler.wait_for_results()
        self.assertEqual([a_number], list(ret))

    def test_run_locally(self):
        a_number = random.random()
        self.task_handler.enqueue(self.task_cls, a_number)
        ret = self.task_handler.run_locally()
        self.assertEqual([a_number], list(ret))
