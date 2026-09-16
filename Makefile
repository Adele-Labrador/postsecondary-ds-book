.PHONY: data test clean

data:
	python -m src.features.panel_builder

test:
	pytest -v

clean:
	rm -rf data/interim/*.parquet data/processed/*.parquet
	find . -name "__pycache__" -type d -exec rm -rf {} +
