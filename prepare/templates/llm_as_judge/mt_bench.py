from src.unitxt.catalog import add_to_catalog
from src.unitxt.templates import InputOutputTemplate

add_to_catalog(
    InputOutputTemplate(
        instruction="Please act as an impartial judge and evaluate the quality of the response"
        " provided by an AI assistant to the user question displayed below. Your evaluation should"
        " consider factors such as the helpfulness, relevance, accuracy, depth, creativity, "
        " and level of detail of the response. Begin your evaluation by providing a short"
        " explanation. Be as objective as possible. After providing your explanation, you must rate"
        ' the response on a scale of 1 to 10 by strictly following this format: "[[rating]]",'
        ' for example: "Rating: [[5]]".\n\n',
        input_format="[Question]\n{model_input}\n\n[The Start of Assistant's Answer]"
        "\n{model_output}\n[The End of Assistant's Answer]",
        output_format="{output}",
        postprocessors=[
            r'processors.regex_extractor[pattern=r"Rating: \[\[((\d*\.)?\d+)\]\]"]',
        ],
    ),
    "templates.llm_as_judge.model_response_assessment.mt_bench",
    overwrite=True,
)
