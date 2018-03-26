# ny 2002 county-level elections results parser
# author: ursula.kaczmarek (at) gmail.com

library(fs)
library(pdftools)
library(plyr)
library(tidyverse)

### get 2002 pdfs ###
# identify files
races <- c("2002/general/2002_gov", "2002/general/2002_comp", "2002/general/2002_ag", "2002/general/2002_cong",
           "2002/general/2002_sen", "2002/general/2002_assem","2002/primary/2002primarycanvass",
           "2002/special/0220sd", "2002/special/0226sd", "2002/special/0219ad", "2002/special/0256ad",
           "2002/special/0260ad", "2002/special/02100ad")

urls <- sprintf("https://www.elections.ny.gov/NYSBOE/elections/%s.pdf", races)

# dowload pfs
to.dir <- fs::dir_create(path = file.path("~/r scripts/openelections-data-ny/", "2002PDF"))
download.file(urls, file.path(to.dir, basename(urls)))

### extract text ###
# format is different for special & general election - start with special
special <- list.files(to.dir, pattern = "*d.pdf", full.names = TRUE)

text <- map(special, pdf_text) %>%
   flatten() %>%
   str_split("\n") %>%
   map(~.x[-c(1:7, 9)])
text <- text[-c(2,3)]
text <- ldply(text, rbind)
text <- text[, c(1:11)]

to.remove <- c("PARTY", "CANDIDATE", "DISTRICT", "ELECTED", "Part of", "PART OF", "RECAP", "\"")
text <- as.data.frame(lapply(text, function(x) gsub(paste(to.remove, collapse = "|"), " ", x)), stringsAsFactors = FALSE)

# parse special
party.parse <- c("DEM", "REP", "GRE", "WOR", "IND", "LIB", "LBT", "RTL", "CON", "Blk,Vd,Sct", "[0-9]")

text %<>%
   mutate(district = str_extract(X1, "[[:digit:]]+"),
          X2 = str_extract_all(X2, "[[:alpha:]]+"),
          county = ifelse(grepl("NEW", X2), "NEW YORK", strsplit(as.character(X2), " ")),
          office = ifelse(grepl("ASSEMBLY", X1), "State House", "State Senate")) %>%
   unnest(county) %>%
   group_by(district, county, office) %>%
   nest(X3:X11) %>%
   mutate(party = map(data, ~ substr(.x, 1, 3)),
          candidate = map(data, ~ gsub(paste(party.parse, collapse = "|"), "", .)),
          votes = map(data, ~ str_trim(gsub("[[:alpha:]]|\\.|,", "", .x), side = "left"))) %>%
   unnest(party, candidate, votes) %>%
   filter(str_trim(votes) != "")

text %<>%
   mutate(county = str_extract(county, "[A-Z\\s]+"),
          county = str_to_title(county),
          candidate = gsub("TOTAL....", "Total", candidate),
          candidate = gsub(" ,|^ *|(?<= ) | *$", "", candidate, perl = TRUE),
          candidate = ifelse(grepl("Blk,Vd,Scat", candidate), gsub("Blk,Vd,Scat", "Blank Void Scattering", candidate), candidate),
          candidate = str_trim(candidate, side = "both"),
          votes = ifelse(grepl("Saratoga", county), gsub(" +.*$", "", votes),
                  ifelse(grepl("Washington", county), str_trim(str_extract(votes, " .* "), side = "left"), votes)),
          party = gsub("\\s+", "", party)) %>%
   filter(county != "Total") %>%
   select(county, office, district, party, candidate, votes)

write.csv(text, "2002/20020212_ny_special.csv", row.names = FALSE, quote = FALSE)

# parse non-legislative general elections with same format
gen <- list.files(to.dir, pattern = "ag|comp|gov", full.names = TRUE)

text <- map(gen, pdf_text) %>%
   str_split("\n") %>%
   map(~ .x[-c(1:2, 64, 70:72)]) %>%
   lapply(as.data.frame) %>% bind_rows() %>%
   select(X1 = "X[[i]]")

text %<>%
   transmute(X1 = gsub(" ,|^ *|(?<= ) | *$", " ", X1, perl = TRUE)) %>%
   filter(!grepl("Working|Marijunana", X1))

party.parse <- function(x){
   paste0(str_replace_all(x, c("Republican" = "REP", "Democratic"  = "DEM", "Independence" = "IND",
                   "Conservative" = "CON", "Liberal" = "LIB", "Right To Life" = "RTL", "Green" = "GRE",
                   "Families" = "WOR", "Libertarian" = "LBT", "Reform" = "MRF", "County" = "county")), "BVS")
}

genvote <- map(gen, pdf_text) %>%
   str_split("\\s+") %>%
   lapply(as.data.frame) %>% bind_rows() %>%
   slice(-c(1:60, 746:759, 821:901, 1587:1600, 1662:1746, 2489:2503, 2570:2598)) %>%
   select(votes = "X[[i]]") %>%
   filter(!grepl("[[:alpha:]]+", votes)) %>%
   mutate(votes = gsub(",", "", votes))

text %<>%
   transmute(X1 = ifelse(grepl("County", X1), party.parse(X1), X1),
             X1 = ifelse(grepl("county", X1), paste(X1, "TOTAL"), X1)) %>%
   mutate(county = ifelse(!grepl("county|Eliot|Spitzer|Pataki|Donohue|John|Faso", X1),
                          gsub("[[:digit:]]|,|\\s+", "", X1, perl = TRUE), NA),
          office = ifelse(grepl("Dora|Irizzary", X1), "Attorney General",
                   ifelse(grepl("John|Faso", X1), "Comptroller",
                   ifelse(grepl("Pataki|Donohue", X1), "Governor", NA))),
          district = "") %>%
   fill(office) %>%
   mutate(party = ifelse(grepl("Attorney General", office), str_extract_all(X1[1], "[[:upper:]]+"),
                  ifelse(grepl("Comptroller", office), str_extract_all(X1[66], "[[:upper:]]+"),
                  ifelse(grepl("Governor", office), str_extract_all(X1[131], "[[:upper:]]+"), NA)))) %>%
   unnest(party) %>% fill(party) %>%
   filter(!is.na(county)) %>%
   select(-X1)

gencandidate <- map(gen, pdf_text) %>%
   str_split("[ ]{2,}") %>%
   lapply(as.data.frame) %>% bind_rows() %>%
   slice(-c(1:16, 36:762, 783:1515, 1538:2317)) %>%
   select(candidates = "X[[i]]") %>%
   transmute(first = ifelse(row_number() %in% c(1:11, 20:30, 40:50), candidates, NA),
             last = ifelse(row_number() %in% c(12:19, 31:39, 51:61), gsub("Albany", "Total", candidates), NA),
             last = strsplit(as.character(last), "\\s|\n")) %>%
   unnest(last) %>%
   mutate(last = ifelse(grepl("Conti", last), "Conti Jr.", last),
          first = ifelse(grepl("Cuomo", first), strsplit(as.character(first), " "), first)) %>%
   unnest(first) %>% slice(-21)

gencandidate <- cbind(gencandidate$first[c(1:11, 23:33, 45:56)], gencandidate$last[c(12:22, 34:44, 57:68)])
gencandidate %<>%
   as.data.frame() %>%
   transmute(candidate = paste(V1, V2, sep = " ")) %>%
   mutate(candidate = ifelse(grepl("Total", candidate), gsub("Total\n Total", "Total", candidate),
                      ifelse(grepl("Blk.,Void Scattering", candidate), gsub("Blk.,Void Scattering", "Blank Void Scattering", candidate), candidate)))

ag <- replicate(62, gencandidate[1:11, ], simplify = FALSE)
comp <- replicate(62, gencandidate[12:22, ], simplify = FALSE)
gov <- replicate(62, gencandidate[23:34, ], simplify = FALSE)
candlist <- list(ag, comp, gov)

gencandidate <- candlist %>%
   unlist(recursive = FALSE) %>% enframe() %>% unnest() %>%
   select(candidate = value)

text <- bind_cols(text, gencandidate, genvote) %>%
   mutate(party = ifelse(grepl("BVS", party), "",
                  ifelse(grepl("TOTAL", party), "", party)))

# parse legislative general races
leg <- list.files(to.dir, pattern = "assem|sen", full.names = TRUE)

legtext <- map(leg, pdf_text) %>%
   flatten() %>%
   str_split("\n") %>%
   map( ~ discard(.x, grepl("NYS|RECAP", .))) %>%
   map( ~ str_trim(.x))

legtext <- ldply(legtext, cbind)
legtext <- as.data.frame(lapply(legtext, function(x) gsub(paste(c("County", to.remove), collapse = "|"), "", x)),
              stringsAsFactors = FALSE)

legvote <- legtext %>%
   filter(!grepl("TOTAL|ASSEMBLY|SENATE|[[:lower:]]", X1)) %>%
   filter(X1 != "") %>%
   transmute(X1 = gsub("1,489                            580", "1489           0                 580", X1),
             X1 = gsub("382                   9,498", "382         0          9498", X1),
             X1 = str_trim(gsub("\\s+", " ", X1, perl = TRUE))) %>%
   mutate(votes = str_split(str_trim(gsub("[[:alpha:]]+|\\.|,", "", X1)), " ")) %>%
   select(votes) %>% unnest()

legcandidate <- map(leg, pdf_text) %>%
   flatten() %>%
   str_split("\n") %>%
   map( ~ discard(.x, grepl("TOTAL|RECAP|NYS", .))) %>%
   map( ~ gsub("PART OF", "", .x)) %>%
   map(~ gsub("[^(JE)]([[:upper:]]\\.)([[:space:]])([[:upper:]])", "\\1  \\2 \\3", .x)) %>%
   map( ~ gsub("r\\.", "r\\.   ", .x)) %>%
   map( ~ gsub("I De", "I  De", .x)) %>%
   map( ~ gsub("Adam", " Adam", .x)) %>%
   map( ~ gsub("Toby", " Toby", .x)) %>%
   map( ~ gsub("Liz", "Liz ", .x)) %>%
   map( ~ gsub("Patricia", " Patricia", .x)) %>%
   map( ~ gsub("Frederick", " Frederick", .x)) %>%
   map( ~ gsub("Diaz", "Diaz ", .x)) %>%
   map( ~ gsub("E.    Christopher", "E. Christopher", .x)) %>%
   map( ~ gsub("Espaillat", "Espaillat ", .x)) %>%
   map( ~ gsub("Tallon Christian Ortloff Christian Ortloff", "Tallon  Christian Ortloff  Christian Ortloff", .x)) %>%
   map( ~ str_trim(.x)) %>%
   lapply(as.data.frame) %>% bind_rows() %>%
   select(candidate = "X[[i]]") %>%
   transmute(candidate = paste(candidate, " BVS", "  TOTAL", collapse = ";")) %>%
   slice(1) %>%
   flatten() %>%
   str_split(";") %>%
   lapply(as.data.frame) %>% bind_rows() %>%
   select(candidate = "X[[i]]") %>%
   mutate(district = ifelse(grepl("ASSEMBLY|SENATE", candidate), str_extract(candidate, "[[:digit:]]+"), NA),
          office = ifelse(grepl("ASSEMBLY", candidate), "State House",
                          ifelse(grepl("SENATE", candidate), "State Senate", NA))) %>%
   fill(district, office) %>%
   filter(!grepl("[[:digit:]]+", candidate), candidate != "  BVS   TOTAL")

legcandidate <- legcandidate %>%
   mutate(first = ifelse(as.numeric(row.names(legcandidate)) %% 2,
                         str_split(candidate, pattern = "\\s{2,}" ), NA),
          last = ifelse(is.na(first),
                        str_split(candidate, pattern = "\\s{2,}"), NA))

firstname <- legcandidate %>% unnest(first) %>%
   mutate(first = gsub("([[:lower:]])([[:upper:]])", "\\1 \\2", first),
             first = ifelse(first == ("Gary"), gsub("Gary", "J. Gary", first), first),
             first = ifelse(first == ("Patricia"), gsub("Patricia", "Mary Patricia", first), first),
             first = ifelse(first == ("C."), gsub("C.", "J. C.", first), first),
             first = ifelse(first == ("M."), gsub("M.", "M. Tracey", first), first),
             first = ifelse(first == ("N."), gsub("N.", "N. Nick", first), first),
             first = ifelse(first == ("E."), gsub("E.", "E. Clyde", first), first)) %>%
   filter(!is.na(first)) %>%
   slice(-c(83, 390, 393, 544, 547, 549, 590, 592, 594, 741, 854, 858)) %>%
   select(-candidate)

lastname <- legcandidate %>% unnest(last) %>%
   mutate(last = ifelse(grepl(", Jr.", last), gsub(", Jr.", " Jr.", last),
                 ifelse(grepl(", Sr.", last), gsub(", Sr.", " Sr.", last),
                 ifelse(grepl(", III", last), gsub(", III", " III", last), last)))) %>%
   filter(!is.na(last), nchar(last) > 0)

party <- legtext %>%
   mutate(party = ifelse(grepl("BVS", X1), X1, NA)) %>%
   select(party) %>%
   filter(!is.na(party)) %>%
   fill(party) %>%
   mutate(party = str_extract_all(party, "[[:upper:]]+")) %>%
   unnest(party)

legcandidate <- bind_cols(party, firstname, lastname) %>%
   mutate(candidate = paste(first, last),
          candidate = gsub("BVS BVS", "Blank Void Scattering", candidate),
          candidate = gsub("TOTAL TOTAL", "", candidate)) %>%
   select(district, office, candidate, party)

legtext %<>%
   filter(!grepl("TOTAL |[[:lower:]]", X1)) %>%
   filter(X1 != "") %>%
   transmute(X1 = str_trim(gsub("\\s+", " ", X1, perl = TRUE))) %>%
   mutate(district = ifelse(grepl("ASSEMBLY|SENATE", X1), str_extract(X1, "[[:digit:]]+"), NA),
          office = ifelse(grepl("ASSEMBLY", X1), "State House",
                          ifelse(grepl("SENATE", X1), "State Senate", NA)),
          county = ifelse(grepl("NEW YORK", X1), "New York",
                          ifelse(grepl("ST. LAWRENCE", X1), "St. Lawrence",
                          ifelse(grepl("[[:digit:]]+ ", X1), str_to_title(str_extract_all(X1, "[[:alpha:]]+")), NA))),
          party = ifelse(grepl("TOTAL", X1), X1, NA)) %>%
   fill(district, office) %>%
   filter(!grepl("ASSEMBLY|SENATE", X1)) %>%
   fill(party) %>%
   filter(!grepl("TOTAL", X1), !is.na(county)) %>%
   mutate(party = str_extract_all(party, "[[:upper:]]+")) %>%
   unnest(party)

legtext <- full_join(legtext, legcandidate, by = c("district", "office", "party")) %>%
   bind_cols(legtext, legvote) %>%
   select(county, office, district, party, candidate, votes)

# combine general
text <- bind_rows(text, legtext)

write.csv(text, "2002/20020212_ny_general.csv", row.names = FALSE, quote = FALSE)

# parse primary
primary <- list.files(to.dir, pattern = "primary", full.names = TRUE)

party.parse <- function(x){
   abv <- str_replace_all(x, c("Republican" = "REP", "Democratic"  = "DEM", "Independence" = "IND", "Independance" = "IND",
                               "Conservative" = "CON", "Liberal" = "LIB", "Right to Life" = "RTL", "Green" = "GRE",
                               "Working Families" = "WOR", "Libertarian" = "LBT", "Reform" = "MRF"))
   party <- str_extract_all(abv, "[[:upper:]]{3}")
   return(party)
}

text <- pdf_text(primary) %>%
   str_split("\n")

text <- text[-1] %>%
   lapply(as.data.frame) %>% bind_rows() %>%
   select(X1 = "X[[i]]") %>%
   filter(!grepl("NYC|STATE|CANVASS|Board|eptember|Candidate|Districts|MEMBER|REPRESENTATIVE|GIVEN|Wilkey|: SS:|Executive|votes", X1)) %>%
   slice(-c(597:807, 991:1006)) %>%
   transmute(X1 = gsub("Part of|County|Statewide|Primary", "", X1)) %>%
   mutate(office = ifelse(grepl("Gubernatorial", X1), "Governor",
                   ifelse(grepl("Lieutenant Governor", X1), "Lieutenant Governor",
                   ifelse(grepl("Comptroller", X1), "Comptroller",
                   ifelse(grepl("Congress", X1), "U.S. House",
                   ifelse(grepl("Senate", X1), "State Senate",
                   ifelse(grepl("Assembly", X1), "State House", NA)))))),
          district = ifelse(grepl("Congress|Senate|Assembly", X1),
                            str_trim(gsub("[[:alpha:]]+|-", "", X1)), NA),
          party = ifelse(grepl("Gubernatorial|Lieutenant|Comptroller|Congress|Senate|Assembly", X1), party.parse(X1), NA),
          county = ifelse(grepl("New York", X1), "New York",
                   ifelse(grepl("St.", X1), "St. Lawrence",
                   ifelse(grepl("[[:digit:]]", X1) & !grepl("-|Senate", X1), str_to_title(str_extract_all(X1, "[[:alpha:]]+")), NA)))) %>%
   unnest(party) %>%
   fill(office, district, party) %>%
   filter(X1 != "", !grepl("Total", X1))

primarycandidate <- text %>%
   mutate(candidate = ifelse(is.na(county) & !grepl("Gubernatorial|Lieutenant|Comptroller|Congress|Senate|Assembly", X1), X1, NA)) %>%
   filter(!is.na(candidate)) %>%
   mutate(candidate = ifelse(row_number() == 56, paste0(candidate, "  -"), candidate)) %>%
   select(office, district, party, candidate)

primarycandidate <- primarycandidate %>%
   mutate(first = ifelse(as.numeric(row.names(primarycandidate)) %% 2,
                         str_split(gsub("n ", "n   ",candidate), pattern = "\\s{2,}"), NA),
          last = ifelse(is.na(first), str_split(gsub("\\.", "\\.  ", candidate), pattern = "\\s{2,}"), NA))

firstname <- primarycandidate[ ,c(1:3, 5)] %>%
   unnest(first) %>%
   mutate(first = str_split(gsub("\\.", "\\.-", first), pattern = "-")) %>%
   unnest(first) %>%
   mutate(first = ifelse(first == (" Carl"), gsub("Carl", "H. Carl", first),
                  ifelse(first == (" Thomas"), gsub("Thomas", "B. Thomas", first),
                  ifelse(first == ("Alan"), gsub("Alan", "Alan G.", first),
                  ifelse(first == ("John"), gsub("John", "John W.", first),
                  ifelse(first == (" Tracey"), gsub("Tracey", "M. Tracey", first),
                  ifelse(first == ("Preston"), gsub("Preston", "Preston L.", first),
                  ifelse(first == ("Byron"), gsub("Byron", "Byron W.", first),
                  ifelse(first == ("Rau"), gsub("Rau", "Ethan Rau", first), first))))))))) %>%
   filter(!is.na(first), first != "") %>%
   slice(-c(2, 5, 8, 18, 21, 24, 38, 44, 54, 75))

lastname <- primarycandidate[ ,6] %>%
   unnest(last) %>%
   transmute(last = str_split(gsub("([[:lower:]])([[:space:]])([[:upper:]])", "\\1  \\2 \\3", last), pattern = "\\s{2,}")) %>%
   unnest(last) %>%
   mutate(last = ifelse(last == ("Ortloff"), gsub("Ortloff", "Christian Ortloff", last),
                        ifelse(last == ("Lowry"), gsub("Lowry", "Lowry Lamb", last),
                        ifelse(grepl(", Jr.", last), gsub(", Jr.", " Jr.", last), last)))) %>%
   filter(!is.na(last), last != "") %>%
   slice(-c(47, 71))

primarycandidate <- bind_cols(firstname, lastname) %>%
   mutate(candidate = paste(first, last)) %>%
   select(-first, -last)

primaryvote <- text %>%
   filter(!is.na(county)) %>%
   transmute(X1 = ifelse(row_number() %in% c(182:186), paste(X1, " 0"), X1)) %>%
   mutate(votes = str_split(gsub("[[:alpha:]]+|\\.|,", "", X1), " "))  %>%
   select(votes) %>%
   unnest() %>%
   filter(votes != "")

text %<>%
   filter(!is.na(county)) %>%
   select(-X1) %>%
   full_join(primarycandidate, text, by = c("district", "office", "party"))

text <- text %>%
   bind_cols(text, primaryvote) %>%
   mutate(district = ifelse(is.na(district), "", district)) %>%
   select(county, office, district, party, candidate, votes)

write.csv(text, "2002/20020212_ny_primary.csv", row.names = FALSE, quote = FALSE)

dir_delete(to.dir)








