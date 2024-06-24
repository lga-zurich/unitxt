from typing import Any, Dict, List, Literal, Optional

from .api import evaluate, produce
from .inference import InferenceEngine, OpenAiInferenceEngine
from .metrics import BulkInstanceMetric
from .operator import SequentialOperator

# TODO: pairwise ranking cannot be used with shuffled template. Need to add support.


class LLMAsJudge(BulkInstanceMetric):
    """LLM as judge based metric class for evaluating correctness.

    Attributes:
        main_score (str): The main score label used for evaluation.
        task (Literal["rating.single_turn"]): The type of task the llm-as-judge runs. This defines the output and input
         format of the jude model.
        template (str): The template used when generating inputs for the judge llm.
        format (str): The format used when generating inputs for judge llm.
        system_prompt (str): The system prompt used when generating inputs for judge llm.
        strip_system_prompt_and_format_from_inputs (bool): Whether to strip the system prompt and formatting from the
         inputs that the models that is being judges received, when they are inserted to the llm-as-judge prompt.
        inference_model (InferenceEngine): the module that creates the inference of the judge llm.
        reduction_map (dict): A dictionary specifying the reduction method for the metric.
        batch_size (int): The size of the bulk.
        pairwise_comparison_include_swapped_positions bool): If True, the comparison will be done twice,
                                   once with the original instance and once with the models swapped.
    """

    main_score: str = "llm_as_judge"
    task: Literal[
        "rating.single_turn",
        "rating.single_turn_with_reference",
        "pairwise_comparative_rating.single_turn",
    ]
    template: str
    format: Optional[str] = None
    system_prompt: Optional[str] = None
    strip_system_prompt_and_format_from_inputs: bool = True
    inference_model: InferenceEngine
    pairwise_comparison_include_swapped_positions: bool = False
    reduction_map: Optional[Dict[str, List[str]]] = None
    batch_size: int = 32

    def _get_input_instances(self, task_data: List[Dict]) -> List:
        if self.strip_system_prompt_and_format_from_inputs:
            instances = []
            for task_data_instance in task_data:
                template = task_data_instance["metadata"]["template"]
                instance = SequentialOperator(
                    steps=[template, "formats.empty"]
                ).process_instance(
                    {"inputs": task_data_instance, "outputs": task_data_instance}
                )
                instances.append(instance["source"])
                """
                We also have access to: instance["target"]
                                        instance["references"]
                """
            return instances
        return [t["source"] for t in task_data]

    def _get_instance_for_judge_model(
        self, input_instances: List[str], predictions: List, references: List
    ) -> List[Dict]:
        if self.task == "rating.single_turn":
            instances = [
                {
                    "question": input_instance,
                    "answer": prediction,
                    "rating": 5.0,  # This is a dummy value that is not used in practice
                }
                for input_instance, prediction, reference in zip(
                    input_instances, predictions, references
                )
            ]
        elif self.task == "rating.single_turn_with_reference":
            instances = [
                {
                    "question": input_instance,
                    "answer": prediction,
                    "reference_answer": reference[0],
                    "rating": 5.0,  # This is a dummy value that is not used in practice
                }
                for input_instance, prediction, reference in zip(
                    input_instances, predictions, references
                )
            ]
        elif self.task == "pairwise_comparative_rating.single_turn":
            instances = [
                {
                    "question": input_instance,
                    "answer_a": prediction,
                    "answer_b": reference[0],
                    "model_a": "input_model",
                    "model_b": "baseline_model",
                    "answer_a_preference": 0,  # This is a dummy value that is not used in practice
                }
                for input_instance, prediction, reference in zip(
                    input_instances, predictions, references
                )
            ]
            if self.pairwise_comparison_include_swapped_positions:
                reversed_instances = [
                    {
                        "question": input_instance,
                        "answer_a": reference[0],
                        "answer_b": prediction,
                        "model_a": "baseline_model",
                        "model_b": "input_model",
                        "answer_a_preference": 0,  # This is a dummy value that is not used in practice
                    }
                    for input_instance, prediction, reference in zip(
                        input_instances, predictions, references
                    )
                ]
                instances.extend(reversed_instances)
        else:
            raise NotImplementedError(
                f"Error in 'LLMAsJudge' metric. {self.task} is not a supported task type."
            )
        return instances

    def prepare(self):
        assert (
            not self.pairwise_comparison_include_swapped_positions
        ), "Feature not yet fully implemented"
        super().prepare()
        if self.task == "pairwise_comparative_rating.single_turn":
            self.reduction_map = {"weighted_win_rate": [self.main_score]}
        if self.reduction_map is None:
            self.reduction_map = {"mean": [self.main_score]}

        supported_tasks = [
            "rating.single_turn",
            "rating.single_turn_with_reference",
            "pairwise_comparative_rating.single_turn",
        ]
        assert self.task in supported_tasks, (
            f"Error in 'LLMAsJudge' metric. {self.task} is not a supported task type."
            f"The supported tasks types are: {', '.join(supported_tasks)}."
        )

        if isinstance(self.inference_model, OpenAiInferenceEngine):
            if self.format:
                raise ValueError(
                    "Error in 'LLMAsJudge' metric. Inference model 'OpenAiInferenceEngine' does "
                    "not support formatting. Please remove the format definition from the recipe"
                    " (OpenAi Chat API take care of the formatting automatically)."
                )
            if self.system_prompt:
                raise ValueError(
                    "Error in 'LLMAsJudge' metric. Inference model 'OpenAiInferenceEngine' does "
                    "not support system prompt. Please remove the system_prompt definition from the recipe"
                    " (Current implementation of Unitxt does not support this."
                    " Support will be added in future updates)."
                )

    def compute(
        self,
        references: List[List[Any]],
        predictions: List[Any],
        task_data: List[Dict],
    ) -> List[Dict[str, Any]]:
        input_instances = self._get_input_instances(task_data)
        instances = self._get_instance_for_judge_model(
            input_instances, predictions, references
        )

        card = f"cards.dynamic_cards_for_llm_judges.{self.task}"
        recipe = (
            f"card={card},"
            f"template={self.template},"
            "demos_pool_size=0,"
            "num_demos=0"
        )
        if self.system_prompt:
            recipe = f"{recipe},system_prompt={self.system_prompt}"
        if self.format:
            recipe = f"{recipe},format={self.format}"

        dataset = produce(instances, recipe)
        verdicts = self.inference_model.infer(dataset)
        meta_scores = evaluate(predictions=verdicts, data=dataset)

        res_list = []
        for instance, verdict in zip(meta_scores, verdicts):
            if self.task == "pairwise_comparative_rating.single_turn":
                is_model_b_the_baseline = (
                    instance["task_data"]["model_b"] == "baseline_model"
                )
                if is_model_b_the_baseline:
                    model_a_preference_score = instance["prediction"]
                else:
                    model_a_preference_score = instance["prediction"] * -1

                res = {
                    self.main_score: model_a_preference_score,
                    "judge_raw_output": verdict,
                }
            else:
                res = {
                    self.main_score: instance["prediction"],
                    "judge_raw_output": verdict,
                }
            res_list.append(res)

        return res_list
