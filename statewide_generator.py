import os
import glob
import csv

year = '2022'
election = '20221108'
path = 'counties/'+election+'*precinct.csv'
output_file = f"{election}__ny__general__precinct.csv"

def generate_headers(year, path):
    os.chdir(year)
    os.chdir('counties')
    vote_headers = []
    for fname in glob.glob(path):
        with open(fname, "r") as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader)
            print(list(fname + ': ' + h for h in headers if h not in ['county','precinct', 'office', 'district', 'candidate', 'party', 'votes']))
            #vote_headers.append(h for h in headers if h not in ['county','precinct', 'office', 'district', 'candidate', 'party'])
#    with open('vote_headers.csv', "w") as csv_outfile:
#        outfile = csv.writer(csv_outfile)
#        outfile.writerows(vote_headers)

def generate_offices(year, path):
    os.chdir(year)
    os.chdir('counties')
    offices = []
    for fname in glob.glob(path):
        with open(fname, "r") as csvfile:
            print(fname)
            reader = csv.DictReader(csvfile)
            for row in reader:
                if not row['office'] in offices:
                    offices.append(row['office'])
    with open('../../offices.csv', "w") as csv_outfile:
        outfile = csv.writer(csv_outfile)
        outfile.writerows(offices)

def generate_consolidated_file(year, path, output_file):
    results = []
    os.chdir(year)
    os.chdir('counties')
    for fname in glob.glob(path):
        print(fname)
        with open(fname, "r") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['office'].strip() in ['Registered Voters', 'Ballots Cast', 'Ballots Cast Blank', 'President', 'U.S. Senate', 'U.S. House', 'Governor', 'Comptroller', 'Attorney General', 'State Senate', 'State Assembly']:
                    if 'election_day' in row:
                        election_day = row['election_day']
                    else:
                        election_day = None
                    if 'early' in row:
                        early_voting = row['early_voting']
                    else:
                        early_voting = None
                    if 'tally' in row:
                        hand_tally = row['hand_tally']
                    else:
                        hand_tally = None
                    if 'federal' in row:
                        federal = row['federal']
                    else:
                        federal = None
                    if 'absentee' in row:
                        absentee = row['absentee']
                    else:
                        absentee = None
                    if 'military' in row:
                        military = row['military']
                    else:
                        military = None
                    if 'affidavit' in row:
                        affidavit = row['affidavit']
                    else:
                        affidavit = None
                    results.append([row['county'], row['precinct'], row['office'], row['district'], row['candidate'], row['party'], row['votes'], early_voting, election_day, absentee, military, federal, affidavit, hand_tally])

    os.chdir('..')
    with open(output_file, "w") as csv_outfile:
        outfile = csv.writer(csv_outfile)
        outfile.writerow(['county','precinct', 'office', 'district', 'candidate', 'party', 'votes', 'early_voting', 'election_day', 'absentee', 'military', 'federal', 'affidavit', 'hand_tally'])
        outfile.writerows(results)
