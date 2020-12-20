import csv

source = '/Users/derekwillis/code/openelections-sources-ny/2020/Rockland NY GE 2020 EL30.txt'
offices = ['REGISTERED VOTERS - TOTAL', 'BALLOTS CAST - TOTAL', 'BALLOTS CAST - BLANK', 'Presidential Electors for President and Vice President',
    'Justice of the Supreme Court 9th Judicial District', 'Representative in Congress', 'State Senator 38th Senatorial District',
    'Member of Assembly 96th Assembly District', 'County Clerk', 'Referendum - Palisades Mall Clarkstown', 'State Senator 39th Senatorial District',
    'Town Justice Haverstraw', 'Village Trustee Village of Haverstraw', 'Member of Assembly 97th Assembly District', 'Village Trustee Village of Nyack',
    'Member of Assembly 98th Assembly District', 'Mayor Village of Sloatsburg', 'Village Trustee Village of Sloatsburg', 'Village Trustee Village of Suffern',
    'Village Justice Village of Sloatsburg', 'Village Trustee Village of Piermont', 'Village Justice Village of West Haverstraw', 'Village Trustee Village of South Nyack',
    'Village Justice Village of South Nyack', 'Member of Assembly 99th Assembly District'
]

lines = open(source).readlines()
results = []

for line in lines:
    print(line)
    if line.strip()[0] == '0':
        precinct = line.strip()
    elif 'VOTE FOR' in line:
        continue
    elif any(o in line for o in offices):
        office = line.strip()
    elif "REGISTERED VOTERS" in line:
        office = None
        candidate = "Registered Voters"
        party = None
        votes = line.split('\t')[1]
    elif "BALLOTS CAST" in line:
        office = None
        candidate = "Ballots Cast"
        party = None
        votes = line.split('\t')[1]
    elif 'WRITE-IN' in line:
        candidate = 'Write-ins'
        party = None
        votes = line.split('\t')[1]
    elif 'Total' in line:
        continue
    elif 'Over Votes' in line:
        candidate = 'Over Votes'
        party = None
        votes = line.split('\t')[1]
    elif 'Under Votes' in line:
        candidate = 'Under Votes'
        party = None
        votes = line.split('\t')[1]
    else:
        candidate = line.split('\t')[0]
        if candidate.strip() == 'YES' or candidate.strip() == 'NO':
            party = None
        else:
            candidate, party = candidate.split('(')
            candidate = candidate.strip()
            party = party.replace(')','')
        try:
            votes, pct = line.split('\t')[1:]
        except:
            votes = line.split('\t')[1:][0]
        results.append(['Rockland', precinct, office, None, party, candidate, votes.replace(',','').strip()])

with open('20201103__ny__general__rockland__precinct.csv', 'wt') as csvfile:
    w = csv.writer(csvfile)
    headers = ['county', 'precinct', 'office', 'district', 'party', 'candidate', 'votes', 'election_day', 'absentee', 'absentee2']
    w.writerow(headers)
    w.writerows(results)
