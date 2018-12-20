# read/write width is relatively slow to resolve
# Even slower with multi bit masks...
N ?= 8
DO_DBFIXUP?=N

include ../fuzzer.mk

database: build/segbits_bramx.db

build/segbits_bramx.rdb: $(SPECIMENS_OK)
	${XRAY_SEGMATCH} -o build/segbits_bramx.rdb $(addsuffix /segdata_bram_[lr].txt,$(SPECIMENS))

build/segbits_bramx.db: build/segbits_bramx.rdb
ifeq ($(DO_DBFIXUP),Y)
	${XRAY_DBFIXUP} --db-root build --zero-db bits.dbf --seg-fn-in $^ --seg-fn-out $@
else
	cp $^ $@
endif
	${XRAY_MASKMERGE} build/mask_bramx.db $(addsuffix /segdata_bram_[lr].txt,$(SPECIMENS))

pushdb:
	${XRAY_MERGEDB} bram_l build/segbits_bramx.db
	${XRAY_MERGEDB} bram_r build/segbits_bramx.db
	${XRAY_MERGEDB} mask_bram_l build/mask_bramx.db
	${XRAY_MERGEDB} mask_bram_r build/mask_bramx.db

.PHONY: database pushdb
