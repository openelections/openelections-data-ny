import xlrd
import unicodecsv as csv

results = []

county = 'Oneida'

offices = [
    ('Governor', None, "/Users/dwillis/code/openelections-sources-ny/Oneida/Oneida governor lt gov  2014.xls", 2, 5),
    ('State Comptroller', None, "/Users/dwillis/code/openelections-sources-ny/Oneida/Oneida nystate comptroller  2014.xls", 3, 5),
    ('Attorney General', None, "/Users/dwillis/code/openelections-sources-ny/Oneida/Oneida nystate attorney general  2014.xls", 3, 5),
    ('U.S. House', '22', "/Users/dwillis/code/openelections-sources-ny/Oneida/Oneida USCONG 22 2014.xls", 3, 5),
    ('State Senate', '47', "/Users/dwillis/code/openelections-sources-ny/Oneida/Oneida SENATE47-2014.xls", 4, 6),
    ('State Senate', '53', "/Users/dwillis/code/openelections-sources-ny/Oneida/Oneida SENATE53-2014.xls", 4, 6),
    ('State Assembly', '101', "/Users/dwillis/code/openelections-sources-ny/Oneida/Oneida 101AD 2014.xls", 3, 5),
    ('State Assembly', '117', "/Users/dwillis/code/openelections-sources-ny/Oneida/Oneida 117AD 2014.xls", 3, 5),
    ('State Assembly', '118', "/Users/dwillis/code/openelections-sources-ny/Oneida/Oneida 118AD 2014.xls", 3, 5),
    ('State Assembly', '119', "/Users/dwillis/code/openelections-sources-ny/Oneida/Oneida 119AD 2014.xlsx", 3, 5),
    ('State Assembly', '121', "/Users/dwillis/code/openelections-sources-ny/Oneida/Oneida 121AD 2014.xls", 4, 6),
]

for office, district, url, cand_row, party_row in offices:
    workbook = xlrd.open_workbook(url)
    sheets = workbook.sheets()[1:-1]

    for sheet in sheets:
        ward = ''
        candidates = ['Ballots Cast']+[x.replace('/','').title() for x in sheet.row_values(cand_row)[3:-1] if x != '']+['Blanks', 'Write-ins']
        parties = [None]+[x for x in sheet.row_values(party_row)[3:-1] if x not in ['TVC', 'BLK', 'WTN']]+[None, None]
        for row in range(6, sheet.nrows):
            if sheet.row_values(row)[1] == 'District':
                precinct_prefix = sheet.row_values(row)[0]
            elif str(sheet.row_values(row)[1]) == '' or 'Totals' in str(sheet.row_values(row)[1]) or str(sheet.row_values(row)[2]) == '':
                next
            elif 'Ward' in sheet.row_values(row)[0]:
                ward = sheet.row_values(row)[0].replace('ard ','')
                precinct = precinct_prefix + ' '+ ward + 'D' + str(sheet.row_values(row)[1]).replace('.0','')
                row_results = zip(candidates, parties, sheet.row_values(row)[2:])
                for candidate, party, votes in row_results:
                    results.append([county, precinct, office, district, party, candidate, votes])
            else:
                precinct = precinct_prefix + ' '+ ward + 'D' + str(sheet.row_values(row)[1]).replace('.0','')
                row_results = zip(candidates, parties, sheet.row_values(row)[2:])
                for candidate, party, votes in row_results:
                    results.append([county, precinct, office, district, party, candidate, votes])

with open("2014/20141104__ny__general__oneida__precinct.csv", 'wb') as csvfile:
    csvwriter = csv.writer(csvfile, encoding='utf-8')
    csvwriter.writerow(['county','precinct','office','district','party','candidate','votes'])
    csvwriter.writerows(results)
