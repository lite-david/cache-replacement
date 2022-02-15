build_schmoo() {
  for i in ./configs/*$1*.json; do
    ./config.sh $i
    make
  done
}

#build_schmoo shippp_maxrrpv
#build_schmoo shippp_maxshctr
#build_schmoo shippp_leaders
#build_schmoo hawkeye_maxrrpv
#build_schmoo hawkeye_sampler
#build_schmoo hawkeye_optgenvector
build_schmoo shippp_shctsize

