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
Post processing functionality for the classical PSHA hazard calculator.
"""

import numpy


class PostProcessor(object):
    """Calculate post-processing per-site aggregate results: mean and
    quantile curves.

    :attribute _job
      The _job object associated with the post process

    :attribute _calculation
      The hazard calculation object with the configuration of the calculation

    :attribute _curve_finder
      An object used to query for individual hazard curves

    :attribute _curve_writer
      An object used to save aggregate hazard curves

    :attribute _task_handler
      An object used to distribute the post process in subtasks
    """

    # Number of locations processed by each task in the post process phase
    CURVE_BLOCK_SIZE = 100

    def __init__(self, job, hc,
                 curve_finder=None, curve_writer=None, task_handler=None):
        self._job = job
        self._calculation = hc,
        self._curve_finder = curve_finder
        self._curve_writer = curve_writer
        self._task_handler = task_handler
        self._curves_per_location = hc.individual_curves_per_location()

    def initialize(self):
        """
        Divide the whole computation in tasks.

        Each task is responsible to calculate the mean/quantile curve
        for a chunk of curves and for a specific intensity measure
        type.
        """

        curves_per_task = self.curves_per_task()

        for imt in self.imts:
            chunks_of_curves = self._curve_finder.individual_curves_chunks(
                self._job, imt, curves_per_task)

            if self.should_compute_mean_curves():
                for chunk_of_curves in chunks_of_curves:
                    self._task_handler.enqueue(
                        MeanCurveCalculator,
                        curves_per_location=self._curves_per_location,
                        chunk_of_curves=chunk_of_curves,
                        curve_writer=self._curve_writer)

            if self.should_compute_quantile_functions():
                for chunk_of_curves in chunks_of_curves:
                    self._task_handler.enqueue(
                        QuantileCurveCalculator,
                        curves_per_location=self._curves_per_location,
                        chunk_of_curves=chunk_of_curves)

    def execute(self):
        if self.is_too_big():
            self._task_handler.apply_async()
            self._task_handler.wait_for_results()
        else:
            self._task_handler.run_locally()

    def should_compute_mean_curves(self):
        return self._calculation.mean_hazard_curves

    def should_compute_quantiles(self):
        return self._calculation.quantile_hazard_curves

    def is_too_big(self):
        return False

    def curves_per_task(self):
        block_size = self.__class__.CURVE_BLOCK_SIZE
        chunk_size = self._curves_per_location
        return block_size * chunk_size

    def intensity_measure_types(self):
        return (
            self._calculation.intensity_measure_types_and_levels.keys())


class MeanCurveCalculator(object):
    def __init__(self, curves_per_location, chunk_of_curves,
                 curve_writer):
        self._chunk_of_curves = chunk_of_curves
        self._curves_per_location = curves_per_location
        self._curve_writer = curve_writer

    def execute(self):
        poe_matrix = self.fetch_curves()

        mean_curves = numpy.mean(poe_matrix, 2).transpose()

        locations = self.locations()
        _, job, imt, _, _ = self._chunk_of_curves

        for mean_curve in mean_curves:
            location = locations.next()
            self._curve_writer.add_mean_curve(job, imt, location, mean_curve)
        self._curve_writer.flush()

    def locations(self):
        curve_finder, job, imt, offset, size = self._chunk_of_curves
        locations = curve_finder.individual_curves_for_job_ordered(
            job, imt).values_list('location', flat=True).distinct()
        locations = locations[offset: size + offset]
        for location in locations:
            yield location

    def fetch_curves(self):
        """
        Returns a 3d matrix with shape given by
        (curves_per_location x number of locations x levels))
        """
        curve_finder, job, imt, offset, size = self._chunk_of_curves
        curves = curve_finder.individual_curves_for_job_ordered(
            job, imt).values_list('poes', flat=True)[offset: size + offset]

        level_nr = len(curves[0])
        loc_nr = len(curves) / self._curves_per_location
        return numpy.reshape(curves,
                             (self._curves_per_location, loc_nr, level_nr),
                             'F')


class QuantileCurveCalculator(object):
    def __init__(self, *args):
        raise NotImplementedError

    def execute(self):
        raise NotImplementedError
