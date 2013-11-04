import shutil
from io import StringIO
import unittest

from django.db import connections

from openquake.engine.db.models import OqJob
from openquake.engine.tools.dump_hazards import HazardDumper
from openquake.engine.tools.restore_hazards import hazard_restore
from openquake.engine.tools.import_gmf_scenario import import_gmf_scenario

# fake gmfs like the ones generated by a scenario calculator
test_data = StringIO(unicode('''\
SA	0.025	5.0	{0.2}	POINT(0.0 0.0)
SA	0.025	5.0	{1.4}	POINT(1.0 0.0)
SA	0.025	5.0	{0.6}	POINT(0.0 1.0)
PGA	\N	\N	{0.2,0.3}	POINT(0.0 0.0)
PGA	\N	\N	{1.4,1.5}	POINT(1.0 0.0)
PGA	\N	\N	{0.6,0.7}	POINT(0.0 1.0)
PGV	\N	\N	{0.2}	POINT(0.0 0.0)
PGV	\N	\N	{1.4}	POINT(1.0 0.0)
'''))
test_data.name = 'test_data'


class DumperTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        connections['admin'].cursor()  # open a connection
        cls.conn = connections['admin'].connection
        cls.output, cls.hc = import_gmf_scenario(test_data)
        cls.output.oq_job = OqJob.objects.create(
            user_name='openquake', hazard_calculation=cls.hc)  # fake job
        cls.output.save()

    def test_dump_and_restore(self):
        # dump the Gmf generated in setUpClass into a directory
        hd = HazardDumper(self.conn)
        hd.dump(self.hc.id)
        curs = self.conn.cursor()
        try:
            # delete the original hazard calculation
            curs.execute('DELETE FROM uiapi.hazard_calculation '
                         'WHERE id=%s', (self.hc.id,))
            # restore the deleted Gmf
            hazard_restore(self.conn, hd.outdir)
            curs.execute('SELECT 1 FROM uiapi.hazard_calculation WHERE id=%s',
                         (self.hc.id,))
            self.assertEqual(curs.fetchall(), [(1,)])
        finally:
            shutil.rmtree(hd.outdir)