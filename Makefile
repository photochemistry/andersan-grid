data/%.csv:
	poetry run python -m andersan_grid.cli fetch \
		--pref $* \
		--target-datetime 2026-03-06T12:00:00+09:00 \
		--pollutants pm25,ox,no2 \
		--output data/$*.csv

output14/%: data/%.csv
	poetry run python -m andersan_grid.cli interpolate \
		--input data/$*.csv \
		--out-dir $@ \
		--method tps linear atps \
		--tile-zoom 14 \
		--bbox-margin-deg 0.1 \
		--atps-smoothing 0.001

output12/%: data/%.csv
	poetry run python -m andersan_grid.cli interpolate \
		--input data/$*.csv \
		--out-dir $@ \
		--method tps linear atps \
		--tile-zoom 12 \
		--bbox-margin-deg 0.1 \
		--atps-smoothing 0.001
