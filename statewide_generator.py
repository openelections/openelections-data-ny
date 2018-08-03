import os
import glob
import csv

year = '2016'
election = '20161108'
path = 'counties/'+election+'*precinct.csv'
output_file = election+'__ny__general__precinct.csv'

def generate_headers(year, path):
    os.chdir(year)
    vote_headers = []
    for fname in glob.glob(path):
        with open(fname, "r") as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader)
            print(list(fname + ': ' + h for h in headers if h not in ['county','precinct', 'office', 'district', 'candidate', 'party']))
            #vote_headers.append(h for h in headers if h not in ['county','precinct', 'office', 'district', 'candidate', 'party'])
#    with open('vote_headers.csv', "w") as csv_outfile:
#        outfile = csv.writer(csv_outfile)
#        outfile.writerows(vote_headers)

def generate_offices(year, path):
    os.chdir(year)
    offices = []
    for fname in glob.glob(path):
        with open(fname, "r") as csvfile:
            print(fname)
            reader = csv.DictReader(csvfile)
            for row in reader:
                if not row['office'] in offices:
                    offices.append(row['office'])
    with open('offices.csv', "w") as csv_outfile:
        outfile = csv.writer(csv_outfile)
        outfile.writerows(offices)

def generate_consolidated_file(year, path, output_file):
    results = []
    os.chdir(year)
    for fname in glob.glob(path):
        with open(fname, "rU") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['office'].strip() in ['President', 'U.S. Senate', 'U.S. House', 'State Senate', 'State Assembly']:
                    if 'election_day' in row:
                        election_day = row['election_day']
                    else:
                        election_day = None
                    if 'absentee_hc' in row:
                        absentee_hc = row['absentee_hc']
                    else:
                        absentee_hc = None
                    if 'absentee' in row:
                        absentee = row['absentee']
                    else:
                        absentee = None
                    if 'machine_votes' in row:
                        machine_votes = row['machine_votes']
                    else:
                        machine_votes = None
                    if 'affidavit' in row:
                        affidavit = row['affidavit']
                    else:
                        affidavit = None
                    results.append([row['county'], row['precinct'], row['office'], row['district'], row['candidate'], row['party'], row['votes'], election_day, absentee, machine_votes, absentee_hc, affidavit])

    with open(output_file, "w") as csv_outfile:
        outfile = csv.writer(csv_outfile)
        outfile.writerow(['county','precinct', 'office', 'district', 'candidate', 'party', 'votes', 'election_day', 'absentee', 'machine_votes', 'absentee_hc', 'affidavit'])
        outfile.writerows(results)
