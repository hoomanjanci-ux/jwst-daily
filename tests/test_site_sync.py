import sys
from pathlib import Path
import unittest
from unittest.mock import Mock
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pipeline'))
import verify_site

class SiteSyncTests(unittest.TestCase):
    def test_expected_routes_and_sitemap_are_checked(self):
        get=Mock(side_effect=[Mock(text='x'*200),Mock(text='x'*200),Mock(text='/post/fresh-analysis')])
        verify_site.verify('https://example.test',{'analyses':[
            {'slug':'fresh-analysis','text_fa':'real text'}]},get)
        self.assertEqual(get.call_args_list[1].args[0],
                         'https://example.test/post/fresh-analysis')
    def test_successful_homepage_does_not_hide_missing_analysis(self):
        bad=Mock(text='not found');bad.raise_for_status.side_effect=requests.HTTPError('404')
        get=Mock(side_effect=[Mock(text='x'*200),bad])
        with self.assertRaises(requests.HTTPError):
            verify_site.verify('https://example.test',{'analyses':[
                {'slug':'missing','text_fa':'text'}]},get)
    def test_stale_sitemap_is_failure(self):
        get=Mock(side_effect=[Mock(text='x'*200),Mock(text='x'*200),Mock(text='old sitemap')])
        with self.assertRaises(RuntimeError):
            verify_site.verify('https://example.test',{'analyses':[
                {'slug':'fresh','text_en':'text'}]},get)
