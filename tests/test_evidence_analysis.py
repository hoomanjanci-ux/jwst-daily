import sys,tempfile
from pathlib import Path
import unittest
import numpy as np
from astropy.io import fits
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pipeline'))
import evidence_analysis as evidence
class EvidenceTests(unittest.TestCase):
    def test_real_fits_statistics_and_dq(self):
        rng=np.random.default_rng(7);data=rng.normal(size=(100,100));data[0:2,0:2]=100
        dq=np.zeros((100,100),dtype=np.uint32);dq[0:2,0:2]=3
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.fits';fits.HDUList([fits.PrimaryHDU(),fits.ImageHDU(data,name='SCI'),fits.ImageHDU(dq,name='DQ')]).writeto(p)
            m=evidence.measure(p,1)
        self.assertEqual(m['sample_count'],9996)
        self.assertGreater(m['robust_scatter'],0)
        self.assertLess(m['above_5scatter_percent'],0.1)
    def test_blank_image_is_not_publishable(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.fits';fits.PrimaryHDU(np.zeros((100,100))).writeto(p)
            with self.assertRaises(ValueError):evidence.measure(p,0)
    def test_known_nircam_filter_wavelength(self):
        self.assertEqual(evidence.wavelength('F335M'),3.35)
        self.assertEqual(evidence.wavelength('F444W'),4.44)
        self.assertIsNone(evidence.wavelength('unknown'))
    def test_no_unmeasured_or_low_quality_content(self):
        self.assertFalse(evidence.validate({},None,{'score':99}))
        self.assertFalse(evidence.validate({}, {'sample_count':3000,'finite_fraction':1,'robust_scatter':1},{'score':0}))
