#!/bin/bash

BIN='python nyc_parser.py'
SOURCE_DIR='../openelections-sources-ny'

$BIN '--print_header' 'True' "$SOURCE_DIR/2016/New York/Presidential Primary/01100200000New York Democratic President Citywide EDLevel.csv" &> "./2016/20160419__ny__democratic__primary__new_york__precinct.csv"
$BIN '--print_header' 'True' "$SOURCE_DIR/2016/New York/Presidential Primary/02100300000New York Republican President Citywide EDLevel.csv" &> "./2016/20160419__ny__republican__primary__new_york__precinct.csv"
$BIN '--print_header' 'True' "$SOURCE_DIR/2016/Bronx/Presidential Primary/01200200000Bronx Democratic President Citywide EDLevel.csv" &> "./2016/20160419__ny__democratic__primary__bronx__precinct.csv"
$BIN '--print_header' 'True' "$SOURCE_DIR/2016/Bronx/Presidential Primary/02200300000Bronx Republican President Citywide EDLevel.csv" &> "./2016/20160419__ny__republican__primary__bronx__precinct.csv"
$BIN '--print_header' 'True' "$SOURCE_DIR/2016/Queens/Presidential Primary/01400200000Queens Democratic President Citywide EDLevel.csv" &> "./2016/20160419__ny__democratic__primary__queens__precinct.csv"
$BIN '--print_header' 'True' "$SOURCE_DIR/2016/Queens/Presidential Primary/02400300000Queens Republican President Citywide EDLevel.csv" &> "./2016/20160419__ny__republican__primary__queens__precinct.csv"
$BIN '--print_header' 'True' "$SOURCE_DIR/2016/Kings/Presidential Primary/01300200000Kings Democratic President Citywide EDLevel.csv" &> "./2016/20160419__ny__democratic__primary__kings__precinct.csv"
$BIN '--print_header' 'True' "$SOURCE_DIR/2016/Kings/Presidential Primary/02300300000Kings Republican President Citywide EDLevel.csv" &> "./2016/20160419__ny__republican__primary__kings__precinct.csv"
$BIN '--print_header' 'True' "$SOURCE_DIR/2016/Richmond/Primaries/01500200000Richmond Democratic President Citywide EDLevel.csv" &> "./2016/20160419__ny__democratic__primary__richmond__precinct.csv"
$BIN '--print_header' 'True' "$SOURCE_DIR/2016/Richmond/Primaries/02500300000Richmond Republican President Citywide EDLevel.csv" &> "./2016/20160419__ny__republican__primary__richmond__precinct.csv"

$BIN '--print_header' 'True' "$SOURCE_DIR/2016/New York/Federal Primaries/01102000007New York Democratic Representative in Congress 7th Congressional District EDLevel.csv" &> "./2016/20160628__ny__democratic__primary__new_york__precinct.csv"
$BIN "$SOURCE_DIR/2016/New York/Federal Primaries/01102000010New York Democratic Representative in Congress 10th Congressional District EDLevel.csv" >> "./2016/20160628__ny__democratic__primary__new_york__precinct.csv"
$BIN "$SOURCE_DIR/2016/New York/Federal Primaries/01102000012New York Democratic Representative in Congress 12th Congressional District EDLevel.csv" >> "./2016/20160628__ny__democratic__primary__new_york__precinct.csv"
$BIN "$SOURCE_DIR/2016/New York/Federal Primaries/01102000013New York Democratic Representative in Congress 13th Congressional District EDLevel.csv" >> "./2016/20160628__ny__democratic__primary__new_york__precinct.csv"

$BIN '--print_header' 'True' "$SOURCE_DIR/2016/Bronx/Federal Primaries/01202000013Bronx Democratic Representative in Congress 13th Congressional District EDLevel.csv" &> "./2016/20160628__ny__democratic__primary__bronx__precinct.csv"
$BIN "$SOURCE_DIR/2016/Bronx/Federal Primaries/01202000015Bronx Democratic Representative in Congress 15th Congressional District EDLevel.csv" >> "./2016/20160628__ny__democratic__primary__bronx__precinct.csv"

$BIN '--print_header' 'True' "$SOURCE_DIR/2016/Queens/Federal Primaries/01402000003Queens Democratic Representative in Congress 3rd Congressional District EDLevel.csv" &> "./2016/20160628__ny__democratic__primary__queens__precinct.csv"
$BIN "$SOURCE_DIR/2016/Queens/Federal Primaries/01402000005Queens Democratic Representative in Congress 5th Congressional District EDLevel.csv" >> "./2016/20160628__ny__democratic__primary__queens__precinct.csv"
$BIN "$SOURCE_DIR/2016/Queens/Federal Primaries/01402000007Queens Democratic Representative in Congress 7th Congressional District EDLevel.csv" >> "./2016/20160628__ny__democratic__primary__queens__precinct.csv"
$BIN "$SOURCE_DIR/2016/Queens/Federal Primaries/01402000012Queens Democratic Representative in Congress 12th Congressional District EDLevel.csv" >> "./2016/20160628__ny__democratic__primary__queens__precinct.csv"

$BIN '--print_header' 'True' "$SOURCE_DIR/2016/Kings/Federal Primaries/01302000007Kings Democratic Representative in Congress 7th Congressional District EDLevel.csv" &> "./2016/20160628__ny__democratic__primary__kings__precinct.csv"
$BIN "$SOURCE_DIR/2016/Kings/Federal Primaries/01302000010Kings Democratic Representative in Congress 10th Congressional District EDLevel.csv" >> "./2016/20160628__ny__democratic__primary__kings__precinct.csv"
$BIN "$SOURCE_DIR/2016/Kings/Federal Primaries/01302000012Kings Democratic Representative in Congress 12th Congressional District EDLevel.csv" >> "./2016/20160628__ny__democratic__primary__kings__precinct.csv"

$BIN '--print_header' 'True' "$SOURCE_DIR/2016/New York/State Primaries/01102100031New York Democratic State Senator 31st Senatorial District EDLevel.csv" &> "./2016/20160913__ny__democratic__primary__new_york__precinct.csv"
$BIN "$SOURCE_DIR/2016/New York/State Primaries/01102300065New York Democratic Member of the Assembly 65th Assembly District EDLevel.csv" >> "./2016/20160913__ny__democratic__primary__new_york__precinct.csv"
$BIN "$SOURCE_DIR/2016/New York/State Primaries/01102300066New York Democratic Member of the Assembly 66th Assembly District EDLevel.csv" >> "./2016/20160913__ny__democratic__primary__new_york__precinct.csv"
$BIN "$SOURCE_DIR/2016/New York/State Primaries/01102300067New York Democratic Member of the Assembly 67th Assembly District EDLevel.csv" >> "./2016/20160913__ny__democratic__primary__new_york__precinct.csv"
$BIN "$SOURCE_DIR/2016/New York/State Primaries/01102300069New York Democratic Member of the Assembly 69th Assembly District EDLevel.csv" >> "./2016/20160913__ny__democratic__primary__new_york__precinct.csv"
$BIN "$SOURCE_DIR/2016/New York/State Primaries/01102300072New York Democratic Member of the Assembly 72nd Assembly District EDLevel.csv" >> "./2016/20160913__ny__democratic__primary__new_york__precinct.csv"

$BIN '--print_header' 'True' "$SOURCE_DIR/2016/Bronx/State Primaries/01202100032Bronx Democratic State Senator 32nd Senatorial District EDLevel.csv" &> "./2016/20160913__ny__democratic__primary__bronx__precinct.csv"
$BIN "$SOURCE_DIR/2016/Bronx/State Primaries/01202100033Bronx Democratic State Senator 33rd Senatorial District EDLevel.csv" >> "./2016/20160913__ny__democratic__primary__bronx__precinct.csv"
$BIN "$SOURCE_DIR/2016/Bronx/State Primaries/01202100036Bronx Democratic State Senator 36th Senatorial District EDLevel.csv" >> "./2016/20160913__ny__democratic__primary__bronx__precinct.csv"

$BIN '--print_header' 'True' "$SOURCE_DIR/2016/Queens/State Primaries/01402100010Queens Democratic State Senator 10th Senatorial District EDLevel.csv" &> "./2016/20160913__ny__democratic__primary__queens__precinct.csv"
$BIN "$SOURCE_DIR/2016/Queens/State Primaries/01402100016Queens Democratic State Senator 16th Senatorial District EDLevel.csv" >> "./2016/20160913__ny__democratic__primary__queens__precinct.csv"
$BIN "$SOURCE_DIR/2016/Queens/State Primaries/01402300029Queens Democratic Member of the Assembly 29th Assembly District EDLevel.csv" >> "./2016/20160913__ny__democratic__primary__queens__precinct.csv"
$BIN "$SOURCE_DIR/2016/Queens/State Primaries/01402300030Queens Democratic Member of the Assembly 30th Assembly District EDLevel.csv" >> "./2016/20160913__ny__democratic__primary__queens__precinct.csv"
$BIN "$SOURCE_DIR/2016/Queens/State Primaries/01402300032Queens Democratic Member of the Assembly 32nd Assembly District EDLevel.csv" >> "./2016/20160913__ny__democratic__primary__queens__precinct.csv"
$BIN "$SOURCE_DIR/2016/Queens/State Primaries/01402300033Queens Democratic Member of the Assembly 33rd Assembly District EDLevel.csv" >> "./2016/20160913__ny__democratic__primary__queens__precinct.csv"

$BIN '--print_header' 'True' "$SOURCE_DIR/2016/Kings/State Primaries/01302100018Kings Democratic State Senator 18th Senatorial District EDLevel.csv" &> "./2016/20160913__ny__democratic__primary__kings__precinct.csv"
$BIN "$SOURCE_DIR/2016/Kings/State Primaries/01302100019Kings Democratic State Senator 19th Senatorial District EDLevel.csv" >> "./2016/20160913__ny__democratic__primary__kings__precinct.csv"
$BIN "$SOURCE_DIR/2016/Kings/State Primaries/01302100025Kings Democratic State Senator 25th Senatorial District EDLevel.csv" >> "./2016/20160913__ny__democratic__primary__kings__precinct.csv"
$BIN "$SOURCE_DIR/2016/Kings/State Primaries/01302300042Kings Democratic Member of the Assembly 42nd Assembly District EDLevel.csv" >> "./2016/20160913__ny__democratic__primary__kings__precinct.csv"
$BIN "$SOURCE_DIR/2016/Kings/State Primaries/01302300044Kings Democratic Member of the Assembly 44th Assembly District EDLevel.csv" >> "./2016/20160913__ny__democratic__primary__kings__precinct.csv"
$BIN "$SOURCE_DIR/2016/Kings/State Primaries/01302300046Kings Democratic Member of the Assembly 46th Assembly District EDLevel.csv" >> "./2016/20160913__ny__democratic__primary__kings__precinct.csv"
$BIN "$SOURCE_DIR/2016/Kings/State Primaries/01302300055Kings Democratic Member of the Assembly 55th Assembly District EDLevel.csv" >> "./2016/20160913__ny__democratic__primary__kings__precinct.csv"
$BIN "$SOURCE_DIR/2016/Kings/State Primaries/01302300056Kings Democratic Member of the Assembly 56th Assembly District EDLevel.csv" >> "./2016/20160913__ny__democratic__primary__kings__precinct.csv"

$BIN '--print_header' 'True' "$SOURCE_DIR/2016/Richmond/Primaries/02502300062Richmond Republican Member of the Assembly 62nd Assembly District EDLevel.csv" &> "./2016/20160913__ny__republican__primary__richmond__precinct.csv"

function gen_precinct () {
  source_sub_dir=$1
  dest_file_path=$2
  
  print_header=true
  for source_file in "$SOURCE_DIR/$source_sub_dir"/*; do
    if [ "$print_header" = true ] ; then
      $BIN '--print_header' 'True' "$source_file" &> "$dest_file_path"
      print_header=false
   else
      $BIN "$source_file" >> "$dest_file_path"
    fi
  done
}

gen_precinct "2016/New York/General" "./2016/20161108__ny__general__new_york__precinct.csv"
gen_precinct "2016/Bronx/General" "./2016/20161108__ny__general__bronx__precinct.csv"
gen_precinct "2016/Queens/General" "./2016/20161108__ny__general__queens__precinct.csv"
gen_precinct "2016/Kings/General" "./2016/20161108__ny__general__kings__precinct.csv"
gen_precinct "2016/Richmond/General" "./2016/20161108__ny__general__richmond__precinct.csv"
