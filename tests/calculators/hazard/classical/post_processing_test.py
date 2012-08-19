# -*- coding: utf-8 -*-
# unittest.TestCase base class does not honor the following coding
# convention
# pylint: disable=C0103,R0904

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
Test classical calculator post processing features
"""

import random
import numpy
import unittest
import itertools
import math
import mock

from openquake.calculators.hazard.classical.post_processing import (
    MeanCurveCalculator, PostProcessor)


class MeanCurveCalculatorTestCase(unittest.TestCase):
    """
    Tests for the main methods of the classical hazard post processor.
    """

    MAX_LOCATION_NR = 50
    MAX_CURVES_PER_LOCATION = 50
    MAX_LEVEL_NR = 10
    SIGMA = 0.001

    def setUp(self):
        self.location_nr = random.randint(1, self.__class__.MAX_LOCATION_NR)
        self.curves_per_location = random.randint(
            1,
            self.__class__.MAX_CURVES_PER_LOCATION)
        self.level_nr = random.randint(1, self.__class__.MAX_LEVEL_NR)
        self.curve_db = _populate_curve_db(self.location_nr,
                                           self.level_nr,
                                           self.curves_per_location,
                                           self.__class__.SIGMA)
        self.curve_writer = SimpleCurveWriter()

    def test_locations(self):
        getter = curve_chunks_getter(self.curve_db)

        mean_calculator = MeanCurveCalculator(
            curves_per_location=self.curves_per_location,
            chunk_of_curves=getter,
            curve_writer=self.curve_writer)

        locations = list(mean_calculator.locations())
        expected_locations = [v['location'] for v in self.curve_db]
        numpy.testing.assert_allclose(expected_locations, locations)

    def test_fetch_curves(self):
        getter = curve_chunks_getter(self.curve_db)

        mean_calculator = MeanCurveCalculator(
            curves_per_location=self.curves_per_location,
            chunk_of_curves=getter,
            curve_writer=self.curve_writer)

        poe_matrix = mean_calculator.fetch_curves()

        expected_shape = (self.curves_per_location,
                          self.location_nr,
                          self.level_nr)
        self.assertEqual(expected_shape, numpy.shape(poe_matrix))

        for x in range(0, self.location_nr):
            for y in range(0, self.curves_per_location):
                for z in range(0, self.level_nr):
                    index = x * self.curves_per_location + y
                    numpy.testing.assert_allclose(
                        self.curve_db[index]['poes'][z],
                        poe_matrix[y][x][z])

    def test_execute(self):
        getter = curve_chunks_getter(self.curve_db)

        mean_calculator = MeanCurveCalculator(
            curves_per_location=self.curves_per_location,
            chunk_of_curves=getter,
            curve_writer=self.curve_writer)

        mean_calculator.execute()

        self.assertAlmostEqual(self.location_nr, len(self.curve_writer.curves))
        locations = [v['location'] for v in self.curve_writer.curves]

        expected_mean_curves = [
            dict(location=locations[i],
                 poes=[i + j for j in range(0, self.level_nr)])
            for i in range(0, self.location_nr)]

        for i in range(0, self.location_nr):
            numpy.testing.assert_allclose(
                expected_mean_curves[i]['location'],
                self.curve_writer.curves[i]['location'])
            numpy.testing.assert_allclose(
                expected_mean_curves[i]['poes'],
                self.curve_writer.curves[i]['poes'],
                atol=self.__class__.SIGMA * 10)


class PostProcessorTestCase(unittest.TestCase):
    """
    Tests for the main methods of the post processor of the classical
    hazard calculator
    """
    def setUp(self):
        self.curves_per_location = 10
        location_nr = 10
        curve_nr = 100
        chunk_size = 1 + curve_nr / 5

        self.curve_writer = mock.Mock()
        self.task_handler = mock.Mock()

        curve_db = _populate_curve_db(location_nr, 1,
                                      self.curves_per_location, 0)

        self.a_chunk_getter = curve_chunks_getter(curve_db[0: chunk_size])
        self.task_nr = math.ceil(curve_nr / float(chunk_size))
        self.chunk_getters = list(itertools.repeat(
            self.a_chunk_getter, int(self.task_nr)))

        self.curve_finder = mock.Mock()
        self.curve_finder.individual_curve_nr = mock.Mock(
            return_value=curve_nr)

        self.curve_finder.individual_curves_chunks = mock.Mock(
            return_value=self.chunk_getters)

    def test_initialize_both_calculation_with_2imt(self):
        """
        Test that #initialize method has divided properly the main
        task with 2 imts and both mean and quantile calculation
        """

        # Arrange
        calculation = mock.Mock()
        calculation.individual_curves_per_location = mock.Mock(
            return_value=self.curves_per_location)

        calculation.intensity_measure_types_and_levels = {
            'PGA': range(1, 10),
            'SA(10)': range(1, 10)
            }
        calculation.mean_hazard_curves = True
        calculation.quantile_hazard_curves = True

        a_post_processor = PostProcessor(calculation,
                                         self.curve_finder,
                                         self.curve_writer,
                                         self.task_handler)
        # Act
        a_post_processor.initialize()

        # Assert
        expected_task_nr = 2 * 2 * self.task_nr
        self.assertEqual(expected_task_nr,
                         self.task_handler.enqueue.call_count)

    def test_initialize_one_calculation_with_1imt(self):
        """
        Test that #initialize method has divided properly the main
        task with 1 imt and only mean curves
        """

        # Arrange
        calculation = mock.Mock()
        calculation.individual_curves_per_location = mock.Mock(
            return_value=self.curves_per_location)

        calculation.intensity_measure_types_and_levels = {
            'SA(10)': range(1, 10)
            }
        calculation.mean_hazard_curves = True
        calculation.quantile_hazard_curves = False

        a_post_processor = PostProcessor(calculation,
                                         self.curve_finder,
                                         self.curve_writer,
                                         self.task_handler)
        # Act
        a_post_processor.initialize()

        # Assert
        self.task_handler.enqueue.assert_called_with(
            MeanCurveCalculator,
            curves_per_location=self.curves_per_location,
            chunk_of_curves=self.a_chunk_getter,
            curve_writer=self.curve_writer)

        expected_task_nr = self.task_nr
        self.assertEqual(expected_task_nr,
                         self.task_handler.enqueue.call_count)

    def test_execute(self):
        calculation = mock.Mock()

        a_post_processor = PostProcessor(calculation,
                                         self.curve_finder,
                                         self.curve_writer,
                                         self.task_handler)
        a_post_processor.should_be_distributed = mock.MagicMock(
            return_value=True, name="should_be_distributed")
        a_post_processor.execute()
        self.assertEqual(self.task_handler.apply_async.call_count, 1)
        self.assertEqual(self.task_handler.wait_for_results.call_count, 1)

        a_post_processor.should_be_distributed.return_value = False
        a_post_processor.execute()
        self.assertEqual(self.task_handler.apply_async.call_count, 1)
        self.assertEqual(self.task_handler.wait_for_results.call_count, 1)
        self.assertEqual(self.task_handler.apply.call_count, 1)


def curve_chunks_getter(db):
    """
    Simple curve chunks getter. Returns a function that extracts
    curve fields from a dictionary
    """
    return (lambda field: [curve[field] for curve in db])


class SimpleCurveWriter(object):
    """
    Simple Curve Writer that stores curves in a list of dictionaries
    """
    def __init__(self):
        self.curves = []

    def create_mean_curve(self, location, poes):
        """
        Implement the Curve writer protocol
        """
        self.curves.append(dict(location=location,
                                poes=poes.tolist()))


def _populate_curve_db(location_nr, level_nr, curves_per_location, sigma):
    """
    Create a fake db of curves
    """
    random_location = lambda: random.random() * 360
    curve_db = []

    for i in range(0, location_nr):
        location = (random_location(), random_location())
        # let's cheat. mean curve set to [i + j for j in level_indexes]
        curve_db.extend(
            [dict(location=location,
                  poes=[random.gauss(i + j, sigma)
                        for j in range(0, level_nr)])
            for _ in range(0, curves_per_location)])
    return curve_db
