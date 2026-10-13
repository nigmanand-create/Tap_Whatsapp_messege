import unittest

from tap_buddy.wgas.excel_utils import map_headers, split_groups


class TestWGASExcel(unittest.TestCase):
	def test_header_mapping(self):
		headers = map_headers(["Date", "Time", "WhatsApp Groups", "Message", "Flow"])
		self.assertEqual(headers["date"], 0)
		self.assertEqual(headers["time"], 1)
		self.assertEqual(headers["groups"], 2)
		self.assertEqual(headers["message"], 3)
		self.assertEqual(headers["flow"], 4)

	def test_split_groups(self):
		self.assertEqual(split_groups("A, B;C|D"), ["A", "B", "C", "D"])
