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
Concrete classes to manage task queueing.
"""

import celery


class CeleryTask(celery.task.base.Task):
    def __init__(self, delegate):
        self.delegate = delegate

    def run(self, *args, **kwargs):
        self.delegate.run(*args, **kwargs)


class CeleryTaskHandler(object):
    def __init__(self):
        self.taskset = celery.task.sets.TaskSet()

    def enqueue(self, plain_task_cls, *args, **kwargs):
        plain_task = plain_task_cls(*args, **kwargs)
        task = CeleryTask(plain_task)
        self.taskset.tasks.add(task)

    def apply_async(self):
        self.taskset.apply_async()

    def wait_for_results(self):
        self.taskset.join()
