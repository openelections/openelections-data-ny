import re
import csv

results = []

with open("2014AttorneyGeneral.csv", "rU") as csvfile:
    reader = csv.reader(csvfile)
    office = 'Attorney General'
    district = None
    for row in reader:
        if row[0].strip() == 'NYS Board of Elections Comptroller Election Returns November 4, 2014':
            continue
        if row[0] == 'Revised:  4/3/2015':
            continue
        if row[1] == '':
            continue
        if row[0] == 'RECAP':
            continue
        if any(party in row[1] for party in ['DEM', 'REP']):
            parties = row[1:]
            candidates = zip(candidates, parties)
            continue
        if row[0] == 'County':
            candidates = row[1:] + ['Blank', 'Void', 'Scattering', 'Total']
            continue
        else:
            print row
            county = row[0].strip()
            votes = row[1:]
            candidates_with_votes = zip(candidates, votes)
            for candidate in candidates_with_votes:
                if candidate[0][0] == 'Blank Void':
                    continue
                if candidate[0][0] == '':
                    continue
                if candidate[0][0] == "County":
                    continue
                results.append([county, office, district, candidate[0][1].strip(), candidate[0][0].strip(), candidate[1].replace(',','')])

with open("20141104__ny__general_ag.csv", "wb") as csv_outfile:
    outfile = csv.writer(csv_outfile)
    outfile.writerow(['county', 'office', 'district', 'party', 'candidate', 'votes'])
    outfile.writerows(results)
