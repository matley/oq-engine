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

import StringIO
import numpy
import os
import shutil
import tempfile

from nose.plugins.attrib import attr
from openquake.db import models
from openquake.export import hazard as hazard_export
from qa_tests import _utils as qa_utils


class ClassicalHazardCase12TestCase(qa_utils.BaseQATestCase):

    EXPECTED_XML = """<nrml xmlns:gml="http://www.opengis.net/gml" xmlns="http://openquake.org/xmlns/nrml/0.4">
  <hazardCurves IMT="PGA" investigationTime="1.0" sourceModelTreePath="b1" gsimTreePath="b1|b2">
    <IMLs>0.1 0.4 0.6</IMLs>
    <hazardCurve>
      <gml:Point>
        <gml:pos>0.0 0.0</gml:pos>
      </gml:Point>
      <poEs>0.751664728823 0.0780348539189 0.00686616439666</poEs>
    </hazardCurve>
  </hazardCurves>
</nrml>
"""

    @attr('qa', 'classical')
    def test(self):
        result_dir = tempfile.mkdtemp()
        aaae = numpy.testing.assert_array_almost_equal

        try:
            cfg = os.path.join(os.path.dirname(__file__), 'job.ini')
            expected_curve_poes = [0.75421006, 0.08098179, 0.00686616]

            job = self.run_hazard(cfg)

            # Test the poe values of the single curve:
            [curve] = models.HazardCurveData.objects.filter(
                hazard_curve__output__oq_job=job.id)

            aaae(expected_curve_poes, curve.poes, decimal=2)

            # Test the exports as well:
            [exported_file] = hazard_export.export(
                curve.hazard_curve.output.id, result_dir)
            self.assert_xml_equal(
                StringIO.StringIO(self.EXPECTED_XML),
                exported_file)
        finally:
            shutil.rmtree(result_dir)
