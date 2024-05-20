from unitxt import add_to_catalog
from unitxt.task import Task

add_to_catalog(
    Task(
        inputs=["original_text"],
        outputs=["corrected_texts"],
        metrics=[
            "metrics.char_edit_dist_accuracy",
            "metrics.rouge",
            "metrics.char_edit_distance[reference_field=original_text]",
        ],
    ),
    "tasks.grammatical_error_correction",
    overwrite=True,
)
