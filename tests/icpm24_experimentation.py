import time
from enum import Enum
from typing import Tuple, List, Set

import numpy as np
from pm4py.objects import petri
from pm4py.objects.log.importer.xes import factory as xes_import_factory
from scipy.stats import t

from icpm24_prefix_alignment import calculate_prefix_alignment_modified_a_star_with_heuristic, \
    calculate_prefix_alignment_modified_a_star_with_heuristic_without_recalculation, calculate_prefix_alignment_occ
from process_running_state.bpmn_model import BPMNModel
from process_running_state.markovian_marking import MarkovianMarking
from process_running_state.reachability_graph import ReachabilityGraph


class AlignmentType(Enum):
    IASR = 0
    IAS = 1
    OCC = 2


def compute_current_states():
    """
    - Run both techniques, "our proposal" and "prefix-alignments", to compute the state of each ongoing process case.
    - Save the results in an intermediate CSV file storing the case ID, technique, ongoing state, avg runtime
    - In this way, the states can be reused later to evaluate any of the RQs.
    """
    # Instantiate datasets
    datasets = ["Sepsis_Cases", "BPIC_2019", "Traffic_Fines"]
    # For each dataset,
    for dataset in datasets:
        # Instantiate paths
        ongoing_cases_csv = f"../inputs/{dataset}_ongoing.csv.gz"
        ongoing_cases_xes = f"../inputs/{dataset}_ongoing.xes.gz"
        bpmn_model_path = f"../inputs/{dataset}.bpmn"
        pnml_model_path = f"../inputs/{dataset}.pnml"
        output_filename = f"../outputs/{dataset}_ongoing_states.csv"
        # Read preprocessed event log(s)
        event_log_xes = xes_import_factory.apply(ongoing_cases_xes)
        event_log_csv = read_csv_log(ongoing_cases_csv, log_ids)
        # Read proces model(s)
        bpmn_model = read_bpmn_model(bpmn_model_path)
        pnml_model, initial_marking, final_marking = petri.importer.pnml.import_net(pnml_model_path)
        # Open file and compute&save ongoing states
        with open(output_filename, 'a') as output_file:
            # Write headers
            output_file.write("technique,case_id,state,runtime_avg,runtime_cnf\n")
            # Compute markings
            markovian_marking_3, runtime_avg, runtime_cnf = compute_markovian_marking(bpmn_model, 3)
            output_file.write(f"build-marking-3,,,{runtime_avg}, {runtime_cnf}\n")
            markovian_marking_5, runtime_avg, runtime_cnf = compute_markovian_marking(bpmn_model, 5)
            output_file.write(f"build-marking-5,,,{runtime_avg}, {runtime_cnf}\n")
            markovian_marking_7, runtime_avg, runtime_cnf = compute_markovian_marking(bpmn_model, 7)
            output_file.write(f"build-marking-7,,,{runtime_avg}, {runtime_cnf}\n")
            markovian_marking_9, runtime_avg, runtime_cnf = compute_markovian_marking(bpmn_model, 9)
            output_file.write(f"build-marking-9,,,{runtime_avg}, {runtime_cnf}\n")
            # Compute with alignments
            for trace in event_log_xes:
                # A-star with recalculation
                state, runtime_avg, runtime_cnf = get_state_prefix_alignment(trace, pnml_model, initial_marking,
                                                                             final_marking, AlignmentType.IASR,
                                                                             markovian_marking_3.graph)
                output_file.write(f"IASR,{trace.id},{state},{runtime_avg}, {runtime_cnf}\n")
                # A-star without recalculation
                state, runtime_avg, runtime_cnf = get_state_prefix_alignment(trace, pnml_model, initial_marking,
                                                                             final_marking, AlignmentType.IAS,
                                                                             markovian_marking_3.graph)
                output_file.write(f"IAS,{trace.id},{state},{runtime_avg}, {runtime_cnf}\n")
                # OCC
                state, runtime_avg, runtime_cnf = get_state_prefix_alignment(trace, pnml_model, initial_marking,
                                                                             final_marking, AlignmentType.OCC,
                                                                             markovian_marking_3.graph)
                output_file.write(f"OCC,{trace.id},{state},{runtime_avg}, {runtime_cnf}\n")
            # Compute with our proposal
            for trace_id, events in event_log_csv.groupby(log_ids.case):
                n = min(len(events), 9)
                n_gram = list(events.sort_values(log_ids.end_time, axis=1).tail(n)[log_ids.activity])
                # 3-gram
                state, runtime_avg, runtime_cnf = get_state_markovian_marking(markovian_marking_3, n_gram)
                output_file.write(f"marking-3,{trace_id},{state},{runtime_avg}, {runtime_cnf}\n")
                # 5-gram
                state, runtime_avg, runtime_cnf = get_state_markovian_marking(markovian_marking_5, n_gram)
                output_file.write(f"marking-5,{trace_id},{state},{runtime_avg}, {runtime_cnf}\n")
                # 7-gram
                state, runtime_avg, runtime_cnf = get_state_markovian_marking(markovian_marking_7, n_gram)
                output_file.write(f"marking-7,{trace_id},{state},{runtime_avg}, {runtime_cnf}\n")
                # 9-gram
                state, runtime_avg, runtime_cnf = get_state_markovian_marking(markovian_marking_9, n_gram)
                output_file.write(f"marking-9,{trace_id},{state},{runtime_avg}, {runtime_cnf}\n")


def compute_markovian_marking(
        bpmn_model: BPMNModel,
        n_gram_size_limit: int
) -> Tuple[MarkovianMarking, float, float]:
    """Compute the reachability graph and n-gram indexing of the given BPMN model"""
    runtimes = []
    final_markovian_marking = None
    # Compute state 10 times
    for i in range(10):
        start = time.time()
        reachability_graph = bpmn_model.get_reachability_graph()
        markovian_marking = MarkovianMarking(reachability_graph, n_gram_size_limit)
        end = time.time()
        runtimes += [end - start]
        if i == 0:
            final_markovian_marking = markovian_marking
    # Compute runtime confidence interval
    runtime_avg, runtime_cnf = compute_mean_conf_interval(runtimes)
    return final_markovian_marking, runtime_avg, runtime_cnf


def get_state_prefix_alignment(
        trace,
        pnml_model,
        initial_marking,
        final_marking,
        alignment_type: AlignmentType,
        reachability_graph: ReachabilityGraph
) -> Tuple[Set[str], float, float]:
    """Compute the state of an ongoing case with a prefix-alignment technique."""
    runtimes = []
    state = None
    # Compute state 10 times
    for i in range(10):
        start = time.time()
        if alignment_type == AlignmentType.IASR:
            result = calculate_prefix_alignment_modified_a_star_with_heuristic(trace, pnml_model,
                                                                               initial_marking,
                                                                               final_marking)
        elif alignment_type == AlignmentType.IAS:
            result = calculate_prefix_alignment_modified_a_star_with_heuristic_without_recalculation(trace, pnml_model,
                                                                                                     initial_marking,
                                                                                                     final_marking)
        else:
            result = calculate_prefix_alignment_occ(trace, pnml_model,
                                                    initial_marking,
                                                    final_marking)
        end = time.time()
        runtimes += [end - start]
        if i == 0:
            state = reachability_graph.get_marking_from_activity_sequence(result)
    # Compute runtime confidence interval
    runtime_avg, runtime_cnf = compute_mean_conf_interval(runtimes)
    return state, runtime_avg, runtime_cnf


def get_state_markovian_marking(
        markovian_marking: MarkovianMarking,
        n_gram: List[str]
) -> Tuple[Set[str], float, float]:
    """Compute the state of an ongoing case with the n-gram indexing technique (our proposal)."""
    runtimes = []
    state = None
    # Compute state 10 times
    for i in range(10):
        start = time.time()
        result = markovian_marking.get_best_marking_state_for(n_gram)
        end = time.time()
        runtimes += [end - start]
        if i == 0:
            state = result
    # Compute runtime confidence interval
    runtime_avg, runtime_cnf = compute_mean_conf_interval(runtimes)
    return state, runtime_avg, runtime_cnf


def evaluation_question_one():
    pass


def evaluation_question_two():
    pass


def compute_mean_conf_interval(data: list, confidence: float = 0.95) -> Tuple[float, float]:
    # Compute the sample mean and standard deviation
    sample_mean = float(np.mean(data))
    sample_std = np.std(data, ddof=1)  # ddof=1 calculates the sample standard deviation
    # Compute the degrees of freedom
    df = len(data) - 1
    # Compute the t-value for the confidence level
    t_value = t.ppf(1 - (1 - confidence) / 2, df)
    # Compute the standard error of the mean
    std_error = sample_std / np.sqrt(len(data))
    conf_interval = t_value * std_error
    # Compute the confidence interval
    return sample_mean, conf_interval


if __name__ == '__main__':
    compute_current_states()
    evaluation_question_one()
    evaluation_question_two()
