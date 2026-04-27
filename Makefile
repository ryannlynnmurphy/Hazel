# Minimal ergonomics for ship-into-the-future
.PHONY: future ship
future:
	@bash scripts/ship-future.sh
ship: future
