import enum
import random
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
from pix_framework.io.event_log import DEFAULT_CSV_IDS, read_csv_log

log_ids = DEFAULT_CSV_IDS


class NoiseType(enum.Enum):
    ADD = 0
    REMOVE = 1
    SWAP = 2

    @staticmethod
    def random(amount: int = 1) -> List['NoiseType']:
        return list(np.random.choice([NoiseType.ADD, NoiseType.REMOVE, NoiseType.SWAP], amount, replace=False))


def add_noise_to_logs():
    """
    Preprocess each event log by adding noise to each case. The possible noise modifications are: i) add an activity
    instance, ii) remove an activity instance, iii) swap two activity instances. Produce three event logs with added
    noise:
     - One random noise alteration per case.
     - Two different random noise alterations per case.
     - Three different random noise alterations per case.
    """
    # Instantiate datasets
    datasets = ["synthetic_xor_loop", "synthetic_xor", "synthetic_and_kinf",
                "synthetic_and_k7", "synthetic_and_k5_loop", "synthetic_and_k5",
                "synthetic_and_k3"]
    # datasets = ["synthetic_xor_loop_ongoing", "synthetic_xor_ongoing", "synthetic_and_kinf_ongoing",
    #            "synthetic_and_k7_ongoing", "synthetic_and_k5_loop_ongoing", "synthetic_and_k5_ongoing",
    #            "synthetic_and_k3_ongoing"]
    # For each dataset
    for dataset in datasets:
        # Instantiate paths
        event_log_path = Path(f"../inputs/synthetic/{dataset}.csv.gz")
        noise_one_path = Path(f"../outputs/{dataset}_noise_1.csv.gz")
        noise_two_path = Path(f"../outputs/{dataset}_noise_2.csv.gz")
        noise_three_path = Path(f"../outputs/{dataset}_noise_3.csv.gz")
        # Read preprocessed event log(s)
        event_log = read_csv_log(event_log_path, log_ids, sort=True)
        activities = list(event_log[log_ids.activity].unique())
        # Create copy for each noise
        noise_one, noise_two, noise_three = None, None, None
        for trace_id, events in event_log.groupby(log_ids.case):
            print(f"{trace_id}\n{list(events.sort_values(log_ids.start_time)[log_ids.activity])}")
            # Add noise for noise_one
            events_one = events.copy(deep=True)
            types = NoiseType.random(1)
            trace_with_noise = _add_noise_to_trace(events_one, types[0], activities)
            noise_one = trace_with_noise if noise_one is None else pd.concat([noise_one, trace_with_noise])
            print(f"\t{list(trace_with_noise.sort_values(log_ids.start_time)[log_ids.activity])}")
            # Add noise for noise_two
            events_two = events.copy(deep=True)
            types = NoiseType.random(2)
            trace_with_noise = _add_noise_to_trace(events_two, types[0], activities)
            trace_with_noise = _add_noise_to_trace(trace_with_noise, types[1], activities)
            noise_two = trace_with_noise if noise_two is None else pd.concat([noise_two, trace_with_noise])
            print(f"\t{list(trace_with_noise.sort_values(log_ids.start_time)[log_ids.activity])}")
            # Add noise for noise_three
            events_three = events.copy(deep=True)
            types = NoiseType.random(3)
            trace_with_noise = _add_noise_to_trace(events_three, types[0], activities)
            trace_with_noise = _add_noise_to_trace(trace_with_noise, types[1], activities)
            trace_with_noise = _add_noise_to_trace(trace_with_noise, types[2], activities)
            noise_three = trace_with_noise if noise_three is None else pd.concat([noise_three, trace_with_noise])
            print(f"\t{list(trace_with_noise.sort_values(log_ids.start_time)[log_ids.activity])}")
        # Output datasets
        # noise_one.to_csv(noise_one_path, index=False)
        # noise_two.to_csv(noise_two_path, index=False)
        # noise_three.to_csv(noise_three_path, index=False)


def _add_noise_to_trace(events: pd.DataFrame, noise_type: NoiseType, activities: List[str]) -> pd.DataFrame:
    """
    Add one noise modification (add new activity instance, remove an activity
    instance, swap two consecutive activity instances) to a trace.
    - Warning: The swap operation is only performed if the trace has more than two
    activity instances.
    - Warning: Performing more than one operation to a trace could end in no noise
    addition, e.g., add a new activity and delete a random (the same one) after.
    """
    if noise_type == NoiseType.REMOVE:
        # Get random index within the trace
        i = np.random.choice(events.index, 1, replace=False)
        # Remove the event from the trace
        events = events.drop(i)
    elif noise_type == NoiseType.ADD:
        # Get random activity label
        activity_label = random.choice(activities)
        # Get a random position on the trace
        previous_idx = np.random.choice(events.index, 1, replace=False)
        # Copy event in that position and override data
        added_event = events.loc[previous_idx].copy(deep=True)
        added_event[log_ids.activity] = activity_label
        added_event[log_ids.resource] = "ADDED_RESOURCE"
        # Get future events and displace them 1 second forward
        events.loc[
            events[log_ids.start_time] >= added_event[log_ids.start_time].iloc[0],
            [log_ids.end_time]
        ] += pd.Timedelta(seconds=5)
        events.loc[
            events[log_ids.start_time] >= added_event[log_ids.start_time].iloc[0],
            [log_ids.start_time]
        ] += pd.Timedelta(seconds=5)
        # Reset start/end of copied event
        events.loc[previous_idx, log_ids.start_time] = added_event[log_ids.start_time]
        events.loc[previous_idx, log_ids.end_time] = added_event[log_ids.end_time]
        # Set timestamps of added event to one second after previous event finished
        added_event[log_ids.start_time] = added_event[log_ids.end_time]
        added_event[log_ids.end_time] = added_event[log_ids.end_time] + pd.Timedelta(seconds=5)
        # Add new event to trace
        events = pd.concat([events, added_event]).reset_index(drop=True)
    elif noise_type == NoiseType.SWAP and len(events) > 1:
        # Get index of two consecutive events
        i = np.random.randint(0, len(events) - 1)
        events.sort_values(by=log_ids.start_time, inplace=True)
        event_one_idx = events.index[i]
        event_two_idx = events.index[i + 1]
        # Swap activity labels
        tmp_activity = events.loc[event_one_idx][log_ids.activity]
        events.loc[event_one_idx, log_ids.activity] = events.loc[event_two_idx][log_ids.activity]
        events.loc[event_two_idx, log_ids.activity] = tmp_activity
    # Return edited (if possible) trace
    return events


if __name__ == '__main__':
    add_noise_to_logs()