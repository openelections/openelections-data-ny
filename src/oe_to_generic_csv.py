#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

# The MIT License (MIT)
# Copyright (c) 2017 Nick Kocharhook
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all 
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE 
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE 
# SOFTWARE.

import csv
import sys
import os
import argparse
import pandas


def main():
	args = parseArguments()

	builder = CSVBuilder(args.path)
	builder.build()
	builder.printCSV()


class CSVBuilder(object):
	def __init__(self, path):
		self.path = path
		self.outResults = []

		self.populateResults()

	def populateResults(self):
		self.oeResults = pandas.read_csv(self.path).fillna('')
		self.oeResults[['votes']] = self.oeResults[['votes']].apply(pandas.to_numeric)
		self.oeResults['precinct'] = self.oeResults['precinct'].astype(str)

	def build(self):
		officeDistrictSortColumns = ['office', 'district']
		grouped_offices = self.oeResults.groupby(officeDistrictSortColumns)
		gb_groups = grouped_offices.groups

		for officeDistrictTuple, officeDistrictIndexes in gb_groups.items():
			self.outResults.append(self.buildHeader(officeDistrictTuple))

			officeDistrictData = self.oeResults.ix[officeDistrictIndexes]
			grouped_precincts = officeDistrictData.groupby(['precinct'])
			gb_precincts = grouped_precincts.groups

			for precinct, precinctIndexes in gb_precincts.items():
				data = self.oeResults.ix[precinctIndexes]
				# print(type(data))
				resultLine = ['', precinct]
				
				for index, row in data.iterrows():
					# print(row)
					resultLine.append(row.votes)

				self.outResults.append(resultLine)

	def buildHeader(self, officeDistrictTuple):
		header = []

		# 1. Create the office/district name
		officeName = f"{officeDistrictTuple[0]}"

		if officeDistrictTuple[1]:
			officeName += " DIST {}".format(int(officeDistrictTuple[1]))

		header.append(officeName)

		# 2. Precinct
		header.append('Precinct')

		# 3. Candidates

		
		return header

	def printCSV(self):
		stdout_writer = csv.writer(sys.stdout, lineterminator='\n')
		for line in self.outResults:
			stdout_writer.writerow(line)



def parseArguments():
	parser = argparse.ArgumentParser(description='Verify votes are correct using a simple checksum')
	# parser.add_argument('--verbose', '-v', dest='verbose', action='store_true')
	# parser.add_argument('--excludeOverUnder', dest='excludeOverUnder', action='store_true')
	# parser.add_argument('--singleError', dest='singleError', action='store_true', help='Display only the first error in each file')
	parser.add_argument('path', type=str, help='path to a CSV file')
	parser.set_defaults(verbose=False)

	# By default, the script will assume the file is a general, --general doesn't have to be specified (but can be).
	# If multiple arguments are passed, the last one wins.
	parser.add_argument('--primary', action='store_false', dest='isGeneral', help='Process the file as a primary (parties per office).')
	parser.add_argument('--general', action='store_true', dest='isGeneral', help='Process the file as a general (parties per candidate). This is the default.')

	return parser.parse_args()


# Default function is main()
if __name__ == '__main__':
	main()