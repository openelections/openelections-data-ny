#!/bin/bash

BIN='python nyc_parser.py'
SOURCE_DIR='../openelections-sources-ny'

$BIN "$SOURCE_DIR/2016/New York/Presidential Primary/01100200000New York Democratic President Citywide EDLevel.csv" &> "./2016/20160628__ny__democratic__primary__new_york__precinct.csv"
$BIN "$SOURCE_DIR/2016/New York/Presidential Primary/02100300000New York Republican President Citywide EDLevel.csv" &> "./2016/20160628__ny__republican__primary__new_york__precinct.csv"
$BIN "$SOURCE_DIR/2016/Bronx/Presidential Primary/01200200000Bronx Democratic President Citywide EDLevel.csv" &> "./2016/20160628__ny__democratic__primary__bronx__precinct.csv"
$BIN "$SOURCE_DIR/2016/Bronx/Presidential Primary/02200300000Bronx Republican President Citywide EDLevel.csv" &> "./2016/20160628__ny__republican__primary__bronx__precinct.csv"
$BIN "$SOURCE_DIR/2016/Queens/Presidential Primary/01400200000Queens Democratic President Citywide EDLevel.csv" &> "./2016/20160628__ny__democratic__primary__queens__precinct.csv"
$BIN "$SOURCE_DIR/2016/Queens/Presidential Primary/02400300000Queens Republican President Citywide EDLevel.csv" &> "./2016/20160628__ny__republican__primary__queens__precinct.csv"
$BIN "$SOURCE_DIR/2016/Kings/Presidential Primary/01300200000Kings Democratic President Citywide EDLevel.csv" &> "./2016/20160628__ny__democratic__primary__kings__precinct.csv"
$BIN "$SOURCE_DIR/2016/Kings/Presidential Primary/02300300000Kings Republican President Citywide EDLevel.csv" &> "./2016/20160628__ny__republican__primary__kings__precinct.csv"
$BIN "$SOURCE_DIR/2016/Richmond/Primaries/01500200000Richmond Democratic President Citywide EDLevel.csv" &> "./2016/20160628__ny__democratic__primary__richmond__precinct.csv"
$BIN "$SOURCE_DIR/2016/Richmond/Primaries/02500300000Richmond Republican President Citywide EDLevel.csv" &> "./2016/20160628__ny__republican__primary__richmond__precinct.csv"
