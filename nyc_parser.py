import argparse
import csv
import re
import sys

arg_parser = argparse.ArgumentParser(description='Parse nyc voting csv\'s.')
arg_parser.add_argument('csvfilepath', type=str, nargs=1)
arg_parser.add_argument('--print_header', type=bool, default=False)

args = arg_parser.parse_args()

precinct_to_data = {}

other_vote_titles = ['Public Counter', 'Emergency', 'Absentee/Military', 'Federal', 'Affidavit', 'Scattered', 'Manually Counted Emergency', 'Special Presidential']

office_mapping = {
  'United States Senator': 'U.S. Senate',
  'Representative in Congress': 'U.S. House',
  'State Senator': 'State Senate',
  'Member of the Assembly': 'State Assembly',
  'President/Vice President': 'President'
}

if args.print_header:
    print('county,precinct,office,district,party,candidate,votes,public_counter_votes,emergency_votes,absentee_military_votes,federal_votes,affidavit_votes,manually_counted_emergency,special_presidential')
with open(args.csvfilepath[0], 'rb') as csvfile:
  line = csv.reader(csvfile, delimiter=',', quotechar='"')
  line_number = 0
  for row in line:
    if line_number == 0:
      line_number += 1
      continue
    (ad, ed, county, edad_status, _, party, office, district, _, candidate, votes) = row
    if not party:
      match = re.search('^(.*) \((.*)\)$', candidate)
      if match:
        party = match.group(2)
    precinct = '%s/%s' % (ed, ad)
    data = precinct_to_data.get(precinct, {})
    data[candidate] = {}
    data[candidate]['county'] = county
    data[candidate]['party'] = party
    data[candidate]['office'] = office
    data[candidate]['district'] = district
    data[candidate]['votes'] = votes
    data[candidate]['status'] = edad_status
    precinct_to_data[precinct] = data
    line_number += 1

def print_precinct(precinct, data):
  actual_candidates = set(data.keys()) - set(other_vote_titles)
  for candidate in actual_candidates:
    candidate_data = data.get(candidate)
    votes = 0
    line = None
    if candidate_data:
      match = re.search('^(.*) \((.*)\)$', candidate)
      if match:
        candidate = match.group(1)
      votes = int(candidate_data['votes'].replace(',', ''))
      county = candidate_data['county']
      party = candidate_data['party']
      office = candidate_data['office']
      if office in office_mapping:
        office = office_mapping[office];
      district = candidate_data['district']
      if not district.isdigit():
        district = ''
      else:
        district = int(district)
      line = '%s,%s,%s,%s,%s,%s,%d' % (
        county, precinct, office, district, party, candidate, votes)

    if not line:
      datum = (data.values())[0]
      county = datum['county']
      party = datum['party']
      office = datum['office']
      if office in office_mapping:
        office = office_mapping[office];
      district = datum['district']
      if not district.isdigit():
        district = ''
      else:
        district = int(district)
      line = '%s,%s,%s,%s,%s,%s,%d' % (
        county, precinct, office, district, party, candidate, votes)

    for other_vote_title in other_vote_titles:
      other_vote_data = data.get(other_vote_title)
      if other_vote_data:
        line += ',' + other_vote_data['votes']
      else:
        line += ','
    print(line)

for precinct in precinct_to_data:
  data = precinct_to_data[precinct]
  status = data[other_vote_titles[0]]['status']
  if status == 'IN-PLAY':
    print_precinct(precinct, data)

