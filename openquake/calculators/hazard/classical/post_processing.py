# -*- coding: utf-8 -*-
# pylint: enable=W0511,W0142,I0011,E1101,E0611,F0401,E1103,R0801,W0232

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
    """Calculate post-processing per-site aggregate results. E.g. mean
    and quantile curves.

    Implements the Command pattern where the commands are instances
    for computing the post-processing output

    The instances of this class should used with the following protocol:
    a_post_processor = PostProcessor(...)
    a_post_processor.initialize() # divide the calculation in subtasks
    a_post_processor.execute() # execute subtasks

    :attribute _calculation
      The hazard calculation object with the configuration of the calculation

    :attribute _curve_finder
      An object used to query for individual hazard curves.
      It should implement the methods #individual_curve_nr and
      #individual_curve_chunks

    :attribute _curve_writer
      An object used to save aggregate hazard curves.
      It should implement the methods #create_mean_curve and
      #create_quantile_curves

    :attribute _task_handler
      An object used to distribute the post process in subtasks.
      It should implement the method #enqueue, #apply_async, #wait_for_results
      and #apply
    """

    # Number of locations processed by each task in the post process phase
    CURVE_BLOCK_SIZE = 100

    # minimum number of curves to be processed with a distributed queue
    DISTRIBUTION_THRESHOLD = 1000

    def __init__(self, hc,
                 curve_finder=None, curve_writer=None, task_handler=None):
        self._calculation = hc
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

        for imt in self._calculation.intensity_measure_types_and_levels:
            chunks_of_curves = self._curve_finder.individual_curves_chunks(
                imt, curves_per_task)

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
                        chunk_of_curves=chunk_of_curves,
                        curve_writer=self._curve_writer)

    def execute(self):
        """
        Execute the calculation using the task queue handler
        """
        if self.should_be_distributed():
            self._task_handler.apply_async()
            self._task_handler.wait_for_results()
        else:
            self._task_handler.apply()

    def should_compute_mean_curves(self):
        """
        Returns None if no mean curve calculation has been requested
        """
        return self._calculation.mean_hazard_curves

    def should_compute_quantile_functions(self):
        """
        Returns None if no quantile curve calculation has been requested
        """
        return self._calculation.quantile_hazard_curves

    def should_be_distributed(self):
        """
        Returns True if the calculation should be distributed
        """
        curve_nr = self._curve_finder.individual_curves_nr()
        return curve_nr > self.__class__.DISTRIBUTION_THRESHOLD

    def curves_per_task(self):
        """
        Returns the number of curves calculated by each task
        """
        block_size = self.__class__.CURVE_BLOCK_SIZE
        chunk_size = self._curves_per_location
        return block_size * chunk_size


class MeanCurveCalculator(object):
    """
    Calculate mean curves.

    :attribute _curves_per_location
      the number of curves for each location considered for mean
      calculation

    :attribute _chunk_of_curves
      a list of individual curve chunks (usually spanning more
      locations). Each chunk is a function that actually fetches the
      curves when it is invoked.

    :attribute _curve_writer
      an object that can save the result by calling #create_mean_curve
    """
    def __init__(self, curves_per_location, chunk_of_curves,
                 curve_writer):
        self._chunk_of_curves = chunk_of_curves
        self._curves_per_location = curves_per_location
        self._curve_writer = curve_writer

    def execute(self):
        """
        Fetch the curves, calculate the mean curves and saves them
        """
        poe_matrix = self.fetch_curves()

        mean_curves = numpy.mean(poe_matrix, 0)

        for mean_curve in mean_curves:
            location = self.locations().next()
            self._curve_writer.create_mean_curve(location, mean_curve)

    def locations(self):
        """
        A generator of locations considered by the computation
        """
        locations = self._chunk_of_curves('location')
        for location in locations:
            yield location

    def fetch_curves(self):
        """
        Returns a 3d matrix with shape given by
        (curves_per_location x number of locations x levels))
        """
        curves = self._chunk_of_curves('poes')
        level_nr = len(curves[0])
        loc_nr = len(curves) / self._curves_per_location
        return numpy.reshape(curves,
                             (self._curves_per_location, loc_nr, level_nr),
                             'F')


class QuantileCurveCalculator(object):
    """
    TBI
    """
    def __init__(self, *args):
        raise NotImplementedError

    def execute(self):
        """
        tbi
        """
        raise NotImplementedError
