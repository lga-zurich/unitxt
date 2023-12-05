import evaluate

from src import unitxt
from src.unitxt.load import load_dataset
from src.unitxt.text_utils import print_dict

dataset = load_dataset("recipes.wnli_3_shot")

metric = evaluate.load(unitxt.metric_url)

results = metric.compute(
    predictions=["none" for t in dataset["test"]], references=dataset["test"]
)

print_dict(results[0])
