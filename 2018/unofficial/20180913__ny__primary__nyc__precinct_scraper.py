'''
Author: Will Adler, will@wtadler.com

Scrapes NYC Board of Elections site, as of noon, 9/14/2018.
'''


import pandas as pd
import requests
import numpy as np
from bs4 import BeautifulSoup as bs

base_url = 'https://enrweb.boenyc.us/'
counties = ['New York', 'Bronx', 'Kings', 'Queens', 'Richmond']

def soup(url):
    page_response = requests.get(base_url + url)
    return bs(page_response.content, 'html.parser')

page_content = soup('index.html')
tb = page_content.find_all('table')[0]

rows = [row for row in tb.find_all('tr')]


# find links for each office
urls = pd.DataFrame()
for row in rows:
    if len(row.find_all('td', {'width': '450'})) != 0:
        office = row.find_all('td', {'width': '450'})[0].text
        party = row.find_all('td', {'width': '250'})[0].text
        details_url = row.find_all('td', {'width': '150'})[0].find_all('a')[0]['href']
        
        urls = urls.append({'office': office,
                            'party': party,
                            'details_url': details_url},
                           ignore_index=True)

        urls.drop_duplicates(inplace=True)
        urls.reset_index(drop=True, inplace=True)


def scrape_boroughs(page_content):
    # use this on the first page to break results down by borough
    results = pd.DataFrame()
        
    boro_links = [{'name': a['title'], 'url': a['href']} for a in page_content.find_all('a') if a['title'] in counties]
    
    for boro in boro_links:
        page_content = soup(boro['url'])
        
        ADs = [{'name': a['title'], 'url': a['href']} for a in page_content.find_all('a')[2:]]

        for AD in ADs:
            page_content = soup(AD['url'])
            
            table = pd.read_html(str(page_content.find_all('table', {'class': 'underline'})[0]), header=0)[0][1:-1]
            table.rename(columns={'Unnamed: 0': 'ED'}, inplace=True)
            table.drop(table.filter(regex='Unnamed').columns, axis=1, inplace=True)
            table['AD'] = AD['name']
            table['county'] = boro['name']
            
            results = results.append(table)
            
    return results

all_results = pd.DataFrame()

# for each office
for _, race in urls.iterrows():
    page_content = soup(race['details_url'])
    
    results = scrape_boroughs(page_content)
    
    # if it's the borough page
    if len(results) > 0:
        results['office'] = race['office']
        results['party'] = race['party']
        all_results = all_results.append(results, sort=False, ignore_index=True)
        
    # if not, dig one level deeper
    elif len(results) == 0:
        subraces = [{'name': a['title'], 'url': a['href']} for a in page_content.find_all('a')[2:]]
        for subrace in subraces:
            page_content = soup(subrace['url'])
            results = scrape_boroughs(page_content)
            results['office'] = race['office']
            results['party'] = race['party']
            results['district'] = subrace['name']
            all_results = all_results.append(results, sort=False, ignore_index=True)

# clean up, melt, sort, save
all_results.rename(columns={'ED': 'election district', 'AD': 'assembly district'}, inplace=True)

def digits(x):
    if x == x:
        return ''.join([i for i in x if i.isdigit()])
    else:
        return x

all_results['election district'] = all_results['election district'].apply(digits)
all_results['assembly district'] = all_results['assembly district'].apply(digits)
all_results['district'] = all_results['district'].apply(digits)

cols = ['party', 'office', 'county', 'assembly district', 'election district', 'district']

reordered_cols = cols + [i for i in all_results.columns if i not in cols]

all_results = all_results[cols + [i for i in all_results.columns if i not in cols]]

melted = all_results.melt(id_vars=['party', 'office', 'county', 'assembly district', 'election district', 'district'], var_name='candidate', value_name='votes')

melted = melted[~melted['votes'].isna()]
melted.loc[melted['votes']=='-', 'votes'] = 0

melted = melted.sort_values(['party', 'office', 'county', 'assembly district', 'election district', 'district', 'candidate'])

melted.to_csv('20180913_nyc_unofficial_primary.csv', index=False)
