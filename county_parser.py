import re
import csv

results = []

with open("2013GeneralElection-AD.txt", "rU") as csvfile:
    reader = csv.reader(csvfile, delimiter='\t')
    for row in reader:
        print row
        if row == []:
            continue
        if row[0].strip() == 'NYS Board of Elections Representative in Congress':
            continue
        if row[0] == '#REF!':
            continue
        if 'Assembly District' in row[0]:
            office = 'State House'
            district = int(re.search(r'\d+', row[0]).group())
            continue
#        if row[1] == '':
#            continue
        if row[0] == 'RECAP':
            continue
        if any(party in row[1] for party in ['DEM', 'REP','CON']):
            parties = row[1:]
            candidates = zip(candidates, parties)
            continue
        if row[0] == '' and row[1] != '':
            first_names = row[1:]
            continue
        if row[0] == 'County':
            last_names = row[1:]
            candidates = zip(first_names, last_names)
            candidates.append(['Blank', 'Void', 'Scattering', 'Total'])
            candidates = [c[0] + ' ' + c[1] for c in candidates if c[1]]
            continue
        else:
            print row
            county = row[0].replace("Part of ", "")
            votes = row[1:]
            candidates_with_votes = zip(candidates, votes)
            for candidate in candidates_with_votes:
                if candidate[0][0] == 'Blank Void':
                    continue
                results.append([county, office, district, candidate[0][1].strip(), candidate[0][0].strip(), candidate[1].replace(',','')])

with open("2012_primary.csv", "wb") as csv_outfile:
    outfile = csv.writer(csv_outfile)
    outfile.writerow(['county', 'office', 'district', 'party', 'candidate', 'votes'])
    outfile.writerows(results)
