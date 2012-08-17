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

from celery import registry
from celery.task import task, Task
from celery.task.sets import TaskSet


@task
class CeleryTask(Task):
    def run(self, task_cls):
        return task_cls.run()
celery_task = registry.tasks[CeleryTask.name]


class CeleryTaskHandler(object):
    def __init__(self):
        self._tasks = []
        self._taskset = None
        self._async_ret = None

    def enqueue(self, plain_task_cls, *args, **kwargs):
        plain_task = plain_task_cls(*args, **kwargs)
        self._tasks.append(plain_task)

    def _create_taskset(self):
        tasks = [celery_task.subtask((t,)) for t in self._tasks]
        self._taskset = TaskSet(tasks)

    def apply_async(self):
        self._create_taskset()
        self._async_ret = self._taskset.apply_async()

    def wait_for_results(self):
        return self._async_ret.join()

    def run_locally(self):
        self._create_taskset()
        return self._taskset.apply()
