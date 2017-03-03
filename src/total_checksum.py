#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

# The MIT License (MIT)
# Copyright (c) 2016 Nick Kocharhook
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
import os
import argparse
import pandas


def main():
	args = parseArguments()

	checker = TotalChecker(args.path, args.excludeOverUnder)
	checker.singleError = args.singleError

	sortColumns = ['office', 'district']

	if not args.isGeneral:
		sortColumns += ['party']

	# Candidate total
	checkedCandidateTotals = checker.checkTotals('precinct', sortColumns + ['candidate'])

	# Precinct total
	checkedPrecinctTotals = checker.checkTotals('candidate', sortColumns + ['precinct'])

	if not checkedCandidateTotals and not checkedPrecinctTotals:
		print("No totals to check")


class TotalChecker(object):
	def __init__(self, path, excludeOverUnder):
		self.path = path
		self.singleError = False
		self.excludeOverUnder = excludeOverUnder

		print("==> {}".format(os.path.basename(path)))

		self.populateResults()

	def populateResults(self):
		self.results = pandas.read_csv(self.path).fillna('')
		self.results[['votes']] = self.results[['votes']].apply(pandas.to_numeric)
		self.results['precinct'] = self.results['precinct'].astype(str)

		if self.excludeOverUnder:
			self.results = self.results[(self.results.candidate != 'Over Votes') & 
										(self.results.candidate != 'Under Votes')]

		self.results_sans_totals = self.results.loc[(self.results.candidate != 'Total') & (self.results.precinct != 'Total')]


	def checkTotals(self, totalColumn, columns):
		contests = self.results.drop_duplicates(columns)[columns].values
		total_data = self.results.loc[self.results[totalColumn] == 'Total']
		
		if len(total_data):
			# Calculate our own totals to compare
			totals = self.results_sans_totals.groupby(columns).votes.sum()

			for index, row in total_data.iterrows():
				file_total = row.votes
				index_values = tuple(row[x] for x in columns)
				actual_total = totals.loc[index_values]

				if file_total != actual_total:
					lineNo = index + 2 # 1 for header, 1 for zero-indexing
					print("ERROR: {} total incorrect, line {}. {} != {}".format(
						"precinct" if totalColumn == "candidate" else "candidate",
						lineNo, file_total, actual_total))
					print(row.to_dict())

					if self.singleError:
						break

			return True

		return False

def parseArguments():
	parser = argparse.ArgumentParser(description='Verify votes are correct using a simple checksum')
	parser.add_argument('--verbose', '-v', dest='verbose', action='store_true')
	parser.add_argument('--excludeOverUnder', dest='excludeOverUnder', action='store_true')
	parser.add_argument('--singleError', dest='singleError', action='store_true', help='Display only the first error in each file')
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