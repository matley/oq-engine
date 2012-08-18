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
OO Interface to manage task queueing.
"""

from celery import registry
from celery.task import task, Task
from celery.task.sets import TaskSet

# pylint: enable=W0511,W0142,I0011,E1101,E0611,F0401,E1103,R0801,W0232


@task
class CeleryTask(Task):
    """
    Implements the delegation pattern to separate the concern of
    concrete task from celery task
    """

    def __init__(self):
        # Do not do anything to honour the celery metaclass magic
        pass

    @classmethod
    def run_task(cls, a_task, *args, **kwargs):
        """
        Call #run method of a_task passing in *args and **kwargs
        """
        return a_task.run(*args, **kwargs)

    def run(self, a_task):
        """
        Call #run method of a_task passing in *args and **kwargs
        """
        return self.__class__.run_task(a_task)
CELERY_TASK = registry.tasks[CeleryTask.name]


class CeleryTaskHandler(object):
    """
    A task handler for celery task queueing
    """
    def __init__(self):
        self._tasks = []
        self._taskset = None
        self._async_ret = None

    def enqueue(self, plain_task_cls, *args, **kwargs):
        """
        Build a task from a plain task callable with *args and **kwargs
        then append the built task to the queue
        """
        plain_task = plain_task_cls(*args, **kwargs)
        self._tasks.append(plain_task)

    def _create_taskset(self):
        """
        Create a celery TaskSet suitable for apply_* function
        """
        tasks = [CELERY_TASK.subtask((t,)) for t in self._tasks]
        self._taskset = TaskSet(tasks)

    def apply_async(self):
        """
        Consume the whole queue executing the task asynchronously
        """
        self._create_taskset()
        self._async_ret = self._taskset.apply_async()

    def wait_for_results(self):
        """
        Wait the results, if an async execution has been requested
        """
        return self._async_ret.join()

    def apply(self):
        """
        Consume the whole queue executing the task synchronously
        """
        self._create_taskset()
        return self._taskset.apply()
