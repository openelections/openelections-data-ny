library(curl)
library(data.table)
library(tidyxl)
library(stringr)

# Download raw returns as linked from https://github.com/openelections/openelections-data-ny/issues/30
f = tempfile()
curl_download('https://github.com/openelections/openelections-data-ny/files/1082791/2016.SUFFOLK.NY.xlsx',
  f)

# Create a tidy data.table in which each row describes a cell in a sheet
d = setDT(xlsx_cells(f))

#' Extract candidate names and parties from headers that span rows
extract_candidates = function(.data, rows, relative = TRUE) {
  if (relative) {
    rows = rows + min(.data$row) - 1
  }
  .data = .data[c(row %in% rows), .(candidate = paste(na.omit(character), collapse
        = ' ')), by = 'col']
  .data[, candidate := str_remove_all(candidate, '\\s*NA\\s*')]
  .data[, c('candidate', 'party') := tstrsplit(candidate, '[()]', keep = 1:2)]
  .data[, candidate := str_trim(candidate)]
  .data[]
}

#' Merge extracted candidates into returns
add_candidates = function(.data, candidates, drop_rows, relative = TRUE) {
  stopifnot(!anyDuplicated(candidates, by = 'col'))
  if (!missing(drop_rows)) {
    if (relative) {
      drop_rows = drop_rows + min(.data$row) - 1
    }
    .data = .data[!row %in% drop_rows]
  }
  merge(.data, candidates, by = 'col', all.x = TRUE)[]
}

#' Drop rows in which any cell text matches a pattern, and optionally
#' neighboring rows
drop_rows = function(.data, pattern = 'Voids', pre = 1, post = 1) {
  rows = .data[str_detect(character, regex(pattern, TRUE)), row]
  rows = unique(c(rows - pre, rows, rows + post))
  .data[!row %in% rows][]
}

#' Drop columns in which any cell text matches a pattern
drop_cols = function(.data, pattern = 'Whole') {
  cols = .data[str_detect(character, regex(pattern, TRUE)), col]
  .data[!col %in% cols][]
}

#' Create a column `precinct` from column-A text
create_precinct = function(.data) {
  .data[col == 1, precinct := character]
  .data[, precinct := precinct[1], by = 'row']
  .data = .data[col != 1][]
}

#' Wrap str_replace for candidate name fixups
fix_name = function(.data, pattern, replacement) {
  .data[, candidate := str_replace(candidate, pattern, replacement)]
}

# Allow for character-type vote counts by combining the numeric and character
# columns; later we'll type.convert the votes back to integer
d[data_type == 'character', value := character]
d[data_type == 'numeric', value := as.character(numeric)]

# Parse sheet of presidential returns (extends to column AA, or 27)
pres = d[sheet == 'PRES' & row <= 1091 & col <= 27]
pres = drop_cols(pres, 'Whole')
pres_cand = extract_candidates(pres, 1:3)
pres_cand = fix_name(pres_cand, 'Clin.*', 'Hillary Clinton')
pres_cand = fix_name(pres_cand, 'Trump.*', 'Donald Trump')
pres_cand = fix_name(pres_cand, 'Stein.*', 'Jill Stein')
pres_cand = fix_name(pres_cand, 'Johnson.*', 'Gary Johnson')
pres_cand = fix_name(pres_cand, '.*Fuent', 'Rocky De La Fuente')
pres_cand = fix_name(pres_cand, 'Zoltan.*', 'Zoltan Istvan Gyurko')
pres_cand = fix_name(pres_cand, 'Mc Mullin', 'McMullin')
pres_cand = fix_name(pres_cand, ' \\w ', ' ')
pres = drop_rows(pres, 'Voids')
pres = drop_rows(pres, 'Total for', 0, 0)
pres = add_candidates(pres, pres_cand)
pres = create_precinct(pres)
pres[, office := 'President']

# Parse sheet of Senate returns
sen = d[sheet == 'USS' & row <= 1091]
sen = drop_cols(sen, 'Whole')
sen_cand = extract_candidates(sen, 1:3)
sen = drop_rows(sen, 'Voids')
sen = drop_rows(sen, 'Total for', 0, 0)
sen = add_candidates(sen, sen_cand)
sen = create_precinct(sen)
sen[, office := 'U.S. Senate']

# Parse sheet of House returns by district
# Returns for CD 1, 2, and 3 are concatenated on the CD sheet
d_house = list(d[sheet == 'CD' & row > 1 & row < 506],
  d[sheet == 'CD' & row >= 520 & row < 896],
  d[sheet == 'CD' & row >= 904 & row < 1121])

house = lapply(d_house, function(.d)  {
  .d = drop_cols(.d, 'Whole')
  cand = extract_candidates(.d, 1:3)
  .d = drop_rows(.d, 'Voids')
  .d = drop_rows(.d, 'Total for', 0, 0)
  .d = create_precinct(.d)
  .d[, office := 'U.S. House']
  .d = add_candidates(.d, cand)
  .d
})
house = setNames(house, c('1', '2', '3'))
house = rbindlist(house, idcol = 'district')

# Identify district row ranges in sheet of State Senate returns
sd_ranges = d[sheet == 'SD' & str_detect(character, 'Senatorial District'), .(row, district = character)]
sd_ranges[, district := str_extract(district, '\\d')]
sd_ranges[, start_row := row + 1]
sd_ranges[, end_row := shift(start_row - 8, type = 'lead')]
sd_ranges[district == '1', end_row := 236]
sd_ranges[district == '2', end_row := 480]
sd_ranges[district == '2', end_row := 480]
sd_ranges[district == '8', end_row := 1146]

# Parse Senate returns by district
state_senate = Map(function(i) {
  print(i)
  .d = d[sheet == 'SD' & row >= sd_ranges[i, start_row] &
    row <= sd_ranges[i, end_row]]
  .d = drop_cols(.d, 'Whole')
  sd_cand = extract_candidates(.d, 1:3)
  .d = drop_rows(.d, 'Voids')
  .d = drop_rows(.d, 'Total for', 0, 0)
  .d = create_precinct(.d)
  .d[, office := 'State Senate']
  .d = add_candidates(.d, sd_cand)
  .d
}, 1:nrow(sd_ranges))
state_senate = setNames(state_senate, sd_ranges$district)
state_senate = rbindlist(state_senate, idcol = 'district')

# Identify district row ranges in sheet of Assembly returns
ad_ranges = d[sheet == 'AD' & str_detect(character, 'Assembly District'),
  .(row, district = character)]
ad_ranges[, district := str_extract(district, '\\d+')]
ad_ranges[, start_row := row + 1]
ad_ranges[, end_row := shift(start_row - 10, type = 'lead')]
ad_ranges[district %in% c('3', '4', '6', '11'), end_row := end_row + 7]
ad_ranges[district == '10', start_row := start_row + 1]
ad_ranges[district %in% c('5', '7', '8', '9', '10'), end_row := end_row + 2]
ad_ranges[district == '12', end_row := 1206]

# Parse Assembly returns by district
state_assembly = Map(function(i) {
  .d = d[sheet == 'AD' & row >= ad_ranges[i, start_row] &
    row <= ad_ranges[i, end_row]]
  .d = drop_cols(.d, 'Whole')
  ad_cand = extract_candidates(.d, 1:3)
  .d = drop_rows(.d, 'Voids')
  .d = drop_rows(.d, 'Total for', 0, 0)
  .d = create_precinct(.d)
  .d[, office := 'State Assembly']
  .d = add_candidates(.d, ad_cand)
  .d
}, 1:nrow(ad_ranges))
state_assembly = setNames(state_assembly, ad_ranges$district)
state_assembly = rbindlist(state_assembly, idcol = 'district')

# Combine offices and select columns for output
votes = rbindlist(list(pres, sen, house, state_senate, state_assembly), fill = TRUE)
votes = votes[, .(precinct, office, district, candidate, party, votes =
  value, address)]

# Drop 20 blank cells where we expected to find character or numeric votes, but
# cells were instead blank: in sheet CD, row 888, 894:895, and sheet AD, rows
# 300, 651, and 683
votes = votes[!is.na(votes)]

# Drop total columns for candidates who ran on multiple party lines
votes = votes[is.na(party) | party != 'Total']

# unique(votes$candidate)
# unique(votes$precinct)

# Recast votes and clean up precinct and candidate names
votes[, votes := type.convert(votes)]
votes[, precinct := str_replace_all(precinct, '\\s+', ' ')]
votes[, candidate := str_replace(candidate, ' \\w ', ' ')]

# For QA, summarize totals by candidate-party and town:
# votes[, town := str_extract(precinct, '.*(?= #)')]
# votes[, town := str_remove(town, '(\\(in \\d+\\))*')]
# votes[, .(votes = sum(votes)), by = c('office', 'candidate', 'party', 'town')]

# The `address` column gave cell addresses (e.g. 'A1') for debugging
votes[, `:=`(county = 'Suffolk', address = NULL)]

setcolorder(votes, c("county", "precinct", "office", "district",
    "party", "candidate", "votes"))

fwrite(votes, '../../2016/20161108__ny__general__suffolk__precinct.csv')
