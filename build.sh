build_maxrrpv_schmoo() {
  for i in ./configs/*maxrrpv*.json; do
    ./config.sh $i
    make
  done
}

build_maxshctr_schmoo() {
  for i in ./configs/*maxshctr*.json; do
    ./config.sh $i
    make
  done
}

#build_maxrrpv_schmoo
build_maxshctr_schmoo

