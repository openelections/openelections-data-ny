import csv
import sys

precinct_to_data = {}

other_vote_titles = ['Public Counter', 'Emergency', 'Absentee/Military', 'Federal', 'Affidavit']
all_actual_candidates = {
    'Democratic/President': ['Bernie Sanders', 'Hillary Clinton'],
    'Republican/President': ['Donald J. Trump', 'John R. Kasich', 'Ben Carson', 'Ted Cruz']
}

print('county,precinct,office,district,party,candidate,votes,public_counter_votes,emergency_votes,absentee_military_votes,federal_votes,affidavit_votes')
with open(sys.argv[1], 'rb') as csvfile:
  line = csv.reader(csvfile, delimiter=',', quotechar='"')
  line_number = 0
  for row in line:
    if line_number == 0:
      line_number += 1
      continue
    (ad, ed, county, _, _, party, office, _, _, candidate, votes) = row
    precinct = '%s/%s' % (ed, ad)
    data = precinct_to_data.get(precinct, {})
    data[candidate] = {}
    data[candidate]['county'] = county
    data[candidate]['party'] = party
    data[candidate]['office'] = office
    data[candidate]['votes'] = votes
    precinct_to_data[precinct] = data
    line_number += 1

for precinct in precinct_to_data:
  data = precinct_to_data[precinct]
  party = data[other_vote_titles[0]]['party']
  office = data[other_vote_titles[0]]['office']
  party_office = '%s/%s' % (party, office)
  actual_candidates = all_actual_candidates[party_office]
  for candidate in actual_candidates:
    candidate_data = data.get(candidate)
    votes = 0
    if candidate_data:
      votes = int(candidate_data['votes'])
    line = None
    for other_vote_title in other_vote_titles:
      other_vote_data = data[other_vote_title]
      if not line:
        county = other_vote_data['county']
        party = other_vote_data['party']
        office = other_vote_data['office']
        line = '%s,%s,%s,,%s,%s,%d' % (
          county, precinct, office, party, candidate, votes)
      line += ',' + other_vote_data['votes']
    print(line)

