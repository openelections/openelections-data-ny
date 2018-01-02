library(tabulizer)
library(tidyverse)
library(pdftools)

fileName <- '/opt/data/openelections/2014-PUTNAM NY GENERAL-ELECTION-CERTIFIED.pdf'
dfs <- list()

convertToDataFrame <- function(rdfm, officeValue, districtValue=NA_character_, partyFunction=function(candidate) NA_character_) {
  as_data_frame(rdfm) %>% select(-starts_with('X')) %>%
    gather(key='candidate', value='votes', -precinct) %>%
    mutate(county='Putnam', district=districtValue, party=partyFunction(candidate), office=officeValue) %>%
    filter(precinct != 'TOTAL') %>% mutate(votes=as.integer(votes))
}

makeX <- function(i) {
  paste0('X', as.character(i))
}

office <- 'State Proposal #1'
rdfm <- extract_tables(fileName, pages=1:4)
rdf <- map_df(rdfm[1:6], function(rdfm) {
  colnames(rdfm) <- c('precinct', makeX(1:6), 'yes', 'no', makeX(7:8))
  convertToDataFrame(rdfm, office)
})

dfs <- c(dfs, setNames(list(rdf), office))

office <- 'State Proposal #2'
rdfm <- extract_tables(fileName, pages=5:8)
rdf <- map_df(rdfm[1:6], function(rdfm) {
  colnames(rdfm) <- c('precinct', makeX(1:6), 'yes', 'no', makeX(7:8))
  convertToDataFrame(rdfm, office)
})

dfs <- c(dfs, setNames(list(rdf), office))

rdfs <- list()
office <- 'State Proposal #3'
rdfm <- extract_tables(fileName, pages=9:12)
rdfmm <- rdfm[[1]]
colnames(rdfmm) <- c('precinct', makeX(1:5), 'yes', 'X6', 'no', makeX(7:8))
rdf <- as_data_frame(rdfmm) %>% .[-7,] %>%
  bind_rows(tibble(precinct='CA 07', yes='174', no='134')) %>%
  bind_rows(tibble(precinct='CA 08', yes='187', no='129')) %>% as.matrix() %>%
  convertToDataFrame(office)
rdfs <- c(rdfs, list(rdf))
rdfmm <- rdfm[[2]]
colnames(rdfmm) <- c(makeX(1:2), 'precinct', makeX(3:9), 'yes', 'no', makeX(12:13))
rdf <- as_data_frame(rdfmm) %>% .[-12,] %>%
  bind_rows(tibble(precinct='KE 12', yes='105', no='114')) %>% as.matrix() %>%
  convertToDataFrame(office)
rdfs <- c(rdfs, list(rdf))
rdfmm <- rdfm[[3]]
colnames(rdfmm) <- c(makeX(1:4), 'precinct', makeX(6:15), 'yes', 'no', makeX(18:19))
rdf <- as_data_frame(rdfmm) %>%
  filter(precinct != '') %>%
  convertToDataFrame(office) %>%
  mutate(precinct=paste0('PA ', precinct))
rdfs <- c(rdfs, list(rdf))
rdfmm <- rdfm[[4]]
colnames(rdfmm) <- c(makeX(1:2), 'precinct', makeX(4:9), 'yes', 'no', makeX(12:13))
rdf <- as_data_frame(rdfmm) %>% .[-c(9,11),] %>%
  bind_rows(tibble(precinct='PH 09', yes='170', no='106')) %>%
  bind_rows(tibble(precinct='PH 10', yes='120', no='73')) %>% as.matrix() %>%
  convertToDataFrame(office)
rdfs <- c(rdfs, list(rdf))
rdfmm <- rdfm[[5]]
colnames(rdfmm) <- c(makeX(1:3), 'precinct', makeX(5:17), 'yes', 'X19', 'no', makeX(21:24))
rdf5 <- as_data_frame(rdfmm) %>% .[-c(1),] %>%
  filter(precinct != '') %>%
  bind_rows(tibble(precinct='01', yes='208', no='116')) %>%
  bind_rows(tibble(precinct='02', yes='212', no='131')) %>% as.matrix() %>%
  convertToDataFrame(office) %>%
  mutate(precinct=paste0('PV ', precinct))
rdfs <- c(rdfs, list(rdf))
rdfmm <- rdfm[[6]]
colnames(rdfmm) <- c('precinct', makeX(2:7), 'yes', 'no', makeX(10:11))
rdf <- as_data_frame(rdfmm) %>% .[-c(4,7,9),] %>%
  filter(precinct != '') %>%
  bind_rows(tibble(precinct='SE 04', yes='123', no='107')) %>%
  bind_rows(tibble(precinct='SE 05', yes='86', no='88')) %>%
  bind_rows(tibble(precinct='SE 06', yes='161', no='107')) %>%
  bind_rows(tibble(precinct='SE 09', yes='170', no='125')) %>%
  bind_rows(tibble(precinct='SE 10', yes='216', no='141')) %>%
  bind_rows(tibble(precinct='SE 12', yes='136', no='93')) %>%
  bind_rows(tibble(precinct='SE 13', yes='95', no='89')) %>%
  as.matrix() %>%
  convertToDataFrame(office)
rdfs <- c(rdfs, list(rdf))

dfs <- c(dfs, setNames(list(bind_rows(rdfs)), office))

pdfText <- pdf_text(fileName)

createTibbleFromPageLines <- function(page) {
  lines <- read_lines(page)
  lines <- lines[grepl(x=lines, pattern='^CA |^PA |^KE |^PH |^PV |^SE ')]
  if (length(lines) == 1) {
    read_delim(paste0(gsub(x=lines, pattern=' [ ]*', replacement=' '), '\n'), delim=' ', col_names = FALSE)
  } else  if (length(lines) > 0) {
    read_delim(paste0(gsub(x=lines, pattern=' [ ]*', replacement=' '), collapse='\n'), delim=' ', col_names = FALSE)
  } else {
    tibble()
  }
}

# from here on, we used pdftools, as tabulizer did not seem to find the second table on a page when there were two (many pages)...

office <- 'Governor'
rdf <- map_df(pdfText[13:16], createTibbleFromPageLines)

colnames(rdf) <- c('X10', 'X11', 'Machine', 'Absentee', 'Turnout', 'Voter Registration', 'X1',
                   'Cuomo1', 'Astorino1', 'Astorino2', 'Cuomo2', 'Cuomo3', 'Hawkins', 'Cuomo4', 'Cohn', 'Astorino3',
                   'McDermott', 'Write-In', 'X2', 'X3')

rdf <- rdf %>%
  mutate(precinct=paste(X10, X11)) %>%
  select(-starts_with('X')) %>%
  gather(key='candidate', value='votes', -precinct) %>%
  mutate(votes=gsub(x=votes, pattern='[ ,]', replacement='')) %>%
  mutate(county='Putnam', district=NA_character_, office=office) %>%
  mutate(precinct=gsub(x=precinct, pattern='\r', replacement=' ')) %>%
  mutate(votes=as.integer(votes)) %>%
  mutate(party=case_when(
    candidate=='Cuomo1' ~ 'Democratic',
    candidate=='Cuomo2' ~ 'Working Families',
    candidate=='Cuomo3' ~ 'Independent',
    candidate=='Cuomo4' ~ 'Womens Equality',
    candidate=='Astorino1' ~ 'Republican',
    candidate=='Astorino2' ~ 'Constitution',
    candidate=='Astorino3' ~ 'Stop Common Core',
    candidate=='Hawkins' ~ 'Green',
    candidate=='Cohn' ~ 'Sapient',
    candidate=='McDermott' ~ 'Libertarian',
    TRUE ~ NA_character_
  )) %>%
  mutate(candidate=case_when(
    startsWith(candidate, 'Cuomo') ~ 'Andrew M. Cuomo / Kathy C. Hochul',
    startsWith(candidate, 'Astorino') ~ 'Rob Astorino / Chris Moss',
    candidate=='Hawkins' ~ 'Howie Hawkins / Brian P. Jones',
    candidate=='Cohn' ~ 'Steven Cohn / Bobby K. Kalotee',
    candidate=='McDermott' ~ 'Michael McDermott / Chris Edes',
    candidate=='Machine' ~ 'Machine Turnout',
    candidate=='Absentee' ~ 'Absentee Turnout',
    candidate=='Turnout' ~ 'Total Turnout',
    TRUE ~ candidate
  ))

rdfs <- c(rdfs, list(rdf))

office <- 'Comptroller'
rdf <- map_df(pdfText[17:20], createTibbleFromPageLines)

colnames(rdf) <- c('X10', 'X11', makeX(1:5),
                   'Dinapoli1', 'Antonacci1', 'Antonacci2', 'Dinapoli2', 'Dinapoli3', 'Portelli', 'Clifton',
                   'Write-In', 'X6', 'X7')

rdf <- rdf %>%
  mutate(precinct=paste(X10, X11)) %>%
  select(-starts_with('X')) %>%
  gather(key='candidate', value='votes', -precinct) %>%
  mutate(votes=gsub(x=votes, pattern='[ ,]', replacement='')) %>%
  mutate(county='Putnam', district=NA_character_, office=office) %>%
  mutate(precinct=gsub(x=precinct, pattern='\r', replacement=' ')) %>%
  mutate(votes=as.integer(votes)) %>%
  mutate(party=case_when(
    candidate=='Dinapoli1' ~ 'Democratic',
    candidate=='Antonacci1' ~ 'Republican',
    candidate=='Antonacci2' ~ 'Constitution/Stop Common Core',
    candidate=='Dinapoli2' ~ 'Working Families',
    candidate=='Dinapoli3' ~ 'Independent/Womens Equality',
    candidate=='Portelli' ~ 'Green',
    candidate=='Clifton' ~ 'Libertarian',
    TRUE ~ NA_character_
  )) %>%
  mutate(candidate=case_when(
    startsWith(candidate, 'Dinapoli') ~ 'Thomas P. Dinapoli',
    startsWith(candidate, 'Antonacci') ~ 'Robert Antonacci',
    candidate=='Portelli' ~ 'Theresa M. Portelli',
    candidate=='Clifton' ~ 'John Clifton',
    TRUE ~ candidate
  ))

rdfs <- c(rdfs, list(rdf))

office <- 'Attorney General'
rdf <- map_df(pdfText[21:24], createTibbleFromPageLines)

colnames(rdf) <- c('X10', 'X11', makeX(1:5),
                   'Schneiderman1', 'Cahill1', 'Cahill2', 'Schneiderman2', 'Schneiderman3', 'Jiminez', 'Person',
                   'Write-In', 'X6', 'X7')

rdf <- rdf %>%
  mutate(precinct=paste(X10, X11)) %>%
  select(-starts_with('X')) %>%
  gather(key='candidate', value='votes', -precinct) %>%
  mutate(votes=gsub(x=votes, pattern='[ ,]', replacement='')) %>%
  mutate(county='Putnam', district=NA_character_, office=office) %>%
  mutate(precinct=gsub(x=precinct, pattern='\r', replacement=' ')) %>%
  mutate(votes=as.integer(votes)) %>%
  mutate(party=case_when(
    candidate=='Schneiderman1' ~ 'Democratic',
    candidate=='Cahill1' ~ 'Republican',
    candidate=='Cahill2' ~ 'Constitution/Stop Common Core',
    candidate=='Schneiderman2' ~ 'Working Families',
    candidate=='Schneiderman3' ~ 'Independent/Womens Equality',
    candidate=='Jiminez' ~ 'Green',
    candidate=='Person' ~ 'Libertarian',
    TRUE ~ NA_character_
  )) %>%
  mutate(candidate=case_when(
    startsWith(candidate, 'Schneiderman') ~ 'Eric T. Schneiderman',
    startsWith(candidate, 'Cahill') ~ 'John Cahill',
    candidate=='Jiminez' ~ 'Ramon Jiminez',
    candidate=='Person' ~ 'Carl E. Person',
    TRUE ~ candidate
  ))

rdfs <- c(rdfs, list(rdf))

office <- 'Supreme Court Justice'
rdf <- map_df(pdfText[25:28], createTibbleFromPageLines)

colnames(rdf) <- c('X10', 'X11', makeX(1:5),
                   'Hubert1', 'Delaney1', 'Delaney2', 'Hubert2', 
                   'Write-In', 'X6', 'X7')

rdf <- rdf %>%
  mutate(precinct=paste(X10, X11)) %>%
  select(-starts_with('X')) %>%
  gather(key='candidate', value='votes', -precinct) %>%
  mutate(votes=gsub(x=votes, pattern='[ ,]', replacement='')) %>%
  mutate(county='Putnam', district='9th Judicial District', office=office) %>%
  mutate(precinct=gsub(x=precinct, pattern='\r', replacement=' ')) %>%
  mutate(votes=as.integer(votes)) %>%
  mutate(party=case_when(
    candidate=='Hubert1' ~ 'Democratic',
    candidate=='Delaney1' ~ 'Republican',
    candidate=='Delaney2' ~ 'Constitution',
    candidate=='Hubert2' ~ 'Independent',
    TRUE ~ NA_character_
  )) %>%
  mutate(candidate=case_when(
    startsWith(candidate, 'Hubert') ~ 'James W. Hubert',
    startsWith(candidate, 'Delaney') ~ 'Montgomery J. Delaney',
    TRUE ~ candidate
  ))

rdfs <- c(rdfs, list(rdf))

office <- 'U.S. House'
rdf <- map_df(pdfText[29:32], createTibbleFromPageLines)

colnames(rdf) <- c('X10', 'X11', makeX(1:5),
                   'Maloney1', 'Hayworth1', 'Hayworth2', 'Maloney2', 'Hayworth3', 'Smith',
                   'Write-In', 'X6', 'X7')

rdf <- rdf %>%
  mutate(precinct=paste(X10, X11)) %>%
  select(-starts_with('X')) %>%
  gather(key='candidate', value='votes', -precinct) %>%
  mutate(votes=gsub(x=votes, pattern='[ ,]', replacement='')) %>%
  mutate(county='Putnam', district='18', office=office) %>%
  mutate(precinct=gsub(x=precinct, pattern='\r', replacement=' ')) %>%
  mutate(votes=as.integer(votes)) %>%
  mutate(party=case_when(
    candidate=='Maloney1' ~ 'Democratic',
    candidate=='Hayworth1' ~ 'Republican',
    candidate=='Hayworth2' ~ 'Constitution',
    candidate=='Maloney2' ~ 'Working Families',
    candidate=='Hayworth3' ~ 'Independent',
    candidate=='Smith' ~ 'Send Mr. Smith',
    TRUE ~ NA_character_
  )) %>%
  mutate(candidate=case_when(
    startsWith(candidate, 'Maloney') ~ 'Sean Patrick Maloney',
    startsWith(candidate, 'Hayworth') ~ 'Nan Hayworth',
    startsWith(candidate, 'Smith') ~ 'Scott A. Smith',
    TRUE ~ candidate
  ))

rdfs <- c(rdfs, list(rdf))

office <- 'State Senate'
rdf <- map_df(pdfText[33:35], createTibbleFromPageLines)

colnames(rdf) <- c('X10', 'X11', makeX(1:5),
                   'Wagner1', 'Murphy1', 'Murphy2', 'Wagner2', 'Murphy3', 'Murphy4', 'Murphy5',
                   'Write-In', 'X6', 'X7')

rdf <- rdf %>%
  mutate(precinct=paste(X10, X11)) %>%
  select(-starts_with('X')) %>%
  gather(key='candidate', value='votes', -precinct) %>%
  mutate(votes=gsub(x=votes, pattern='[ ,]', replacement='')) %>%
  mutate(county='Putnam', district='40', office=office) %>%
  mutate(precinct=gsub(x=precinct, pattern='\r', replacement=' ')) %>%
  mutate(votes=as.integer(votes)) %>%
  mutate(party=case_when(
    candidate=='Wagner1' ~ 'Democratic',
    candidate=='Murphy1' ~ 'Republican',
    candidate=='Murphy2' ~ 'Constitution',
    candidate=='Wagner2' ~ 'Working Families',
    candidate=='Murphy3' ~ 'Independent',
    candidate=='Murphy4' ~ 'Green',
    candidate=='Murphy5' ~ 'Stop Common Core',
    TRUE ~ NA_character_
  )) %>%
  mutate(candidate=case_when(
    startsWith(candidate, 'Wagner') ~ 'Justin R. Wagner',
    startsWith(candidate, 'Murphy') ~ 'Terrence P. Murphy',
    TRUE ~ candidate
  ))

rdfs <- c(rdfs, list(rdf))

office <- 'State Senate'
rdf <- map_df(pdfText[36:38], createTibbleFromPageLines)

colnames(rdf) <- c('X10', 'X11', makeX(1:5),
                   'Gipson1', 'Serino1', 'Serino2', 'Gipson2', 'Serino3', 'Gipson3', 'Gipson4',
                   'Write-In', 'X6', 'X7')

rdf <- rdf %>%
  mutate(precinct=paste(X10, X11)) %>%
  select(-starts_with('X')) %>%
  gather(key='candidate', value='votes', -precinct) %>%
  mutate(votes=gsub(x=votes, pattern='[ ,]', replacement='')) %>%
  mutate(county='Putnam', district='41', office=office) %>%
  mutate(precinct=gsub(x=precinct, pattern='\r', replacement=' ')) %>%
  mutate(votes=as.integer(votes)) %>%
  mutate(party=case_when(
    candidate=='Gipson1' ~ 'Democratic',
    candidate=='Serino1' ~ 'Republican',
    candidate=='Serino2' ~ 'Constitution',
    candidate=='Gipson2' ~ 'Working Families',
    candidate=='Serino3' ~ 'Independent',
    candidate=='Gipson3' ~ 'Green',
    candidate=='Gipson4' ~ 'Tax Relief Now',
    TRUE ~ NA_character_
  )) %>%
  mutate(candidate=case_when(
    startsWith(candidate, 'Gipson') ~ 'Terry W. Gipson',
    startsWith(candidate, 'Serino') ~ 'Susan J. Serino',
    TRUE ~ candidate
  ))

rdfs <- c(rdfs, list(rdf))

office <- 'State Assembly'
rdf <- map_df(pdfText[39:42], createTibbleFromPageLines)

colnames(rdf) <- c('X10', 'X11', makeX(1:5),
                   'Falk1', 'Katz1', 'Katz2', 'Falk2',
                   'Write-In', 'X6', 'X7')

rdf <- rdf %>%
  mutate(precinct=paste(X10, X11)) %>%
  select(-starts_with('X')) %>%
  gather(key='candidate', value='votes', -precinct) %>%
  mutate(votes=gsub(x=votes, pattern='[ ,]', replacement='')) %>%
  mutate(county='Putnam', district='94', office=office) %>%
  mutate(precinct=gsub(x=precinct, pattern='\r', replacement=' ')) %>%
  mutate(votes=as.integer(votes)) %>%
  mutate(party=case_when(
    candidate=='Falk1' ~ 'Democratic',
    candidate=='Katz1' ~ 'Republican',
    candidate=='Katz2' ~ 'Constitution',
    candidate=='Falk2' ~ 'Working Families',
    TRUE ~ NA_character_
  )) %>%
  mutate(candidate=case_when(
    startsWith(candidate, 'Falk') ~ 'Andrew I. Falk',
    startsWith(candidate, 'Katz') ~ 'Stephen M. Katz',
    TRUE ~ candidate
  ))

rdfs <- c(rdfs, list(rdf))

office <- 'State Assembly'
rdf <- map_df(pdfText[43:44], createTibbleFromPageLines)

colnames(rdf) <- c('X10', 'X11', makeX(1:5),
                   'Galef1', 'Galef2', 'Galef3',
                   'Write-In', 'X6', 'X7')

rdf <- rdf %>%
  mutate(precinct=paste(X10, X11)) %>%
  select(-starts_with('X')) %>%
  gather(key='candidate', value='votes', -precinct) %>%
  mutate(votes=gsub(x=votes, pattern='[ ,]', replacement='')) %>%
  mutate(county='Putnam', district='95', office=office) %>%
  mutate(precinct=gsub(x=precinct, pattern='\r', replacement=' ')) %>%
  mutate(votes=as.integer(votes)) %>%
  mutate(party=case_when(
    candidate=='Galef1' ~ 'Democratic',
    candidate=='Galef2' ~ 'Working Families',
    candidate=='Galef3' ~ 'Independent',
    TRUE ~ NA_character_
  )) %>%
  mutate(candidate=case_when(
    startsWith(candidate, 'Galef') ~ 'Sandra R. Galef',
    TRUE ~ candidate
  ))

rdfs <- c(rdfs, list(rdf))

office <- 'County Executive'
rdf <- map_df(pdfText[45:48], createTibbleFromPageLines)

colnames(rdf) <- c('X10', 'X11', makeX(1:5),
                   'Oliverio', 'Odell1', 'Odell2', 'Odell3',
                   'Write-In', 'X6', 'X7')

rdf <- rdf %>%
  mutate(precinct=paste(X10, X11)) %>%
  select(-starts_with('X')) %>%
  gather(key='candidate', value='votes', -precinct) %>%
  mutate(votes=gsub(x=votes, pattern='[ ,]', replacement='')) %>%
  mutate(county='Putnam', district=NA_character_, office=office) %>%
  mutate(precinct=gsub(x=precinct, pattern='\r', replacement=' ')) %>%
  mutate(votes=as.integer(votes)) %>%
  mutate(party=case_when(
    candidate=='Oliverio' ~ 'Democratic',
    candidate=='Odell1' ~ 'Republican',
    candidate=='Odell2' ~ 'Constitution',
    candidate=='Odell3' ~ 'Independent',
    TRUE ~ NA_character_
  )) %>%
  mutate(candidate=case_when(
    startsWith(candidate, 'Oliverio') ~ 'Samuel J. Oliverio, Jr.',
    startsWith(candidate, 'Odell') ~ 'Maryellen Odell',
    TRUE ~ candidate
  ))

rdfs <- c(rdfs, list(rdf))

office <- 'County Clerk'
rdf <- map_df(pdfText[49:52], createTibbleFromPageLines)

colnames(rdf) <- c('X10', 'X11', makeX(1:5),
                   'Osborne1', 'Bartolotti1', 'Bartolotti2', 'Osborne2', 'Bartolotti3',
                   'Write-In', 'X6', 'X7')

rdf <- rdf %>%
  mutate(precinct=paste(X10, X11)) %>%
  select(-starts_with('X')) %>%
  gather(key='candidate', value='votes', -precinct) %>%
  mutate(votes=gsub(x=votes, pattern='[ ,]', replacement='')) %>%
  mutate(county='Putnam', district=NA_character_, office=office) %>%
  mutate(precinct=gsub(x=precinct, pattern='\r', replacement=' ')) %>%
  mutate(votes=as.integer(votes)) %>%
  mutate(party=case_when(
    candidate=='Osborne1' ~ 'Democratic',
    candidate=='Bartolotti1' ~ 'Republican',
    candidate=='Bartolotti2' ~ 'Constitution',
    candidate=='Osborne2' ~ 'Working Families',
    candidate=='Bartolotti3' ~ 'Independent',
    TRUE ~ NA_character_
  )) %>%
  mutate(candidate=case_when(
    startsWith(candidate, 'Osborne') ~ 'Lithgow Osborne',
    startsWith(candidate, 'Bartolotti') ~ 'Michael C. Bartolotti',
    TRUE ~ candidate
  ))

rdfs <- c(rdfs, list(rdf))

office <- 'County Coroner'
rdf <- map_df(pdfText[53:56], createTibbleFromPageLines)

colnames(rdf) <- c('X10', 'X11', makeX(1:5),
                   'Nesheiwat1', 'Bourges1', 'Nesheiwat2', 'Bourges2', 'Nesheiwat3', 'Bourges3',
                   'Write-In', 'X6', 'X7')

rdf <- rdf %>%
  mutate(precinct=paste(X10, X11)) %>%
  select(-starts_with('X')) %>%
  gather(key='candidate', value='votes', -precinct) %>%
  mutate(votes=gsub(x=votes, pattern='[ ,]', replacement='')) %>%
  mutate(county='Putnam', district=NA_character_, office=office) %>%
  mutate(precinct=gsub(x=precinct, pattern='\r', replacement=' ')) %>%
  mutate(votes=as.integer(votes)) %>%
  mutate(party=case_when(
    candidate=='Nesheiwat1' ~ 'Democratic',
    candidate=='Bourges1' ~ 'Republican',
    candidate=='Nesheiwat2' ~ 'Constitution',
    candidate=='Bourges2' ~ 'Constitution',
    candidate=='Nesheiwat3' ~ 'Independent',
    candidate=='Bourges3' ~ 'Independent',
    TRUE ~ NA_character_
  )) %>%
  mutate(candidate=case_when(
    startsWith(candidate, 'Nesheiwat') ~ 'Michael J. Nesheiwat',
    startsWith(candidate, 'Bourges') ~ 'John F. Bourges',
    TRUE ~ candidate
  ))

rdfs <- c(rdfs, list(rdf))

office <- 'County Legislator'
rdf <- map_df(pdfText[57], createTibbleFromPageLines)

colnames(rdf) <- c('X10', 'X11', makeX(1:5),
                   'Whetsel', 'Gouldman1', 'Gouldman2', 'Gouldman3',
                   'Write-In', 'X6', 'X7')

rdf <- rdf %>%
  mutate(precinct=paste(X10, X11)) %>%
  select(-starts_with('X')) %>%
  gather(key='candidate', value='votes', -precinct) %>%
  mutate(votes=gsub(x=votes, pattern='[ ,]', replacement='')) %>%
  mutate(county='Putnam', district='2', office=office) %>%
  mutate(precinct=gsub(x=precinct, pattern='\r', replacement=' ')) %>%
  mutate(votes=as.integer(votes)) %>%
  mutate(party=case_when(
    candidate=='Whetsel' ~ 'Democratic',
    candidate=='Gouldman1' ~ 'Republican',
    candidate=='Gouldman2' ~ 'Constitution',
    candidate=='Gouldman3' ~ 'Independent',
    TRUE ~ NA_character_
  )) %>%
  mutate(candidate=case_when(
    startsWith(candidate, 'Whetsel') ~ 'Wendy M. Whetsel',
    startsWith(candidate, 'Gouldman') ~ 'William J. Gouldman',
    TRUE ~ candidate
  ))

rdfs <- c(rdfs, list(rdf))

office <- 'County Legislator'
rdf <- map_df(pdfText[58], createTibbleFromPageLines)

colnames(rdf) <- c('X10', 'X11', makeX(1:5),
                   'Green1', 'Addonzio1', 'Addonzio2', 'Green2', 'Tartaro', 'Green3',
                   'Write-In', 'X6', 'X7')

rdf <- rdf %>%
  mutate(precinct=paste(X10, X11)) %>%
  select(-starts_with('X')) %>%
  gather(key='candidate', value='votes', -precinct) %>%
  mutate(votes=gsub(x=votes, pattern='[ ,]', replacement='')) %>%
  mutate(county='Putnam', district='3', office=office) %>%
  mutate(precinct=gsub(x=precinct, pattern='\r', replacement=' ')) %>%
  mutate(votes=as.integer(votes)) %>%
  mutate(party=case_when(
    candidate=='Green1' ~ 'Democratic',
    candidate=='Addonzio1' ~ 'Republican',
    candidate=='Addonzio2' ~ 'Constitution',
    candidate=='Green2' ~ 'Working Families',
    candidate=='Tartaro' ~ 'Independent',
    candidate=='Green3' ~ 'Green',
    TRUE ~ NA_character_
  )) %>%
  mutate(candidate=case_when(
    startsWith(candidate, 'Green') ~ 'Jeff Green',
    startsWith(candidate, 'Addonzio') ~ 'Toni E. Addonzio',
    startsWith(candidate, 'Tartaro') ~ 'Louis D. Tartaro',
    TRUE ~ candidate
  ))

rdfs <- c(rdfs, list(rdf))

office <- 'County Legislator'
rdf <- map_df(pdfText[59], createTibbleFromPageLines)

colnames(rdf) <- c('X10', 'X11', makeX(1:5),
                   'Lobue1', 'Lobue2', 'Sayegh',
                   'Write-In', 'X6', 'X7')

rdf <- rdf %>%
  mutate(precinct=paste(X10, X11)) %>%
  select(-starts_with('X')) %>%
  gather(key='candidate', value='votes', -precinct) %>%
  mutate(votes=gsub(x=votes, pattern='[ ,]', replacement='')) %>%
  mutate(county='Putnam', district='8', office=office) %>%
  mutate(precinct=gsub(x=precinct, pattern='\r', replacement=' ')) %>%
  mutate(votes=as.integer(votes)) %>%
  mutate(party=case_when(
    candidate=='Lobue1' ~ 'Republican',
    candidate=='Lobue2' ~ 'Constitution',
    candidate=='Sayegh' ~ 'Independent',
    TRUE ~ NA_character_
  )) %>%
  mutate(candidate=case_when(
    startsWith(candidate, 'Lobue') ~ 'Dini Lobue',
    startsWith(candidate, 'Sayegh') ~ 'Amy E. Sayegh',
    TRUE ~ candidate
  ))

rdfs <- c(rdfs, list(rdf))

office <- 'Kent Proposition #1'
rdf <- map_df(pdfText[60], createTibbleFromPageLines)

colnames(rdf) <- c('X10', 'X11', makeX(1:5),
                   'yes', 'no',
                   'X6', 'X7')

rdf <- rdf %>%
  mutate(precinct=paste(X10, X11)) %>%
  select(-starts_with('X')) %>%
  gather(key='candidate', value='votes', -precinct) %>%
  mutate(votes=gsub(x=votes, pattern='[ ,]', replacement='')) %>%
  mutate(county='Putnam', district=NA_character_, office=office, party=NA_character_) %>%
  mutate(precinct=gsub(x=precinct, pattern='\r', replacement=' ')) %>%
  mutate(votes=as.integer(votes))

rdfs <- c(rdfs, list(rdf))

office <- 'Patterson Town Justice'
rdf <- map_df(pdfText[61], createTibbleFromPageLines)

colnames(rdf) <- c('X10', 'X11', makeX(1:5),
                   'Mole1', 'Mole2', 'Mole3',
                   'Write-In', 'X6', 'X7')

rdf <- rdf %>%
  mutate(precinct=paste(X10, X11)) %>%
  select(-starts_with('X')) %>%
  gather(key='candidate', value='votes', -precinct) %>%
  mutate(votes=gsub(x=votes, pattern='[ ,]', replacement='')) %>%
  mutate(county='Putnam', district=NA_character_, office=office) %>%
  mutate(precinct=gsub(x=precinct, pattern='\r', replacement=' ')) %>%
  mutate(votes=as.integer(votes)) %>%
  mutate(party=case_when(
    candidate=='Mole1' ~ 'Republican',
    candidate=='Mole2' ~ 'Constitution',
    candidate=='Mole3' ~ 'Independent',
    TRUE ~ NA_character_
  )) %>%
  mutate(candidate=case_when(
    startsWith(candidate, 'Mole') ~ 'Anthony R. Mole',
    TRUE ~ candidate
  ))

rdfs <- c(rdfs, list(rdf))

office <- 'Patterson Councilman'
rdf <- map_df(pdfText[62], createTibbleFromPageLines)

colnames(rdf) <- c('X10', 'X11', makeX(1:5),
                   'Shulgin1', 'Rogan1', 'Rogan2', 'Shulgin2',
                   'Write-In', 'X6', 'X7')

rdf <- rdf %>%
  mutate(precinct=paste(X10, X11)) %>%
  select(-starts_with('X')) %>%
  gather(key='candidate', value='votes', -precinct) %>%
  mutate(votes=gsub(x=votes, pattern='[ ,]', replacement='')) %>%
  mutate(county='Putnam', district=NA_character_, office=office) %>%
  mutate(precinct=gsub(x=precinct, pattern='\r', replacement=' ')) %>%
  mutate(votes=as.integer(votes)) %>%
  mutate(party=case_when(
    candidate=='Shulgin1' ~ 'Democratic',
    candidate=='Rogan1' ~ 'Republican',
    candidate=='Rogan2' ~ 'Constitution',
    candidate=='Shulgin2' ~ 'Working Families',
    TRUE ~ NA_character_
  )) %>%
  mutate(candidate=case_when(
    startsWith(candidate, 'Shulgin') ~ 'Luz G. Shulgin',
    startsWith(candidate, 'Rogan') ~ 'Shawn E. Rogan',
    TRUE ~ candidate
  ))

rdfs <- c(rdfs, list(rdf))

office <- 'Southeast Highway Superintendent'
rdf <- map_df(pdfText[63], createTibbleFromPageLines)

colnames(rdf) <- c('X10', 'X11', makeX(1:5),
                   'Bruen1', 'Bruen2',
                   'Write-In', 'X6', 'X7')

rdf <- rdf %>%
  mutate(precinct=paste(X10, X11)) %>%
  select(-starts_with('X')) %>%
  gather(key='candidate', value='votes', -precinct) %>%
  mutate(votes=gsub(x=votes, pattern='[ ,]', replacement='')) %>%
  mutate(county='Putnam', district=NA_character_, office=office) %>%
  mutate(precinct=gsub(x=precinct, pattern='\r', replacement=' ')) %>%
  mutate(votes=as.integer(votes)) %>%
  mutate(party=case_when(
    candidate=='Bruen1' ~ 'Republican',
    candidate=='Bruen2' ~ 'Independent',
    TRUE ~ NA_character_
  )) %>%
  mutate(candidate=case_when(
    startsWith(candidate, 'Bruen') ~ 'Michael E. Bruen',
    TRUE ~ candidate
  ))

rdfs <- c(rdfs, list(rdf))

office <- 'Brewster Village Trustee'
rdf <- map_df(pdfText[64], createTibbleFromPageLines)

colnames(rdf) <- c('X10', 'X11', makeX(1:5),
                   'Boissonnault', 'Bryde',
                   'Write-In', 'X6', 'X7')

rdf <- rdf %>%
  mutate(precinct=paste(X10, X11)) %>%
  select(-starts_with('X')) %>%
  gather(key='candidate', value='votes', -precinct) %>%
  mutate(votes=gsub(x=votes, pattern='[ ,]', replacement='')) %>%
  mutate(county='Putnam', district=NA_character_, office=office) %>%
  mutate(precinct=gsub(x=precinct, pattern='\r', replacement=' ')) %>%
  mutate(votes=as.integer(votes)) %>%
  mutate(party=case_when(
    candidate=='Boissonnault' ~ 'A Better Brewster',
    candidate=='Bryde' ~ 'A Better Brewster',
    TRUE ~ NA_character_
  )) %>%
  mutate(candidate=case_when(
    startsWith(candidate, 'Boissonnault') ~ 'Tom J. Boissonnault',
    startsWith(candidate, 'Bryde') ~ 'Mary C. Bryde',
    TRUE ~ candidate
  ))

rdfs <- c(rdfs, list(rdf))

bind_rows(rdfs) %>%
  select(county, precinct, office, district, candidate, party, votes) %>%
  write_csv('20141104__ny__general__putnam__precinct.csv')
